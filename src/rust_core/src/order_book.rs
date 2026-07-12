//! Order Book Processing — imbalance detection, spread analysis,
//! liquidity pool detection, and delta analysis.

use pyo3::prelude::*;
use pyo3::types::PyList;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderLevel {
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub quantity: f64,
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookSnapshot {
    #[pyo3(get)]
    pub timestamp_ms: i64,
    #[pyo3(get)]
    pub bids: Vec<OrderLevel>,  // sorted descending by price
    #[pyo3(get)]
    pub asks: Vec<OrderLevel>,  // sorted ascending by price
}

#[pymethods]
impl OrderBookSnapshot {
    #[new]
    fn new(timestamp_ms: i64, bids: Vec<OrderLevel>, asks: Vec<OrderLevel>) -> Self {
        Self { timestamp_ms, bids, asks }
    }

    fn best_bid(&self) -> Option<f64> { self.bids.first().map(|l| l.price) }
    fn best_ask(&self) -> Option<f64> { self.asks.first().map(|l| l.price) }
    fn mid_price(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(b), Some(a)) => Some((b + a) / 2.0),
            _ => None,
        }
    }
    fn spread(&self) -> Option<f64> {
        match (self.best_bid(), self.best_ask()) {
            (Some(b), Some(a)) => Some(a - b),
            _ => None,
        }
    }
    fn spread_bps(&self) -> Option<f64> {
        match (self.spread(), self.mid_price()) {
            (Some(s), Some(m)) if m != 0.0 => Some(10_000.0 * s / m),
            _ => None,
        }
    }
}

// ---------------------------------------------------------------------------
// Analyzer
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyOrderBookAnalyzer {
    history: Vec<OrderBookSnapshot>,
    max_history: usize,
}

#[pymethods]
impl PyOrderBookAnalyzer {
    #[new]
    #[pyo3(signature = (max_history=1000))]
    fn new(max_history: usize) -> Self {
        Self { history: Vec::with_capacity(max_history), max_history }
    }

    /// Push a new snapshot into history.
    fn push(&mut self, snapshot: OrderBookSnapshot) {
        if self.history.len() >= self.max_history {
            self.history.remove(0);
        }
        self.history.push(snapshot);
    }

    /// Order book imbalance: (bid_qty - ask_qty) / (bid_qty + ask_qty).
    /// Range [-1, 1]; positive = buy pressure.
    #[pyo3(signature = (snapshot, depth=10))]
    fn imbalance(snapshot: &OrderBookSnapshot, depth: usize) -> f64 {
        let bid_qty: f64 = snapshot.bids.iter().take(depth).map(|l| l.quantity).sum();
        let ask_qty: f64 = snapshot.asks.iter().take(depth).map(|l| l.quantity).sum();
        let total = bid_qty + ask_qty;
        if total == 0.0 { return 0.0; }
        (bid_qty - ask_qty) / total
    }

    /// Detect liquidity pools — price levels with quantity significantly
    /// above the mean (> 2x std dev above mean).
    #[pyo3(signature = (snapshot, depth=20, std_mult=2.0))]
    fn liquidity_pools(snapshot: &OrderBookSnapshot, depth: usize, std_mult: f64) -> Vec<(f64, f64, String)> {
        let mut pools = Vec::new();
        let sides: [(&Vec<OrderLevel>, &str); 2] = [
            (&snapshot.bids, "bid"),
            (&snapshot.asks, "ask"),
        ];

        for (levels, side) in &sides {
            let subset: Vec<f64> = levels.iter().take(depth).map(|l| l.quantity).collect();
            if subset.len() < 3 { continue; }
            let n = subset.len() as f64;
            let mean: f64 = subset.iter().sum::<f64>() / n;
            let var: f64 = subset.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n;
            let std = var.sqrt();
            let threshold = mean + std_mult * std;

            for level in levels.iter().take(depth) {
                if level.quantity > threshold {
                    pools.push((level.price, level.quantity, (*side).into()));
                }
            }
        }
        pools
    }

    /// Cumulative delta from recent snapshots: sum of (bid_vol - ask_vol).
    /// Positive = net buying pressure.
    fn cumulative_delta(&self, lookback: usize) -> f64 {
        self.history
            .iter()
            .rev()
            .take(lookback)
            .map(|snap| {
                let bid_vol: f64 = snap.bids.iter().map(|l| l.quantity).sum();
                let ask_vol: f64 = snap.asks.iter().map(|l| l.quantity).sum();
                bid_vol - ask_vol
            })
            .sum()
    }

    /// Weighted mid-price: volume-weighted best bid/ask.
    #[pyo3(signature = (snapshot, depth=5))]
    fn weighted_mid(snapshot: &OrderBookSnapshot, depth: usize) -> Option<f64> {
        let bid_qty: f64 = snapshot.bids.iter().take(depth).map(|l| l.quantity).sum();
        let ask_qty: f64 = snapshot.asks.iter().take(depth).map(|l| l.quantity).sum();
        let best_bid = snapshot.best_bid()?;
        let best_ask = snapshot.best_ask()?;
        let total = bid_qty + ask_qty;
        if total == 0.0 { return Some((best_bid + best_ask) / 2.0); }
        Some((best_bid * ask_qty + best_ask * bid_qty) / total)
    }

    /// Spread trend over recent history: positive = widening.
    fn spread_trend(&self, lookback: usize) -> f64 {
        let spreads: Vec<f64> = self.history
            .iter()
            .rev()
            .take(lookback)
            .filter_map(|s| s.spread())
            .collect();
        if spreads.len() < 2 { return 0.0; }
        let first_half: f64 = spreads[..spreads.len() / 2].iter().sum::<f64>() / (spreads.len() / 2) as f64;
        let second_half: f64 = spreads[spreads.len() / 2..].iter().sum::<f64>() / (spreads.len() - spreads.len() / 2) as f64;
        second_half - first_half
    }

    fn snapshot_count(&self) -> usize { self.history.len() }
    fn clear(&mut self) { self.history.clear(); }
}
