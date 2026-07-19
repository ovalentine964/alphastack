//! Risk Calculations — position sizing, drawdown, correlation, CVaR,
//! and the full Risk Governor with circuit breaker logic.
//!
//! Aligned with Python's `risk/governor.py`:
//! - Circuit breaker (max daily loss, consecutive losses)
//! - Drawdown manager (daily + total drawdown tracking)
//! - Position sizing (Kelly, fixed fractional, regime-adaptive)
//! - Trade approval pipeline (7-gate validation)
//! - Risk event system

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Risk Events (mirrors Python's RiskEventType)
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskEvent {
    #[pyo3(get)]
    pub event_type: String,
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub severity: String,
    #[pyo3(get)]
    pub details: String, // JSON string
}

#[pymethods]
impl RiskEvent {
    fn __repr__(&self) -> String {
        format!(
            "RiskEvent({}, {}, {})",
            self.event_type, self.symbol, self.severity
        )
    }
}

// ---------------------------------------------------------------------------
// Trade Request / Approval
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyTradeRequest {
    #[pyo3(get, set)]
    pub symbol: String,
    #[pyo3(get, set)]
    pub direction: String, // "long" | "short"
    #[pyo3(get, set)]
    pub requested_size: f64,
    #[pyo3(get, set)]
    pub entry_price: f64,
    #[pyo3(get, set)]
    pub stop_loss: f64,
    #[pyo3(get, set)]
    pub take_profit: f64,
    #[pyo3(get, set)]
    pub strategy_id: String,
}

#[pymethods]
impl PyTradeRequest {
    #[new]
    #[pyo3(signature = (symbol, direction, requested_size, entry_price, stop_loss, take_profit=0.0, strategy_id=""))]
    fn new(
        symbol: String,
        direction: String,
        requested_size: f64,
        entry_price: f64,
        stop_loss: f64,
        take_profit: f64,
        strategy_id: String,
    ) -> Self {
        Self {
            symbol,
            direction,
            requested_size,
            entry_price,
            stop_loss,
            take_profit,
            strategy_id,
        }
    }
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyTradeApproval {
    #[pyo3(get)]
    pub approved: bool,
    #[pyo3(get)]
    pub adjusted_size: f64,
    #[pyo3(get)]
    pub rejection_reason: String,
    #[pyo3(get)]
    pub warnings: Vec<String>,
    #[pyo3(get)]
    pub risk_score: f64,
}

#[pymethods]
impl PyTradeApproval {
    fn __repr__(&self) -> String {
        if self.approved {
            format!(
                "TradeApproval(approved, size={:.4}, risk={:.3})",
                self.adjusted_size, self.risk_score
            )
        } else {
            format!(
                "TradeApproval(rejected: {})",
                self.rejection_reason
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Circuit Breaker
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyCircuitBreaker {
    #[pyo3(get)]
    pub max_daily_loss_pct: f64,
    #[pyo3(get)]
    pub max_consecutive_losses: u32,
    #[pyo3(get)]
    pub daily_pnl: f64,
    #[pyo3(get)]
    pub consecutive_losses: u32,
    #[pyo3(get)]
    pub is_tripped: bool,
    #[pyo3(get)]
    pub trip_reason: String,
}

#[pymethods]
impl PyCircuitBreaker {
    #[new]
    #[pyo3(signature = (max_daily_loss_pct=5.0, max_consecutive_losses=5))]
    fn new(max_daily_loss_pct: f64, max_consecutive_losses: u32) -> Self {
        Self {
            max_daily_loss_pct,
            max_consecutive_losses,
            daily_pnl: 0.0,
            consecutive_losses: 0,
            is_tripped: false,
            trip_reason: String::new(),
        }
    }

    /// Record a trade result. Trips breaker if limits exceeded.
    fn record_loss(&mut self, pnl: f64, account_balance: f64) {
        self.daily_pnl += pnl;
        if pnl <= 0.0 {
            self.consecutive_losses += 1;
        } else {
            self.consecutive_losses = 0;
        }

        // Check daily loss limit
        let daily_loss_pct = if account_balance > 0.0 {
            (-self.daily_pnl / account_balance) * 100.0
        } else {
            0.0
        };
        if daily_loss_pct >= self.max_daily_loss_pct {
            self.is_tripped = true;
            self.trip_reason = format!(
                "Daily loss {:.2}% exceeds limit {:.2}%",
                daily_loss_pct, self.max_daily_loss_pct
            );
        }

        // Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses {
            self.is_tripped = true;
            self.trip_reason = format!(
                "{} consecutive losses (limit: {})",
                self.consecutive_losses, self.max_consecutive_losses
            );
        }
    }

    /// Reset the circuit breaker (e.g. at start of new trading day).
    fn reset(&mut self) {
        self.daily_pnl = 0.0;
        self.consecutive_losses = 0;
        self.is_tripped = false;
        self.trip_reason.clear();
    }
}

// ---------------------------------------------------------------------------
// Drawdown Manager
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyDrawdownManager {
    #[pyo3(get)]
    pub account_balance: f64,
    #[pyo3(get)]
    pub peak_balance: f64,
    #[pyo3(get)]
    pub daily_start_balance: f64,
    #[pyo3(get)]
    pub max_daily_loss_pct: f64,
    #[pyo3(get)]
    pub max_total_drawdown_pct: f64,
    #[pyo3(get)]
    pub current_drawdown_pct: f64,
    #[pyo3(get)]
    pub daily_loss_pct: f64,
    #[pyo3(get)]
    pub max_drawdown_seen: f64,
    #[pyo3(get)]
    pub drawdown_duration: usize,
}

#[pymethods]
impl PyDrawdownManager {
    #[new]
    fn new(
        account_balance: f64,
        max_daily_loss_pct: f64,
        max_total_drawdown_pct: f64,
    ) -> Self {
        Self {
            account_balance,
            peak_balance: account_balance,
            daily_start_balance: account_balance,
            max_daily_loss_pct,
            max_total_drawdown_pct,
            current_drawdown_pct: 0.0,
            daily_loss_pct: 0.0,
            max_drawdown_seen: 0.0,
            drawdown_duration: 0,
        }
    }

    /// Update balance after a trade settles.
    fn update_balance(&mut self, new_balance: f64) {
        self.account_balance = new_balance;
        if new_balance > self.peak_balance {
            self.peak_balance = new_balance;
            self.drawdown_duration = 0;
        } else {
            self.drawdown_duration += 1;
        }
        // Current drawdown from peak
        self.current_drawdown_pct = if self.peak_balance > 0.0 {
            ((self.peak_balance - new_balance) / self.peak_balance) * 100.0
        } else {
            0.0
        };
        if self.current_drawdown_pct > self.max_drawdown_seen {
            self.max_drawdown_seen = self.current_drawdown_pct;
        }
        // Daily loss
        self.daily_loss_pct = if self.daily_start_balance > 0.0 {
            ((self.daily_start_balance - new_balance) / self.daily_start_balance) * 100.0
        } else {
            0.0
        };
    }

    /// Check if drawdown limits are breached.
    fn is_breach(&self) -> bool {
        self.current_drawdown_pct >= self.max_total_drawdown_pct
            || self.daily_loss_pct >= self.max_daily_loss_pct
    }

    /// Reset daily tracking (call at start of each trading day).
    fn reset_daily(&mut self) {
        self.daily_start_balance = self.account_balance;
        self.daily_loss_pct = 0.0;
    }

    /// Drawdown metrics from an equity curve (static computation).
    fn drawdown_metrics(equity: Vec<f64>) -> (Vec<f64>, f64, usize, usize) {
        compute_drawdown_metrics(&equity)
    }
}

// ---------------------------------------------------------------------------
// Position Sizer
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyPositionSizer {
    #[pyo3(get)]
    pub account_balance: f64,
    #[pyo3(get)]
    pub max_position_pct: f64,
    #[pyo3(get)]
    pub risk_per_trade_pct: f64,
    #[pyo3(get)]
    pub min_position_size: f64,
    #[pyo3(get)]
    pub max_position_size: f64,
}

#[pymethods]
impl PyPositionSizer {
    #[new]
    #[pyo3(signature = (account_balance, max_position_pct=10.0, risk_per_trade_pct=2.0, min_position_size=0.001, max_position_size=1000000.0))]
    fn new(
        account_balance: f64,
        max_position_pct: f64,
        risk_per_trade_pct: f64,
        min_position_size: f64,
        max_position_size: f64,
    ) -> Self {
        Self {
            account_balance,
            max_position_pct,
            risk_per_trade_pct,
            min_position_size,
            max_position_size,
        }
    }

    /// Update account balance.
    fn update_balance(&mut self, new_balance: f64) {
        self.account_balance = new_balance;
    }

    /// Kelly criterion optimal fraction.
    fn kelly_fraction(win_rate: f64, win_loss_ratio: f64) -> f64 {
        if win_loss_ratio == 0.0 {
            return 0.0;
        }
        let k = win_rate - (1.0 - win_rate) / win_loss_ratio;
        k.clamp(0.0, 1.0)
    }

    /// Fixed fractional position size.
    fn position_size(capital: f64, risk_pct: f64, entry: f64, stop_loss: f64) -> f64 {
        let risk_amount = capital * risk_pct;
        let risk_per_unit = (entry - stop_loss).abs();
        if risk_per_unit == 0.0 {
            return 0.0;
        }
        risk_amount / risk_per_unit
    }

    /// Full position sizing with min/max constraints and regime scaling.
    /// Returns (size, min_size, max_size).
    fn size_position(
        &self,
        entry_price: f64,
        stop_loss: f64,
        regime_size_factor: f64,
    ) -> (f64, f64, f64) {
        let risk_amount = self.account_balance * (self.risk_per_trade_pct / 100.0);
        let sl_distance = (entry_price - stop_loss).abs();

        let raw_size = if sl_distance > 0.0 {
            risk_amount / sl_distance
        } else {
            0.0
        };

        // Apply regime scaling
        let regime_adjusted = raw_size * regime_size_factor;

        // Max position limit
        let max_by_pct = if entry_price > 0.0 {
            (self.account_balance * self.max_position_pct / 100.0) / entry_price
        } else {
            f64::MAX
        };

        let final_size = regime_adjusted
            .min(max_by_pct)
            .min(self.max_position_size)
            .max(self.min_position_size);

        (final_size, self.min_position_size, self.max_position_size)
    }
}

// ---------------------------------------------------------------------------
// Risk Calculator (static computations)
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyRiskCalculator;

#[pymethods]
impl PyRiskCalculator {
    #[new]
    fn new() -> Self {
        Self
    }

    // -- Correlation Matrix -------------------------------------------------
    fn correlation_matrix(returns: Vec<Vec<f64>>) -> Vec<Vec<f64>> {
        let n = returns.len();
        let mut matrix = vec![vec![0.0; n]; n];
        for i in 0..n {
            matrix[i][i] = 1.0;
            for j in (i + 1)..n {
                let corr = pearson(&returns[i], &returns[j]);
                matrix[i][j] = corr;
                matrix[j][i] = corr;
            }
        }
        matrix
    }

    // -- CVaR (Conditional Value at Risk) -----------------------------------
    fn cvar(returns: Vec<f64>, confidence: f64) -> f64 {
        let mut sorted = returns.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let idx = ((1.0 - confidence) * sorted.len() as f64).ceil() as usize;
        let tail = &sorted[..idx.max(1)];
        tail.iter().sum::<f64>() / tail.len() as f64
    }

    /// Value at Risk (VaR) at given confidence level.
    fn var(returns: Vec<f64>, confidence: f64) -> f64 {
        let mut sorted = returns.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let idx = ((1.0 - confidence) * sorted.len() as f64).floor() as usize;
        sorted[idx.min(sorted.len() - 1)]
    }

    // -- Sharpe Ratio -------------------------------------------------------
    fn sharpe_ratio(returns: Vec<f64>, risk_free_rate: f64) -> f64 {
        compute_sharpe_ratio(&returns, risk_free_rate)
    }

    // -- Sortino Ratio ------------------------------------------------------
    fn sortino_ratio(returns: Vec<f64>, risk_free_rate: f64) -> f64 {
        let n = returns.len() as f64;
        if n == 0.0 {
            return 0.0;
        }
        let mean = returns.iter().sum::<f64>() / n;
        let downside_var: f64 = returns
            .iter()
            .filter(|&&r| r < 0.0)
            .map(|r| r.powi(2))
            .sum::<f64>()
            / n;
        let downside_std = downside_var.sqrt();
        if downside_std == 0.0 {
            return 0.0;
        }
        (mean - risk_free_rate) / downside_std
    }

    // -- Portfolio Risk -----------------------------------------------------
    fn portfolio_volatility(weights: Vec<f64>, cov_matrix: Vec<Vec<f64>>) -> f64 {
        let n = weights.len();
        let mut var = 0.0_f64;
        for i in 0..n {
            for j in 0..n {
                var += weights[i] * weights[j] * cov_matrix[i][j];
            }
        }
        var.max(0.0).sqrt()
    }

    // -- Max Favorable / Adverse Excursion ----------------------------------
    fn mfe_mae(equity: Vec<f64>) -> (Vec<f64>, Vec<f64>) {
        let len = equity.len();
        let mut mfe = vec![0.0; len];
        let mut mae = vec![0.0; len];
        let mut peak = equity[0];
        let mut trough = equity[0];
        for i in 0..len {
            if equity[i] > peak {
                peak = equity[i];
            }
            if equity[i] < trough {
                trough = equity[i];
            }
            mfe[i] = peak - equity[i];
            mae[i] = equity[i] - trough;
        }
        (mfe, mae)
    }
}

// ---------------------------------------------------------------------------
// Risk Governor — the main orchestrator
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyRiskGovernor {
    #[pyo3(get)]
    pub account_balance: f64,
    #[pyo3(get)]
    pub halted: bool,
    #[pyo3(get)]
    pub halt_reason: String,
    circuit_breaker: PyCircuitBreaker,
    drawdown_manager: PyDrawdownManager,
    position_sizer: PyPositionSizer,
    events: Vec<RiskEvent>,
    max_open_positions: usize,
    max_correlation: f64,
    max_leverage: f64,
    current_open_positions: usize,
    current_leverage: f64,
}

#[pymethods]
impl PyRiskGovernor {
    #[new]
    #[pyo3(signature = (account_balance=10000.0, max_daily_loss_pct=5.0, max_drawdown_pct=15.0, max_consecutive_losses=5, risk_per_trade_pct=2.0, max_position_pct=10.0, max_open_positions=5, max_correlation=0.7, max_leverage=10.0))]
    fn new(
        account_balance: f64,
        max_daily_loss_pct: f64,
        max_drawdown_pct: f64,
        max_consecutive_losses: u32,
        risk_per_trade_pct: f64,
        max_position_pct: f64,
        max_open_positions: usize,
        max_correlation: f64,
        max_leverage: f64,
    ) -> Self {
        Self {
            account_balance,
            halted: false,
            halt_reason: String::new(),
            circuit_breaker: PyCircuitBreaker::new(max_daily_loss_pct, max_consecutive_losses),
            drawdown_manager: PyDrawdownManager::new(
                account_balance,
                max_daily_loss_pct,
                max_drawdown_pct,
            ),
            position_sizer: PyPositionSizer::new(
                account_balance,
                max_position_pct,
                risk_per_trade_pct,
                0.001,
                1_000_000.0,
            ),
            events: Vec::new(),
            max_open_positions,
            max_correlation,
            max_leverage,
            current_open_positions: 0,
            current_leverage: 0.0,
        }
    }

    /// Record a completed trade's P&L across all risk sub-systems.
    fn record_trade_result(&mut self, pnl: f64) {
        self.drawdown_manager.update_balance(self.account_balance + pnl);
        self.circuit_breaker
            .record_loss(pnl, self.account_balance);
        self.account_balance += pnl;
        self.position_sizer.update_balance(self.account_balance);

        // Check circuit breaker
        if self.circuit_breaker.is_tripped {
            self.halted = true;
            self.halt_reason = self.circuit_breaker.trip_reason.clone();
            self.events.push(RiskEvent {
                event_type: "circuit_breaker_triggered".into(),
                symbol: String::new(),
                severity: "critical".into(),
                details: serde_json::json!({
                    "reason": self.halt_reason,
                    "daily_pnl": self.circuit_breaker.daily_pnl,
                    "consecutive_losses": self.circuit_breaker.consecutive_losses,
                })
                .to_string(),
            });
        }

        // Check drawdown warning
        if self.drawdown_manager.current_drawdown_pct
            > self.drawdown_manager.max_total_drawdown_pct * 0.8
        {
            self.events.push(RiskEvent {
                event_type: "drawdown_warning".into(),
                symbol: String::new(),
                severity: "warning".into(),
                details: serde_json::json!({
                    "daily_pct": self.drawdown_manager.daily_loss_pct,
                    "total_pct": self.drawdown_manager.current_drawdown_pct,
                })
                .to_string(),
            });
        }
    }

    /// Manually halt trading.
    fn halt(&mut self, reason: String) {
        self.halted = true;
        self.halt_reason = reason.clone();
        self.events.push(RiskEvent {
            event_type: "halt_trading".into(),
            symbol: String::new(),
            severity: "critical".into(),
            details: serde_json::json!({ "reason": reason }).to_string(),
        });
    }

    /// Resume trading.
    fn resume(&mut self) {
        if self.circuit_breaker.is_tripped {
            return; // Cannot resume with active circuit breaker
        }
        self.halted = false;
        self.halt_reason.clear();
        self.events.push(RiskEvent {
            event_type: "resume_trading".into(),
            symbol: String::new(),
            severity: "info".into(),
            details: "{}".into(),
        });
    }

    /// Reset daily risk counters (call at start of each trading day).
    fn reset_daily(&mut self) {
        self.circuit_breaker.reset();
        self.drawdown_manager.reset_daily();
    }

    /// Full trade approval pipeline (7-gate validation).
    /// Mirrors Python's `RiskGovernor.approve_trade()`.
    fn approve_trade(&mut self, request: &PyTradeRequest) -> PyTradeApproval {
        let mut warnings: Vec<String> = Vec::new();

        // Gate 0: Global halt
        if self.halted {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: format!("Trading halted: {}", self.halt_reason),
                warnings,
                risk_score: 1.0,
            };
        }

        // Gate 1: Basic validation
        if request.entry_price <= 0.0 || request.stop_loss <= 0.0 {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: "Invalid entry/stop price".into(),
                warnings,
                risk_score: 1.0,
            };
        }
        if request.requested_size <= 0.0 {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: "Invalid position size".into(),
                warnings,
                risk_score: 1.0,
            };
        }
        // Stop loss must be on the correct side
        if request.direction == "long" && request.stop_loss >= request.entry_price {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: "Long trade stop loss must be below entry".into(),
                warnings,
                risk_score: 1.0,
            };
        }
        if request.direction == "short" && request.stop_loss <= request.entry_price {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: "Short trade stop loss must be above entry".into(),
                warnings,
                risk_score: 1.0,
            };
        }

        // Gate 2: Circuit breaker
        if self.circuit_breaker.is_tripped {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: format!(
                    "Circuit breaker tripped: {}",
                    self.circuit_breaker.trip_reason
                ),
                warnings,
                risk_score: 1.0,
            };
        }

        // Gate 3: Drawdown limits
        if self.drawdown_manager.is_breach() {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: "Drawdown limit breached".into(),
                warnings,
                risk_score: 1.0,
            };
        }

        // Gate 4: Exposure limits
        if self.current_open_positions >= self.max_open_positions {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: format!(
                    "Max open positions reached ({}/{})",
                    self.current_open_positions, self.max_open_positions
                ),
                warnings,
                risk_score: 0.8,
            };
        }

        // Gate 5: Leverage check
        let position_value = request.requested_size * request.entry_price;
        let new_leverage = self.current_leverage
            + (position_value / self.account_balance).max(0.0);
        if new_leverage > self.max_leverage {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: format!(
                    "Leverage {:.2}x exceeds max {:.2}x",
                    new_leverage, self.max_leverage
                ),
                warnings,
                risk_score: 0.9,
            };
        }

        // Gate 6: Position sizing (may adjust size)
        let regime_factor = 1.0; // Default — can be overridden
        let (adjusted_size, min_size, _max_size) = self.position_sizer.size_position(
            request.entry_price,
            request.stop_loss,
            regime_factor,
        );
        let final_size = adjusted_size.min(request.requested_size);

        if final_size < request.requested_size {
            warnings.push(format!(
                "Size reduced from {:.4} to {:.4}",
                request.requested_size, final_size
            ));
        }

        // Gate 7: Minimum viable size
        if final_size < min_size {
            return PyTradeApproval {
                approved: false,
                adjusted_size: 0.0,
                rejection_reason: format!("Size {:.6} below minimum {:.6}", final_size, min_size),
                warnings,
                risk_score: 0.5,
            };
        }

        // All gates passed
        let risk_score = self.compute_risk_score(request, final_size);
        self.events.push(RiskEvent {
            event_type: "trade_approved".into(),
            symbol: request.symbol.clone(),
            severity: "info".into(),
            details: serde_json::json!({
                "requested_size": request.requested_size,
                "approved_size": final_size,
                "risk_score": risk_score,
            })
            .to_string(),
        });

        PyTradeApproval {
            approved: true,
            adjusted_size: final_size,
            rejection_reason: String::new(),
            warnings,
            risk_score,
        }
    }

    /// Get pending risk events and clear the buffer.
    fn drain_events(&mut self) -> Vec<RiskEvent> {
        std::mem::take(&mut self.events)
    }

    /// Full risk system status.
    fn status(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("halted", self.halted)?;
        dict.set_item("halt_reason", &self.halt_reason)?;
        dict.set_item("account_balance", self.account_balance)?;
        dict.set_item(
            "drawdown_pct",
            self.drawdown_manager.current_drawdown_pct,
        )?;
        dict.set_item("daily_loss_pct", self.drawdown_manager.daily_loss_pct)?;
        dict.set_item("max_drawdown_seen", self.drawdown_manager.max_drawdown_seen)?;
        dict.set_item(
            "circuit_breaker_tripped",
            self.circuit_breaker.is_tripped,
        )?;
        dict.set_item("daily_pnl", self.circuit_breaker.daily_pnl)?;
        dict.set_item(
            "consecutive_losses",
            self.circuit_breaker.consecutive_losses,
        )?;
        dict.set_item("open_positions", self.current_open_positions)?;
        dict.set_item("current_leverage", self.current_leverage)?;
        Ok(dict.into())
    }

    /// Set current exposure state (called by the orchestrator).
    fn set_exposure(&mut self, open_positions: usize, leverage: f64) {
        self.current_open_positions = open_positions;
        self.current_leverage = leverage;
    }
}

impl PyRiskGovernor {
    fn compute_risk_score(&self, request: &PyTradeRequest, size: f64) -> f64 {
        let mut scores: Vec<f64> = Vec::new();

        // Drawdown proximity
        let dd_score = (self.drawdown_manager.current_drawdown_pct
            / self.drawdown_manager.max_total_drawdown_pct)
            .min(1.0);
        scores.push(dd_score);

        // Exposure fraction
        let position_value = size * request.entry_price;
        let exp_score = (position_value / (self.account_balance * 10.0)).min(1.0);
        scores.push(exp_score);

        // Distance to stop loss (tighter stop = higher risk)
        if request.entry_price > 0.0 {
            let sl_pct =
                (request.entry_price - request.stop_loss).abs() / request.entry_price;
            let sl_score = (1.0 - sl_pct * 20.0).max(0.0);
            scores.push(sl_score);
        }

        if scores.is_empty() {
            0.0
        } else {
            scores.iter().sum::<f64>() / scores.len() as f64
        }
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn pearson(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len().min(b.len()) as f64;
    if n == 0.0 {
        return 0.0;
    }
    let mean_a: f64 = a.iter().take(n as usize).sum::<f64>() / n;
    let mean_b: f64 = b.iter().take(n as usize).sum::<f64>() / n;
    let mut cov = 0.0_f64;
    let mut var_a = 0.0_f64;
    let mut var_b = 0.0_f64;
    for i in 0..(n as usize) {
        let da = a[i] - mean_a;
        let db = b[i] - mean_b;
        cov += da * db;
        var_a += da * da;
        var_b += db * db;
    }
    let denom = (var_a * var_b).sqrt();
    if denom == 0.0 {
        return 0.0;
    }
    cov / denom
}

pub fn compute_sharpe_ratio(returns: &[f64], risk_free_rate: f64) -> f64 {
    let n = returns.len() as f64;
    if n == 0.0 {
        return 0.0;
    }
    let mean = returns.iter().sum::<f64>() / n;
    let var: f64 = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / n;
    let std = var.sqrt();
    if std == 0.0 {
        return 0.0;
    }
    (mean - risk_free_rate) / std
}

pub fn compute_drawdown_metrics(equity: &[f64]) -> (Vec<f64>, f64, usize, usize) {
    let len = equity.len();
    if len == 0 {
        return (vec![], 0.0, 0, 0);
    }
    let mut dd = vec![0.0; len];
    let mut peak = equity[0];
    let mut max_dd = 0.0_f64;
    let mut current_dur: usize = 0;
    let mut max_dur: usize = 0;

    for i in 0..len {
        if equity[i] > peak {
            peak = equity[i];
            if current_dur > max_dur {
                max_dur = current_dur;
            }
            current_dur = 0;
        } else {
            dd[i] = if peak > 0.0 {
                (peak - equity[i]) / peak
            } else {
                0.0
            };
            current_dur += 1;
        }
        if dd[i] > max_dd {
            max_dd = dd[i];
        }
    }
    if current_dur > max_dur {
        max_dur = current_dur;
    }
    (dd, max_dd, current_dur, max_dur)
}
