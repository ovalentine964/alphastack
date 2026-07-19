//! Technical Indicators — all computed in Rust, exposed to Python via PyO3.
//!
//! Aligned with Python's `ai/signals.py` indicator functions.
//! Includes: RSI, MACD, Bollinger Bands, ATR, ADX, VWAP, OBV, Stochastic, EMA, SMA.
//!
//! Uninitialized values use `f64::NAN` to match Python's `np.nan` convention.

use pyo3::prelude::*;
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
    #[pyo3(get)]
    pub pct_b: Vec<f64>,
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

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StochasticResult {
    #[pyo3(get)]
    pub k: Vec<f64>,
    #[pyo3(get)]
    pub d: Vec<f64>,
}

// ---------------------------------------------------------------------------
// Indicators engine
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyIndicators;

#[pymethods]
impl PyIndicators {
    #[new]
    fn new() -> Self {
        Self
    }

    // -- RSI ----------------------------------------------------------------
    /// Relative Strength Index (Wilder's smoothing).
    /// Returns NaN for the first `period` values (matching Python convention).
    #[pyo3(signature = (closes, period=14))]
    fn rsi(closes: Vec<f64>, period: usize) -> Vec<f64> {
        let len = closes.len();
        if len < period + 1 {
            return vec![f64::NAN; len];
        }
        let mut result = vec![f64::NAN; len];
        let mut gains = 0.0_f64;
        let mut losses = 0.0_f64;

        // Seed with simple average of first `period` changes
        for i in 1..=period {
            let delta = closes[i] - closes[i - 1];
            if delta >= 0.0 {
                gains += delta;
            } else {
                losses -= delta;
            }
        }
        let mut avg_gain = gains / period as f64;
        let mut avg_loss = losses / period as f64;
        result[period] = if avg_loss == 0.0 {
            100.0
        } else {
            100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        };

        // Wilder's EMA smoothing
        for i in (period + 1)..len {
            let delta = closes[i] - closes[i - 1];
            let (g, l) = if delta >= 0.0 {
                (delta, 0.0)
            } else {
                (0.0, -delta)
            };
            avg_gain = (avg_gain * (period as f64 - 1.0) + g) / period as f64;
            avg_loss = (avg_loss * (period as f64 - 1.0) + l) / period as f64;
            result[i] = if avg_loss == 0.0 {
                100.0
            } else {
                100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
            };
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
        let mut macd_line = vec![f64::NAN; len];
        for i in 0..len {
            if !ema_fast[i].is_nan() && !ema_slow[i].is_nan() {
                macd_line[i] = ema_fast[i] - ema_slow[i];
            }
        }
        let signal_line = Self::ema(&macd_line, signal);
        let mut histogram = vec![f64::NAN; len];
        for i in 0..len {
            if !macd_line[i].is_nan() && !signal_line[i].is_nan() {
                histogram[i] = macd_line[i] - signal_line[i];
            }
        }
        MacdResult {
            macd_line,
            signal_line,
            histogram,
        }
    }

    // -- Bollinger Bands ----------------------------------------------------
    /// Bollinger Bands with %B indicator.
    #[pyo3(signature = (closes, period=20, num_std=2.0))]
    fn bollinger_bands(closes: Vec<f64>, period: usize, num_std: f64) -> BollingerResult {
        let len = closes.len();
        let mut upper = vec![f64::NAN; len];
        let mut middle = vec![f64::NAN; len];
        let mut lower = vec![f64::NAN; len];
        let mut bandwidth = vec![f64::NAN; len];
        let mut pct_b = vec![f64::NAN; len];

        for i in 0..len {
            if i + 1 < period {
                continue;
            }
            let window = &closes[i + 1 - period..=i];
            let mean: f64 = window.iter().sum::<f64>() / period as f64;
            let var: f64 = window.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / period as f64;
            let std = var.sqrt();
            middle[i] = mean;
            upper[i] = mean + num_std * std;
            lower[i] = mean - num_std * std;
            let bb_width = upper[i] - lower[i];
            bandwidth[i] = if mean != 0.0 { bb_width / mean } else { 0.0 };
            // %B: position within bands (0 = lower, 1 = upper)
            pct_b[i] = if bb_width > 0.0 {
                (closes[i] - lower[i]) / bb_width
            } else {
                0.5
            };
        }
        BollingerResult {
            upper,
            middle,
            lower,
            bandwidth,
            pct_b,
        }
    }

    // -- ATR ----------------------------------------------------------------
    /// Average True Range (Wilder's smoothing).
    /// Returns NaN for first `period-1` values.
    #[pyo3(signature = (highs, lows, closes, period=14))]
    fn atr(highs: Vec<f64>, lows: Vec<f64>, closes: Vec<f64>, period: usize) -> Vec<f64> {
        let len = closes.len();
        if len < 2 {
            return vec![f64::NAN; len];
        }
        let mut tr = vec![0.0; len];
        tr[0] = highs[0] - lows[0];
        for i in 1..len {
            let hl = highs[i] - lows[i];
            let hc = (highs[i] - closes[i - 1]).abs();
            let lc = (lows[i] - closes[i - 1]).abs();
            tr[i] = hl.max(hc).max(lc);
        }
        let mut atr_vals = vec![f64::NAN; len];
        if len < period {
            return atr_vals;
        }
        let sum: f64 = tr[..period].iter().sum();
        atr_vals[period - 1] = sum / period as f64;
        for i in period..len {
            atr_vals[i] = (atr_vals[i - 1] * (period as f64 - 1.0) + tr[i]) / period as f64;
        }
        atr_vals
    }

    // -- ADX ----------------------------------------------------------------
    /// Average Directional Index with +DI/-DI.
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

        let mut plus_di = vec![f64::NAN; len];
        let mut minus_di = vec![f64::NAN; len];
        let mut dx = vec![f64::NAN; len];
        for i in 0..len {
            if smooth_tr[i] != 0.0 && !smooth_tr[i].is_nan() {
                plus_di[i] = 100.0 * smooth_plus[i] / smooth_tr[i];
                minus_di[i] = 100.0 * smooth_minus[i] / smooth_tr[i];
                let di_sum = plus_di[i] + minus_di[i];
                dx[i] = if di_sum != 0.0 {
                    100.0 * (plus_di[i] - minus_di[i]).abs() / di_sum
                } else {
                    0.0
                };
            }
        }
        let adx_vals = Self::wilders_smooth(&dx, period);
        AdxResult {
            adx: adx_vals,
            plus_di,
            minus_di,
        }
    }

    // -- VWAP ---------------------------------------------------------------
    /// Volume-Weighted Average Price using typical price (H+L+C)/3.
    /// Matches Python's `compute_vwap` which uses typical_price.
    fn vwap(
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        volumes: Vec<f64>,
    ) -> Vec<f64> {
        let len = closes.len();
        let mut result = vec![0.0; len];
        let mut cum_pv = 0.0_f64;
        let mut cum_v = 0.0_f64;
        for i in 0..len {
            let typical = (highs[i] + lows[i] + closes[i]) / 3.0;
            cum_pv += typical * volumes[i];
            cum_v += volumes[i];
            result[i] = if cum_v > 0.0 {
                cum_pv / cum_v
            } else {
                closes[i]
            };
        }
        result
    }

    // -- OBV ----------------------------------------------------------------
    /// On-Balance Volume.
    fn obv(closes: Vec<f64>, volumes: Vec<f64>) -> Vec<f64> {
        let len = closes.len();
        if len == 0 {
            return vec![];
        }
        let mut obv_vals = vec![0.0; len];
        for i in 1..len {
            if closes[i] > closes[i - 1] {
                obv_vals[i] = obv_vals[i - 1] + volumes[i];
            } else if closes[i] < closes[i - 1] {
                obv_vals[i] = obv_vals[i - 1] - volumes[i];
            } else {
                obv_vals[i] = obv_vals[i - 1];
            }
        }
        obv_vals
    }

    // -- Stochastic ---------------------------------------------------------
    /// Stochastic Oscillator (%K, %D).
    #[pyo3(signature = (highs, lows, closes, k_period=14, d_period=3))]
    fn stochastic(
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        k_period: usize,
        d_period: usize,
    ) -> StochasticResult {
        let len = closes.len();
        let mut k = vec![f64::NAN; len];
        for i in (k_period - 1)..len {
            let mut window_high = f64::NEG_INFINITY;
            let mut window_low = f64::INFINITY;
            for j in (i + 1 - k_period)..=i {
                if highs[j] > window_high {
                    window_high = highs[j];
                }
                if lows[j] < window_low {
                    window_low = lows[j];
                }
            }
            k[i] = if window_high != window_low {
                100.0 * (closes[i] - window_low) / (window_high - window_low)
            } else {
                50.0
            };
        }
        let d = Self::sma(&k, d_period);
        StochasticResult { k, d }
    }

    // -- EMA (standalone) ---------------------------------------------------
    /// Exponential Moving Average.
    #[pyo3(signature = (data, period))]
    fn ema_standalone(data: Vec<f64>, period: usize) -> Vec<f64> {
        Self::ema(&data, period)
    }

    // -- SMA (standalone) ---------------------------------------------------
    /// Simple Moving Average (handles NaN).
    #[pyo3(signature = (data, period))]
    fn sma_standalone(data: Vec<f64>, period: usize) -> Vec<f64> {
        Self::sma(&data, period)
    }

    // -- Compute all indicators at once -------------------------------------
    /// Compute a full indicator suite and return as a dict-like struct.
    /// This is the primary entry point for the pipeline.
    fn compute_all(
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        volumes: Vec<f64>,
    ) -> IndicatorSuite {
        let rsi = Self::rsi(closes.clone(), 14);
        let macd = Self::macd(closes.clone(), 12, 26, 9);
        let bb = Self::bollinger_bands(closes.clone(), 20, 2.0);
        let atr = Self::atr(highs.clone(), lows.clone(), closes.clone(), 14);
        let adx = Self::adx(highs.clone(), lows.clone(), closes.clone(), 14);
        let vwap = Self::vwap(highs.clone(), lows.clone(), closes.clone(), volumes.clone());
        let obv = Self::obv(closes.clone(), volumes.clone());
        let stoch = Self::stochastic(highs, lows, closes, 14, 3);
        let ema_9 = Self::ema(&closes, 9);
        let ema_21 = Self::ema(&closes, 21);
        let ema_50 = Self::ema(&closes, 50);

        IndicatorSuite {
            rsi,
            macd_line: macd.macd_line,
            macd_signal: macd.signal_line,
            macd_histogram: macd.histogram,
            bb_upper: bb.upper,
            bb_middle: bb.middle,
            bb_lower: bb.lower,
            bb_bandwidth: bb.bandwidth,
            bb_pct_b: bb.pct_b,
            atr,
            adx: adx.adx,
            plus_di: adx.plus_di,
            minus_di: adx.minus_di,
            vwap,
            obv,
            stoch_k: stoch.k,
            stoch_d: stoch.d,
            ema_9,
            ema_21,
            ema_50,
        }
    }
}

/// Full indicator suite — returned by `compute_all`.
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndicatorSuite {
    #[pyo3(get)]
    pub rsi: Vec<f64>,
    #[pyo3(get)]
    pub macd_line: Vec<f64>,
    #[pyo3(get)]
    pub macd_signal: Vec<f64>,
    #[pyo3(get)]
    pub macd_histogram: Vec<f64>,
    #[pyo3(get)]
    pub bb_upper: Vec<f64>,
    #[pyo3(get)]
    pub bb_middle: Vec<f64>,
    #[pyo3(get)]
    pub bb_lower: Vec<f64>,
    #[pyo3(get)]
    pub bb_bandwidth: Vec<f64>,
    #[pyo3(get)]
    pub bb_pct_b: Vec<f64>,
    #[pyo3(get)]
    pub atr: Vec<f64>,
    #[pyo3(get)]
    pub adx: Vec<f64>,
    #[pyo3(get)]
    pub plus_di: Vec<f64>,
    #[pyo3(get)]
    pub minus_di: Vec<f64>,
    #[pyo3(get)]
    pub vwap: Vec<f64>,
    #[pyo3(get)]
    pub obv: Vec<f64>,
    #[pyo3(get)]
    pub stoch_k: Vec<f64>,
    #[pyo3(get)]
    pub stoch_d: Vec<f64>,
    #[pyo3(get)]
    pub ema_9: Vec<f64>,
    #[pyo3(get)]
    pub ema_21: Vec<f64>,
    #[pyo3(get)]
    pub ema_50: Vec<f64>,
}

#[pymethods]
impl IndicatorSuite {
    fn __repr__(&self) -> String {
        let len = self.rsi.len();
        let last_rsi = self.rsi.last().copied().unwrap_or(f64::NAN);
        let last_atr = self.atr.last().copied().unwrap_or(f64::NAN);
        let last_adx = self.adx.last().copied().unwrap_or(f64::NAN);
        format!(
            "IndicatorSuite(len={}, rsi={:.1}, atr={:.4}, adx={:.1})",
            len, last_rsi, last_atr, last_adx
        )
    }
}

// Internal helpers
impl PyIndicators {
    pub fn ema(data: &[f64], period: usize) -> Vec<f64> {
        let len = data.len();
        let mut out = vec![f64::NAN; len];
        if len < period {
            return out;
        }
        let k = 2.0 / (period as f64 + 1.0);
        // Seed with SMA of first `period` values
        let mut sum = 0.0_f64;
        let mut valid_count = 0usize;
        for i in 0..period {
            if !data[i].is_nan() {
                sum += data[i];
                valid_count += 1;
            }
        }
        if valid_count == 0 {
            return out;
        }
        out[period - 1] = sum / valid_count as f64;
        for i in period..len {
            if data[i].is_nan() {
                out[i] = out[i - 1]; // propagate last valid
            } else {
                out[i] = data[i] * k + out[i - 1] * (1.0 - k);
            }
        }
        out
    }

    pub fn sma(data: &[f64], period: usize) -> Vec<f64> {
        let len = data.len();
        let mut out = vec![f64::NAN; len];
        if len < period {
            return out;
        }
        for i in (period - 1)..len {
            let mut sum = 0.0_f64;
            let mut count = 0usize;
            for j in (i + 1 - period)..=i {
                if !data[j].is_nan() {
                    sum += data[j];
                    count += 1;
                }
            }
            if count > 0 {
                out[i] = sum / count as f64;
            }
        }
        out
    }

    fn wilders_smooth(data: &[f64], period: usize) -> Vec<f64> {
        let len = data.len();
        let mut out = vec![f64::NAN; len];
        if len < period {
            return out;
        }
        let mut sum: f64 = data[..period].iter().sum();
        out[period - 1] = sum / period as f64;
        for i in period..len {
            out[i] = (out[i - 1] * (period as f64 - 1.0) + data[i]) / period as f64;
        }
        out
    }
}
