"""Model Trainer — walk-forward validation, hyperparameter tuning, versioning.

Supports PyTorch models with ONNX export for production serving.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np
import torch
import torch.nn as nn
from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocols & types
# ---------------------------------------------------------------------------

@runtime_checkable
class TrainableModel(Protocol):
    """Any model that can be trained and exported to ONNX."""

    def train(self) -> None: ...
    def eval(self) -> None: ...
    def state_dict(self) -> dict[str, Any]: ...
    def load_state_dict(self, state: dict[str, Any]) -> Any: ...
    def forward(self, x: torch.Tensor) -> torch.Tensor: ...


class TrainingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WalkForwardSplit(BaseModel):
    """A single walk-forward window."""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    fold_index: int = 0


class HyperParamConfig(BaseModel):
    """Hyperparameter search space."""
    learning_rates: list[float] = Field(default_factory=lambda: [1e-4, 3e-4, 1e-3])
    batch_sizes: list[int] = Field(default_factory=lambda: [32, 64, 128])
    hidden_dims: list[int] = Field(default_factory=lambda: [64, 128, 256])
    dropout_rates: list[float] = Field(default_factory=lambda: [0.1, 0.2, 0.3])
    weight_decays: list[float] = Field(default_factory=lambda: [0.0, 1e-5, 1e-4])
    max_combinations: int = 20  # cap grid search


class TrainingMetrics(BaseModel):
    """Metrics from a single training run."""
    epoch: int = 0
    train_loss: float = 0.0
    val_loss: float = 0.0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0


class TrainingResult(BaseModel):
    """Final result of a training run."""
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    model_name: str = ""
    version: str = ""
    status: TrainingStatus = TrainingStatus.PENDING
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    best_metrics: TrainingMetrics = Field(default_factory=TrainingMetrics)
    all_metrics: list[TrainingMetrics] = Field(default_factory=list)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    walk_forward_folds: int = 0
    onnx_path: str = ""
    model_hash: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

class TrainingDataPreparer:
    """Prepare feature matrices and labels from market data."""

    def __init__(self, lookback: int = 60, prediction_horizon: int = 5) -> None:
        self.lookback = lookback
        self.prediction_horizon = prediction_horizon

    def prepare_sequences(
        self,
        features: np.ndarray,
        labels: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create sliding-window sequences for time-series models.

        Args:
            features: Shape (n_samples, n_features).
            labels: Shape (n_samples,).

        Returns:
            X: Shape (n_windows, lookback, n_features).
            y: Shape (n_windows,).
        """
        n = len(features)
        if n < self.lookback + self.prediction_horizon:
            raise ValueError(
                f"Need at least {self.lookback + self.prediction_horizon} samples, got {n}"
            )

        xs: list[np.ndarray] = []
        ys: list[float] = []
        for i in range(self.lookback, n - self.prediction_horizon + 1):
            xs.append(features[i - self.lookback : i])
            ys.append(labels[i + self.prediction_horizon - 1])

        return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)

    def create_walk_forward_splits(
        self,
        n_samples: int,
        n_folds: int = 5,
        train_ratio: float = 0.7,
        gap: int = 0,
    ) -> list[WalkForwardSplit]:
        """Generate expanding-window walk-forward splits.

        Each fold uses all data up to the split point for training
        and the next chunk for testing, with an optional gap to avoid
        look-ahead bias.
        """
        fold_size = n_samples // (n_folds + 1)
        splits: list[WalkForwardSplit] = []

        for i in range(n_folds):
            train_end_idx = fold_size * (i + 1)
            test_start_idx = train_end_idx + gap
            test_end_idx = min(test_start_idx + fold_size, n_samples)

            if test_start_idx >= n_samples:
                break

            splits.append(WalkForwardSplit(
                train_start=datetime(2020, 1, 1),  # placeholder timestamps
                train_end=datetime(2020, 1, 1),
                test_start=datetime(2020, 1, 1),
                test_end=datetime(2020, 1, 1),
                fold_index=i,
            ))

        return splits

    def normalize_features(
        self,
        train: np.ndarray,
        test: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Z-score normalize using training stats only (no leakage)."""
        mean = train.mean(axis=0, keepdims=True)
        std = train.std(axis=0, keepdims=True) + 1e-8
        return (train - mean) / std, (test - mean) / std, mean.squeeze(), std.squeeze()


# ---------------------------------------------------------------------------
# Walk-forward trainer
# ---------------------------------------------------------------------------

class ModelTrainer:
    """Train models with walk-forward validation and hyperparameter tuning.

    Workflow:
    1. Prepare data via ``TrainingDataPreparer``
    2. Run hyperparameter search (grid or random)
    3. For each candidate, evaluate via walk-forward
    4. Select best, export to ONNX, register version
    """

    def __init__(
        self,
        model_name: str = "alphastack_signal_model",
        output_dir: str | Path = "models/artifacts",
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.data_preparer = TrainingDataPreparer()

    # ------------------------------------------------------------------
    # Hyperparameter tuning
    # ------------------------------------------------------------------

    def generate_hyperparam_grid(
        self,
        config: HyperParamConfig | None = None,
    ) -> list[dict[str, Any]]:
        """Generate a capped grid of hyperparameter combinations."""
        cfg = config or HyperParamConfig()
        import itertools

        keys = ["learning_rate", "batch_size", "hidden_dim", "dropout", "weight_decay"]
        grid = list(itertools.product(
            cfg.learning_rates,
            cfg.batch_sizes,
            cfg.hidden_dims,
            cfg.dropout_rates,
            cfg.weight_decays,
        ))

        # Cap the grid
        if len(grid) > cfg.max_combinations:
            import random
            random.seed(42)
            grid = random.sample(grid, cfg.max_combinations)

        return [dict(zip(keys, combo)) for combo in grid]

    # ------------------------------------------------------------------
    # Core training loop
    # ------------------------------------------------------------------

    async def train(
        self,
        model: nn.Module,
        train_x: np.ndarray,
        train_y: np.ndarray,
        *,
        val_x: np.ndarray | None = None,
        val_y: np.ndarray | None = None,
        epochs: int = 100,
        learning_rate: float = 1e-3,
        batch_size: int = 64,
        weight_decay: float = 0.0,
        patience: int = 10,
        onnx_opset: int = 17,
    ) -> TrainingResult:
        """Train a model with early stopping and optional ONNX export.

        Args:
            model: A ``torch.nn.Module`` to train.
            train_x: Training features, shape (n, seq_len, n_features) or (n, n_features).
            train_y: Training labels, shape (n,).
            val_x: Validation features (optional).
            val_y: Validation labels (optional).
            epochs: Maximum training epochs.
            learning_rate: Adam learning rate.
            batch_size: Mini-batch size.
            weight_decay: L2 regularisation.
            patience: Early stopping patience (epochs without improvement).
            onnx_opset: ONNX opset version for export.

        Returns:
            TrainingResult with metrics and artifact paths.
        """
        result = TrainingResult(
            model_name=self.model_name,
            status=TrainingStatus.RUNNING,
            hyperparameters={
                "epochs": epochs,
                "learning_rate": learning_rate,
                "batch_size": batch_size,
                "weight_decay": weight_decay,
            },
        )

        try:
            model = model.to(self.device)
            model.train()

            optimizer = torch.optim.Adam(
                model.parameters(), lr=learning_rate, weight_decay=weight_decay,
            )
            criterion = nn.MSELoss()

            # Build tensors
            x_tensor = torch.tensor(train_x, dtype=torch.float32).to(self.device)
            y_tensor = torch.tensor(train_y, dtype=torch.float32).to(self.device)
            dataset = torch.utils.data.TensorDataset(x_tensor, y_tensor)
            loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

            val_loader = None
            if val_x is not None and val_y is not None:
                vx = torch.tensor(val_x, dtype=torch.float32).to(self.device)
                vy = torch.tensor(val_y, dtype=torch.float32).to(self.device)
                val_dataset = torch.utils.data.TensorDataset(vx, vy)
                val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size)

            best_val_loss = float("inf")
            patience_counter = 0
            best_state: dict[str, Any] | None = None

            for epoch in range(1, epochs + 1):
                # --- train ---
                model.train()
                epoch_loss = 0.0
                n_batches = 0
                for xb, yb in loader:
                    optimizer.zero_grad()
                    pred = model(xb).squeeze(-1)
                    loss = criterion(pred, yb)
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item()
                    n_batches += 1

                avg_train_loss = epoch_loss / max(n_batches, 1)

                # --- validate ---
                val_loss = avg_train_loss
                if val_loader is not None:
                    model.eval()
                    val_total = 0.0
                    val_n = 0
                    with torch.no_grad():
                        for xb, yb in val_loader:
                            pred = model(xb).squeeze(-1)
                            val_total += criterion(pred, yb).item()
                            val_n += 1
                    val_loss = val_total / max(val_n, 1)

                metrics = TrainingMetrics(
                    epoch=epoch,
                    train_loss=avg_train_loss,
                    val_loss=val_loss,
                )
                result.all_metrics.append(metrics)

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                    result.best_metrics = metrics
                else:
                    patience_counter += 1

                if patience_counter >= patience:
                    log.info("Early stopping at epoch %d", epoch)
                    break

            # Restore best weights
            if best_state is not None:
                model.load_state_dict(best_state)
            model.eval()

            # Export ONNX
            onnx_path = self._export_onnx(model, train_x, onnx_opset)
            result.onnx_path = str(onnx_path)
            result.model_hash = self._hash_file(onnx_path)
            result.status = TrainingStatus.COMPLETED

        except Exception as exc:
            result.status = TrainingStatus.FAILED
            result.error = str(exc)
            log.error("Training failed: %s", exc)

        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()
        return result

    # ------------------------------------------------------------------
    # Walk-forward evaluation
    # ------------------------------------------------------------------

    async def walk_forward_evaluate(
        self,
        model_factory: Any,
        features: np.ndarray,
        labels: np.ndarray,
        *,
        n_folds: int = 5,
        epochs: int = 50,
        learning_rate: float = 1e-3,
        batch_size: int = 64,
    ) -> list[TrainingResult]:
        """Run walk-forward validation across multiple folds.

        Args:
            model_factory: Callable that returns a fresh ``nn.Module``.
            features: Full feature matrix.
            labels: Full label vector.
            n_folds: Number of walk-forward folds.
            epochs: Max epochs per fold.
            learning_rate: Adam LR.
            batch_size: Mini-batch size.

        Returns:
            List of TrainingResult, one per fold.
        """
        splits = self.data_preparer.create_walk_forward_splits(
            len(features), n_folds=n_folds,
        )
        results: list[TrainingResult] = []

        for split in splits:
            fold = split.fold_index
            # Approximate split indices
            fold_size = len(features) // (n_folds + 1)
            train_end = fold_size * (fold + 1)
            test_start = train_end
            test_end = min(test_start + fold_size, len(features))

            train_x, train_y = features[:train_end], labels[:train_end]
            test_x, test_y = features[test_start:test_end], labels[test_start:test_end]

            # Normalize
            train_x, test_x, _, _ = self.data_preparer.normalize_features(train_x, test_x)

            # Fresh model each fold
            model = model_factory()
            result = await self.train(
                model, train_x, train_y,
                val_x=test_x, val_y=test_y,
                epochs=epochs, learning_rate=learning_rate, batch_size=batch_size,
            )
            result.walk_forward_folds = n_folds
            results.append(result)
            log.info(
                "Fold %d: val_loss=%.6f, sharpe=%.3f",
                fold, result.best_metrics.val_loss, result.best_metrics.sharpe_ratio,
            )

        return results

    # ------------------------------------------------------------------
    # ONNX export
    # ------------------------------------------------------------------

    def _export_onnx(
        self,
        model: nn.Module,
        sample_data: np.ndarray,
        opset: int = 17,
    ) -> Path:
        """Export model to ONNX format."""
        model.eval()
        onnx_path = self.output_dir / f"{self.model_name}.onnx"

        # Create dummy input from sample shape
        dummy = torch.tensor(sample_data[:1], dtype=torch.float32).to(self.device)
        if dummy.dim() == 2:
            dummy = dummy.unsqueeze(0)  # add batch dim

        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            opset_version=opset,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        )
        log.info("Exported ONNX model to %s", onnx_path)
        return onnx_path

    @staticmethod
    def _hash_file(path: Path) -> str:
        """SHA-256 hash of a file for integrity tracking."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
