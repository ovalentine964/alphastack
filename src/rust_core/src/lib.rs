//! AlphaStack Rust Core — high-performance computation layer.
//!
//! Exposes tick processing, technical indicators, signal computation,
//! order-book analysis, risk calculations, and backtesting to Python
//! via PyO3 bindings.
//!
//! Aligned with the AlphaStack 16-step strategy pipeline architecture.

use pyo3::prelude::*;

mod backtest_engine;
mod indicators;
mod order_book;
mod risk_calculator;
mod signal_compute;
mod tick_processor;

/// Top-level Python module `alphastack_rust_core`.
#[pymodule]
fn alphastack_rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ── Tick Processing ───────────────────────────────────────────────
    m.add_class::<tick_processor::PyTick>()?;
    m.add_class::<tick_processor::PyCandle>()?;
    m.add_class::<tick_processor::PyTickProcessor>()?;
    m.add_class::<tick_processor::DataQualityReport>()?;

    // ── Technical Indicators ──────────────────────────────────────────
    m.add_class::<indicators::PyIndicators>()?;
    m.add_class::<indicators::MacdResult>()?;
    m.add_class::<indicators::BollingerResult>()?;
    m.add_class::<indicators::AdxResult>()?;
    m.add_class::<indicators::StochasticResult>()?;
    m.add_class::<indicators::IndicatorSuite>()?;

    // ── Signal Computation ────────────────────────────────────────────
    m.add_class::<signal_compute::PySignalEngine>()?;
    m.add_class::<signal_compute::PySmcDetector>()?;
    m.add_class::<signal_compute::StructurePoint>()?;
    m.add_class::<signal_compute::Level>()?;
    m.add_class::<signal_compute::OrderBlock>()?;
    m.add_class::<signal_compute::FairValueGap>()?;
    m.add_class::<signal_compute::LiquiditySweep>()?;
    m.add_class::<signal_compute::SmcAnalysis>()?;
    m.add_class::<signal_compute::ConfluenceResult>()?;
    m.add_class::<signal_compute::GeneratedSignal>()?;

    // ── Order Book ────────────────────────────────────────────────────
    m.add_class::<order_book::PyOrderBook>()?;
    m.add_class::<order_book::PyOrderBookAnalyzer>()?;

    // ── Risk Calculator & Governor ────────────────────────────────────
    m.add_class::<risk_calculator::PyRiskCalculator>()?;
    m.add_class::<risk_calculator::PyRiskGovernor>()?;
    m.add_class::<risk_calculator::PyCircuitBreaker>()?;
    m.add_class::<risk_calculator::PyDrawdownManager>()?;
    m.add_class::<risk_calculator::PyPositionSizer>()?;
    m.add_class::<risk_calculator::PyTradeRequest>()?;
    m.add_class::<risk_calculator::PyTradeApproval>()?;
    m.add_class::<risk_calculator::RiskEvent>()?;

    // ── Backtesting ───────────────────────────────────────────────────
    m.add_class::<backtest_engine::PyBacktestEngine>()?;
    m.add_class::<backtest_engine::PyBacktestResult>()?;
    m.add_class::<backtest_engine::TradeRecord>()?;

    Ok(())
}
