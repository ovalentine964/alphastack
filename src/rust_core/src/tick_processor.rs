//! Tick Processing Engine — high-performance tick ingestion, OHLCV aggregation,
//! normalization, and volume profiling.

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
        Self { timestamp_ms, price, volume, side }
    }

    fn __repr__(&self) -> String {
        format!("Tick(ts={}, price={}, vol={}, side={})", self.timestamp_ms, self.price, self.volume, self.side)
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
}

#[pymethods]
impl PyTickProcessor {
    #[new]
    #[pyo3(signature = (interval_ms=60000, bucket_size=0.01))]
    fn new(interval_ms: i64, bucket_size: f64) -> Self {
        Self {
            interval_ms,
            ticks: Vec::with_capacity(10_000),
            candles: Vec::with_capacity(1_000),
            current_candle: None,
            volume_profile: HashMap::new(),
            bucket_size,
        }
    }

    /// Ingest a single tick; returns a completed candle if the interval boundary was crossed.
    fn ingest_tick(&mut self, tick: &PyTick) -> Option<PyCandle> {
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
                if tick.side == "buy" { c.buy_volume += tick.volume; } else { c.sell_volume += tick.volume; }
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

    /// Return all completed candles.
    fn get_candles(&self) -> Vec<PyCandle> {
        self.candles.clone()
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

    /// Total tick count ingested.
    fn tick_count(&self) -> usize {
        self.ticks.len()
    }

    /// Reset processor state.
    fn reset(&mut self) {
        self.ticks.clear();
        self.candles.clear();
        self.current_candle = None;
        self.volume_profile.clear();
    }

    /// Normalize ticks to z-scores on price.
    fn normalize_ticks(&self) -> Vec<(i64, f64)> {
        if self.ticks.is_empty() { return vec![]; }
        let n = self.ticks.len() as f64;
        let mean: f64 = self.ticks.iter().map(|t| t.price).sum::<f64>() / n;
        let var: f64 = self.ticks.iter().map(|t| (t.price - mean).powi(2)).sum::<f64>() / n;
        let std = var.sqrt();
        if std == 0.0 {
            return self.ticks.iter().map(|t| (t.timestamp_ms, 0.0)).collect();
        }
        self.ticks.iter().map(|t| (t.timestamp_ms, (t.price - mean) / std)).collect()
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
            buy_volume: if tick.side == "buy" { tick.volume } else { 0.0 },
            sell_volume: if tick.side == "sell" { tick.volume } else { 0.0 },
            tick_count: 1,
        }
    }
}
