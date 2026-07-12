//! Signal Computation Engine — confluence scoring, multi-timeframe analysis,
//! structure detection (HH/HL/LH/LL), and support/resistance levels.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StructurePoint {
    #[pyo3(get)]
    pub index: usize,
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub kind: String, // "HH", "HL", "LH", "LL"
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Level {
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub strength: f64,   // 0..1
    #[pyo3(get)]
    pub kind: String,    // "support" | "resistance"
    #[pyo3(get)]
    pub touches: u32,
}

// ---------------------------------------------------------------------------
// Signal Engine
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PySignalEngine;

#[pymethods]
impl PySignalEngine {
    #[new]
    fn new() -> Self { Self }

    // -- Confluence Scoring -------------------------------------------------
    /// Score confluence from individual signal scores (each 0..1).
    /// Returns weighted confluence score 0..1.
    #[pyo3(signature = (signals, weights=None))]
    fn confluence_score(signals: Vec<f64>, weights: Option<Vec<f64>>) -> f64 {
        let w = weights.unwrap_or_else(|| vec![1.0; signals.len()]);
        assert_eq!(signals.len(), w.len(), "signals and weights must have same length");
        let total_w: f64 = w.iter().sum();
        if total_w == 0.0 { return 0.0; }
        let score: f64 = signals.iter().zip(w.iter()).map(|(s, wi)| s * wi).sum::<f64>() / total_w;
        score.clamp(0.0, 1.0)
    }

    // -- Structure Detection ------------------------------------------------
    /// Detect swing highs/lows and classify as HH/HL/LH/LL.
    /// `lookback` controls the window for swing detection.
    #[pyo3(signature = (highs, lows, lookback=5))]
    fn detect_structure(highs: Vec<f64>, lows: Vec<f64>, lookback: usize) -> Vec<StructurePoint> {
        let len = highs.len();
        if len < lookback * 2 + 1 { return vec![]; }
        let mut swings: Vec<StructurePoint> = Vec::new();

        // Find swing highs and lows
        for i in lookback..(len - lookback) {
            let is_high = (i - lookback..=i + lookback).all(|j| highs[j] <= highs[i]);
            let is_low = (i - lookback..=i + lookback).all(|j| lows[j] >= lows[i]);
            if is_high {
                swings.push(StructurePoint { index: i, price: highs[i], kind: "swing_high".into() });
            }
            if is_low {
                swings.push(StructurePoint { index: i, price: lows[i], kind: "swing_low".into() });
            }
        }

        // Classify consecutive swing highs / swing lows
        let mut result = Vec::new();
        let mut last_high: Option<&StructurePoint> = None;
        let mut last_low: Option<&StructurePoint> = None;

        for sp in &swings {
            match sp.kind.as_str() {
                "swing_high" => {
                    let kind = match last_high {
                        Some(prev) if sp.price > prev.price => "HH",
                        Some(_) => "LH",
                        None => "HH",
                    };
                    result.push(StructurePoint { index: sp.index, price: sp.price, kind: kind.into() });
                    last_high = Some(sp);
                }
                "swing_low" => {
                    let kind = match last_low {
                        Some(prev) if sp.price > prev.price => "HL",
                        Some(_) => "LL",
                        None => "HL",
                    };
                    result.push(StructurePoint { index: sp.index, price: sp.price, kind: kind.into() });
                    last_low = Some(sp);
                }
                _ => {}
            }
        }
        result
    }

    // -- Multi-Timeframe Alignment -----------------------------------------
    /// Check alignment across multiple timeframe scores.
    /// Each score in [-1, 1] where positive = bullish, negative = bearish.
    /// Returns alignment score in [-1, 1].
    fn multi_timeframe_alignment(scores: Vec<f64>, weights: Vec<f64>) -> f64 {
        assert_eq!(scores.len(), weights.len());
        let total_w: f64 = weights.iter().sum();
        if total_w == 0.0 { return 0.0; }
        let aligned: f64 = scores.iter().zip(weights.iter()).map(|(s, w)| s * w).sum::<f64>() / total_w;
        aligned.clamp(-1.0, 1.0)
    }

    // -- Support / Resistance Detection -------------------------------------
    /// Cluster price levels that have multiple touches.
    /// Returns sorted levels by strength.
    #[pyo3(signature = (highs, lows, closes, tolerance_pct=0.002, min_touches=2))]
    fn detect_levels(
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        tolerance_pct: f64,
        min_touches: u32,
    ) -> Vec<Level> {
        // Collect all price pivots
        let mut all_prices: Vec<f64> = Vec::new();
        all_prices.extend_from_slice(&highs);
        all_prices.extend_from_slice(&lows);
        all_prices.extend_from_slice(&closes);
        all_prices.sort_by(|a, b| a.partial_cmp(b).unwrap());

        if all_prices.is_empty() { return vec![]; }

        // Cluster nearby prices
        let mut clusters: Vec<Vec<f64>> = Vec::new();
        let mut current_cluster: Vec<f64> = vec![all_prices[0]];

        for &p in &all_prices[1..] {
            let base = current_cluster[0];
            if (p - base).abs() / base <= tolerance_pct {
                current_cluster.push(p);
            } else {
                clusters.push(current_cluster);
                current_cluster = vec![p];
            }
        }
        clusters.push(current_cluster);

        let current_price = *closes.last().unwrap_or(&0.0);
        let mut levels: Vec<Level> = Vec::new();

        for cluster in &clusters {
            let touches = cluster.len() as u32;
            if touches < min_touches { continue; }
            let avg_price: f64 = cluster.iter().sum::<f64>() / touches as f64;
            let strength = (touches as f64 / all_prices.len() as f64).min(1.0);
            let kind = if avg_price < current_price { "support" } else { "resistance" };
            levels.push(Level { price: avg_price, strength, kind: kind.into(), touches });
        }

        levels.sort_by(|a, b| b.strength.partial_cmp(&a.strength).unwrap());
        levels
    }

    // -- Trend Bias ---------------------------------------------------------
    /// Simple trend bias from recent HH/HL vs LH/LL count.
    /// Returns value in [-1, 1].
    #[pyo3(signature = (highs, lows, lookback=5))]
    fn trend_bias(highs: Vec<f64>, lows: Vec<f64>, lookback: usize) -> f64 {
        let structures = Self::detect_structure(highs, lows, lookback);
        let recent: Vec<_> = structures.iter().rev().take(10).collect();
        if recent.is_empty() { return 0.0; }
        let bullish = recent.iter().filter(|s| s.kind == "HH" || s.kind == "HL").count();
        let bearish = recent.iter().filter(|s| s.kind == "LH" || s.kind == "LL").count();
        let total = bullish + bearish;
        if total == 0 { return 0.0; }
        (bullish as f64 - bearish as f64) / total as f64
    }
}
