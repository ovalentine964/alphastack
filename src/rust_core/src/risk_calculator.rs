//! Risk Calculations — position sizing, drawdown, correlation matrix,
//! CVaR, and portfolio risk metrics. All in Rust for instant computation.

use pyo3::prelude::*;
use pyo3::types::PyList;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Risk Calculator
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyRiskCalculator;

#[pymethods]
impl PyRiskCalculator {
    #[new]
    fn new() -> Self { Self }

    // -- Position Sizing (Kelly / Fixed Fractional) -------------------------
    /// Kelly criterion optimal fraction.
    /// `win_rate` in (0,1), `win_loss_ratio` = avg_win / avg_loss.
    fn kelly_fraction(win_rate: f64, win_loss_ratio: f64) -> f64 {
        if win_loss_ratio == 0.0 { return 0.0; }
        let k = win_rate - (1.0 - win_rate) / win_loss_ratio;
        k.clamp(0.0, 1.0)
    }

    /// Fixed fractional position size.
    /// `risk_pct` = fraction of capital risked per trade (e.g. 0.02 = 2%).
    fn position_size(capital: f64, risk_pct: f64, entry: f64, stop_loss: f64) -> f64 {
        let risk_amount = capital * risk_pct;
        let risk_per_unit = (entry - stop_loss).abs();
        if risk_per_unit == 0.0 { return 0.0; }
        risk_amount / risk_per_unit
    }

    // -- Drawdown -----------------------------------------------------------
    /// Compute drawdown series from equity curve.
    /// Returns (drawdown_pct, max_drawdown_pct, current_drawdown_duration, max_drawdown_duration).
    fn drawdown_metrics(equity: Vec<f64>) -> (Vec<f64>, f64, usize, usize) {
        let len = equity.len();
        if len == 0 { return (vec![], 0.0, 0, 0); }
        let mut dd = vec![0.0; len];
        let mut peak = equity[0];
        let mut max_dd = 0.0_f64;
        let mut current_dur: usize = 0;
        let mut max_dur: usize = 0;

        for i in 0..len {
            if equity[i] > peak {
                peak = equity[i];
                if current_dur > max_dur { max_dur = current_dur; }
                current_dur = 0;
            } else {
                dd[i] = (peak - equity[i]) / peak;
                current_dur += 1;
            }
            if dd[i] > max_dd { max_dd = dd[i]; }
        }
        if current_dur > max_dur { max_dur = current_dur; }
        (dd, max_dd, current_dur, max_dur)
    }

    // -- Correlation Matrix -------------------------------------------------
    /// Compute pairwise Pearson correlation for a matrix of return series.
    /// `returns` = list of equal-length return series.
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
    /// Historical CVaR at confidence level (e.g. 0.95).
    /// Returns the average of losses beyond the VaR threshold.
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
        let n = returns.len() as f64;
        if n == 0.0 { return 0.0; }
        let mean = returns.iter().sum::<f64>() / n;
        let var: f64 = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / n;
        let std = var.sqrt();
        if std == 0.0 { return 0.0; }
        (mean - risk_free_rate) / std
    }

    // -- Sortino Ratio ------------------------------------------------------
    fn sortino_ratio(returns: Vec<f64>, risk_free_rate: f64) -> f64 {
        let n = returns.len() as f64;
        if n == 0.0 { return 0.0; }
        let mean = returns.iter().sum::<f64>() / n;
        let downside_var: f64 = returns.iter()
            .filter(|&&r| r < 0.0)
            .map(|r| r.powi(2))
            .sum::<f64>() / n;
        let downside_std = downside_var.sqrt();
        if downside_std == 0.0 { return 0.0; }
        (mean - risk_free_rate) / downside_std
    }

    // -- Portfolio Risk -----------------------------------------------------
    /// Weighted portfolio volatility given weights and covariance matrix.
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
            if equity[i] > peak { peak = equity[i]; }
            if equity[i] < trough { trough = equity[i]; }
            mfe[i] = peak - equity[i];
            mae[i] = equity[i] - trough;
        }
        (mfe, mae)
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn pearson(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len().min(b.len()) as f64;
    if n == 0.0 { return 0.0; }
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
    if denom == 0.0 { return 0.0; }
    cov / denom
}
