//! Tick Processing Engine — high-performance tick ingestion, OHLCV aggregation,
//! normalization, volume profiling, gap detection, and data quality metrics.
//!
//! Aligned with Python's `data/feed.py`:
//! - Tick validation with staleness detection
//! - Gap detection in tick streams
//! - Data quality scoring
//! - Multi-timeframe candle aggregation
//! - Volume profiling with POC (Point of Control)

use pyo3::prelude::*;
use pyo3::types::PyList;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyTick {
    #[pyo3(get, set)]
    pub timestamp_ms: i64,
    #[pyo3(get, set)]
    pub price: f64,
    #[pyo3(get, set)]
    pub volume: f64,
    #[pyo3(get, set)]
    pub side: String, // "buy" | "sell"
}

#[pymethods]
impl PyTick {
    #[new]
    fn new(timestamp_ms: i64, price: f64, volume: f64, side: String) -> Self {
        Self {
            timestamp_ms,
            price,
            volume,
            side,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "Tick(ts={}, price={}, vol={}, side={})",
            self.timestamp_ms, self.price, self.volume, self.side
        )
    }
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyCandle {
    #[pyo3(get)]
    pub timestamp_ms: i64,
    #[pyo3(get)]
    pub open: f64,
    #[pyo3(get)]
    pub high: f64,
    #[pyo3(get)]
    pub low: f64,
    #[pyo3(get)]
    pub close: f64,
    #[pyo3(get)]
    pub volume: f64,
    #[pyo3(get)]
    pub buy_volume: f64,
    #[pyo3(get)]
    pub sell_volume: f64,
    #[pyo3(get)]
    pub tick_count: u64,
    #[pyo3(get)]
    pub vwap: f64,
}

#[pymethods]
impl PyCandle {
    fn __repr__(&self) -> String {
        format!(
            "Candle(ts={}, O={}, H={}, L={}, C={}, V={})",
            self.timestamp_ms, self.open, self.high, self.low, self.close, self.volume
        )
    }
}

// ---------------------------------------------------------------------------
// Data quality metrics
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataQualityReport {
    #[pyo3(get)]
    pub total_ticks: u64,
    #[pyo3(get)]
    pub rejected_ticks: u64,
    #[pyo3(get)]
    pub rejection_rate: f64,
    #[pyo3(get)]
    pub gap_count: u64,
    #[pyo3(get)]
    pub largest_gap_ms: i64,
    #[pyo3(get)]
    pub avg_gap_ms: f64,
    #[pyo3(get)]
    pub stale_tick_count: u64,
    #[pyo3(get)]
    pub quality_score: f64, // 0.0 (worst) to 1.0 (best)
}

#[pymethods]
impl DataQualityReport {
    fn __repr__(&self) -> String {
        format!(
            "DataQuality(score={:.2}, ticks={}, rejected={}, gaps={})",
            self.quality_score, self.total_ticks, self.rejected_ticks, self.gap_count
        )
    }
}

// ---------------------------------------------------------------------------
// Gap record
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
struct GapRecord {
    from_ts: i64,
    to_ts: i64,
    duration_ms: i64,
}

// ---------------------------------------------------------------------------
// Tick Processor
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyTickProcessor {
    interval_ms: i64,
    ticks: Vec<PyTick>,
    candles: Vec<PyCandle>,
    current_candle: Option<PyCandle>,
    // Volume profile buckets (price -> volume)
    volume_profile: HashMap<i64, f64>,
    bucket_size: f64,
    // Multi-timeframe aggregation
    multi_tf_processors: Vec<TimeframeProcessor>,
    // Data quality tracking
    rejected_ticks: u64,
    stale_ticks: u64,
    gaps: Vec<GapRecord>,
    last_tick_ts: Option<i64>,
    stale_threshold_ms: i64,
    max_price_deviation_pct: f64,
    last_price: Option<f64>,
}

struct TimeframeProcessor {
    interval_ms: i64,
    label: String,
    current_candle: Option<PyCandle>,
    candles: Vec<PyCandle>,
}

#[pymethods]
impl PyTickProcessor {
    #[new]
    #[pyo3(signature = (interval_ms=60000, bucket_size=0.01, stale_threshold_ms=30000, max_price_deviation_pct=50.0))]
    fn new(
        interval_ms: i64,
        bucket_size: f64,
        stale_threshold_ms: i64,
        max_price_deviation_pct: f64,
    ) -> Self {
        Self {
            interval_ms,
            ticks: Vec::with_capacity(10_000),
            candles: Vec::with_capacity(1_000),
            current_candle: None,
            volume_profile: HashMap::new(),
            bucket_size,
            multi_tf_processors: Vec::new(),
            rejected_ticks: 0,
            stale_ticks: 0,
            gaps: Vec::new(),
            last_tick_ts: None,
            stale_threshold_ms,
            max_price_deviation_pct,
            last_price: None,
        }
    }

    /// Add a secondary timeframe for multi-timeframe aggregation.
    fn add_timeframe(&mut self, label: String, interval_ms: i64) {
        self.multi_tf_processors.push(TimeframeProcessor {
            interval_ms,
            label,
            current_candle: None,
            candles: Vec::with_capacity(500),
        });
    }

    /// Validate a tick before ingestion.
    /// Returns (is_valid, reason).
    fn validate_tick(&mut self, tick: &PyTick) -> (bool, String) {
        // Check for finite values
        if !tick.price.is_finite() || !tick.volume.is_finite() {
            self.rejected_ticks += 1;
            return (false, "non_finite_values".into());
        }

        // Check positivity
        if tick.price <= 0.0 || tick.volume < 0.0 {
            self.rejected_ticks += 1;
            return (false, "non_positive_values".into());
        }

        // Check staleness
        if let Some(last_ts) = self.last_tick_ts {
            if tick.timestamp_ms < last_ts {
                self.rejected_ticks += 1;
                return (false, "timestamp_regression".into());
            }
            let gap = tick.timestamp_ms - last_ts;
            if gap > self.stale_threshold_ms {
                self.stale_ticks += 1;
                self.gaps.push(GapRecord {
                    from_ts: last_ts,
                    to_ts: tick.timestamp_ms,
                    duration_ms: gap,
                });
            }
        }

        // Check price deviation
        if let Some(last_p) = self.last_price {
            if last_p > 0.0 {
                let deviation = ((tick.price - last_p) / last_p * 100.0).abs();
                if deviation > self.max_price_deviation_pct {
                    self.rejected_ticks += 1;
                    return (false, format!("price_deviation_{:.1}pct", deviation));
                }
            }
        }

        (true, "ok".into())
    }

    /// Ingest a single tick with validation; returns a completed candle if the interval boundary was crossed.
    fn ingest_tick(&mut self, tick: &PyTick) -> Option<PyCandle> {
        // Validate
        let (valid, _reason) = self.validate_tick(tick);
        if !valid {
            return None;
        }

        let candle_start = (tick.timestamp_ms / self.interval_ms) * self.interval_ms;
        let mut completed: Option<PyCandle> = None;

        match &mut self.current_candle {
            Some(c) if c.timestamp_ms == candle_start => {
                // Same candle — extend
                c.high = c.high.max(tick.price);
                c.low = c.low.min(tick.price);
                c.close = tick.price;
                c.volume += tick.volume;
                c.tick_count += 1;
                // Update VWAP
                let total_pv = c.vwap * (c.volume - tick.volume) + tick.price * tick.volume;
                c.vwap = if c.volume > 0.0 {
                    total_pv / c.volume
                } else {
                    tick.price
                };
                if tick.side == "buy" {
                    c.buy_volume += tick.volume;
                } else {
                    c.sell_volume += tick.volume;
                }
            }
            Some(_) => {
                // New interval — flush old candle
                let finished = self.current_candle.take().unwrap();
                self.candles.push(finished.clone());
                completed = Some(finished);
                self.current_candle = Some(Self::make_candle(candle_start, tick));
            }
            None => {
                self.current_candle = Some(Self::make_candle(candle_start, tick));
            }
        }

        // Volume profile
        let bucket = (tick.price / self.bucket_size).round() as i64;
        *self.volume_profile.entry(bucket).or_insert(0.0) += tick.volume;

        // Multi-timeframe aggregation
        for tf in &mut self.multi_tf_processors {
            let tf_start = (tick.timestamp_ms / tf.interval_ms) * tf.interval_ms;
            match &mut tf.current_candle {
                Some(c) if c.timestamp_ms == tf_start => {
                    c.high = c.high.max(tick.price);
                    c.low = c.low.min(tick.price);
                    c.close = tick.price;
                    c.volume += tick.volume;
                    c.tick_count += 1;
                    if tick.side == "buy" {
                        c.buy_volume += tick.volume;
                    } else {
                        c.sell_volume += tick.volume;
                    }
                }
                Some(_) => {
                    let finished = tf.current_candle.take().unwrap();
                    tf.candles.push(finished);
                    tf.current_candle = Some(Self::make_candle(tf_start, tick));
                }
                None => {
                    tf.current_candle = Some(Self::make_candle(tf_start, tick));
                }
            }
        }

        // Update tracking
        self.last_tick_ts = Some(tick.timestamp_ms);
        self.last_price = Some(tick.price);
        self.ticks.push(tick.clone());
        completed
    }

    /// Batch-ingest a Python list of PyTick objects.
    fn ingest_batch(&mut self, py: Python<'_>, ticks: &Bound<'_, PyList>) -> PyResult<Vec<PyCandle>> {
        let mut completed = Vec::new();
        for item in ticks.iter() {
            let tick: PyTick = item.extract()?;
            if let Some(c) = self.ingest_tick(&tick) {
                completed.push(c);
            }
        }
        Ok(completed)
    }

    /// Flush current partial candle.
    fn flush(&mut self) -> Option<PyCandle> {
        self.current_candle.take().map(|c| {
            self.candles.push(c.clone());
            c
        })
    }

    /// Flush all multi-timeframe candles too.
    fn flush_all(&mut self) -> Vec<PyCandle> {
        let mut all = Vec::new();
        if let Some(c) = self.flush() {
            all.push(c);
        }
        for tf in &mut self.multi_tf_processors {
            if let Some(c) = tf.current_candle.take() {
                tf.candles.push(c.clone());
                all.push(c);
            }
        }
        all
    }

    /// Return all completed candles for the primary timeframe.
    fn get_candles(&self) -> Vec<PyCandle> {
        self.candles.clone()
    }

    /// Return candles for a specific timeframe label.
    fn get_candles_for_timeframe(&self, label: String) -> Vec<PyCandle> {
        for tf in &self.multi_tf_processors {
            if tf.label == label {
                return tf.candles.clone();
            }
        }
        vec![]
    }

    /// Return volume profile as (price_level, volume) pairs.
    fn get_volume_profile(&self) -> Vec<(f64, f64)> {
        self.volume_profile
            .iter()
            .map(|(&bucket, &vol)| (bucket as f64 * self.bucket_size, vol))
            .collect()
    }

    /// POC (Point of Control) — price level with highest volume.
    fn poc(&self) -> Option<f64> {
        self.volume_profile
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(&bucket, _)| bucket as f64 * self.bucket_size)
    }

    /// Value Area High — upper bound of the 70% volume zone.
    fn value_area_high(&self) -> Option<f64> {
        self.value_area_bound(0.7, true)
    }

    /// Value Area Low — lower bound of the 70% volume zone.
    fn value_area_low(&self) -> Option<f64> {
        self.value_area_bound(0.7, false)
    }

    /// Total tick count ingested (including rejected).
    fn tick_count(&self) -> usize {
        self.ticks.len()
    }

    /// Reset processor state.
    fn reset(&mut self) {
        self.ticks.clear();
        self.candles.clear();
        self.current_candle = None;
        self.volume_profile.clear();
        self.rejected_ticks = 0;
        self.stale_ticks = 0;
        self.gaps.clear();
        self.last_tick_ts = None;
        self.last_price = None;
        for tf in &mut self.multi_tf_processors {
            tf.candles.clear();
            tf.current_candle = None;
        }
    }

    /// Normalize ticks to z-scores on price.
    fn normalize_ticks(&self) -> Vec<(i64, f64)> {
        if self.ticks.is_empty() {
            return vec![];
        }
        let n = self.ticks.len() as f64;
        let mean: f64 = self.ticks.iter().map(|t| t.price).sum::<f64>() / n;
        let var: f64 = self.ticks.iter().map(|t| (t.price - mean).powi(2)).sum::<f64>() / n;
        let std = var.sqrt();
        if std == 0.0 {
            return self.ticks.iter().map(|t| (t.timestamp_ms, 0.0)).collect();
        }
        self.ticks
            .iter()
            .map(|t| (t.timestamp_ms, (t.price - mean) / std))
            .collect()
    }

    /// Data quality report.
    fn data_quality(&self) -> DataQualityReport {
        let total = (self.ticks.len() as u64) + self.rejected_ticks;
        let rejection_rate = if total > 0 {
            self.rejected_ticks as f64 / total as f64
        } else {
            0.0
        };

        let (largest_gap, avg_gap) = if !self.gaps.is_empty() {
            let largest = self.gaps.iter().map(|g| g.duration_ms).max().unwrap_or(0);
            let avg = self.gaps.iter().map(|g| g.duration_ms).sum::<i64>() as f64
                / self.gaps.len() as f64;
            (largest, avg)
        } else {
            (0, 0.0)
        };

        // Quality score: penalize rejections, gaps, staleness
        let mut quality = 1.0_f64;
        quality -= rejection_rate * 0.5; // rejections up to -0.5
        let gap_penalty = (self.gaps.len() as f64 / 100.0).min(0.3);
        quality -= gap_penalty;
        let stale_penalty = (self.stale_ticks as f64 / total.max(1) as f64).min(0.2);
        quality -= stale_penalty;

        DataQualityReport {
            total_ticks: total,
            rejected_ticks: self.rejected_ticks,
            rejection_rate,
            gap_count: self.gaps.len() as u64,
            largest_gap_ms: largest_gap,
            avg_gap_ms: avg_gap,
            stale_tick_count: self.stale_ticks,
            quality_score: quality.clamp(0.0, 1.0),
        }
    }
}

impl PyTickProcessor {
    fn make_candle(ts: i64, tick: &PyTick) -> PyCandle {
        PyCandle {
            timestamp_ms: ts,
            open: tick.price,
            high: tick.price,
            low: tick.price,
            close: tick.price,
            volume: tick.volume,
            buy_volume: if tick.side == "buy" {
                tick.volume
            } else {
                0.0
            },
            sell_volume: if tick.side == "sell" {
                tick.volume
            } else {
                0.0
            },
            tick_count: 1,
            vwap: tick.price,
        }
    }

    fn value_area_bound(&self, pct: f64, high: bool) -> Option<f64> {
        if self.volume_profile.is_empty() {
            return None;
        }
        let total_vol: f64 = self.volume_profile.values().sum();
        let target = total_vol * pct;

        let mut sorted: Vec<(i64, f64)> = self.volume_profile.iter().map(|(&k, &v)| (k, v)).collect();
        sorted.sort_by_key(|&(k, _)| k);

        // Find POC
        let poc_bucket = sorted
            .iter()
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap())
            .map(|&(k, _)| k)?;

        let poc_idx = sorted.iter().position(|&(k, _)| k == poc_bucket)?;

        let mut accumulated = sorted[poc_idx].1;
        let mut lo = poc_idx;
        let mut hi = poc_idx;

        while accumulated < target {
            let expand_up = if hi + 1 < sorted.len() {
                Some(sorted[hi + 1].1)
            } else {
                None
            };
            let expand_down = if lo > 0 {
                Some(sorted[lo - 1].1)
            } else {
                None
            };

            match (expand_up, expand_down) {
                (Some(up), Some(down)) => {
                    if up >= down {
                        hi += 1;
                        accumulated += up;
                    } else {
                        lo -= 1;
                        accumulated += down;
                    }
                }
                (Some(up), None) => {
                    hi += 1;
                    accumulated += up;
                }
                (None, Some(down)) => {
                    lo -= 1;
                    accumulated += down;
                }
                (None, None) => break,
            }
        }

        let bound = if high {
            sorted[hi].0 as f64 * self.bucket_size
        } else {
            sorted[lo].0 as f64 * self.bucket_size
        };
        Some(bound)
    }
}
