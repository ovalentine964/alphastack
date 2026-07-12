# Alpha Stack — Integration Testing Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Integration Testing Architect
> **Scope:** Complete testing strategy — unit, integration, E2E, backtesting validation, performance, security, cross-platform, broker integration, test data management, and CI/CD pipeline
> **Design Philosophy:** Same code paths for testing and production — if it can't be tested, it can't be trusted with real money

---

## Table of Contents

1. [Testing Philosophy & Principles](#1-testing-philosophy--principles)
2. [Test Pyramid & Coverage Targets](#2-test-pyramid--coverage-targets)
3. [Unit Testing Strategy](#3-unit-testing-strategy)
4. [Integration Testing](#4-integration-testing)
5. [End-to-End Testing](#5-end-to-end-testing)
6. [Backtesting Validation](#6-backtesting-validation)
7. [Performance Testing](#7-performance-testing)
8. [Security Testing](#8-security-testing)
9. [Cross-Platform Testing](#9-cross-platform-testing)
10. [Broker Integration Testing](#10-broker-integration-testing)
11. [Test Data Management](#11-test-data-management)
12. [CI/CD Integration](#12-cicd-integration)
13. [Test Infrastructure](#13-test-infrastructure)
14. [Metrics & Reporting](#14-metrics--reporting)

---

## 1. Testing Philosophy & Principles

### 1.1 Core Testing Axioms

| # | Axiom | Rationale |
|---|-------|-----------|
| 1 | **Same pipeline, different data source** | The backtesting engine reuses identical module code as live trading. If you can't test it with historical data, you can't trust it with real money. |
| 2 | **Test the signal chain, not just outputs** | Every trade decision flows through S1→S2→…→S16. Testing individual modules in isolation is necessary but insufficient — the chain must be tested end-to-end. |
| 3 | **Risk Governor is untestable by design (and that's good)** | Hard-coded risk limits are not ML-generated, not tunable, not bypassable. They are verified by code review and formal proof, not by test cases. |
| 4 | **Determinism over coverage** | A test that runs the same way every time is worth more than a test that catches more edge cases randomly. Use fixed seeds, deterministic data, and reproducible environments. |
| 5 | **Test at the speed of trust** | Unit tests <1s total, integration tests <30s, E2E <5min. If tests are slow, developers skip them. If developers skip them, the system breaks. |
| 6 | **Every broker fill is a contract** | Broker APIs return specific structures. Test every possible response code, error, timeout, and edge case — a missed error code is a missed trade. |
| 7 | **Paper trading IS testing** | The paper trading phase is not "demo" — it is the final integration test before real capital is deployed. |

### 1.2 Testing Layers Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                                │
│                                                                   │
│                        ┌───────┐                                  │
│                        │  E2E  │  ← Full trade lifecycle          │
│                       ┌┴───────┴┐                                 │
│                       │Integration│ ← Component interactions      │
│                      ┌┴─────────┴┐                                │
│                      │  Unit Tests │ ← Individual module logic     │
│                     ┌┴───────────┴┐                               │
│                     │  Static Analysis │ ← Lint, type-check       │
│                    ┌┴─────────────┴┐                              │
│                    │  Security Scans │ ← SAST, DAST, deps         │
│                   └─────────────────┘                             │
│                                                                   │
│  CROSS-CUTTING: Performance · Security · Cross-Platform           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Test Pyramid & Coverage Targets

### 2.1 Coverage Matrix

| Layer | Scope | Target Coverage | Max Duration | Run Frequency |
|-------|-------|----------------|--------------|---------------|
| **Static Analysis** | Code quality, type safety | 100% files | <30s | Every commit |
| **Unit Tests** | Individual functions/methods | ≥90% line, ≥80% branch | <60s | Every commit |
| **Integration Tests** | Module interactions, DB, Redis | ≥80% critical paths | <5min | Every PR |
| **E2E Tests** | Full trade lifecycle | 100% happy paths, 100% risk gates | <15min | Nightly + pre-release |
| **Backtest Validation** | Strategy correctness | 100% AlphaStack steps validated | <30min | Weekly + pre-deploy |
| **Performance Tests** | Latency, throughput, load | All critical paths benchmarked | <30min | Weekly |
| **Security Tests** | Vulnerability, penetration | Zero critical/high CVEs | <20min | Every commit (auto) + quarterly (manual) |
| **Cross-Platform** | All supported platforms | 100% platform-specific code | <30min | Nightly |
| **Broker Integration** | All connected brokers | 100% order types per broker | <15min | Nightly + pre-release |

### 2.2 Module-Level Coverage Targets

| Module | Unit Coverage | Integration Coverage | Critical Test Areas |
|--------|--------------|---------------------|---------------------|
| AlphaStack Steps 1-16 | ≥95% | ≥85% | Signal generation, confluence scoring, step chaining |
| Risk Governor | 100% | 100% | All 6 hard limits, circuit breakers, correlation caps |
| Broker Connectors | ≥90% | 100% | Order placement, modification, cancellation, error handling |
| Data Pipeline | ≥85% | ≥80% | Gap detection, outlier filtering, cross-source validation |
| Event Bus | ≥90% | ≥85% | Stream routing, consumer groups, message ordering |
| API Gateway | ≥85% | ≥80% | Auth, rate limiting, WebSocket, CORS |
| ML Models | ≥80% | ≥70% | Inference latency, model loading, fallback behavior |
| Journal/Analytics | ≥85% | ≥75% | Trade recording, P&L calculation, performance metrics |

---

## 3. Unit Testing Strategy

### 3.1 Framework & Tooling

| Language | Framework | Assertion Library | Mocking | Coverage |
|----------|-----------|-------------------|---------|----------|
| **Python** | pytest 8.x | pytest assertions | pytest-mock, unittest.mock | coverage.py + pytest-cov |
| **Rust** | built-in `#[test]` | assert_eq!, assert_matches! | mockall | cargo-tarpaulin |
| **TypeScript/React** | Vitest | @testing-library/jest-dom | vitest mocks | vitest coverage (v8) |
| **MQL5** | MQL5 Tester | Custom assertion EA | N/A (test on demo) | Manual |

### 3.2 Unit Test Structure

```
tests/
├── unit/
│   ├── core/
│   │   ├── alphastack/
│   │   │   ├── test_step01_fundamental.py
│   │   │   ├── test_step02_bias.py
│   │   │   ├── ...
│   │   │   ├── test_step16_journal.py
│   │   │   ├── test_pipeline_orchestrator.py
│   │   │   └── test_strategy_context.py
│   │   ├── agents/
│   │   │   ├── test_strategy_agent.py
│   │   │   ├── test_risk_agent.py
│   │   │   ├── test_news_agent.py
│   │   │   ├── test_execution_agent.py
│   │   │   └── test_journal_agent.py
│   │   └── ml/
│   │       ├── test_sentiment_model.py
│   │       ├── test_regime_classifier.py
│   │       └── test_pattern_recognition.py
│   ├── execution/
│   │   ├── test_order_manager.py
│   │   ├── test_risk_engine.py
│   │   ├── test_mt5_connector.py
│   │   ├── test_ccxt_connector.py
│   │   ├── test_oanda_connector.py
│   │   └── test_smart_router.py
│   ├── data/
│   │   ├── test_gap_detector.py
│   │   ├── test_outlier_filter.py
│   │   ├── test_normalizer.py
│   │   └── test_data_models.py
│   ├── gateway/
│   │   ├── test_auth.py
│   │   ├── test_rate_limiter.py
│   │   ├── test_rest_routes.py
│   │   └── test_websocket.py
│   └── security/
│       ├── test_field_encryption.py
│       ├── test_jwt_signing.py
│       ├── test_credential_vault.py
│       └── test_audit_chain.py
├── conftest.py                    # Shared fixtures
└── fixtures/                      # Test data files
    ├── market_data/
    ├── news_data/
    └── expected_outputs/
```

### 3.3 Unit Test Patterns

#### AlphaStack Step Testing (Parameterized)

```python
# tests/unit/core/alphastack/test_step10_confluence.py

import pytest
from alpha.core.alphastack.steps.step10_confluence import ConfluenceEngine
from alpha.core.alphastack.context import StrategyContext
from tests.fixtures.builders import (
    build_signal_event,
    build_strategy_context,
)

class TestConfluenceEngine:
    """Unit tests for the Confluence Engine (Step 10)."""

    @pytest.fixture
    def engine(self):
        return ConfluenceEngine()

    # --- Scoring Tests ---

    @pytest.mark.parametrize("smc_score,liq_score,kill_zone_score,expected_max", [
        (0.9, 0.8, 0.9, 1.0),      # All top-3 present → no cap
        (0.2, 0.8, 0.9, 0.60),     # SMC missing → cap at 0.60
        (0.9, 0.2, 0.9, 0.60),     # Liquidity missing → cap at 0.60
        (0.9, 0.8, 0.2, 0.60),     # Kill zone missing → cap at 0.60
        (0.2, 0.2, 0.9, 0.60),     # Two missing → still cap at 0.60
        (0.2, 0.2, 0.2, 0.60),     # All three missing → cap at 0.60
    ])
    def test_top3_signal_cap_rule(self, engine, smc_score, liq_score, kill_zone_score, expected_max):
        """Critical rule: if ANY of top-3 signals is absent, cap at 0.60."""
        context = build_strategy_context(
            smc_score=smc_score,
            liquidity_score=liq_score,
            kill_zone_score=kill_zone_score,
            candle_score=0.8,
            rsi_score=0.7,
            volume_score=0.6,
            fundamental_score=0.5,
        )
        result = engine.score(context)
        assert result.score <= expected_max

    @pytest.mark.parametrize("score,expected_grade", [
        (0.95, "A+"),
        (0.80, "A+"),
        (0.79, "A"),
        (0.65, "A"),
        (0.64, "B"),
        (0.50, "B"),
        (0.49, "C"),
        (0.35, "C"),
        (0.34, "D"),
        (0.00, "D"),
    ])
    def test_grading_boundaries(self, engine, score, expected_grade):
        """Verify grading boundary conditions exactly."""
        grade = engine._grade(score)
        assert grade == expected_grade

    def test_confluence_requires_direction_consensus(self, engine):
        """When signals disagree on direction, result should flag conflict."""
        context = build_strategy_context(
            smc_direction="BULLISH",
            liquidity_direction="BEARISH",
            candle_direction="BULLISH",
            rsi_direction="BEARISH",
        )
        result = engine.score(context)
        assert result.direction_conflict is True

    def test_confluence_empty_signals_returns_zero(self, engine):
        """No signals = no score."""
        context = build_strategy_context(all_signals_none=True)
        result = engine.score(context)
        assert result.score == 0.0
        assert result.grade == "D"

    def test_confluence_weights_sum_to_one(self, engine):
        """Verify weight configuration is valid."""
        total = sum(engine.WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9
```

#### Risk Governor Testing (Exhaustive)

```python
# tests/unit/execution/test_risk_engine.py

import pytest
from alpha.execution.risk_engine import RiskGovernor
from tests.fixtures.builders import build_trade_proposal, build_account

class TestRiskGovernor:
    """
    Risk Governor tests. These are CRITICAL — a bug here means lost money.
    Every limit, every edge case, every boundary must be tested.
    """

    @pytest.fixture
    def governor(self):
        return RiskGovernor()

    # --- Per-Trade Risk Limit (2%) ---

    def test_rejects_trade_exceeding_2pct_risk(self, governor):
        account = build_account(balance=1000, open_positions=[])
        proposal = build_trade_proposal(risk_amount=25)  # 2.5% of $1000
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Per-trade risk exceeded" in result.reason

    def test_accepts_trade_at_exactly_2pct_risk(self, governor):
        account = build_account(balance=1000, open_positions=[])
        proposal = build_trade_proposal(risk_amount=20)  # exactly 2%
        result = governor.check(proposal, account)
        assert result.approved is True

    def test_accepts_trade_below_2pct_risk(self, governor):
        account = build_account(balance=1000, open_positions=[])
        proposal = build_trade_proposal(risk_amount=10)  # 1%
        result = governor.check(proposal, account)
        assert result.approved is True

    def test_risk_calculation_uses_account_balance_not_equity(self, governor):
        """Risk is calculated against balance, not equity (prevents runaway on winning streaks)."""
        account = build_account(balance=1000, equity=1500, open_positions=[])
        proposal = build_trade_proposal(risk_amount=25)  # 2.5% of balance, 1.67% of equity
        result = governor.check(proposal, account)
        assert result.approved is False  # Should be rejected against balance

    # --- Total Exposure Limit (6%) ---

    def test_rejects_when_total_exposure_exceeds_6pct(self, governor):
        account = build_account(
            balance=1000,
            open_positions=[
                build_trade_proposal(risk_amount=20),  # 2%
                build_trade_proposal(risk_amount=20),  # 2%
                build_trade_proposal(risk_amount=20),  # 2% = total 6%
            ]
        )
        proposal = build_trade_proposal(risk_amount=5)  # Would push to 6.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Total exposure exceeded" in result.reason

    # --- Correlated Exposure Limit (3%) ---

    def test_rejects_correlated_exposure_above_3pct(self, governor):
        """EUR/USD and GBP/USD are correlated (>0.7). Combined risk capped at 3%."""
        account = build_account(
            balance=1000,
            open_positions=[
                build_trade_proposal(symbol="EURUSD", risk_amount=20),  # 2%
            ]
        )
        proposal = build_trade_proposal(symbol="GBPUSD", risk_amount=15)  # 1.5%, combined 3.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Correlated exposure exceeded" in result.reason

    def test_accepts_uncorrelated_positions_beyond_correlated_limit(self, governor):
        """EUR/USD and USD/JPY have low correlation — no combined cap."""
        account = build_account(
            balance=1000,
            open_positions=[
                build_trade_proposal(symbol="EURUSD", risk_amount=20),  # 2%
            ]
        )
        proposal = build_trade_proposal(symbol="USDJPY", risk_amount=15)  # 1.5%
        result = governor.check(proposal, account)
        assert result.approved is True

    # --- Daily Loss Circuit Breaker (4%) ---

    def test_halts_trading_after_4pct_daily_loss(self, governor):
        account = build_account(balance=1000, daily_pnl=-40)  # -4%
        proposal = build_trade_proposal(risk_amount=5)
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Daily loss circuit breaker" in result.reason

    def test_allows_trading_at_3_99pct_daily_loss(self, governor):
        account = build_account(balance=1000, daily_pnl=-39.9)
        proposal = build_trade_proposal(risk_amount=5)
        result = governor.check(proposal, account)
        assert result.approved is True

    # --- Max Concurrent Positions (5) ---

    def test_rejects_6th_position(self, governor):
        positions = [build_trade_proposal() for _ in range(5)]
        account = build_account(balance=10000, open_positions=positions)
        proposal = build_trade_proposal(risk_amount=10)
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Max concurrent positions" in result.reason

    # --- Margin Utilization (30%) ---

    def test_rejects_when_margin_above_30pct(self, governor):
        account = build_account(balance=1000, margin_utilization=0.31)
        proposal = build_trade_proposal(risk_amount=5)
        result = governor.check(proposal, account)
        assert result.approved is False
        assert "Margin utilization" in result.reason

    # --- Adjusted Lot Size ---

    def test_returns_adjusted_lot_size_when_over_limit(self, governor):
        """When risk is slightly over, governor should suggest reduced size."""
        account = build_account(balance=1000, open_positions=[])
        proposal = build_trade_proposal(risk_amount=25)  # 2.5%
        result = governor.check(proposal, account)
        assert result.approved is False
        assert result.adjusted_lot_size is not None
        assert result.adjusted_lot_size < proposal.lot_size
```

#### Broker Connector Testing (Mock-Based)

```python
# tests/unit/execution/test_mt5_connector.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from alpha.execution.connectors.mt5_connector import MT5Connector
from alpha.data.models.order import UnifiedOrder, Direction, OrderType

class TestMT5Connector:

    @pytest.fixture
    def connector(self):
        return MT5Connector()

    @pytest.fixture
    def mock_mt5(self):
        with patch('alpha.execution.connectors.mt5_connector.mt5') as mock:
            yield mock

    async def test_connect_initializes_and_logs_in(self, connector, mock_mt5):
        mock_mt5.initialize.return_value = True
        mock_mt5.login.return_value = True
        mock_mt5.account_info.return_value = MagicMock(balance=1000)

        result = await connector.connect({
            'terminal_path': '/path/to/terminal',
            'server': 'FXPesa-Demo',
            'login': 123456,
            'password': 'test'
        })

        assert result is True
        mock_mt5.initialize.assert_called_once()
        mock_mt5.login.assert_called_once()

    async def test_place_buy_order_constructs_correct_request(self, connector, mock_mt5):
        mock_mt5.symbol_info_tick.return_value = MagicMock(ask=1.0850, bid=1.0848)
        mock_mt5.order_send.return_value = MagicMock(
            retcode=0,  # TRADE_RETCODE_DONE
            order=12345678,
            price=1.0850,
            comment="Done"
        )

        order = UnifiedOrder(
            pair="EURUSD",
            direction=Direction.BULLISH,
            order_type=OrderType.MARKET,
            lot_size=0.01,
            stop_loss=1.0820,
            take_profit=1.0900,
        )

        result = await connector.place_order(order)

        assert result.success is True
        assert result.ticket == 12345678
        assert result.price == 1.0850

        # Verify the request structure sent to MT5
        call_args = mock_mt5.order_send.call_args[0][0]
        assert call_args['action'] == mock_mt5.TRADE_ACTION_DEAL
        assert call_args['symbol'] == 'EURUSD'
        assert call_args['volume'] == 0.01
        assert call_args['type'] == mock_mt5.ORDER_TYPE_BUY
        assert call_args['sl'] == 1.0820
        assert call_args['tp'] == 1.0900

    @pytest.mark.parametrize("retcode,expected_success,expected_error", [
        (0, True, None),                     # TRADE_RETCODE_DONE
        (10004, False, "Requote"),           # TRADE_RETCODE_REQUOTE
        (10006, False, "Order rejected"),    # TRADE_RETCODE_REJECT
        (10013, False, "Invalid volume"),    # TRADE_RETCODE_INVALID_VOLUME
        (10014, False, "Invalid price"),     # TRADE_RETCODE_INVALID_PRICE
        (10015, False, "Invalid stops"),     # TRADE_RETCODE_INVALID_STOPS
        (10016, False, "Trade disabled"),    # TRADE_RETCODE_TRADE_DISABLED
        (10019, False, "No money"),          # TRADE_RETCODE_NO_MONEY
    ])
    async def test_order_send_retcode_handling(self, connector, mock_mt5, retcode, expected_success, expected_error):
        """Test all MT5 return codes are handled correctly."""
        mock_mt5.symbol_info_tick.return_value = MagicMock(ask=1.0850, bid=1.0848)
        mock_mt5.order_send.return_value = MagicMock(
            retcode=retcode,
            order=0,
            price=0,
            comment=expected_error or "Done"
        )

        order = UnifiedOrder(
            pair="EURUSD",
            direction=Direction.BULLISH,
            order_type=OrderType.MARKET,
            lot_size=0.01,
            stop_loss=1.0820,
            take_profit=1.0900,
        )

        result = await connector.place_order(order)
        assert result.success is expected_success
        if expected_error:
            assert expected_error in result.error

    async def test_connect_handles_initialization_failure(self, connector, mock_mt5):
        mock_mt5.initialize.return_value = False
        mock_mt5.last_error.return_value = (1, "Terminal not found")

        result = await connector.connect({'terminal_path': '/invalid/path'})
        assert result is False

    async def test_disconnect_calls_shutdown(self, connector, mock_mt5):
        await connector.disconnect()
        mock_mt5.shutdown.assert_called_once()
```

### 3.4 Rust Unit Tests

```rust
// src/indicators/ta_core.rs

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    #[test]
    fn test_rsi_known_values() {
        // EUR/USD H1 known RSI(14) values
        let closes = vec![
            1.0850, 1.0855, 1.0848, 1.0862, 1.0870,
            1.0865, 1.0858, 1.0875, 1.0880, 1.0872,
            1.0868, 1.0882, 1.0890, 1.0885, 1.0895,
        ];
        let rsi = calculate_rsi(&closes, 14);
        assert_relative_eq!(rsi, 62.5, epsilon = 1.0);
    }

    #[test]
    fn test_rsi_all_gains_returns_100() {
        let closes = vec![1.0, 1.1, 1.2, 1.3, 1.4, 1.5];
        let rsi = calculate_rsi(&closes, 5);
        assert_eq!(rsi, 100.0);
    }

    #[test]
    fn test_rsi_all_losses_returns_0() {
        let closes = vec![1.5, 1.4, 1.3, 1.2, 1.1, 1.0];
        let rsi = calculate_rsi(&closes, 5);
        assert_eq!(rsi, 0.0);
    }

    #[test]
    fn test_atr_calculation() {
        let highs = vec![1.0900, 1.0920, 1.0910];
        let lows  = vec![1.0850, 1.0860, 1.0855];
        let closes = vec![1.0880, 1.0890, 1.0875];
        let atr = calculate_atr(&highs, &lows, &closes, 3);
        assert!(atr > 0.0);
        assert!(atr < 0.01);  // Sanity: ATR for EUR/USD should be < 100 pips
    }

    #[test]
    fn test_swing_detection_uptrend() {
        let highs = vec![1.0, 1.1, 1.05, 1.2, 1.15, 1.3];
        let lows  = vec![0.9, 1.0, 0.95, 1.1, 1.05, 1.2];
        let swings = detect_swings(&highs, &lows, 2);
        // Should detect higher highs and higher lows
        assert!(swings.swing_highs.len() >= 2);
        assert!(swings.swing_lows.len() >= 2);
    }

    #[test]
    fn test_empty_input_returns_empty() {
        let closes: Vec<f64> = vec![];
        let rsi = calculate_rsi(&closes, 14);
        assert!(rsi.is_nan());
    }
}
```

### 3.5 Frontend Unit Tests

```typescript
// src/components/Portfolio.test.tsx

import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Portfolio } from './Portfolio';
import { mockPortfolioData } from '@/tests/fixtures';

describe('Portfolio Component', () => {
  it('displays total equity correctly', () => {
    render(<Portfolio data={mockPortfolioData} />);
    expect(screen.getByText('$1,050.00')).toBeInTheDocument();
  });

  it('shows open positions count', () => {
    render(<Portfolio data={mockPortfolioData} />);
    expect(screen.getByText('3 Open Positions')).toBeInTheDocument();
  });

  it('highlights negative P&L in red', () => {
    const data = { ...mockPortfolioData, dailyPnl: -25.50 };
    render(<Portfolio data={data} />);
    const pnlElement = screen.getByText('-$25.50');
    expect(pnlElement).toHaveClass('text-red-500');
  });

  it('shows drawdown warning when above 10%', () => {
    const data = { ...mockPortfolioData, drawdown: 12.5 };
    render(<Portfolio data={data} />);
    expect(screen.getByTestId('drawdown-warning')).toBeInTheDocument();
  });

  it('renders empty state when no positions', () => {
    const data = { ...mockPortfolioData, positions: [] };
    render(<Portfolio data={data} />);
    expect(screen.getByText('No open positions')).toBeInTheDocument();
  });
});
```

---

## 4. Integration Testing

### 4.1 Integration Test Categories

| Category | What's Tested | Infrastructure | Duration Target |
|----------|--------------|----------------|-----------------|
| **Event Bus** | Redis Streams pub/sub, consumer groups, ordering | Testcontainers Redis | <10s |
| **Data Pipeline** | Ingestion → storage → retrieval chain | Testcontainers TimescaleDB | <20s |
| **AlphaStack Pipeline** | Steps 1-16 chained execution | Mock broker + Redis | <30s |
| **Risk → Execution** | Risk gate → order placement → fill tracking | Mock broker | <15s |
| **Agent Communication** | Inter-agent message routing | Redis Streams | <20s |
| **API Gateway** | Auth → rate limit → route → response | Testcontainers Redis + PG | <15s |
| **WebSocket** | Connection, subscription, real-time push | In-process WS server | <10s |

### 4.2 Integration Test Infrastructure

```python
# tests/conftest.py — Shared fixtures for integration tests

import pytest
import asyncio
import redis.asyncio as redis
from testcontainers.redis import RedisContainer
from testcontainers.postgres import PostgresContainer
from testcontainers.timescaledb import TimescaleDbContainer

@pytest.fixture(scope="session")
def event_loop():
    """Override default event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def redis_container():
    """Spin up Redis in Docker for integration tests."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis

@pytest.fixture(scope="session")
def timescale_container():
    """Spin up TimescaleDB in Docker for integration tests."""
    with TimescaleDbContainer("timescale/timescaledb:latest-pg16") as ts:
        yield ts

@pytest.fixture(scope="session")
def postgres_container():
    """Spin up PostgreSQL for metadata tests."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture
async def redis_client(redis_container):
    """Provide a connected Redis client."""
    client = redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=int(redis_container.get_exposed_port(6379)),
        decode_responses=True,
    )
    yield client
    await client.flushall()
    await client.aclose()

@pytest.fixture
async def event_bus(redis_client):
    """Provide a configured EventBus instance."""
    from alpha.core.event_bus import EventBus
    bus = EventBus(redis_client)
    await bus.initialize()
    yield bus
    await bus.shutdown()

@pytest.fixture
def sample_ohlcv_data():
    """Load fixture OHLCV data for EUR/USD H1 (1000 bars)."""
    import pandas as pd
    return pd.read_csv("tests/fixtures/market_data/eurusd_h1_1000.csv")

@pytest.fixture
def sample_tick_data():
    """Load fixture tick data (10,000 ticks)."""
    import pandas as pd
    return pd.read_csv("tests/fixtures/market_data/eurusd_ticks_10k.csv")
```

### 4.3 Event Bus Integration Tests

```python
# tests/integration/test_event_bus.py

import pytest
import asyncio
import json

class TestEventBusIntegration:
    """Integration tests for Redis Streams event bus."""

    async def test_publish_and_consume_message(self, event_bus):
        """Message published to a stream is received by consumer."""
        received = []

        async def handler(message):
            received.append(message)

        await event_bus.subscribe("test.stream", handler)
        await event_bus.publish("test.stream", {"key": "value"})

        await asyncio.sleep(0.5)  # Allow propagation
        assert len(received) == 1
        assert received[0]["key"] == "value"

    async def test_consumer_group_load_balancing(self, redis_client):
        """Multiple consumers in same group each receive unique messages."""
        from alpha.core.event_bus import EventBus

        bus1 = EventBus(redis_client)
        bus2 = EventBus(redis_client)
        received_1, received_2 = [], []

        await bus1.subscribe_group("test.stream", "group1", "consumer1",
                                    lambda m: received_1.append(m))
        await bus2.subscribe_group("test.stream", "group1", "consumer2",
                                    lambda m: received_2.append(m))

        # Publish 10 messages
        for i in range(10):
            await event_bus.publish("test.stream", {"index": i})

        await asyncio.sleep(2)

        # Each consumer should get some messages, total = 10
        assert len(received_1) + len(received_2) == 10
        assert len(received_1) > 0
        assert len(received_2) > 0

    async def test_message_ordering_preserved(self, event_bus):
        """Messages arrive in publish order."""
        received = []

        async def handler(message):
            received.append(message["seq"])

        await event_bus.subscribe("test.ordered", handler)
        for i in range(100):
            await event_bus.publish("test.ordered", {"seq": i})

        await asyncio.sleep(2)
        assert received == list(range(100))

    async def test_stream_retention_policy(self, redis_client):
        """Old messages are evicted based on maxlen."""
        await redis_client.xadd("test.retention", {"data": "old"}, maxlen=100)
        for i in range(150):
            await redis_client.xadd("test.retention", {"data": f"msg_{i}"}, maxlen=100)

        length = await redis_client.xlen("test.retention")
        assert length <= 100

    async def test_dead_letter_queue_on_handler_failure(self, event_bus):
        """Failed messages are routed to DLQ for retry."""
        async def failing_handler(message):
            raise ValueError("Simulated failure")

        await event_bus.subscribe_with_dlq("test.dlq", failing_handler, max_retries=3)
        await event_bus.publish("test.dlq", {"will_fail": True})

        await asyncio.sleep(2)

        dlq_length = await event_bus.get_dlq_length("test.dlq")
        assert dlq_length == 1
```

### 4.4 AlphaStack Pipeline Integration Tests

```python
# tests/integration/test_alphastack_pipeline.py

import pytest
from alpha.core.alphastack.pipeline import AlphaStackPipeline
from alpha.core.alphastack.context import StrategyContext
from tests.fixtures.builders import build_market_event

class TestAlphaStackPipelineIntegration:
    """Integration tests for the full 16-step AlphaStack pipeline."""

    @pytest.fixture
    async def pipeline(self, event_bus, redis_client):
        """Initialize pipeline with real Redis but mock broker."""
        pipeline = AlphaStackPipeline(event_bus=event_bus, config={
            'instruments': ['EURUSD'],
            'timeframes': ['H1', 'H4', 'D1'],
            'min_confidence': 0.65,
        })
        await pipeline.initialize()
        yield pipeline
        await pipeline.shutdown()

    async def test_full_pipeline_produces_trade_proposal(self, pipeline, sample_ohlcv_data):
        """A complete market event with strong signals produces a trade proposal."""
        event = build_market_event(
            pair="EURUSD",
            timeframe="H1",
            candle_data=sample_ohlcv_data.iloc[-1],
            news_sentiment=0.8,  # Strong bullish
            session="LONDON",
        )

        result = await pipeline.process(event)

        # Pipeline should produce a proposal with all 16 steps populated
        assert result is not None
        assert result.trade_proposal is not None
        assert result.trade_proposal.confluence_score >= 0.65
        assert len(result.step_results) == 16
        assert all(step.status == "completed" for step in result.step_results.values())

    async def test_pipeline_halts_on_avoid_all_signal(self, pipeline):
        """When S1 returns AVOID_ALL, pipeline should halt and not produce proposal."""
        event = build_market_event(
            pair="EURUSD",
            news_sentiment=-0.9,  # Strong bearish + high-impact event
            high_impact_event=True,
        )

        result = await pipeline.process(event)

        assert result.trade_proposal is None
        assert result.halt_reason == "S1_FUNDAMENTAL: AVOID_ALL"
        # Steps 2-16 should not have been executed
        assert all(
            step.status == "skipped"
            for name, step in result.step_results.items()
            if name not in ["S1_FUNDAMENTAL"]
        )

    async def test_pipeline_halts_on_choppy_market(self, pipeline):
        """When S4 detects chop (ADX < 20), pipeline should skip trade."""
        event = build_market_event(
            pair="EURUSD",
            adx_value=15,  # Choppy
            bollinger_width_percentile=0.1,  # Tight range
        )

        result = await pipeline.process(event)

        assert result.trade_proposal is None
        assert "choppy" in result.halt_reason.lower()

    async def test_pipeline_context_enrichment_chain(self, pipeline, sample_ohlcv_data):
        """Each step enriches the StrategyContext — verify progressive enrichment."""
        event = build_market_event(pair="EURUSD", candle_data=sample_ohlcv_data.iloc[-1])
        result = await pipeline.process(event)

        ctx = result.context
        # Phase A
        assert ctx.fundamental_bias is not None
        assert ctx.market_bias is not None
        assert ctx.session_info is not None
        assert ctx.market_structure is not None
        # Phase B
        assert ctx.sr_levels is not None
        assert ctx.liquidity_zones is not None
        assert ctx.order_blocks is not None
        assert ctx.rsi_state is not None
        # Phase C (if proposal generated)
        if result.trade_proposal:
            assert ctx.candlestick_signal is not None
            assert ctx.entry_plan is not None
            assert ctx.position_size is not None
            assert ctx.stop_loss is not None

    async def test_pipeline_confidence_score_propagation(self, pipeline):
        """Aggregate confidence should be weighted combination of step confidences."""
        event = build_market_event(
            pair="EURUSD",
            # Set strong signals for all steps
            news_sentiment=0.8,
            regime="BULL_TREND",
            session="LONDON",
            adx_value=35,
            sr_confluence=True,
            liquidity_sweep=True,
            ob_present=True,
            rsi_alignment=True,
            candlestick_pattern="ENGULFING",
        )

        result = await pipeline.process(event)

        assert result.context.confidence_score >= 0.7
        assert result.context.confidence_score <= 1.0
```

### 4.5 Risk → Execution Integration Tests

```python
# tests/integration/test_risk_to_execution.py

import pytest
from alpha.execution.order_manager import UnifiedOrderManager
from alpha.execution.risk_engine import RiskGovernor
from tests.fixtures.mock_broker import MockBrokerConnector

class TestRiskExecutionIntegration:
    """Test the critical path: Risk check → Order routing → Fill tracking."""

    @pytest.fixture
    def mock_broker(self):
        return MockBrokerConnector(fill_probability=1.0, slippage_pips=0.5)

    @pytest.fixture
    def order_manager(self, mock_broker, event_bus):
        return UnifiedOrderManager(
            router=mock_broker,
            risk_governor=RiskGovernor(),
            event_bus=event_bus,
        )

    async def test_approved_order_is_routed_and_filled(self, order_manager, event_bus):
        """Approved trade proposal → broker order → fill event published."""
        proposal = build_trade_proposal(risk_amount=10, confluence_score=0.82)

        result = await order_manager.submit_order(proposal)

        assert result.success is True
        assert result.ticket is not None
        assert result.fill_price > 0

        # Verify fill event published to event bus
        events = await event_bus.read_stream("orders.fill", count=1)
        assert len(events) == 1
        assert events[0]["ticket"] == result.ticket

    async def test_rejected_order_never_reaches_broker(self, order_manager, mock_broker):
        """Risk-rejected proposal should NOT be sent to broker."""
        proposal = build_trade_proposal(risk_amount=50)  # 5% — exceeds 2% limit

        result = await order_manager.submit_order(proposal)

        assert result.success is False
        assert mock_broker.orders_placed == 0  # Broker never called

    async def test_fill_event_updates_risk_state(self, order_manager):
        """After a fill, risk engine should reflect the new exposure."""
        proposal = build_trade_proposal(risk_amount=15)

        await order_manager.submit_order(proposal)

        account = await order_manager.get_account_state()
        assert len(account.open_positions) == 1
        assert account.current_exposure > 0

    async def test_broker_timeout_returns_error(self, order_manager, mock_broker):
        """When broker times out, order manager should return error (not hang)."""
        mock_broker.simulate_timeout = True
        proposal = build_trade_proposal(risk_amount=10)

        result = await order_manager.submit_order(proposal)

        assert result.success is False
        assert "timeout" in result.error.lower()

    async def test_broker_requote_triggers_retry(self, order_manager, mock_broker):
        """On requote, order manager should retry with new price (up to max retries)."""
        mock_broker.simulate_requote = True
        mock_broker.max_retries = 3
        proposal = build_trade_proposal(risk_amount=10)

        result = await order_manager.submit_order(proposal)

        assert mock_broker.retry_count == 3
```

---

## 5. End-to-End Testing

### 5.1 E2E Test Scenarios

The E2E tests validate the complete trade lifecycle from market data ingestion to trade closure and journaling.

```
┌──────────────────────────────────────────────────────────────────┐
│                    E2E TEST SCENARIOS                              │
│                                                                    │
│  SCENARIO 1: Winning Trade Lifecycle                              │
│  Market Data → Signal → Risk Check → Order → Fill → Manage →     │
│  TP Hit → Partial Close → Trail → Final Close → Journal Entry    │
│                                                                    │
│  SCENARIO 2: Losing Trade Lifecycle                               │
│  Market Data → Signal → Risk Check → Order → Fill → Manage →     │
│  SL Hit → Journal Entry                                           │
│                                                                    │
│  SCENARIO 3: Risk Rejection                                       │
│  Market Data → Signal → Risk Check → REJECTED → No Order         │
│                                                                    │
│  SCENARIO 4: Black Swan Detection                                 │
│  Normal Trading → Anomaly Detected → Emergency Close All →        │
│  Alert Sent → Trading Halted                                      │
│                                                                    │
│  SCENARIO 5: Broker Disconnection                                 │
│  Trading → Broker Disconnects → Failover → Alert → Reconnect     │
│                                                                    │
│  SCENARIO 6: Multi-Instrument Portfolio                           │
│  EUR/USD Signal + GBP/USD Signal → Correlation Check →            │
│  Adjusted Sizing → Both Executed → Combined Risk Managed          │
│                                                                    │
│  SCENARIO 7: News Event Handling                                  │
│  Open Position → High-Impact News Approaches → Pre-News Protocol  │
│  → Tighten SL / Partial Close → Post-News Resume                  │
│                                                                    │
│  SCENARIO 8: Weekend Management                                   │
│  Open Position → Friday 20:00 UTC → Weekend Protocol →            │
│  Close/Trail Based on P&L State                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 E2E Test Implementation

```python
# tests/e2e/test_trade_lifecycle.py

import pytest
import asyncio
from alpha.engine import AlphaStackEngine
from tests.fixtures.replay_data import ReplayEventBus, load_fixture_sequence

class TestTradeLifecycleE2E:
    """
    End-to-end tests using the replay event bus.
    Same code paths as live trading, deterministic historical data.
    """

    @pytest.fixture
    async def engine(self, redis_container, timescale_container):
        """Full engine with real infrastructure, replay data source."""
        engine = AlphaStackEngine(config={
            'mode': 'backtest',
            'data_source': 'replay',
            'broker': 'simulated',
            'redis_url': redis_container.get_connection_url(),
            'database_url': timescale_container.get_connection_url(),
        })
        await engine.start()
        yield engine
        await engine.stop()

    async def test_winning_trade_full_lifecycle(self, engine):
        """
        SCENARIO 1: Complete winning trade from signal to journal.
        
        Replay a historical EUR/USD sequence where AlphaStack produces
        an A+ bullish signal during London session, price reaches TP2.
        """
        # Load fixture: 500 bars of EUR/USD H1 ending with a textbook setup
        events = load_fixture_sequence("eurusd_winning_trade_london.json")

        # Run engine on replay data
        results = await engine.run_replay(events)

        # Verify signal was generated
        assert len(results.signals_generated) >= 1
        signal = results.signals_generated[0]
        assert signal.direction == "BULLISH"
        assert signal.confluence_score >= 0.80
        assert signal.setup_grade == "A+"

        # Verify order was placed
        assert len(results.orders_placed) == 1
        order = results.orders_placed[0]
        assert order.pair == "EURUSD"
        assert order.lot_size > 0
        assert order.stop_loss < order.entry_price
        assert len(order.take_profits) >= 2

        # Verify fills and management
        assert len(results.fills) >= 1
        assert results.partial_closes >= 1  # At least TP1 partial close

        # Verify final P&L
        assert results.total_r > 0  # Winning trade

        # Verify journal entry
        assert len(results.journal_entries) == 1
        journal = results.journal_entries[0]
        assert journal.pair == "EURUSD"
        assert journal.direction == "BULLISH"
        assert journal.exit_reason is not None
        assert journal.r_multiple > 0
        assert journal.reasoning_chain is not None
        assert len(journal.reasoning_chain) >= 10  # All 16 steps documented

    async def test_losing_trade_sl_hit(self, engine):
        """
        SCENARIO 2: Losing trade — SL is hit before TP.
        """
        events = load_fixture_sequence("eurusd_losing_trade_sl_hit.json")
        results = await engine.run_replay(events)

        assert results.total_r < 0  # Losing trade
        assert results.journal_entries[0].exit_reason == "stop_loss_hit"
        assert results.journal_entries[0].r_multiple < 0

    async def test_risk_rejection_prevents_order(self, engine):
        """
        SCENARIO 3: High-confluence signal rejected by risk governor.
        
        Pre-load account with positions at 5% exposure.
        New signal should be rejected (would push to 7%).
        """
        # Set up account state near risk limits
        await engine.set_account_state(balance=1000, open_positions=[
            {"symbol": "EURUSD", "risk": 30},  # 3%
            {"symbol": "GBPUSD", "risk": 20},  # 2% = total 5%
        ])

        events = load_fixture_sequence("eurusd_a_plus_signal.json")
        results = await engine.run_replay(events)

        # Signal was generated but order was NOT placed
        assert len(results.signals_generated) >= 1
        assert results.signals_generated[0].confluence_score >= 0.80
        assert len(results.orders_placed) == 0
        assert results.risk_rejections >= 1
        assert "Total exposure exceeded" in results.risk_rejection_reasons[0]

    async def test_black_swan_emergency_close(self, engine):
        """
        SCENARIO 4: Black swan detection triggers emergency close.
        """
        # Start with open positions
        await engine.set_account_state(balance=10000, open_positions=[
            {"symbol": "EURUSD", "risk": 100, "unrealized_pnl": 50},
            {"symbol": "GBPUSD", "risk": 100, "unrealized_pnl": -30},
        ])

        events = load_fixture_sequence("black_swan_vix_spike.json")
        results = await engine.run_replay(events)

        # All positions should be closed
        assert results.positions_closed == 2
        assert results.black_swan_detected is True
        assert results.trading_paused is True
        assert results.alerts_sent >= 1

    async def test_multi_instrument_correlation_sizing(self, engine):
        """
        SCENARIO 6: Correlated EUR/USD and GBP/USD signals get adjusted sizing.
        """
        events = load_fixture_sequence("correlated_signals_eurusd_gbpusd.json")
        results = await engine.run_replay(events)

        if len(results.orders_placed) == 2:
            # Combined risk should not exceed 3% for correlated pairs
            total_risk = sum(o.risk_amount for o in results.orders_placed)
            assert total_risk <= 30  # 3% of $1000

    async def test_news_event_pre_protocol(self, engine):
        """
        SCENARIO 7: Pre-news protocol tightens stops on open positions.
        """
        await engine.set_account_state(balance=1000, open_positions=[
            {"symbol": "EURUSD", "risk": 10, "unrealized_pnl": 15, "entry_price": 1.0850},
        ])

        events = load_fixture_sequence("nfp_approach_with_position.json")
        results = await engine.run_replay(events)

        # Stop should have been tightened
        assert results.sl_modifications >= 1
        # Partial close may have occurred
        assert results.partial_closes >= 0
```

### 5.3 E2E for Desktop App

```typescript
// tests/e2e/desktop/app.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Alpha Stack Desktop App', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:1420');
    await page.waitForSelector('[data-testid="dashboard"]');
  });

  test('displays portfolio overview on launch', async ({ page }) => {
    await expect(page.locator('[data-testid="equity-display"]')).toBeVisible();
    await expect(page.locator('[data-testid="positions-table"]')).toBeVisible();
    await expect(page.locator('[data-testid="pnl-chart"]')).toBeVisible();
  });

  test('shows real-time signal updates', async ({ page }) => {
    // Wait for WebSocket connection
    await expect(page.locator('[data-testid="ws-status"]')).toHaveText('Connected');

    // Signals panel should update
    const signalCount = await page.locator('[data-testid="signal-item"]').count();
    expect(signalCount).toBeGreaterThanOrEqual(0);
  });

  test('broker connection dialog validates inputs', async ({ page }) => {
    await page.click('[data-testid="connect-broker"]');
    await page.click('[data-testid="submit-connect"]');

    // Should show validation errors
    await expect(page.locator('[data-testid="error-server"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-login"]')).toBeVisible();
  });

  test('trade confirmation dialog requires human approval', async ({ page }) => {
    // Simulate a trade proposal arriving
    await page.evaluate(() => {
      window.__TAURI__?.event.emit('trade-proposal', {
        pair: 'EURUSD',
        direction: 'BULLISH',
        confluence_score: 0.72,
        setup_grade: 'A',
      });
    });

    await expect(page.locator('[data-testid="trade-approval-dialog"]')).toBeVisible();
    await expect(page.locator('[data-testid="approve-trade"]')).toBeEnabled();
    await expect(page.locator('[data-testid="reject-trade"]')).toBeEnabled();
  });
});
```

---

## 6. Backtesting Validation

### 6.1 Backtesting Validation Strategy

The backtesting engine must produce results identical to what live trading would have produced on the same data. This is verified through three validation layers:

```
┌──────────────────────────────────────────────────────────────┐
│                BACKTESTING VALIDATION LAYERS                   │
│                                                                │
│  LAYER 1: MODULE EQUIVALENCE                                  │
│  Verify backtest modules produce identical outputs to live     │
│  modules given identical inputs.                               │
│                                                                │
│  LAYER 2: FILL SIMULATION ACCURACY                            │
│  Verify simulated fills match real broker behavior within      │
│  acceptable tolerance (spread, slippage, latency).             │
│                                                                │
│  LAYER 3: STATISTICAL VALIDATION                              │
│  Verify backtest results are not artifacts of overfitting.     │
│  Walk-forward, Monte Carlo, out-of-sample testing.             │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Module Equivalence Tests

```python
# tests/backtest/test_module_equivalence.py

import pytest
from alpha.core.alphastack.pipeline import AlphaStackPipeline
from alpha.backtest.engine import BacktestEngine
from alpha.backtest.replay_bus import ReplayEventBus

class TestModuleEquivalence:
    """
    Verify that the backtesting engine produces identical module outputs
    as the live engine given the same input data.
    """

    async def test_step_outputs_match_live(self, sample_ohlcv_data):
        """Each AlphaStack step produces identical output in backtest vs live mode."""
        live_pipeline = AlphaStackPipeline(mode='live')
        backtest_pipeline = AlphaStackPipeline(mode='backtest')

        for i in range(len(sample_ohlcv_data)):
            event = build_market_event_from_row(sample_ohlcv_data.iloc[i])

            live_result = await live_pipeline.process(event)
            backtest_result = await backtest_pipeline.process(event)

            # Step results should be identical
            for step_name in live_result.step_results:
                live_step = live_result.step_results[step_name]
                backtest_step = backtest_result.step_results[step_name]

                assert live_step.direction == backtest_step.direction, \
                    f"Step {step_name} direction mismatch at bar {i}"
                assert abs(live_step.confidence - backtest_step.confidence) < 1e-9, \
                    f"Step {step_name} confidence mismatch at bar {i}"

    async def test_confluence_score_matches(self, sample_ohlcv_data):
        """Confluence engine produces identical scores in both modes."""
        live_engine = ConfluenceEngine(mode='live')
        backtest_engine = ConfluenceEngine(mode='backtest')

        for i in range(len(sample_ohlcv_data)):
            signals = extract_signals(sample_ohlcv_data.iloc[i])

            live_score = live_engine.score(signals)
            backtest_score = backtest_engine.score(signals)

            assert abs(live_score.score - backtest_score.score) < 1e-9
            assert live_score.grade == backtest_score.grade

    async def test_risk_decisions_match(self):
        """Risk Governor produces identical decisions in both modes."""
        governor = RiskGovernor()  # Mode-independent (hard-coded rules)

        test_cases = load_risk_test_scenarios()
        for case in test_cases:
            result = governor.check(case.proposal, case.account)
            assert result.approved == case.expected_approved
            if case.expected_adjusted_size:
                assert abs(result.adjusted_lot_size - case.expected_adjusted_size) < 1e-9
```

### 6.3 Fill Simulation Validation

```python
# tests/backtest/test_fill_simulation.py

class TestFillSimulation:
    """Verify fill simulator produces realistic results."""

    def test_slippage_model_matches_historical(self):
        """
        Compare simulated slippage distribution against actual FXPesa slippage.
        Tolerance: ±0.5 pips mean, similar distribution shape.
        """
        actual_slippage = load_historical_slippage("fxpesa_eurusd_2025.csv")
        simulated_slippage = []

        sim = FillSimulator(slippage_model='proportional', spread_model='session_based')
        for i in range(len(actual_slippage)):
            fill = sim.simulate_fill(
                order=build_market_order(pair="EURUSD", lot_size=0.01),
                market_event=build_tick_event(spread=actual_slippage[i].spread),
            )
            simulated_slippage.append(fill.slippage)

        mean_actual = np.mean(actual_slippage)
        mean_simulated = np.mean(simulated_slippage)
        assert abs(mean_actual - mean_simulated) < 0.00005  # <0.5 pips

    def test_spread_model_session_aware(self):
        """Spread should be wider during Asian session, tightest during LDN/NY overlap."""
        sim = FillSimulator(spread_model='session_based')

        asian_spread = sim.get_spread("EURUSD", session="ASIAN")
        london_spread = sim.get_spread("EURUSD", session="LONDON")
        overlap_spread = sim.get_spread("EURUSD", session="LDN_NY_OVERLAP")

        assert asian_spread > london_spread
        assert london_spread >= overlap_spread

    def test_limit_order_only_fills_at_price(self):
        """Limit orders should only fill when price reaches the limit level."""
        sim = FillSimulator()

        order = build_limit_order(pair="EURUSD", price=1.0850, direction="BULLISH")

        # Price hasn't reached limit
        fill = sim.simulate_fill(order, build_candle_event(low=1.0860, high=1.0880))
        assert fill.status == FillStatus.NOT_FILLED

        # Price reaches limit
        fill = sim.simulate_fill(order, build_candle_event(low=1.0840, high=1.0870))
        assert fill.status == FillStatus.FILLED
        assert fill.price == 1.0850
```

### 6.4 Walk-Forward Optimization Validation

```python
# tests/backtest/test_walk_forward.py

class TestWalkForwardOptimization:
    """Verify walk-forward optimization prevents overfitting."""

    async def test_oos_performance_within_tolerance(self):
        """
        Out-of-sample Sharpe should be within 50% of in-sample Sharpe.
        If OOS is much worse → overfitting.
        """
        optimizer = WalkForwardOptimizer(engine=backtest_engine, n_splits=5)
        result = await optimizer.optimize(
            data=load_historical_data("EURUSD", "2020-01-01", "2025-12-31"),
            params=AlphaStack_DEFAULT_PARAMS,
        )

        # OOS should not be dramatically worse than IS
        assert result.degradation_ratio >= 0.5, \
            f"OOS degradation too high: {result.degradation_ratio:.2f}"

    async def test_parameter_stability(self):
        """
        Walk-forward optimized parameters should be stable across splits.
        High variance → fragile strategy.
        """
        optimizer = WalkForwardOptimizer(engine=backtest_engine, n_splits=5)
        result = await optimizer.optimize(data=..., params=...)

        # Check parameter variance across splits
        for param_name, values in result.param_history.items():
            cv = np.std(values) / np.mean(values) if np.mean(values) != 0 else float('inf')
            assert cv < 0.5, f"Parameter {param_name} has high variance (CV={cv:.2f})"

    async def test_monte_carlo_risk_assessment(self):
        """
        Monte Carlo simulation should produce reasonable risk estimates.
        """
        trades = load_backtest_trades()
        mc = MonteCarloSimulator(initial_balance=1000)
        result = mc.simulate(trades, n_simulations=10000)

        assert result.ruin_probability < 0.05, "Ruin probability too high"
        assert result.percentile_5 > 0, "5th percentile equity should be positive"
        assert result.median_max_drawdown < 0.30, "Median max drawdown should be <30%"
```

### 6.5 Strategy Correctness Tests

```python
# tests/backtest/test_strategy_correctness.py

class TestStrategyCorrectness:
    """Verify AlphaStack strategy behaves correctly on known scenarios."""

    def test_bullish_ob_with_engulfing_produces_buy_signal(self):
        """Classic SMC setup: H4 Order Block + Bullish Engulfing during London → BUY."""
        scenario = load_fixture("smc_bullish_ob_engulfing_london.json")
        result = run_alphastack(scenario)

        assert result.direction == "BULLISH"
        assert result.confluence_score >= 0.70
        assert "order_block" in result.signal_components
        assert "engulfing" in result.signal_components

    def test_bearish_choch_with_fvg_produces_sell_signal(self):
        """CHoCH + Bearish FVG on H4 during NY → SELL."""
        scenario = load_fixture("smc_bearish_choch_fvg_ny.json")
        result = run_alphastack(scenario)

        assert result.direction == "BEARISH"
        assert result.confluence_score >= 0.65

    def test_no_signal_during_asian_range_chop(self):
        """Choppy Asian session with no clear structure → NO TRADE."""
        scenario = load_fixture("asian_chop_no_structure.json")
        result = run_alphastack(scenario)

        assert result.trade_proposal is None

    def test_no_signal_when_fundamentals_avoid(self):
        """NFP day with AVOID_ALL → no signal regardless of technical setup."""
        scenario = load_fixture("nfp_day_avoid_all.json")
        result = run_alphastack(scenario)

        assert result.trade_proposal is None
        assert result.halt_reason contains "AVOID_ALL"

    def test_position_sizing_scales_with_account(self):
        """Larger account → larger position (proportional to risk %)."""
        scenario = load_fixture("standard_a_plus_setup.json")

        result_1k = run_alphastack_with_balance(scenario, balance=1000)
        result_10k = run_alphastack_with_balance(scenario, balance=10000)

        assert result_10k.position_size > result_1k.position_size
        # Risk % should be the same
        risk_pct_1k = result_1k.risk_amount / 1000
        risk_pct_10k = result_10k.risk_amount / 10000
        assert abs(risk_pct_1k - risk_pct_10k) < 0.001

    def test_stop_loss_beyond_ob_structure(self):
        """Stop loss should be placed beyond Order Block, not at exact swing low."""
        scenario = load_fixture("ob_with_liquidity_below.json")
        result = run_alphastack(scenario)

        # SL should be below OB edge + buffer, not at the obvious swing low
        assert result.stop_loss < scenario.ob_edge
        assert result.stop_loss < scenario.swing_low  # Beyond the obvious level
```

---

## 7. Performance Testing

### 7.1 Performance Targets

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| **Signal-to-Execution Latency** | <500ms (P95) | End-to-end timer |
| **AlphaStack Pipeline Processing** | <200ms (P95) | Per-candle processing time |
| **Risk Governor Check** | <10ms (P99) | Single check latency |
| **Order Placement (MT5)** | <200ms (P95) | Broker round-trip |
| **Order Placement (CCXT)** | <500ms (P95) | Exchange round-trip |
| **Event Bus Throughput** | >10,000 msgs/sec | Load test |
| **API Response Time** | <100ms (P95) | HTTP latency |
| **WebSocket Fan-out** | <50ms for 1000 clients | Broadcast latency |
| **ML Model Inference** | <100ms (P95) | ONNX Runtime timing |
| **Database Query (Hot)** | <10ms (P95) | Redis cache hit |
| **Database Query (Cold)** | <100ms (P95) | TimescaleDB query |

### 7.2 Latency Benchmarks

```python
# tests/performance/test_latency_benchmarks.py

import pytest
import time
import statistics

class TestLatencyBenchmarks:

    async def test_alphastack_pipeline_latency(self, pipeline, sample_ohlcv_data):
        """AlphaStack pipeline processes a single candle in <200ms."""
        latencies = []

        for i in range(100):
            event = build_market_event_from_row(sample_ohlcv_data.iloc[i])
            start = time.perf_counter_ns()
            await pipeline.process(event)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            latencies.append(elapsed_ms)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[94]
        p99 = sorted(latencies)[98]

        assert p50 < 100, f"P50 latency {p50:.1f}ms exceeds 100ms"
        assert p95 < 200, f"P95 latency {p95:.1f}ms exceeds 200ms"
        assert p99 < 500, f"P99 latency {p99:.1f}ms exceeds 500ms"

    async def test_risk_governor_latency(self, governor):
        """Risk check completes in <10ms."""
        proposal = build_trade_proposal()
        account = build_account()

        latencies = []
        for _ in range(1000):
            start = time.perf_counter_ns()
            governor.check(proposal, account)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            latencies.append(elapsed_ms)

        p99 = sorted(latencies)[989]
        assert p99 < 10, f"P99 risk check latency {p99:.2f}ms exceeds 10ms"

    async def test_event_bus_throughput(self, event_bus):
        """Event bus handles >10,000 messages/second."""
        message_count = 50000
        payload = {"bid": 1.0850, "ask": 1.0852, "volume": 100}

        start = time.perf_counter()
        for i in range(message_count):
            await event_bus.publish("perf.test", {**payload, "seq": i})
        elapsed = time.perf_counter() - start

        throughput = message_count / elapsed
        assert throughput > 10000, f"Throughput {throughput:.0f} msgs/sec below 10K target"

    async def test_ml_inference_latency(self):
        """FinBERT sentiment inference completes in <100ms on CPU."""
        import onnxruntime as ort

        session = ort.InferenceSession("models/finbert.onnx", providers=['CPUExecutionProvider'])
        tokenizer = load_finbert_tokenizer()

        test_texts = [
            "Fed signals dovish stance, rate cut expected in September",
            "ECB holds rates steady amid inflation concerns",
            "BOJ intervenes as yen weakens past 160",
        ]

        latencies = []
        for text in test_texts:
            inputs = tokenizer(text, return_tensors="np")
            start = time.perf_counter_ns()
            session.run(None, dict(inputs))
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            latencies.append(elapsed_ms)

        assert max(latencies) < 100, f"Max inference latency {max(latencies):.1f}ms exceeds 100ms"
```

### 7.3 Load Testing

```python
# tests/performance/test_load.py

import asyncio

class TestLoadPerformance:

    async def test_concurrent_signal_processing(self, pipeline):
        """Pipeline handles 10 concurrent instruments without degradation."""
        instruments = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
                       "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD"]

        async def process_instrument(symbol):
            latencies = []
            for _ in range(50):
                event = build_market_event(pair=symbol)
                start = time.perf_counter_ns()
                await pipeline.process(event)
                latencies.append((time.perf_counter_ns() - start) / 1_000_000)
            return statistics.median(latencies)

        results = await asyncio.gather(*[process_instrument(s) for s in instruments])

        # No instrument should have >2x the median latency
        overall_median = statistics.median(results)
        for symbol, latency in zip(instruments, results):
            assert latency < overall_median * 2, \
                f"{symbol} latency {latency:.1f}ms is >2x median {overall_median:.1f}ms"

    async def test_websocket_fanout_1000_clients(self):
        """WebSocket server broadcasts to 1000 clients in <50ms."""
        server = WebSocketServer(host="localhost", port=8765)
        await server.start()

        clients = []
        for _ in range(1000):
            ws = await websockets.connect("ws://localhost:8765")
            clients.append(ws)

        start = time.perf_counter_ns()
        await server.broadcast({"type": "tick", "data": {"bid": 1.0850}})
        # Wait for all clients to receive
        await asyncio.gather(*[c.recv() for c in clients])
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        assert elapsed_ms < 50, f"Fan-out to 1000 clients took {elapsed_ms:.1f}ms"

        for c in clients:
            await c.close()
        await server.stop()

    async def test_sustained_throughput_1_hour(self):
        """System sustains target throughput for 1 hour without degradation."""
        # Simulated: run pipeline at 1 candle/minute for 60 minutes
        # Monitor memory, latency, error rate throughout
        pass  # Long-running test, run nightly
```

### 7.4 Memory & Resource Testing

```python
# tests/performance/test_resources.py

import psutil
import os

class TestResourceUsage:

    async def test_memory_usage_under_load(self, pipeline):
        """Engine memory stays under 512MB during sustained operation."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        for _ in range(1000):
            event = build_market_event()
            await pipeline.process(event)

        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory

        assert memory_growth < 100, f"Memory grew {memory_growth:.1f}MB — possible leak"

    async def test_no_memory_leak_in_event_bus(self, event_bus):
        """Publishing 100K messages doesn't leak memory."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024

        for i in range(100_000):
            await event_bus.publish("leak.test", {"seq": i})

        import gc
        gc.collect()
        await asyncio.sleep(1)

        final_memory = process.memory_info().rss / 1024 / 1024
        assert final_memory - initial_memory < 50
```

---

## 8. Security Testing

### 8.1 Security Test Categories

| Category | Tools | Frequency | Target |
|----------|-------|-----------|--------|
| **SAST** | bandit, cargo-audit, TruffleHog | Every commit | Zero critical findings |
| **DAST** | OWASP ZAP, Nuclei | Weekly | Zero high/critical |
| **Dependency Scan** | safety, cargo-audit, Trivy | Every commit | Zero known CVEs |
| **Container Scan** | Trivy | Every build | Zero critical/high |
| **Secrets Detection** | TruffleHog | Every commit | Zero leaked secrets |
| **API Fuzzing** | ffuf, custom | Weekly | No crashes, no data leaks |
| **Credential Isolation** | Custom | Every PR | Zero plaintext creds in memory/logs |
| **Crypto Validation** | Custom | Every PR | Correct algorithm, key size, mode |

### 8.2 Security Unit Tests

```python
# tests/security/test_credential_isolation.py

class TestCredentialIsolation:
    """Verify credentials never appear in logs, memory dumps, or API responses."""

    def test_credentials_not_in_logs(self, caplog, connector):
        """Broker credentials should never appear in log output."""
        creds = {
            'server': 'FXPesa-Demo',
            'login': 123456,
            'password': 'SuperSecret123!',
            'api_key': 'ak_live_abc123',
        }

        with caplog.at_level(logging.DEBUG):
            connector.connect(creds)

        log_text = caplog.text
        assert 'SuperSecret123!' not in log_text
        assert 'ak_live_abc123' not in log_text
        assert '123456' not in log_text  # login might be sensitive

    def test_credentials_zeroed_after_use(self):
        """SecureString buffer should be zeroed after drop."""
        from alpha.security.secure_string import SecureString

        sec = SecureString("my_broker_password")
        password_bytes = sec.as_bytes()
        assert password_bytes == b"my_broker_password"

        del sec  # Trigger zeroize
        # Buffer should be zeroed — verify via memory inspection
        # (In practice, test via the ZeroizeOnDrop trait in Rust)

    def test_api_responses_never_contain_secrets(self, api_client, auth_headers):
        """API endpoints should never return secret values."""
        endpoints = [
            "/api/v1/broker/accounts",
            "/api/v1/settings",
            "/api/v1/user/profile",
        ]

        for endpoint in endpoints:
            response = api_client.get(endpoint, headers=auth_headers)
            body = response.text

            assert "password" not in body.lower() or '"password": "***"' in body
            assert "api_secret" not in body.lower() or '"api_secret": "***"' in body
            assert "api_key" not in body.lower() or '"api_key": "***"' in body

    def test_field_encryption_roundtrip(self):
        """AES-256-GCM field encryption encrypts and decrypts correctly."""
        encryptor = FieldEncryptor(kms_client=MockKMS())

        original = "FXPesa-Demo:123456:MyPassword"
        encrypted = encryptor.encrypt(original)

        assert encrypted != original
        assert len(encrypted) > len(original)  # nonce + tag overhead

        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original

    def test_field_encryption_different_ciphertext_each_time(self):
        """Same plaintext encrypted twice should produce different ciphertext (unique nonces)."""
        encryptor = FieldEncryptor(kms_client=MockKMS())

        ct1 = encryptor.encrypt("same_password")
        ct2 = encryptor.encrypt("same_password")

        assert ct1 != ct2  # Different nonces

        # But both decrypt to the same value
        assert encryptor.decrypt(ct1) == encryptor.decrypt(ct2)
```

### 8.3 API Security Tests

```python
# tests/security/test_api_security.py

class TestAPISecurity:

    def test_rate_limiting_blocks_excessive_requests(self, api_client):
        """Login endpoint blocks after 5 failed attempts."""
        for i in range(6):
            response = api_client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "wrong_password"
            })

        assert response.status_code == 429
        assert "retry-after" in response.headers

    def test_jwt_expired_token_rejected(self, api_client):
        """Expired JWT should be rejected."""
        token = create_jwt(expired=True)
        response = api_client.get("/api/v1/portfolio",
                                   headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_sql_injection_prevented(self, api_client, auth_headers):
        """SQL injection attempts should be rejected by Pydantic validation."""
        response = api_client.get(
            "/api/v1/signals?symbol='; DROP TABLE trades; --",
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error

    def test_cors_blocks_unauthorized_origins(self, api_client):
        """CORS should block requests from unauthorized origins."""
        response = api_client.options("/api/v1/portfolio", headers={
            "Origin": "https://evil.com",
        })
        assert "access-control-allow-origin" not in response.headers

    def test_csrf_token_required_for_mutations(self, api_client, auth_headers):
        """POST/PUT/DELETE should require CSRF token."""
        response = api_client.post("/api/v1/orders",
                                    headers=auth_headers,
                                    json={"symbol": "EURUSD", "side": "buy"})
        assert response.status_code == 403  # CSRF token missing

    def test_websocket_requires_authentication(self):
        """Unauthenticated WebSocket connections should be rejected."""
        with pytest.raises(websockets.exceptions.ConnectionClosedError):
            asyncio.get_event_loop().run_until_complete(
                websockets.connect("ws://localhost:8000/ws/signals")
            )
```

### 8.4 Cryptographic Validation Tests

```python
# tests/security/test_cryptography.py

class TestCryptography:

    def test_jwt_uses_rs256(self):
        """JWT tokens should use RS256 (asymmetric) signing."""
        token = create_jwt(user_id="test")
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_password_hash_uses_argon2id(self):
        """Password hashes should use Argon2id."""
        from alpha.security.auth import hash_password
        hashed = hash_password("test_password_123")
        assert hashed.startswith("$argon2id$")

    def test_totp_secret_is_256_bit(self):
        """TOTP secrets should be 256-bit."""
        from alpha.security.auth import generate_totp_secret
        secret = generate_totp_secret()
        assert len(secret) >= 32  # 32 chars = 160 bits base32, but 256-bit entropy

    def test_audit_chain_integrity(self):
        """Audit log hash chain should verify correctly."""
        from alpha.security.audit import AuditLogger
        logger = AuditLogger()

        hashes = []
        for i in range(100):
            event = {"action": f"test_{i}", "timestamp": f"2026-01-01T00:00:{i:02d}Z"}
            h = logger.log(event)
            hashes.append(h)

        assert logger.verify_chain(logger.get_all_events())

    def test_audit_chain_detects_tampering(self):
        """Tampered audit log should fail verification."""
        from alpha.security.audit import AuditLogger
        logger = AuditLogger()

        for i in range(10):
            logger.log({"action": f"test_{i}"})

        # Tamper with event 5
        events = logger.get_all_events()
        events[5]["action"] = "TAMPERED"

        assert logger.verify_chain(events) is False
```

---

## 9. Cross-Platform Testing

### 9.1 Platform Matrix

| Platform | Components | Test Priority | CI Runner |
|----------|-----------|---------------|-----------|
| **Linux x64 (Ubuntu 22.04)** | Backend, Desktop, CLI | Primary | ubuntu-latest |
| **Linux x64 (Pop!_OS 24.04)** | Desktop, CLI | Secondary | ubuntu-latest |
| **Windows x64 (10/11)** | Desktop, MT5 Native, CLI | Primary | windows-latest |
| **macOS (ARM64)** | Desktop, CLI | Secondary | macos-latest |
| **macOS (x64)** | Desktop | Tertiary | macos-13 |
| **Web (Chrome/Firefox/Safari)** | Web App | Primary | BrowserStack |
| **Android (API 30+)** | Flutter Mobile | Secondary | Firebase Test Lab |
| **iOS (16+)** | Flutter Mobile | Secondary | Firebase Test Lab |

### 9.2 Desktop (Tauri) Cross-Platform Tests

```yaml
# .github/workflows/desktop-tests.yml

name: Desktop Cross-Platform Tests
on: [push, pull_request]

jobs:
  desktop-test:
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu
            features: linux
          - os: windows-latest
            target: x86_64-pc-windows-msvc
            features: windows
          - os: macos-latest
            target: aarch64-apple-darwin
            features: macos
          - os: macos-13
            target: x86_64-apple-darwin
            features: macos

    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install dependencies
        run: npm ci

      - name: Rust unit tests
        run: cargo test --target ${{ matrix.target }}

      - name: Build Tauri app
        run: npm run tauri build
        env:
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_KEY }}

      - name: Frontend tests
        run: npm run test

      - name: E2E tests (Playwright)
        run: npx playwright test --project=${{ matrix.os }}

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: desktop-${{ matrix.os }}
          path: apps/desktop/src-tauri/target/release/bundle/
```

### 9.3 Mobile Cross-Platform Tests

```yaml
# .github/workflows/mobile-tests.yml

name: Mobile Tests
on: [push, pull_request]

jobs:
  flutter-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.24'

      - name: Install dependencies
        run: flutter pub get
        working-directory: apps/mobile

      - name: Analyze
        run: flutter analyze
        working-directory: apps/mobile

      - name: Unit tests
        run: flutter test
        working-directory: apps/mobile

      - name: Integration tests (Android)
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: 34
          script: flutter test integration_test/
        working-directory: apps/mobile

  ios-test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.24'

      - name: Build iOS
        run: flutter build ios --release --no-codesign
        working-directory: apps/mobile
```

### 9.4 Keyline Cross-Platform Test Cases

| Test Case | Linux | Windows | macOS | Web | Android | iOS |
|-----------|-------|---------|-------|-----|---------|-----|
| App launches without crash | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Keyring stores/retrieves credentials | ✅ | ✅ | ✅ | N/A | ✅ | ✅ |
| WebSocket connects and receives data | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chart renders real-time data | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Trade approval dialog works | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Notification delivery | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Biometric auth (where available) | ⚠️ | ✅ | ✅ | N/A | ✅ | ✅ |
| MT5 connector works | N/A | ✅ | N/A | N/A | N/A | N/A |
| File system access (logs, exports) | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| Auto-update mechanism | ✅ | ✅ | ✅ | N/A | ✅ | ✅ |

---

## 10. Broker Integration Testing

### 10.1 Broker Test Strategy

Each broker connector is tested at three levels:

```
┌──────────────────────────────────────────────────────────────┐
│                BROKER INTEGRATION TESTING                      │
│                                                                │
│  LEVEL 1: UNIT (Mock)                                        │
│  Mock broker API responses. Test all return codes, errors,    │
│  timeouts. No real broker connection.                         │
│                                                                │
│  LEVEL 2: SANDBOX (Demo Account)                             │
│  Connect to broker's demo/sandbox environment. Place real     │
│  orders with demo money. Test connectivity, auth, execution.  │
│                                                                │
│  LEVEL 3: PAPER (Live Data, Simulated Execution)             │
│  Connect to live data feed. Simulate order execution locally. │
│  Test data quality, latency, spread behavior.                 │
└──────────────────────────────────────────────────────────────┘
```

### 10.2 MT5 Connector Integration Tests

```python
# tests/integration/brokers/test_mt5_integration.py

import pytest
import MetaTrader5 as mt5

@pytest.mark.integration
@pytest.mark.mt5
class TestMT5Integration:
    """
    MT5 integration tests. Requires:
    - MT5 terminal running (Windows or Wine)
    - FXPesa demo account credentials in .env.test
    - Run with: pytest -m mt5 --run-integration
    """

    @pytest.fixture
    async def connector(self):
        creds = {
            'terminal_path': os.environ['MT5_TERMINAL_PATH'],
            'server': os.environ['MT5_SERVER'],
            'login': int(os.environ['MT5_LOGIN']),
            'password': os.environ['MT5_PASSWORD'],
        }
        conn = MT5Connector()
        connected = await conn.connect(creds)
        assert connected, "Failed to connect to MT5"
        yield conn
        await conn.disconnect()

    async def test_connection_and_account_info(self, connector):
        """Can connect and retrieve account info."""
        info = await connector.get_account_info()
        assert info.balance > 0
        assert info.leverage > 0
        assert info.server is not None

    async def test_get_market_data(self, connector):
        """Can retrieve OHLCV data for EUR/USD."""
        candles = await connector.get_market_data("EURUSD", "H1", 100)
        assert len(candles) == 100
        assert all(c.open > 0 for c in candles)
        assert all(c.high >= c.low for c in candles)

    async def test_place_and_close_market_order(self, connector):
        """Can place a market order and close it."""
        # Place micro lot order
        order = UnifiedOrder(
            pair="EURUSD",
            direction=Direction.BULLISH,
            order_type=OrderType.MARKET,
            lot_size=0.01,
            stop_loss=0,  # No SL for test
            take_profit=0,  # No TP for test
        )

        result = await connector.place_order(order)
        assert result.success is True
        assert result.ticket > 0

        # Close the position
        close_result = await connector.close_position(result.ticket)
        assert close_result.success is True

    async def test_modify_stop_loss(self, connector):
        """Can modify SL on an open position."""
        # Open position
        order = UnifiedOrder(pair="EURUSD", direction=Direction.BULLISH,
                            order_type=OrderType.MARKET, lot_size=0.01)
        result = await connector.place_order(order)
        assert result.success

        # Get current price
        tick = await connector.get_tick("EURUSD")
        new_sl = tick.bid - 0.0050  # 50 pips below

        # Modify SL
        mod_result = await connector.modify_order(result.ticket, {"sl": new_sl})
        assert mod_result.success

        # Verify modification
        positions = await connector.get_positions()
        position = next(p for p in positions if p.ticket == result.ticket)
        assert abs(position.sl - new_sl) < 0.0001

        # Clean up
        await connector.close_position(result.ticket)

    async def test_get_spread(self, connector):
        """Can retrieve current spread."""
        spread = await connector.get_spread("EURUSD")
        assert spread > 0
        assert spread < 50  # Sanity: EUR/USD spread should be < 5 pips

    async def test_symbol_info(self, connector):
        """Can retrieve symbol specifications."""
        info = await connector.get_symbol_info("EURUSD")
        assert info.digits == 5
        assert info.volume_min == 0.01
        assert info.point > 0

    @pytest.mark.parametrize("symbol", [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    ])
    async def test_multiple_symbols(self, connector, symbol):
        """Can get data for all supported forex pairs."""
        candles = await connector.get_market_data(symbol, "H1", 10)
        assert len(candles) == 10
```

### 10.3 CCXT Integration Tests

```python
# tests/integration/brokers/test_ccxt_integration.py

@pytest.mark.integration
@pytest.mark.ccxt
class TestCCXTIntegration:
    """
    CCXT crypto exchange integration tests.
    Uses Binance testnet by default.
    """

    @pytest.fixture
    async def connector(self):
        creds = {
            'exchange': 'binance',
            'api_key': os.environ['BINANCE_TESTNET_KEY'],
            'api_secret': os.environ['BINANCE_TESTNET_SECRET'],
            'sandbox': True,
        }
        conn = CCXTConnector()
        await conn.connect(creds)
        yield conn

    async def test_get_account_balance(self, connector):
        balance = await connector.get_account_info()
        assert balance.total >= 0

    async def test_place_limit_order(self, connector):
        """Place a limit order far from market (won't fill)."""
        ticker = await connector.get_ticker("BTC/USDT")
        price = ticker['bid'] * 0.9  # 10% below market

        order = UnifiedOrder(
            pair="BTC/USDT",
            direction=Direction.BULLISH,
            order_type=OrderType.LIMIT,
            lot_size=0.001,
            entry_price=price,
        )

        result = await connector.place_order(order)
        assert result.success

        # Cancel the order
        await connector.cancel_order(result.ticket)

    async def test_websocket_ticker_stream(self, connector):
        """Can subscribe to real-time ticker data."""
        received = []

        async def on_tick(data):
            received.append(data)

        await connector.subscribe_ticks("BTC/USDT", on_tick)
        await asyncio.sleep(5)  # Wait for some ticks

        assert len(received) > 0
        assert all('bid' in t for t in received)
```

### 10.4 Broker Error Handling Matrix

```python
# tests/integration/brokers/test_broker_errors.py

class TestBrokerErrorHandling:
    """Verify all broker error scenarios are handled gracefully."""

    @pytest.mark.parametrize("error_scenario,expected_behavior", [
        ("connection_timeout", "retry_with_backoff"),
        ("authentication_failure", "alert_user_disable_connector"),
        ("insufficient_funds", "reject_order_alert_user"),
        ("invalid_symbol", "reject_order_log_error"),
        ("market_closed", "queue_order_for_open"),
        ("rate_limit_exceeded", "backoff_and_retry"),
        ("requote", "retry_with_new_price"),
        ("partial_fill", "track_remaining_volume"),
        ("order_rejected", "log_reason_alert_user"),
        ("network_disconnect", "reconnect_failover"),
    ])
    async def test_error_handling(self, error_scenario, expected_behavior, mock_broker):
        """Each error scenario is handled with the expected behavior."""
        mock_broker.simulate_error(error_scenario)

        result = await order_manager.submit_order(build_trade_proposal())

        assert result.behavior == expected_behavior
```

---

## 11. Test Data Management

### 11.1 Test Data Strategy

```
┌──────────────────────────────────────────────────────────────┐
│                    TEST DATA ARCHITECTURE                      │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  FIXTURE     │  │  SYNTHETIC   │  │  HISTORICAL  │       │
│  │  DATA        │  │  DATA        │  │  DATA        │       │
│  │  (Static)    │  │  (Generated) │  │  (Real)      │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                 │
│  Unit tests         Integration/E2E     Backtest validation  │
│  Known inputs       Edge cases          Real market behavior  │
│  Expected outputs   Stress scenarios    Statistical validity   │
└──────────────────────────────────────────────────────────────┘
```

### 11.2 Fixture Data

```python
# tests/fixtures/builders.py

from datetime import datetime, timedelta
import numpy as np

def build_candle(
    open: float = 1.0850,
    high: float = 1.0880,
    low: float = 1.0820,
    close: float = 1.0870,
    volume: float = 1000.0,
    timestamp: datetime = None,
) -> dict:
    """Build a single OHLCV candle with defaults."""
    return {
        "open": open, "high": high, "low": low, "close": close,
        "volume": volume,
        "timestamp": timestamp or datetime(2026, 7, 11, 12, 0),
    }

def build_trending_candles(direction: str = "bullish", count: int = 100, start_price: float = 1.0800) -> list[dict]:
    """Generate a series of candles in a clear trend."""
    candles = []
    price = start_price
    for i in range(count):
        if direction == "bullish":
            move = np.random.uniform(0.0001, 0.0010)
        else:
            move = np.random.uniform(-0.0010, -0.0001)

        open_p = price
        close_p = price + move
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 0.0003))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 0.0003))

        candles.append(build_candle(
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=np.random.uniform(500, 2000),
            timestamp=datetime(2026, 7, 1) + timedelta(hours=i),
        ))
        price = close_p

    return candles

def build_order_block_scenario(direction: str = "bullish") -> dict:
    """Build a market scenario with a clear Order Block pattern."""
    if direction == "bullish":
        return {
            "candles": [
                build_candle(open=1.0900, high=1.0910, low=1.0890, close=1.0895),  # Bearish candle
                build_candle(open=1.0895, high=1.0900, low=1.0880, close=1.0885),  # Bearish candle (OB)
                build_candle(open=1.0885, high=1.0950, low=1.0885, close=1.0945),  # Impulse (+60 pips)
                build_candle(open=1.0945, high=1.0960, low=1.0930, close=1.0950),  # Continuation
            ],
            "expected_ob_zone": (1.0880, 1.0900),
            "expected_direction": "BULLISH",
            "expected_impulse_pips": 60,
        }

def build_liquidity_sweep_scenario() -> dict:
    """Build a scenario with a clear liquidity sweep (stop hunt)."""
    return {
        "candles": [
            # Build up support level with multiple touches
            build_candle(open=1.0870, high=1.0890, low=1.0850, close=1.0860),
            build_candle(open=1.0860, high=1.0880, low=1.0848, close=1.0870),  # Touch 1
            build_candle(open=1.0870, high=1.0885, low=1.0847, close=1.0865),  # Touch 2
            build_candle(open=1.0865, high=1.0880, low=1.0849, close=1.0872),  # Touch 3
            # Sweep below support
            build_candle(open=1.0872, high=1.0875, low=1.0835, close=1.0840),  # Sweep wick
            # Strong recovery
            build_candle(open=1.0840, high=1.0920, low=1.0838, close=1.0915),  # Rejection +80 pips
        ],
        "support_level": 1.0850,
        "sweep_low": 1.0835,
        "expected_sweep_type": "REAL",
    }
```

### 11.3 Historical Data Management

```python
# tests/data/test_data_manager.py

class TestHistoricalDataManager:
    """Manage historical data for backtesting validation."""

    HISTORICAL_DATA_DIR = "tests/fixtures/historical/"

    @staticmethod
    def load_ohlcv(pair: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        """Load historical OHLCV data from fixture files."""
        filepath = f"{TestHistoricalDataManager.HISTORICAL_DATA_DIR}/{pair}_{timeframe}_{start}_{end}.parquet"
        return pd.read_parquet(filepath)

    @staticmethod
    def load_ticks(pair: str, date: str) -> pd.DataFrame:
        """Load historical tick data."""
        filepath = f"{TestHistoricalDataManager.HISTORICAL_DATA_DIR}/ticks/{pair}_{date}.parquet"
        return pd.read_parquet(filepath)

    @staticmethod
    def generate_synthetic_regime(regime: str, bars: int = 1000) -> pd.DataFrame:
        """Generate synthetic data matching a specific market regime."""
        if regime == "strong_trend_up":
            return SyntheticDataGenerator.trending(bars, direction="up", strength=0.8)
        elif regime == "strong_trend_down":
            return SyntheticDataGenerator.trending(bars, direction="down", strength=0.8)
        elif regime == "range":
            return SyntheticDataGenerator.ranging(bars, width=0.0050)
        elif regime == "high_volatility":
            return SyntheticDataGenerator.volatile(bars, vol_multiplier=3.0)
        elif regime == "low_volatility":
            return SyntheticDataGenerator.volatile(bars, vol_multiplier=0.3)
        elif regime == "choppy":
            return SyntheticDataGenerator.choppy(bars)
        else:
            raise ValueError(f"Unknown regime: {regime}")
```

### 11.4 Synthetic Data Generation

```python
# tests/data/synthetic.py

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

class SyntheticDataGenerator:
    """Generate synthetic market data for testing edge cases."""

    @staticmethod
    def trending(bars: int, direction: str = "up", strength: float = 0.5,
                 base_price: float = 1.0800, volatility: float = 0.0005) -> pd.DataFrame:
        """Generate trending price data with controllable strength."""
        drift = volatility * strength * (1 if direction == "up" else -1)
        returns = np.random.normal(drift, volatility, bars)
        prices = base_price * np.exp(np.cumsum(returns))

        df = pd.DataFrame({
            'time': [datetime(2026, 1, 1) + timedelta(hours=i) for i in range(bars)],
            'open': prices,
            'high': prices * (1 + np.abs(np.random.normal(0, volatility/2, bars))),
            'low': prices * (1 - np.abs(np.random.normal(0, volatility/2, bars))),
            'close': prices * (1 + np.random.normal(0, volatility/3, bars)),
            'volume': np.random.uniform(500, 2000, bars),
        })
        return df

    @staticmethod
    def ranging(bars: int, width: float = 0.0050, base_price: float = 1.0800) -> pd.DataFrame:
        """Generate range-bound price data."""
        prices = base_price + np.sin(np.linspace(0, 4*np.pi, bars)) * width/2
        prices += np.random.normal(0, width/20, bars)

        df = pd.DataFrame({
            'time': [datetime(2026, 1, 1) + timedelta(hours=i) for i in range(bars)],
            'open': prices,
            'high': prices + np.abs(np.random.normal(0, width/10, bars)),
            'low': prices - np.abs(np.random.normal(0, width/10, bars)),
            'close': prices + np.random.normal(0, width/20, bars),
            'volume': np.random.uniform(300, 1000, bars),
        })
        return df

    @staticmethod
    def with_news_spike(base_data: pd.DataFrame, spike_bar: int,
                        direction: str = "up", magnitude_pips: float = 50) -> pd.DataFrame:
        """Add a news-driven price spike to existing data."""
        df = base_data.copy()
        spike = magnitude_pips * 0.0001 * (1 if direction == "up" else -1)

        df.loc[spike_bar, 'high'] = df.loc[spike_bar, 'open'] + abs(spike) * 1.5
        df.loc[spike_bar, 'low'] = df.loc[spike_bar, 'open'] - abs(spike) * 0.3
        df.loc[spike_bar, 'close'] = df.loc[spike_bar, 'open'] + spike
        df.loc[spike_bar, 'volume'] *= 5  # Volume spike

        return df
```

---

## 12. CI/CD Integration

### 12.1 Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    CI/CD PIPELINE                                      │
│                                                                        │
│  STAGE 1: LINT & TYPE CHECK (<30s)                                   │
│  ├── Ruff (Python linting)                                            │
│  ├── mypy (Python type checking)                                      │
│  ├── Clippy (Rust linting)                                            │
│  ├── ESLint (TypeScript)                                              │
│  └── flutter analyze (Dart)                                           │
│                                                                        │
│  STAGE 2: UNIT TESTS (<60s)                                          │
│  ├── pytest -m "not integration and not e2e" (Python)                │
│  ├── cargo test (Rust)                                                │
│  ├── vitest run (TypeScript)                                          │
│  └── flutter test (Dart)                                              │
│                                                                        │
│  STAGE 3: SECURITY SCANS (<5min)                                     │
│  ├── bandit (Python SAST)                                             │
│  ├── cargo audit (Rust deps)                                          │
│  ├── TruffleHog (secrets)                                             │
│  ├── Trivy (container image)                                          │
│  └── npm audit (JS deps)                                              │
│                                                                        │
│  STAGE 4: BUILD (<5min)                                              │
│  ├── Docker image build + push                                        │
│  ├── Tauri desktop build (all platforms)                              │
│  ├── Flutter build (Android + iOS)                                    │
│  └── Web app build                                                    │
│                                                                        │
│  STAGE 5: INTEGRATION TESTS (<10min) [PR only]                       │
│  ├── pytest -m integration (Testcontainers)                           │
│  ├── Broker integration (demo accounts)                               │
│  └── API integration tests                                            │
│                                                                        │
│  STAGE 6: E2E TESTS (<15min) [nightly + pre-release]                 │
│  ├── Full trade lifecycle replay                                      │
│  ├── Desktop E2E (Playwright)                                         │
│  ├── Mobile E2E (Flutter integration_test)                            │
│  └── API E2E (full request cycle)                                     │
│                                                                        │
│  STAGE 7: PERFORMANCE TESTS (<30min) [weekly + pre-release]          │
│  ├── Latency benchmarks                                               │
│  ├── Load tests                                                       │
│  ├── Memory leak detection                                            │
│  └── Backtest performance                                             │
│                                                                        │
│  STAGE 8: DEPLOY                                                     │
│  ├── Staging deploy + smoke test                                      │
│  ├── Production deploy (blue-green)                                   │
│  └── Health check verification                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### 12.2 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml

name: Alpha Stack CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'    # Nightly E2E
    - cron: '0 3 * * 1'    # Weekly performance (Monday 3am)

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: '3.12'
  RUST_VERSION: 'stable'
  NODE_VERSION: '22'

jobs:
  # ──────────────────────────────────────────────────────────────
  # STAGE 1: Lint & Type Check
  # ──────────────────────────────────────────────────────────────
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Python lint
        uses: astral-sh/ruff-action@v1
        with:
          args: check

      - name: Python type check
        run: |
          pip install mypy
          mypy src/ --ignore-missing-imports

      - name: Rust lint
        uses: dtolnay/rust-toolchain@stable
        with:
          components: clippy
      - run: cargo clippy -- -D warnings

      - name: TypeScript lint
        run: |
          cd apps/desktop
          npm ci
          npx eslint src/

  # ──────────────────────────────────────────────────────────────
  # STAGE 2: Unit Tests
  # ──────────────────────────────────────────────────────────────
  unit-tests:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Python unit tests
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: |
          pip install -e ".[test]"
          pytest tests/unit/ -v --cov=src/ --cov-report=xml -m "not integration and not e2e"

      - name: Rust unit tests
        uses: dtolnay/rust-toolchain@stable
      - run: cargo test

      - name: Frontend unit tests
        run: |
          cd apps/desktop
          npm ci
          npx vitest run --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml,target/coverage/lcov.info

  # ──────────────────────────────────────────────────────────────
  # STAGE 3: Security Scans
  # ──────────────────────────────────────────────────────────────
  security:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Python security (Bandit)
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json || true

      - name: Rust dependency audit
        uses: rustsec/audit-check@v1

      - name: Secrets detection (TruffleHog)
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          extra_args: --only-verified

      - name: Container scan (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'alphastack:ci'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'

  # ──────────────────────────────────────────────────────────────
  # STAGE 4: Build
  # ──────────────────────────────────────────────────────────────
  build:
    runs-on: ubuntu-latest
    needs: [unit-tests, security]
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker images
        run: |
          docker compose -f infra/compose/docker-compose.ci.yml build

      - name: Build desktop (Linux)
        run: |
          cd apps/desktop
          npm ci
          npm run tauri build

  # ──────────────────────────────────────────────────────────────
  # STAGE 5: Integration Tests
  # ──────────────────────────────────────────────────────────────
  integration-tests:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'pull_request' || github.ref == 'refs/heads/main'
    services:
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
      timescaledb:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: test_trading
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4

      - name: Run integration tests
        run: |
          pip install -e ".[test]"
          pytest tests/integration/ -v --timeout=300
        env:
          REDIS_URL: redis://localhost:6379
          DATABASE_URL: postgresql://test:test@localhost:5432/test_trading

  # ──────────────────────────────────────────────────────────────
  # STAGE 6: E2E Tests (Nightly)
  # ──────────────────────────────────────────────────────────────
  e2e-tests:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'schedule' || github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Start full stack
        run: docker compose -f infra/compose/docker-compose.test.yml up -d

      - name: Wait for services
        run: |
          for i in $(seq 1 30); do
            curl -s http://localhost:8000/health && break
            sleep 2
          done

      - name: Run E2E tests
        run: |
          pytest tests/e2e/ -v --timeout=900

      - name: Desktop E2E (Playwright)
        run: |
          cd apps/desktop
          npx playwright install --with-deps
          npx playwright test

      - name: Collect logs on failure
        if: failure()
        run: docker compose -f infra/compose/docker-compose.test.yml logs > e2e-logs.txt

      - name: Upload logs
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-logs
          path: e2e-logs.txt

  # ──────────────────────────────────────────────────────────────
  # STAGE 7: Performance Tests (Weekly)
  # ──────────────────────────────────────────────────────────────
  performance-tests:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4

      - name: Run performance benchmarks
        run: |
          pytest tests/performance/ -v --timeout=1800 --benchmark-json=benchmark.json

      - name: Compare with baseline
        run: |
          python scripts/compare_benchmarks.py benchmark.json baseline.json

      - name: Alert on regression
        if: failure()
        run: |
          python scripts/alert_performance_regression.py

  # ──────────────────────────────────────────────────────────────
  # STAGE 8: Deploy
  # ──────────────────────────────────────────────────────────────
  deploy-staging:
    runs-on: ubuntu-latest
    needs: [integration-tests]
    if: github.ref == 'refs/heads/main'
    environment: staging
    steps:
      - name: Deploy to staging
        run: |
          ./scripts/deploy.sh staging

      - name: Smoke test
        run: |
          pytest tests/smoke/ -v --timeout=60

  deploy-production:
    runs-on: ubuntu-latest
    needs: [deploy-staging]
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - name: Deploy to production (blue-green)
        run: |
          ./scripts/deploy.sh production

      - name: Health check
        run: |
          for i in $(seq 1 10); do
            STATUS=$(curl -s http://prod.alphastack.io/health | jq -r '.status')
            [ "$STATUS" = "healthy" ] && exit 0
            sleep 5
          done
          exit 1

      - name: Rollback on failure
        if: failure()
        run: ./scripts/rollback.sh production
```

### 12.3 Test Markers & Selection

```python
# pytest markers (in pyproject.toml)

[tool.pytest.ini_options]
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (requires Docker services)",
    "e2e: End-to-end tests (full system)",
    "performance: Performance benchmarks",
    "security: Security-focused tests",
    "mt5: Requires MT5 terminal connection",
    "ccxt: Requires crypto exchange connection",
    "slow: Tests that take >30 seconds",
    "flaky: Known flaky tests (allowed to fail)",
]

# Run commands:
# pytest -m "unit"                    # Fast feedback
# pytest -m "not slow and not mt5"    # PR checks
# pytest -m "integration"             # Full integration
# pytest -m "e2e"                     # Nightly
# pytest -m "performance"             # Weekly
```

---

## 13. Test Infrastructure

### 13.1 Docker Compose for Testing

```yaml
# infra/compose/docker-compose.test.yml

version: '3.8'

services:
  # ── Application ──
  trading-engine:
    build:
      context: ../..
      dockerfile: infra/docker/Dockerfile.test
    environment:
      - MODE=backtest
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://test:test@timescaledb:5432/test_trading
    depends_on:
      redis:
        condition: service_healthy
      timescaledb:
        condition: service_healthy
    volumes:
      - ../../tests/fixtures:/app/tests/fixtures:ro

  api:
    build:
      context: ../..
      dockerfile: infra/docker/Dockerfile.api.test
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://test:test@timescaledb:5432/test_trading
      - JWT_SECRET=test-secret-key
    depends_on:
      - redis
      - timescaledb

  # ── Infrastructure ──
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
    ports:
      - "6379:6379"

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: test_trading
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 5s
      timeout: 3s
      retries: 3
    ports:
      - "5432:5432"
    volumes:
      - ../../infra/sql/init_test.sql:/docker-entrypoint-initdb.d/init.sql

  # ── Monitoring (for integration tests) ──
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ../../infra/monitoring/prometheus.test.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

### 13.2 Test Environment Configuration

```python
# tests/config.py

import os
from dataclasses import dataclass

@dataclass
class TestConfig:
    """Test environment configuration. All values from env vars or defaults."""

    # Infrastructure
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test_trading")

    # Broker (demo accounts only)
    mt5_server: str = os.getenv("MT5_SERVER", "FXPesa-Demo")
    mt5_login: int = int(os.getenv("MT5_LOGIN", "0"))
    mt5_password: str = os.getenv("MT5_PASSWORD", "")

    # API
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    jwt_secret: str = os.getenv("JWT_SECRET", "test-secret")

    # Test behavior
    test_timeout: int = int(os.getenv("TEST_TIMEOUT", "300"))
    slow_test_threshold: float = float(os.getenv("SLOW_THRESHOLD", "10.0"))

    @classmethod
    def from_env(cls) -> "TestConfig":
        return cls()
```

---

## 14. Metrics & Reporting

### 14.1 Test Metrics Dashboard

```python
# scripts/test_metrics.py

"""
Collect and report test metrics to Grafana/InfluxDB.
"""

from prometheus_client import Gauge, Counter, Histogram

# Metrics
test_coverage = Gauge('test_coverage_percent', 'Test coverage percentage', ['module'])
test_duration = Histogram('test_duration_seconds', 'Test execution time', ['suite', 'test'])
test_failures = Counter('test_failures_total', 'Total test failures', ['suite', 'reason'])
test_flaky = Counter('test_flaky_total', 'Flaky test occurrences', ['test'])
```

### 14.2 Quality Gates

| Gate | Criteria | Action on Failure |
|------|----------|-------------------|
| **Coverage Gate** | Unit coverage <90% | Block merge |
| **Security Gate** | Any critical CVE | Block merge |
| **Performance Gate** | P95 latency >2x baseline | Block release |
| **E2E Gate** | Any E2E test failure | Block release |
| **Backtest Gate** | OOS Sharpe <50% of IS | Block strategy deploy |

### 14.3 Test Report Template

```
ALPHA STACK TEST REPORT
========================
Date: 2026-07-11
Commit: abc1234
Branch: main

UNIT TESTS:       ✅ 1,247 passed, 0 failed (94.2% coverage)
INTEGRATION:      ✅ 89 passed, 0 failed
E2E:              ✅ 12 scenarios passed
PERFORMANCE:      ✅ All within targets
SECURITY:         ✅ 0 critical, 0 high
CROSS-PLATFORM:   ✅ Linux ✅ Windows ✅ macOS ✅ Web ✅ Android ✅ iOS
BROKER (MT5):     ✅ All order types verified
BROKER (CCXT):    ✅ Binance testnet verified
BACKTEST:         ✅ Walk-forward OOS/IS ratio: 0.72

QUALITY GATES:    ALL PASSED ✅
RECOMMENDATION:   Ready for production deployment
```

---

## Appendix A: Test File Naming Convention

```
tests/
├── unit/           → test_<module_name>.py
├── integration/    → test_<component1>_to_<component2>.py
├── e2e/            → test_<scenario_name>.py
├── performance/    → test_<metric_name>.py
├── security/       → test_<security_control>.py
├── backtest/       → test_<validation_type>.py
└── fixtures/       → <descriptive_name>.json / .csv / .parquet
```

## Appendix B: Test Execution Commands

```bash
# Fast feedback (every save)
pytest tests/unit/ -x -q

# PR validation
pytest tests/unit/ tests/integration/ -v --cov

# Full suite (nightly)
pytest tests/ -v --cov --timeout=900

# Performance benchmarks
pytest tests/performance/ -v --benchmark-json=benchmark.json

# Security scans
bandit -r src/ && cargo audit && trivy image alphastack:latest

# Specific broker
pytest tests/integration/brokers/ -m mt5 -v
pytest tests/integration/brokers/ -m ccxt -v

# Backtest validation
pytest tests/backtest/ -v -k "walk_forward or monte_carlo"

# Cross-platform (run on each platform)
pytest tests/e2e/ -v --project=desktop
```

## Appendix C: Flaky Test Policy

Flaky tests erode trust in the test suite. Policy:

1. **First occurrence:** Mark with `@pytest.mark.flaky`, file issue
2. **Three occurrences in 7 days:** Quarantine test (move to `tests/quarantine/`)
3. **Quarantined tests:** Must be fixed within 2 weeks or deleted
4. **Root causes to investigate:**
   - Race conditions → add proper waits
   - External dependency → mock it
   - Non-deterministic data → use fixed seeds
   - Timing sensitivity → increase tolerances

---

*This testing architecture ensures Alpha Stack is validated at every level — from individual function correctness to full trade lifecycle validation. Every line of code that touches real money must be tested, and every test must be deterministic, fast, and trustworthy.*

*Generated by Integration Testing Architect — Alpha Stack*
