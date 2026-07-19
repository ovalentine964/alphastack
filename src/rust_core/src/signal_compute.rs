//! Signal Computation Engine — confluence scoring, SMC detection,
//! support/resistance, confidence scoring, and signal generation.
//!
//! Aligned with Python's `ai/signals.py` and `ai/pipeline.py`:
//! - 10-component confluence scoring with weighted aggregation
//! - Smart Money Concepts (order blocks, FVGs, liquidity sweeps)
//! - Support/Resistance detection with clustering
//! - Confidence scoring (harmonic mean of quality factors)
//! - Signal generation with entry/SL/TP levels
//! - Market structure detection (HH/HL/LH/LL)
//! - Multi-timeframe alignment

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};

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
    pub strength: f64,
    #[pyo3(get)]
    pub kind: String, // "support" | "resistance"
    #[pyo3(get)]
    pub touches: u32,
    #[pyo3(get)]
    pub last_test_index: i64,
}

// ---------------------------------------------------------------------------
// SMC types (aligned with Python's ai/signals.py)
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBlock {
    #[pyo3(get)]
    pub high: f64,
    #[pyo3(get)]
    pub low: f64,
    #[pyo3(get)]
    pub direction: String, // "long" | "short"
    #[pyo3(get)]
    pub index: usize,
    #[pyo3(get)]
    pub strength: f64,
    #[pyo3(get)]
    pub mitigated: bool,
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FairValueGap {
    #[pyo3(get)]
    pub high: f64,
    #[pyo3(get)]
    pub low: f64,
    #[pyo3(get)]
    pub direction: String, // "long" | "short"
    #[pyo3(get)]
    pub index: usize,
    #[pyo3(get)]
    pub filled: bool,
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LiquiditySweep {
    #[pyo3(get)]
    pub level: f64,
    #[pyo3(get)]
    pub direction: String, // "long" | "short"
    #[pyo3(get)]
    pub index: usize,
    #[pyo3(get)]
    pub strength: f64,
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SmcAnalysis {
    #[pyo3(get)]
    pub bias: String, // "long" | "short" | "flat"
    #[pyo3(get)]
    pub order_blocks: Vec<OrderBlock>,
    #[pyo3(get)]
    pub fair_value_gaps: Vec<FairValueGap>,
    #[pyo3(get)]
    pub liquidity_sweeps: Vec<LiquiditySweep>,
    #[pyo3(get)]
    pub bullish_score: f64,
    #[pyo3(get)]
    pub bearish_score: f64,
    #[pyo3(get)]
    pub active_obs: usize,
    #[pyo3(get)]
    pub active_fvgs: usize,
}

// ---------------------------------------------------------------------------
// Generated signal
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeneratedSignal {
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub side: String, // "long" | "short" | "flat"
    #[pyo3(get)]
    pub strength: f64,
    #[pyo3(get)]
    pub confluence_score: f64,
    #[pyo3(get)]
    pub confidence: f64,
    #[pyo3(get)]
    pub entry_price: f64,
    #[pyo3(get)]
    pub stop_loss: f64,
    #[pyo3(get)]
    pub take_profit: Vec<f64>,
    #[pyo3(get)]
    pub reasoning: String,
    #[pyo3(get)]
    pub regime: String,
    #[pyo3(get)]
    pub rsi: f64,
    #[pyo3(get)]
    pub macd: f64,
    #[pyo3(get)]
    pub adx: f64,
    #[pyo3(get)]
    pub atr: f64,
    #[pyo3(get)]
    pub smc_bias: String,
}

#[pymethods]
impl GeneratedSignal {
    fn __repr__(&self) -> String {
        format!(
            "Signal({}, {}, strength={:.3}, conf={:.1}, entry={})",
            self.symbol, self.side, self.strength, self.confluence_score, self.entry_price
        )
    }

    /// Whether the signal meets minimum thresholds for execution.
    fn is_actionable(&self) -> bool {
        self.side != "flat" && self.strength >= 0.4 && self.confluence_score >= 40.0 && self.confidence >= 0.5
    }
}

// ---------------------------------------------------------------------------
// SMC Detector (aligned with Python's SMCDetector)
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PySmcDetector {
    ob_lookback: usize,
    fvg_min_gap_pct: f64,
    liquidity_threshold_atr_mult: f64,
}

#[pymethods]
impl PySmcDetector {
    #[new]
    #[pyo3(signature = (ob_lookback=50, fvg_min_gap_pct=0.001, liquidity_threshold_atr_mult=1.5))]
    fn new(ob_lookback: usize, fvg_min_gap_pct: f64, liquidity_threshold_atr_mult: f64) -> Self {
        Self {
            ob_lookback,
            fvg_min_gap_pct,
            liquidity_threshold_atr_mult,
        }
    }

    /// Detect order blocks — last opposing candle before impulsive move.
    fn detect_order_blocks(
        &self,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        atr: Vec<f64>,
    ) -> Vec<OrderBlock> {
        let len = closes.len();
        if len < 3 {
            return vec![];
        }
        let mut blocks = Vec::new();
        let lookback = self.ob_lookback.min(len - 2);
        let start = if len > lookback + 1 {
            len - lookback - 1
        } else {
            0
        };

        for i in start..(len - 1) {
            let body = (closes[i] - opens[i]).abs();
            let threshold = if i < atr.len() && !atr[i].is_nan() && atr[i] > 0.0 {
                atr[i] * self.liquidity_threshold_atr_mult
            } else {
                body * 2.0
            };

            // Bullish OB: bearish candle followed by bullish impulsive move
            if closes[i] < opens[i] {
                let move_size = closes[i + 1] - opens[i + 1];
                if move_size > threshold && closes[i + 1] > opens[i + 1] {
                    let strength = if threshold > 0.0 {
                        (move_size / threshold).min(3.0) / 3.0
                    } else {
                        0.5
                    };
                    blocks.push(OrderBlock {
                        high: highs[i],
                        low: lows[i],
                        direction: "long".into(),
                        index: i,
                        strength,
                        mitigated: false,
                    });
                }
            }
            // Bearish OB: bullish candle followed by bearish impulsive move
            else if closes[i] > opens[i] {
                let move_size = opens[i + 1] - closes[i + 1];
                if move_size > threshold && closes[i + 1] < opens[i + 1] {
                    let strength = if threshold > 0.0 {
                        (move_size / threshold).min(3.0) / 3.0
                    } else {
                        0.5
                    };
                    blocks.push(OrderBlock {
                        high: highs[i],
                        low: lows[i],
                        direction: "short".into(),
                        index: i,
                        strength,
                        mitigated: false,
                    });
                }
            }
        }

        // Check mitigation
        let current_price = *closes.last().unwrap_or(&0.0);
        for block in &mut blocks {
            if block.direction == "long" {
                block.mitigated = current_price <= block.low;
            } else {
                block.mitigated = current_price >= block.high;
            }
        }
        blocks
    }

    /// Detect fair value gaps (3-candle imbalance).
    fn detect_fair_value_gaps(
        &self,
        highs: Vec<f64>,
        lows: Vec<f64>,
    ) -> Vec<FairValueGap> {
        let len = highs.len();
        if len < 3 {
            return vec![];
        }
        let mut fvgs = Vec::new();
        let avg_range: f64 = highs
            .iter()
            .zip(lows.iter())
            .map(|(h, l)| (h - l).abs())
            .sum::<f64>()
            / len as f64;
        let min_gap = avg_range * self.fvg_min_gap_pct * 100.0;

        for i in 2..len {
            // Bullish FVG: candle 3's low > candle 1's high
            let gap_low = highs[i - 2];
            let gap_high = lows[i];
            if gap_high > gap_low && (gap_high - gap_low) > min_gap {
                fvgs.push(FairValueGap {
                    high: gap_high,
                    low: gap_low,
                    direction: "long".into(),
                    index: i - 1,
                    filled: false,
                });
            }

            // Bearish FVG: candle 1's low > candle 3's high
            let gap_low_b = lows[i - 2];
            let gap_high_b = highs[i];
            if gap_low_b > gap_high_b && (gap_low_b - gap_high_b) > min_gap {
                fvgs.push(FairValueGap {
                    high: gap_low_b,
                    low: gap_high_b,
                    direction: "short".into(),
                    index: i - 1,
                    filled: false,
                });
            }
        }

        // Check fill status
        let current_price = *highs.last().unwrap_or(&0.0);
        for fvg in &mut fvgs {
            if fvg.direction == "long" {
                fvg.filled = current_price <= fvg.low;
            } else {
                fvg.filled = current_price >= fvg.high;
            }
        }
        fvgs
    }

    /// Detect liquidity sweeps (stop hunts).
    fn detect_liquidity_sweeps(
        &self,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        lookback: usize,
    ) -> Vec<LiquiditySweep> {
        let len = closes.len();
        if len < lookback + 2 {
            return vec![];
        }
        let mut sweeps = Vec::new();
        let recent_highs = &highs[len - lookback..];
        let recent_lows = &lows[len - lookback..];

        let swing_high = recent_highs[..lookback - 1]
            .iter()
            .cloned()
            .fold(f64::NEG_INFINITY, f64::max);
        let swing_low = recent_lows[..lookback - 1]
            .iter()
            .cloned()
            .fold(f64::INFINITY, f64::min);

        // Sweep of highs (bearish — expect downward move)
        if highs[len - 1] > swing_high && closes[len - 1] < swing_high {
            sweeps.push(LiquiditySweep {
                level: swing_high,
                direction: "short".into(),
                index: len - 1,
                strength: 0.7,
            });
        }

        // Sweep of lows (bullish — expect upward move)
        if lows[len - 1] < swing_low && closes[len - 1] > swing_low {
            sweeps.push(LiquiditySweep {
                level: swing_low,
                direction: "long".into(),
                index: len - 1,
                strength: 0.7,
            });
        }
        sweeps
    }

    /// Full SMC analysis — combines OB, FVG, sweeps into bias.
    fn analyze(
        &self,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        atr: Vec<f64>,
    ) -> SmcAnalysis {
        let order_blocks = self.detect_order_blocks(opens, highs, lows, closes, atr);
        let fvgs = self.detect_fair_value_gaps(highs.clone(), lows.clone());
        let sweeps = self.detect_liquidity_sweeps(highs, lows, closes, 20);

        // Compute bullish/bearish scores
        let mut bullish_score = 0.0_f64;
        let mut bearish_score = 0.0_f64;
        let mut active_obs = 0usize;
        let mut active_fvgs = 0usize;

        for ob in &order_blocks {
            if !ob.mitigated {
                if ob.direction == "long" {
                    bullish_score += ob.strength;
                } else {
                    bearish_score += ob.strength;
                }
                active_obs += 1;
            }
        }
        for fvg in &fvgs {
            if !fvg.filled {
                if fvg.direction == "long" {
                    bullish_score += 0.5;
                } else {
                    bearish_score += 0.5;
                }
                active_fvgs += 1;
            }
        }
        for sweep in &sweeps {
            if sweep.direction == "long" {
                bullish_score += sweep.strength;
            } else {
                bearish_score += sweep.strength;
            }
        }

        let bias = if bullish_score > bearish_score * 1.2 {
            "long"
        } else if bearish_score > bullish_score * 1.2 {
            "short"
        } else {
            "flat"
        };

        SmcAnalysis {
            bias: bias.into(),
            order_blocks,
            fair_value_gaps: fvgs,
            liquidity_sweeps: sweeps,
            bullish_score,
            bearish_score,
            active_obs,
            active_fvgs,
        }
    }
}

// ---------------------------------------------------------------------------
// Signal Engine
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PySignalEngine;

// Default confluence weights — matches Python's DEFAULT_CONFLUENCE_WEIGHTS
const DEFAULT_WEIGHTS: [(&str, f64); 10] = [
    ("trend_alignment", 0.15),
    ("sr_proximity", 0.15),
    ("smc_confluence", 0.15),
    ("rsi_signal", 0.10),
    ("macd_signal", 0.10),
    ("bollinger_position", 0.08),
    ("volume_confirmation", 0.07),
    ("candlestick_pattern", 0.08),
    ("session_quality", 0.06),
    ("regime_fit", 0.06),
];

#[pymethods]
impl PySignalEngine {
    #[new]
    fn new() -> Self {
        Self
    }

    // -- Confluence Scoring -------------------------------------------------
    /// Score confluence from individual signal scores (each -1..+1).
    /// Returns weighted confluence score 0..100.
    #[pyo3(signature = (signals, weights=None))]
    fn confluence_score(signals: Vec<f64>, weights: Option<Vec<f64>>) -> f64 {
        let w = weights.unwrap_or_else(|| vec![1.0; signals.len()]);
        assert_eq!(signals.len(), w.len());
        let total_w: f64 = w.iter().sum();
        if total_w == 0.0 {
            return 0.0;
        }
        let score: f64 = signals
            .iter()
            .zip(w.iter())
            .map(|(s, wi)| s * wi)
            .sum::<f64>()
            / total_w;
        score.clamp(0.0, 1.0)
    }

    // -- Full 10-component confluence scoring -------------------------------
    /// Compute confluence from market data using all 10 weighted components.
    /// Returns (raw_score, score_0_100, direction, component_scores_json).
    fn compute_confluence(
        closes: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        opens: Vec<f64>,
        volumes: Vec<f64>,
        rsi_val: f64,
        macd_histogram: f64,
        bb_pct_b: f64,
        atr_val: f64,
        ema_9: f64,
        ema_21: f64,
        adx_val: f64,
        regime: String,
        session_quality: f64,
    ) -> ConfluenceResult {
        let current = *closes.last().unwrap_or(&0.0);
        let mut components: Vec<f64> = Vec::with_capacity(10);
        let mut component_names: Vec<String> = Vec::with_capacity(10);

        // 1. Trend alignment (EMA crossover)
        let trend_score = if !ema_9.is_nan() && !ema_21.is_nan() && ema_21 > 0.0 {
            let diff = (ema_9 - ema_21) / ema_21;
            (diff * 100.0).clamp(-1.0, 1.0)
        } else {
            0.0
        };
        components.push(trend_score);
        component_names.push("trend_alignment".into());

        // 2. S/R proximity (simplified — full version in Python uses detector)
        let sr_score = Self::sr_proximity_score(current, &highs, &lows);
        components.push(sr_score);
        component_names.push("sr_proximity".into());

        // 3. SMC confluence (passed from SMC detector)
        // Use a simplified inline version
        let smc_score = Self::smc_inline_score(&opens, &highs, &lows, &closes, atr_val);
        components.push(smc_score);
        component_names.push("smc_confluence".into());

        // 4. RSI signal
        let rsi_score = if rsi_val < 30.0 {
            (30.0 - rsi_val) / 30.0 // bullish (oversold)
        } else if rsi_val > 70.0 {
            -(rsi_val - 70.0) / 30.0 // bearish (overbought)
        } else {
            (rsi_val - 50.0) / 50.0 * 0.3
        };
        components.push(rsi_score.clamp(-1.0, 1.0));
        component_names.push("rsi_signal".into());

        // 5. MACD signal
        let macd_score = if current > 0.0 {
            (macd_histogram / (current * 0.001)).clamp(-1.0, 1.0)
        } else {
            0.0
        };
        components.push(macd_score);
        component_names.push("macd_signal".into());

        // 6. Bollinger position (mean reversion)
        let bb_score = if !bb_pct_b.is_nan() {
            (-(bb_pct_b - 0.5) * 2.0).clamp(-1.0, 1.0)
        } else {
            0.0
        };
        components.push(bb_score);
        component_names.push("bollinger_position".into());

        // 7. Volume confirmation
        let vol_score = if volumes.len() > 20 {
            let vol_sma: f64 = volumes[volumes.len() - 20..].iter().sum::<f64>() / 20.0;
            let vol_ratio = if vol_sma > 0.0 {
                volumes.last().unwrap_or(&0.0) / vol_sma
            } else {
                1.0
            };
            let price_dir = if closes.len() >= 2 {
                if closes[closes.len() - 1] > closes[closes.len() - 2] {
                    1.0
                } else {
                    -1.0
                }
            } else {
                0.0
            };
            (vol_ratio.min(3.0) / 3.0 * price_dir).clamp(-1.0, 1.0)
        } else {
            0.0
        };
        components.push(vol_score);
        component_names.push("volume_confirmation".into());

        // 8. Candlestick pattern
        let candle_score = Self::simple_candle_score(&opens, &highs, &lows, &closes);
        components.push(candle_score);
        component_names.push("candlestick_pattern".into());

        // 9. Session quality
        let session_score = (session_quality * 2.0 - 1.0).clamp(-1.0, 1.0);
        components.push(session_score);
        component_names.push("session_quality".into());

        // 10. Regime fit
        let regime_score = Self::regime_fit_score(&regime, rsi_val, atr_val);
        components.push(regime_score);
        component_names.push("regime_fit".into());

        // Weighted sum
        let weights: Vec<f64> = DEFAULT_WEIGHTS.iter().map(|(_, w)| *w).collect();
        let raw_score: f64 = components
            .iter()
            .zip(weights.iter())
            .map(|(s, w)| s * w)
            .sum();

        let direction = if raw_score > 0.05 {
            "long"
        } else if raw_score < -0.05 {
            "short"
        } else {
            "flat"
        };
        let score_100 = (raw_score.abs() * 100.0).min(100.0);

        ConfluenceResult {
            raw_score,
            score: score_100,
            direction: direction.into(),
            component_scores: components,
            component_names,
        }
    }

    // -- Structure Detection ------------------------------------------------
    #[pyo3(signature = (highs, lows, lookback=5))]
    fn detect_structure(highs: Vec<f64>, lows: Vec<f64>, lookback: usize) -> Vec<StructurePoint> {
        detect_market_structure(&highs, &lows, lookback)
    }

    // -- Multi-Timeframe Alignment -----------------------------------------
    fn multi_timeframe_alignment(scores: Vec<f64>, weights: Vec<f64>) -> f64 {
        assert_eq!(scores.len(), weights.len());
        let total_w: f64 = weights.iter().sum();
        if total_w == 0.0 {
            return 0.0;
        }
        let aligned: f64 = scores
            .iter()
            .zip(weights.iter())
            .map(|(s, w)| s * w)
            .sum::<f64>()
            / total_w;
        aligned.clamp(-1.0, 1.0)
    }

    // -- Support / Resistance Detection -------------------------------------
    #[pyo3(signature = (highs, lows, closes, tolerance_pct=0.002, min_touches=2))]
    fn detect_levels(
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        tolerance_pct: f64,
        min_touches: u32,
    ) -> Vec<Level> {
        detect_sr_levels(&highs, &lows, &closes, tolerance_pct, min_touches)
    }

    // -- Trend Bias ---------------------------------------------------------
    #[pyo3(signature = (highs, lows, lookback=5))]
    fn trend_bias(highs: Vec<f64>, lows: Vec<f64>, lookback: usize) -> f64 {
        let structures = detect_market_structure(&highs, &lows, lookback);
        let recent: Vec<_> = structures.iter().rev().take(10).collect();
        if recent.is_empty() {
            return 0.0;
        }
        let bullish = recent
            .iter()
            .filter(|s| s.kind == "HH" || s.kind == "HL")
            .count();
        let bearish = recent
            .iter()
            .filter(|s| s.kind == "LH" || s.kind == "LL")
            .count();
        let total = bullish + bearish;
        if total == 0 {
            return 0.0;
        }
        (bullish as f64 - bearish as f64) / total as f64
    }

    // -- Confidence Scoring -------------------------------------------------
    /// Compute signal confidence (0.0–1.0) using harmonic mean of quality factors.
    fn confidence_score(
        confluence_score: f64,
        component_scores: Vec<f64>,
        regime: String,
        session_quality: f64,
        data_quality: f64,
    ) -> f64 {
        compute_confidence(
            confluence_score,
            &component_scores,
            &regime,
            session_quality,
            data_quality,
        )
    }

    // -- Signal Generation --------------------------------------------------
    /// Generate a complete signal with entry/SL/TP levels.
    fn generate_signal(
        symbol: String,
        closes: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        opens: Vec<f64>,
        volumes: Vec<f64>,
        rsi_val: f64,
        macd_histogram: f64,
        bb_pct_b: f64,
        atr_val: f64,
        ema_9: f64,
        ema_21: f64,
        adx_val: f64,
        regime: String,
        session_quality: f64,
    ) -> GeneratedSignal {
        // Compute confluence
        let confluence = Self::compute_confluence(
            closes.clone(),
            highs.clone(),
            lows.clone(),
            opens,
            volumes.clone(),
            rsi_val,
            macd_histogram,
            bb_pct_b,
            atr_val,
            ema_9,
            ema_21,
            adx_val,
            regime.clone(),
            session_quality,
        );

        // Compute confidence
        let confidence = compute_confidence(
            confluence.score,
            &confluence.component_scores,
            &regime,
            session_quality,
            1.0,
        );

        let current_price = *closes.last().unwrap_or(&0.0);
        let safe_atr = if atr_val > 0.0 {
            atr_val
        } else {
            current_price * 0.01
        };

        // Entry/SL/TP
        let side = confluence.direction.clone();
        let sl_distance = safe_atr * 1.5;
        let (stop_loss, tp1, tp2, tp3) = match side.as_str() {
            "long" => (
                current_price - sl_distance,
                current_price + sl_distance * 1.5,
                current_price + sl_distance * 2.5,
                current_price + sl_distance * 4.0,
            ),
            "short" => (
                current_price + sl_distance,
                current_price - sl_distance * 1.5,
                current_price - sl_distance * 2.5,
                current_price - sl_distance * 4.0,
            ),
            _ => (current_price, 0.0, 0.0, 0.0),
        };

        let strength = (confluence.score / 80.0).min(1.0) * confidence;

        // SMC bias (simplified)
        let smc_score = Self::smc_inline_score(&closes, &highs, &lows, &closes, atr_val);
        let smc_bias = if smc_score > 0.1 {
            "long"
        } else if smc_score < -0.1 {
            "short"
        } else {
            "flat"
        };

        let reasoning = format!(
            "{} signal | confluence={:.1} | RSI={:.1} | ADX={:.1} | regime={} | SMC={}",
            if side == "long" { "Bullish" } else if side == "short" { "Bearish" } else { "No" },
            confluence.score,
            rsi_val,
            adx_val,
            regime,
            smc_bias,
        );

        GeneratedSignal {
            symbol,
            side,
            strength,
            confluence_score: confluence.score,
            confidence,
            entry_price: current_price,
            stop_loss,
            take_profit: vec![tp1, tp2, tp3],
            reasoning,
            regime,
            rsi: rsi_val,
            macd: macd_histogram,
            adx: adx_val,
            atr: atr_val,
            smc_bias: smc_bias.into(),
        }
    }
}

// ---------------------------------------------------------------------------
// Confluence result
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfluenceResult {
    #[pyo3(get)]
    pub raw_score: f64,
    #[pyo3(get)]
    pub score: f64,
    #[pyo3(get)]
    pub direction: String,
    #[pyo3(get)]
    pub component_scores: Vec<f64>,
    #[pyo3(get)]
    pub component_names: Vec<String>,
}

#[pymethods]
impl ConfluenceResult {
    fn __repr__(&self) -> String {
        format!(
            "Confluence(score={:.1}, dir={}, raw={:.4})",
            self.score, self.direction, self.raw_score
        )
    }

    /// Return top N contributing components by absolute value.
    fn top_components(&self, n: usize) -> Vec<(String, f64)> {
        let mut pairs: Vec<(String, f64)> = self
            .component_names
            .iter()
            .zip(self.component_scores.iter())
            .map(|(name, score)| (name.clone(), *score))
            .collect();
        pairs.sort_by(|a, b| b.1.abs().partial_cmp(&a.1.abs()).unwrap());
        pairs.into_iter().take(n).collect()
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

impl PySignalEngine {
    fn sr_proximity_score(current: f64, highs: &[f64], lows: &[f64]) -> f64 {
        // Find nearest support (recent lows) and resistance (recent highs)
        let lookback = 50.min(highs.len());
        if lookback == 0 || current <= 0.0 {
            return 0.0;
        }

        let recent_highs = &highs[highs.len() - lookback..];
        let recent_lows = &lows[lows.len() - lookback..];

        let mut nearest_support_dist = f64::MAX;
        let mut nearest_resistance_dist = f64::MAX;

        for &low in recent_lows {
            if low < current {
                let dist = (current - low) / current;
                if dist < nearest_support_dist {
                    nearest_support_dist = dist;
                }
            }
        }
        for &high in recent_highs {
            if high > current {
                let dist = (high - current) / current;
                if dist < nearest_resistance_dist {
                    nearest_resistance_dist = dist;
                }
            }
        }

        let support_factor = (1.0 - nearest_support_dist * 50.0).max(0.0);
        let resistance_factor = (1.0 - nearest_resistance_dist * 50.0).max(0.0);
        (support_factor - resistance_factor).clamp(-1.0, 1.0)
    }

    fn smc_inline_score(opens: &[f64], highs: &[f64], lows: &[f64], closes: &[f64], atr_val: f64) -> f64 {
        let len = closes.len();
        if len < 3 || atr_val <= 0.0 {
            return 0.0;
        }
        let threshold = atr_val * 1.5;
        let mut score = 0.0_f64;

        // Check last few candles for OB-like patterns
        let check_range = 5.min(len - 1);
        for i in (len - check_range - 1)..(len - 1) {
            let body_curr = closes[i] - opens[i];
            let move_next = closes[i + 1] - opens[i + 1];

            if body_curr < 0.0 && move_next > threshold {
                score += 0.3; // bullish OB
            } else if body_curr > 0.0 && move_next < -threshold {
                score -= 0.3; // bearish OB
            }
        }

        // Check for FVGs
        if len >= 3 {
            let i = len - 1;
            if lows[i] > highs[i - 2] {
                score += 0.2; // bullish FVG
            }
            if lows[i - 2] > highs[i] {
                score -= 0.2; // bearish FVG
            }
        }

        score.clamp(-1.0, 1.0)
    }

    fn simple_candle_score(opens: &[f64], highs: &[f64], lows: &[f64], closes: &[f64]) -> f64 {
        let len = closes.len();
        if len < 3 {
            return 0.0;
        }
        let mut score = 0.0_f64;
        let body = closes[len - 1] - opens[len - 1];
        let wick_range = highs[len - 1] - lows[len - 1];

        if wick_range > 0.0 {
            let body_ratio = body.abs() / wick_range;
            if body > 0.0 {
                score += body_ratio * 0.5;
            } else {
                score -= body_ratio * 0.5;
            }
        }

        // Engulfing
        if len >= 2 {
            let prev_body = closes[len - 2] - opens[len - 2];
            if body > 0.0 && prev_body < 0.0 && body.abs() > prev_body.abs() {
                score += 0.5; // bullish engulfing
            } else if body < 0.0 && prev_body > 0.0 && body.abs() > prev_body.abs() {
                score -= 0.5; // bearish engulfing
            }
        }

        score.clamp(-1.0, 1.0)
    }

    fn regime_fit_score(regime: &str, rsi: f64, atr_val: f64) -> f64 {
        match regime {
            "trending" => {
                if rsi > 55.0 || rsi < 45.0 {
                    0.5
                } else {
                    -0.2
                }
            }
            "ranging" => {
                if rsi > 40.0 && rsi < 60.0 {
                    0.5
                } else {
                    -0.2
                }
            }
            "volatile" => {
                if atr_val > 0.0 {
                    0.3
                } else {
                    0.0
                }
            }
            _ => 0.0,
        }
    }
}

fn detect_market_structure(highs: &[f64], lows: &[f64], lookback: usize) -> Vec<StructurePoint> {
    let len = highs.len();
    if len < lookback * 2 + 1 {
        return vec![];
    }
    let mut swings: Vec<StructurePoint> = Vec::new();

    for i in lookback..(len - lookback) {
        let is_high = (i - lookback..=i + lookback).all(|j| highs[j] <= highs[i]);
        let is_low = (i - lookback..=i + lookback).all(|j| lows[j] >= lows[i]);
        if is_high {
            swings.push(StructurePoint {
                index: i,
                price: highs[i],
                kind: "swing_high".into(),
            });
        }
        if is_low {
            swings.push(StructurePoint {
                index: i,
                price: lows[i],
                kind: "swing_low".into(),
            });
        }
    }

    let mut result = Vec::new();
    let mut last_high_price: Option<f64> = None;
    let mut last_low_price: Option<f64> = None;

    for sp in &swings {
        match sp.kind.as_str() {
            "swing_high" => {
                let kind = match last_high_price {
                    Some(prev) if sp.price > prev => "HH",
                    Some(_) => "LH",
                    None => "HH",
                };
                result.push(StructurePoint {
                    index: sp.index,
                    price: sp.price,
                    kind: kind.into(),
                });
                last_high_price = Some(sp.price);
            }
            "swing_low" => {
                let kind = match last_low_price {
                    Some(prev) if sp.price > prev => "HL",
                    Some(_) => "LL",
                    None => "HL",
                };
                result.push(StructurePoint {
                    index: sp.index,
                    price: sp.price,
                    kind: kind.into(),
                });
                last_low_price = Some(sp.price);
            }
            _ => {}
        }
    }
    result
}

fn detect_sr_levels(
    highs: &[f64],
    lows: &[f64],
    closes: &[f64],
    tolerance_pct: f64,
    min_touches: u32,
) -> Vec<Level> {
    let mut all_prices: Vec<f64> = Vec::new();
    all_prices.extend_from_slice(highs);
    all_prices.extend_from_slice(lows);
    all_prices.extend_from_slice(closes);
    all_prices.sort_by(|a, b| a.partial_cmp(b).unwrap());

    if all_prices.is_empty() {
        return vec![];
    }

    // Cluster nearby prices
    let mut clusters: Vec<Vec<f64>> = Vec::new();
    let mut current_cluster: Vec<f64> = vec![all_prices[0]];

    for &p in &all_prices[1..] {
        let base = current_cluster[0];
        if base > 0.0 && (p - base).abs() / base <= tolerance_pct {
            current_cluster.push(p);
        } else {
            clusters.push(current_cluster);
            current_cluster = vec![p];
        }
    }
    clusters.push(current_cluster);

    let current_price = *closes.last().unwrap_or(&0.0);
    let total_prices = all_prices.len() as f64;
    let mut levels: Vec<Level> = Vec::new();

    for cluster in &clusters {
        let touches = cluster.len() as u32;
        if touches < min_touches {
            continue;
        }
        let avg_price: f64 = cluster.iter().sum::<f64>() / touches as f64;
        let strength = (touches as f64 / total_prices).min(1.0);
        let kind = if avg_price < current_price {
            "support"
        } else {
            "resistance"
        };
        levels.push(Level {
            price: avg_price,
            strength,
            kind: kind.into(),
            touches,
            last_test_index: -1,
        });
    }

    levels.sort_by(|a, b| b.strength.partial_cmp(&a.strength).unwrap());
    levels
}

fn compute_confidence(
    confluence_score: f64,
    component_scores: &[f64],
    regime: &str,
    session_quality: f64,
    data_quality: f64,
) -> f64 {
    let mut factors: Vec<f64> = Vec::new();

    // 1. Confluence strength
    factors.push((confluence_score / 80.0).min(1.0));

    // 2. Component agreement
    if !component_scores.is_empty() {
        let positive = component_scores.iter().filter(|&&v| v > 0.1).count();
        let negative = component_scores.iter().filter(|&&v| v < -0.1).count();
        let total = component_scores.len();
        let agreement = positive.max(negative) as f64 / total.max(1) as f64;
        factors.push(agreement);
    } else {
        factors.push(0.5);
    }

    // 3. Regime clarity
    let regime_factor = match regime {
        "trending" => 0.8,
        "ranging" => 0.6,
        "volatile" => 0.4,
        _ => 0.3,
    };
    factors.push(regime_factor);

    // 4. Session quality
    factors.push(session_quality);

    // 5. Data quality
    factors.push(data_quality);

    // Harmonic mean (penalizes low factors)
    let n = factors.len() as f64;
    let harmonic = n / factors.iter().map(|f| 1.0 / f.max(0.01)).sum::<f64>();
    harmonic.min(1.0)
}
