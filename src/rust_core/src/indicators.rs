//! Technical Indicators — all computed in Rust, exposed to Python via PyO3.
//!
//! Includes: RSI, MACD, Bollinger Bands, ATR, ADX, VWAP.

use pyo3::prelude::*;
use pyo3::types::PyList;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Data containers
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MacdResult {
    #[pyo3(get)]
    pub macd_line: Vec<f64>,
    #[pyo3(get)]
    pub signal_line: Vec<f64>,
    #[pyo3(get)]
    pub histogram: Vec<f64>,
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BollingerResult {
    #[pyo3(get)]
    pub upper: Vec<f64>,
    #[pyo3(get)]
    pub middle: Vec<f64>,
    #[pyo3(get)]
    pub lower: Vec<f64>,
    #[pyo3(get)]
    pub bandwidth: Vec<f64>,
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdxResult {
    #[pyo3(get)]
    pub adx: Vec<f64>,
    #[pyo3(get)]
    pub plus_di: Vec<f64>,
    #[pyo3(get)]
    pub minus_di: Vec<f64>,
}

// ---------------------------------------------------------------------------
// Indicators engine
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyIndicators;

#[pymethods]
impl PyIndicators {
    #[new]
    fn new() -> Self { Self }

    // -- RSI ----------------------------------------------------------------
    /// Relative Strength Index (Wilder's smoothing).
    #[pyo3(signature = (closes, period=14))]
    fn rsi(closes: Vec<f64>, period: usize) -> Vec<f64> {
        let len = closes.len();
        if len < period + 1 {
            return vec![50.0; len];
        }
        let mut result = vec![50.0; len];
        let mut gains = 0.0_f64;
        let mut losses = 0.0_f64;

        // Seed with simple average
        for i in 1..=period {
            let delta = closes[i] - closes[i - 1];
            if delta >= 0.0 { gains += delta; } else { losses -= delta; }
        }
        let mut avg_gain = gains / period as f64;
        let mut avg_loss = losses / period as f64;
        result[period] = if avg_loss == 0.0 { 100.0 } else { 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) };

        // Wilder's EMA
        for i in (period + 1)..len {
            let delta = closes[i] - closes[i - 1];
            let (g, l) = if delta >= 0.0 { (delta, 0.0) } else { (0.0, -delta) };
            avg_gain = (avg_gain * (period as f64 - 1.0) + g) / period as f64;
            avg_loss = (avg_loss * (period as f64 - 1.0) + l) / period as f64;
            result[i] = if avg_loss == 0.0 { 100.0 } else { 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) };
        }
        result
    }

    // -- MACD ---------------------------------------------------------------
    /// MACD (12, 26, 9) with configurable periods.
    #[pyo3(signature = (closes, fast=12, slow=26, signal=9))]
    fn macd(closes: Vec<f64>, fast: usize, slow: usize, signal: usize) -> MacdResult {
        let ema_fast = Self::ema(&closes, fast);
        let ema_slow = Self::ema(&closes, slow);
        let len = closes.len();
        let mut macd_line = vec![0.0; len];
        for i in 0..len {
            macd_line[i] = ema_fast[i] - ema_slow[i];
        }
        let signal_line = Self::ema(&macd_line, signal);
        let mut histogram = vec![0.0; len];
        for i in 0..len {
            histogram[i] = macd_line[i] - signal_line[i];
        }
        MacdResult { macd_line, signal_line, histogram }
    }

    // -- Bollinger Bands ----------------------------------------------------
    #[pyo3(signature = (closes, period=20, num_std=2.0))]
    fn bollinger_bands(closes: Vec<f64>, period: usize, num_std: f64) -> BollingerResult {
        let len = closes.len();
        let mut upper = vec![0.0; len];
        let mut middle = vec![0.0; len];
        let mut lower = vec![0.0; len];
        let mut bandwidth = vec![0.0; len];

        for i in 0..len {
            if i + 1 < period {
                middle[i] = closes[i];
                upper[i] = closes[i];
                lower[i] = closes[i];
                continue;
            }
            let window = &closes[i + 1 - period..=i];
            let mean: f64 = window.iter().sum::<f64>() / period as f64;
            let var: f64 = window.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / period as f64;
            let std = var.sqrt();
            middle[i] = mean;
            upper[i] = mean + num_std * std;
            lower[i] = mean - num_std * std;
            bandwidth[i] = if mean != 0.0 { (upper[i] - lower[i]) / mean } else { 0.0 };
        }
        BollingerResult { upper, middle, lower, bandwidth }
    }

    // -- ATR ----------------------------------------------------------------
    /// Average True Range (Wilder's smoothing).
    #[pyo3(signature = (highs, lows, closes, period=14))]
    fn atr(highs: Vec<f64>, lows: Vec<f64>, closes: Vec<f64>, period: usize) -> Vec<f64> {
        let len = closes.len();
        if len < 2 { return vec![0.0; len]; }
        let mut tr = vec![0.0; len];
        tr[0] = highs[0] - lows[0];
        for i in 1..len {
            let hl = highs[i] - lows[i];
            let hc = (highs[i] - closes[i - 1]).abs();
            let lc = (lows[i] - closes[i - 1]).abs();
            tr[i] = hl.max(hc).max(lc);
        }
        let mut atr_vals = vec![0.0; len];
        if len < period { return atr_vals; }
        let mut sum: f64 = tr[..period].iter().sum();
        atr_vals[period - 1] = sum / period as f64;
        for i in period..len {
            atr_vals[i] = (atr_vals[i - 1] * (period as f64 - 1.0) + tr[i]) / period as f64;
        }
        atr_vals
    }

    // -- ADX ----------------------------------------------------------------
    /// Average Directional Index.
    #[pyo3(signature = (highs, lows, closes, period=14))]
    fn adx(highs: Vec<f64>, lows: Vec<f64>, closes: Vec<f64>, period: usize) -> AdxResult {
        let len = closes.len();
        let mut plus_dm = vec![0.0; len];
        let mut minus_dm = vec![0.0; len];
        let mut tr = vec![0.0; len];

        for i in 1..len {
            let up = highs[i] - highs[i - 1];
            let down = lows[i - 1] - lows[i];
            plus_dm[i] = if up > down && up > 0.0 { up } else { 0.0 };
            minus_dm[i] = if down > up && down > 0.0 { down } else { 0.0 };
            let hl = highs[i] - lows[i];
            let hc = (highs[i] - closes[i - 1]).abs();
            let lc = (lows[i] - closes[i - 1]).abs();
            tr[i] = hl.max(hc).max(lc);
        }

        let smooth_tr = Self::wilders_smooth(&tr, period);
        let smooth_plus = Self::wilders_smooth(&plus_dm, period);
        let smooth_minus = Self::wilders_smooth(&minus_dm, period);

        let mut plus_di = vec![0.0; len];
        let mut minus_di = vec![0.0; len];
        let mut dx = vec![0.0; len];
        for i in 0..len {
            if smooth_tr[i] != 0.0 {
                plus_di[i] = 100.0 * smooth_plus[i] / smooth_tr[i];
                minus_di[i] = 100.0 * smooth_minus[i] / smooth_tr[i];
            }
            let di_sum = plus_di[i] + minus_di[i];
            dx[i] = if di_sum != 0.0 { 100.0 * (plus_di[i] - minus_di[i]).abs() / di_sum } else { 0.0 };
        }
        let adx_vals = Self::wilders_smooth(&dx, period);
        AdxResult { adx: adx_vals, plus_di, minus_di }
    }

    // -- VWAP ---------------------------------------------------------------
    /// Volume-Weighted Average Price (cumulative from session start).
    fn vwap(prices: Vec<f64>, volumes: Vec<f64>) -> Vec<f64> {
        let len = prices.len();
        let mut result = vec![0.0; len];
        let mut cum_pv = 0.0_f64;
        let mut cum_v = 0.0_f64;
        for i in 0..len {
            cum_pv += prices[i] * volumes[i];
            cum_v += volumes[i];
            result[i] = if cum_v != 0.0 { cum_pv / cum_v } else { prices[i] };
        }
        result
    }
}

// Internal helpers
impl PyIndicators {
    fn ema(data: &[f64], period: usize) -> Vec<f64> {
        let len = data.len();
        let mut out = vec![0.0; len];
        if len < period { return out; }
        let k = 2.0 / (period as f64 + 1.0);
        // Seed with SMA
        let mut sum: f64 = data[..period].iter().sum();
        out[period - 1] = sum / period as f64;
        for i in period..len {
            out[i] = data[i] * k + out[i - 1] * (1.0 - k);
        }
        // Backfill early values
        for i in 0..(period - 1) {
            out[i] = out[period - 1];
        }
        out
    }

    fn wilders_smooth(data: &[f64], period: usize) -> Vec<f64> {
        let len = data.len();
        let mut out = vec![0.0; len];
        if len < period { return out; }
        let mut sum: f64 = data[..period].iter().sum();
        out[period - 1] = sum / period as f64;
        for i in period..len {
            out[i] = (out[i - 1] * (period as f64 - 1.0) + data[i]) / period as f64;
        }
        out
    }
}
