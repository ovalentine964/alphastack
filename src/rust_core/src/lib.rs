//! AlphaStack Rust Core — high-performance computation layer.
//!
//! Exposes tick processing, technical indicators, signal computation,
//! order-book analysis, risk calculations, and backtesting to Python
//! via PyO3 bindings.

use pyo3::prelude::*;

mod tick_processor;
mod indicators;
mod signal_compute;
mod order_book;
mod risk_calculator;
mod backtest_engine;

/// Top-level Python module `alphastack_rust_core`.
#[pymodule]
fn alphastack_rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Tick Processing
    m.add_class::<tick_processor::PyTick>()?;
    m.add_class::<tick_processor::PyCandle>()?;
    m.add_class::<tick_processor::PyTickProcessor>()?;

    // Technical Indicators
    m.add_class::<indicators::PyIndicators>()?;

    // Signal Computation
    m.add_class::<signal_compute::PySignalEngine>()?;

    // Order Book
    m.add_class::<order_book::PyOrderBook>()?;
    m.add_class::<order_book::PyOrderBookAnalyzer>()?;

    // Risk Calculator
    m.add_class::<risk_calculator::PyRiskCalculator>()?;

    // Backtesting
    m.add_class::<backtest_engine::PyBacktestEngine>()?;
    m.add_class::<backtest_engine::PyBacktestResult>()?;

    Ok(())
}
