//! Backtesting Engine — high-speed historical replay, trade simulation,
//! performance metrics, and walk-forward optimization.
//!
//! Aligned with Python's strategy pipeline for backtesting integration.
//! Enhanced metrics: Sharpe, Sortino, Calmar, recovery factor, max drawdown,
//! profit factor, win rate, and full equity curve.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyBacktestResult {
    #[pyo3(get)]
    pub total_trades: u64,
    #[pyo3(get)]
    pub winning_trades: u64,
    #[pyo3(get)]
    pub losing_trades: u64,
    #[pyo3(get)]
    pub win_rate: f64,
    #[pyo3(get)]
    pub total_pnl: f64,
    #[pyo3(get)]
    pub avg_win: f64,
    #[pyo3(get)]
    pub avg_loss: f64,
    #[pyo3(get)]
    pub profit_factor: f64,
    #[pyo3(get)]
    pub sharpe_ratio: f64,
    #[pyo3(get)]
    pub sortino_ratio: f64,
    #[pyo3(get)]
    pub calmar_ratio: f64,
    #[pyo3(get)]
    pub recovery_factor: f64,
    #[pyo3(get)]
    pub max_drawdown_pct: f64,
    #[pyo3(get)]
    pub max_drawdown_duration: usize,
    #[pyo3(get)]
    pub avg_trade_duration: f64,
    #[pyo3(get)]
    pub expectancy: f64,
    #[pyo3(get)]
    pub equity_curve: Vec<f64>,
    #[pyo3(get)]
    pub trade_log: Vec<TradeRecord>,
    #[pyo3(get)]
    pub drawdown_curve: Vec<f64>,
}

#[pymethods]
impl PyBacktestResult {
    fn __repr__(&self) -> String {
        format!(
            "BacktestResult(trades={}, win_rate={:.1}%, pnl={:.2}, sharpe={:.2}, sortino={:.2}, max_dd={:.1}%)",
            self.total_trades,
            self.win_rate * 100.0,
            self.total_pnl,
            self.sharpe_ratio,
            self.sortino_ratio,
            self.max_drawdown_pct * 100.0
        )
    }

    /// Summary dict for serialization.
    fn summary(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        dict.set_item("total_trades", self.total_trades)?;
        dict.set_item("win_rate", self.win_rate)?;
        dict.set_item("total_pnl", self.total_pnl)?;
        dict.set_item("profit_factor", self.profit_factor)?;
        dict.set_item("sharpe_ratio", self.sharpe_ratio)?;
        dict.set_item("sortino_ratio", self.sortino_ratio)?;
        dict.set_item("calmar_ratio", self.calmar_ratio)?;
        dict.set_item("recovery_factor", self.recovery_factor)?;
        dict.set_item("max_drawdown_pct", self.max_drawdown_pct)?;
        dict.set_item("max_drawdown_duration", self.max_drawdown_duration)?;
        dict.set_item("avg_trade_duration", self.avg_trade_duration)?;
        dict.set_item("expectancy", self.expectancy)?;
        Ok(dict.into())
    }
}

#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeRecord {
    #[pyo3(get)]
    pub entry_ts: i64,
    #[pyo3(get)]
    pub exit_ts: i64,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    pub entry_price: f64,
    #[pyo3(get)]
    pub exit_price: f64,
    #[pyo3(get)]
    pub quantity: f64,
    #[pyo3(get)]
    pub pnl: f64,
    #[pyo3(get)]
    pub fees: f64,
    #[pyo3(get)]
    pub duration_bars: usize,
    #[pyo3(get)]
    pub max_favorable_excursion: f64,
    #[pyo3(get)]
    pub max_adverse_excursion: f64,
}

// ---------------------------------------------------------------------------
// Backtest Engine
// ---------------------------------------------------------------------------

#[pyclass]
pub struct PyBacktestEngine {
    initial_capital: f64,
    fee_rate: f64,
    slippage_pct: f64,
    risk_free_rate: f64,
}

#[pymethods]
impl PyBacktestEngine {
    #[new]
    #[pyo3(signature = (initial_capital=10000.0, fee_rate=0.001, slippage_pct=0.0005, risk_free_rate=0.0))]
    fn new(initial_capital: f64, fee_rate: f64, slippage_pct: f64, risk_free_rate: f64) -> Self {
        Self {
            initial_capital,
            fee_rate,
            slippage_pct,
            risk_free_rate,
        }
    }

    /// Run a backtest using a Python signal callback.
    ///
    /// The callback receives (index, high, low, open, close) and returns:
    ///   1 = go long, -1 = go short, 0 = hold, 2 = close position
    fn run_backtest(
        &self,
        py: Python<'_>,
        signal_fn: PyObject,
        timestamps: Vec<i64>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        volumes: Vec<f64>,
    ) -> PyResult<PyBacktestResult> {
        let len = closes.len();
        let mut capital = self.initial_capital;
        let mut equity_curve = Vec::with_capacity(len);
        let mut trade_log: Vec<TradeRecord> = Vec::new();

        // Position state
        let mut pos_side: i32 = 0; // 0=flat, 1=long, -1=short
        let mut pos_entry_price = 0.0_f64;
        let mut pos_entry_ts: i64 = 0;
        let mut pos_entry_idx: usize = 0;
        let mut pos_qty = 0.0_f64;
        let mut pos_mfe = 0.0_f64; // max favorable excursion
        let mut pos_mae = 0.0_f64; // max adverse excursion

        for i in 0..len {
            // Call Python signal function
            let signal: i32 = signal_fn
                .call1(py, (i, highs[i], lows[i], opens[i], closes[i]))?
                .extract(py)?;

            // Update MFE/MAE for open position
            if pos_side != 0 {
                let unrealized = if pos_side == 1 {
                    (closes[i] - pos_entry_price) * pos_qty
                } else {
                    (pos_entry_price - closes[i]) * pos_qty
                };
                if unrealized > pos_mfe {
                    pos_mfe = unrealized;
                }
                if unrealized < -pos_mae {
                    pos_mae = -unrealized;
                }
            }

            // Handle signals
            if signal == 1 && pos_side == 0 {
                // Enter long
                let price = closes[i] * (1.0 + self.slippage_pct);
                let fees = capital * self.fee_rate;
                pos_qty = (capital - fees) / price;
                pos_entry_price = price;
                pos_entry_ts = timestamps[i];
                pos_entry_idx = i;
                pos_side = 1;
                pos_mfe = 0.0;
                pos_mae = 0.0;
                capital -= fees;
            } else if signal == -1 && pos_side == 0 {
                // Enter short
                let price = closes[i] * (1.0 - self.slippage_pct);
                let fees = capital * self.fee_rate;
                pos_qty = capital / price;
                pos_entry_price = price;
                pos_entry_ts = timestamps[i];
                pos_entry_idx = i;
                pos_side = -1;
                pos_mfe = 0.0;
                pos_mae = 0.0;
                capital -= fees;
            } else if signal == 2 && pos_side != 0 {
                // Close position
                let price = if pos_side == 1 {
                    closes[i] * (1.0 - self.slippage_pct)
                } else {
                    closes[i] * (1.0 + self.slippage_pct)
                };
                let pnl = if pos_side == 1 {
                    (price - pos_entry_price) * pos_qty
                } else {
                    (pos_entry_price - price) * pos_qty
                };
                let fees = pos_qty * price * self.fee_rate;
                capital += pnl - fees;

                trade_log.push(TradeRecord {
                    entry_ts: pos_entry_ts,
                    exit_ts: timestamps[i],
                    side: if pos_side == 1 {
                        "long".into()
                    } else {
                        "short".into()
                    },
                    entry_price: pos_entry_price,
                    exit_price: price,
                    quantity: pos_qty,
                    pnl,
                    fees,
                    duration_bars: i - pos_entry_idx,
                    max_favorable_excursion: pos_mfe,
                    max_adverse_excursion: pos_mae,
                });

                pos_side = 0;
                pos_qty = 0.0;
            }

            // Mark-to-market equity
            let mtm = if pos_side == 1 {
                capital + pos_qty * closes[i]
            } else if pos_side == -1 {
                capital + pos_qty * (2.0 * pos_entry_price - closes[i])
            } else {
                capital
            };
            equity_curve.push(mtm);
        }

        // Close any remaining position at last close
        if pos_side != 0 {
            let price = closes[len - 1];
            let pnl = if pos_side == 1 {
                (price - pos_entry_price) * pos_qty
            } else {
                (pos_entry_price - price) * pos_qty
            };
            let fees = pos_qty * price * self.fee_rate;
            capital += pnl - fees;
            equity_curve[len - 1] = capital;

            trade_log.push(TradeRecord {
                entry_ts: pos_entry_ts,
                exit_ts: timestamps[len - 1],
                side: if pos_side == 1 {
                    "long".into()
                } else {
                    "short".into()
                },
                entry_price: pos_entry_price,
                exit_price: price,
                quantity: pos_qty,
                pnl,
                fees,
                duration_bars: len - 1 - pos_entry_idx,
                max_favorable_excursion: pos_mfe,
                max_adverse_excursion: pos_mae,
            });
        }

        Ok(self.compute_result(&equity_curve, &trade_log))
    }

    /// Walk-forward optimization: splits data into in-sample/out-of-sample
    /// windows and runs backtest on each.
    fn walk_forward(
        &self,
        py: Python<'_>,
        signal_fn: PyObject,
        timestamps: Vec<i64>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        volumes: Vec<f64>,
        in_sample_pct: f64,
        n_windows: usize,
    ) -> PyResult<Vec<PyBacktestResult>> {
        let len = closes.len();
        let window_size = len / n_windows;
        let in_sample_size = (window_size as f64 * in_sample_pct) as usize;
        let mut results = Vec::with_capacity(n_windows);

        for w in 0..n_windows {
            let start = w * window_size;
            let end = (start + window_size).min(len);
            let oos_start = (start + in_sample_size).min(end);
            if oos_start >= end {
                continue;
            }

            let result = self.run_backtest(
                py,
                signal_fn.clone_ref(py),
                timestamps[oos_start..end].to_vec(),
                opens[oos_start..end].to_vec(),
                highs[oos_start..end].to_vec(),
                lows[oos_start..end].to_vec(),
                closes[oos_start..end].to_vec(),
                volumes[oos_start..end].to_vec(),
            )?;
            results.push(result);
        }
        Ok(results)
    }

    /// Run backtest with regime-aware signal callback.
    ///
    /// The callback receives (index, high, low, open, close, regime_string) and returns signal.
    /// Regime is precomputed from the data using simple heuristics.
    fn run_regime_aware_backtest(
        &self,
        py: Python<'_>,
        signal_fn: PyObject,
        timestamps: Vec<i64>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
        volumes: Vec<f64>,
        regime_window: usize,
    ) -> PyResult<PyBacktestResult> {
        // Precompute regimes
        let regimes = compute_regimes(&closes, &highs, &lows, regime_window);

        let len = closes.len();
        let mut capital = self.initial_capital;
        let mut equity_curve = Vec::with_capacity(len);
        let mut trade_log: Vec<TradeRecord> = Vec::new();

        let mut pos_side: i32 = 0;
        let mut pos_entry_price = 0.0_f64;
        let mut pos_entry_ts: i64 = 0;
        let mut pos_entry_idx: usize = 0;
        let mut pos_qty = 0.0_f64;
        let mut pos_mfe = 0.0_f64;
        let mut pos_mae = 0.0_f64;

        for i in 0..len {
            let signal: i32 = signal_fn
                .call1(py, (i, highs[i], lows[i], opens[i], closes[i], &regimes[i]))?
                .extract(py)?;

            // Update MFE/MAE
            if pos_side != 0 {
                let unrealized = if pos_side == 1 {
                    (closes[i] - pos_entry_price) * pos_qty
                } else {
                    (pos_entry_price - closes[i]) * pos_qty
                };
                if unrealized > pos_mfe {
                    pos_mfe = unrealized;
                }
                if unrealized < -pos_mae {
                    pos_mae = -unrealized;
                }
            }

            if signal == 1 && pos_side == 0 {
                let price = closes[i] * (1.0 + self.slippage_pct);
                let fees = capital * self.fee_rate;
                pos_qty = (capital - fees) / price;
                pos_entry_price = price;
                pos_entry_ts = timestamps[i];
                pos_entry_idx = i;
                pos_side = 1;
                pos_mfe = 0.0;
                pos_mae = 0.0;
                capital -= fees;
            } else if signal == -1 && pos_side == 0 {
                let price = closes[i] * (1.0 - self.slippage_pct);
                let fees = capital * self.fee_rate;
                pos_qty = capital / price;
                pos_entry_price = price;
                pos_entry_ts = timestamps[i];
                pos_entry_idx = i;
                pos_side = -1;
                pos_mfe = 0.0;
                pos_mae = 0.0;
                capital -= fees;
            } else if signal == 2 && pos_side != 0 {
                let price = if pos_side == 1 {
                    closes[i] * (1.0 - self.slippage_pct)
                } else {
                    closes[i] * (1.0 + self.slippage_pct)
                };
                let pnl = if pos_side == 1 {
                    (price - pos_entry_price) * pos_qty
                } else {
                    (pos_entry_price - price) * pos_qty
                };
                let fees = pos_qty * price * self.fee_rate;
                capital += pnl - fees;

                trade_log.push(TradeRecord {
                    entry_ts: pos_entry_ts,
                    exit_ts: timestamps[i],
                    side: if pos_side == 1 {
                        "long".into()
                    } else {
                        "short".into()
                    },
                    entry_price: pos_entry_price,
                    exit_price: price,
                    quantity: pos_qty,
                    pnl,
                    fees,
                    duration_bars: i - pos_entry_idx,
                    max_favorable_excursion: pos_mfe,
                    max_adverse_excursion: pos_mae,
                });
                pos_side = 0;
                pos_qty = 0.0;
            }

            let mtm = if pos_side == 1 {
                capital + pos_qty * closes[i]
            } else if pos_side == -1 {
                capital + pos_qty * (2.0 * pos_entry_price - closes[i])
            } else {
                capital
            };
            equity_curve.push(mtm);
        }

        if pos_side != 0 {
            let price = closes[len - 1];
            let pnl = if pos_side == 1 {
                (price - pos_entry_price) * pos_qty
            } else {
                (pos_entry_price - price) * pos_qty
            };
            let fees = pos_qty * price * self.fee_rate;
            capital += pnl - fees;
            equity_curve[len - 1] = capital;
            trade_log.push(TradeRecord {
                entry_ts: pos_entry_ts,
                exit_ts: timestamps[len - 1],
                side: if pos_side == 1 {
                    "long".into()
                } else {
                    "short".into()
                },
                entry_price: pos_entry_price,
                exit_price: price,
                quantity: pos_qty,
                pnl,
                fees,
                duration_bars: len - 1 - pos_entry_idx,
                max_favorable_excursion: pos_mfe,
                max_adverse_excursion: pos_mae,
            });
        }

        Ok(self.compute_result(&equity_curve, &trade_log))
    }
}

impl PyBacktestEngine {
    fn compute_result(&self, equity_curve: &[f64], trade_log: &[TradeRecord]) -> PyBacktestResult {
        let total_trades = trade_log.len() as u64;
        let winners: Vec<&TradeRecord> = trade_log.iter().filter(|t| t.pnl > 0.0).collect();
        let losers: Vec<&TradeRecord> = trade_log.iter().filter(|t| t.pnl <= 0.0).collect();
        let winning_trades = winners.len() as u64;
        let losing_trades = losers.len() as u64;
        let win_rate = if total_trades > 0 {
            winning_trades as f64 / total_trades as f64
        } else {
            0.0
        };
        let total_pnl: f64 = trade_log.iter().map(|t| t.pnl).sum();
        let avg_win = if !winners.is_empty() {
            winners.iter().map(|t| t.pnl).sum::<f64>() / winners.len() as f64
        } else {
            0.0
        };
        let avg_loss = if !losers.is_empty() {
            losers.iter().map(|t| t.pnl).sum::<f64>() / losers.len() as f64
        } else {
            0.0
        };
        let gross_profit: f64 = winners.iter().map(|t| t.pnl).sum();
        let gross_loss: f64 = losers.iter().map(|t| t.pnl.abs()).sum();
        let profit_factor = if gross_loss != 0.0 {
            gross_profit / gross_loss
        } else {
            f64::INFINITY
        };

        // Returns
        let returns: Vec<f64> = (1..equity_curve.len())
            .map(|i| {
                if equity_curve[i - 1] != 0.0 {
                    (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
                } else {
                    0.0
                }
            })
            .collect();

        let sharpe = compute_sharpe(&returns, self.risk_free_rate);
        let sortino = compute_sortino(&returns, self.risk_free_rate);

        // Drawdown
        let (dd_curve, max_dd, _, max_dd_dur) = compute_drawdown(equity_curve);

        // Calmar ratio = annualized return / max drawdown
        let total_return = if self.initial_capital > 0.0 {
            (equity_curve.last().unwrap_or(&self.initial_capital) - self.initial_capital)
                / self.initial_capital
        } else {
            0.0
        };
        let n_periods = equity_curve.len() as f64;
        let annualized_return = if n_periods > 0.0 {
            (1.0 + total_return).powf(252.0 / n_periods) - 1.0
        } else {
            0.0
        };
        let calmar = if max_dd > 0.0 {
            annualized_return / max_dd
        } else {
            f64::INFINITY
        };

        // Recovery factor = total pnl / max drawdown in dollars
        let max_dd_dollars = dd_curve
            .iter()
            .enumerate()
            .map(|(i, &dd)| dd * equity_curve[i])
            .fold(0.0_f64, f64::max);
        let recovery_factor = if max_dd_dollars > 0.0 {
            total_pnl / max_dd_dollars
        } else {
            f64::INFINITY
        };

        // Average trade duration
        let avg_trade_duration = if !trade_log.is_empty() {
            trade_log.iter().map(|t| t.duration_bars as f64).sum::<f64>()
                / trade_log.len() as f64
        } else {
            0.0
        };

        // Expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        let expectancy = win_rate * avg_win + (1.0 - win_rate) * avg_loss;

        PyBacktestResult {
            total_trades,
            winning_trades,
            losing_trades,
            win_rate,
            total_pnl,
            avg_win,
            avg_loss,
            profit_factor,
            sharpe_ratio: sharpe,
            sortino_ratio: sortino,
            calmar_ratio: calmar,
            recovery_factor,
            max_drawdown_pct: max_dd,
            max_drawdown_duration: max_dd_dur,
            avg_trade_duration,
            expectancy,
            equity_curve: equity_curve.to_vec(),
            trade_log: trade_log.to_vec(),
            drawdown_curve: dd_curve,
        }
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn compute_sharpe(returns: &[f64], risk_free_rate: f64) -> f64 {
    let n = returns.len() as f64;
    if n == 0.0 {
        return 0.0;
    }
    let mean = returns.iter().sum::<f64>() / n;
    let var: f64 = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / n;
    let std = var.sqrt();
    if std == 0.0 {
        return 0.0;
    }
    (mean - risk_free_rate) / std * 252.0_f64.sqrt() // annualized
}

fn compute_sortino(returns: &[f64], risk_free_rate: f64) -> f64 {
    let n = returns.len() as f64;
    if n == 0.0 {
        return 0.0;
    }
    let mean = returns.iter().sum::<f64>() / n;
    let downside_var: f64 = returns
        .iter()
        .filter(|&&r| r < 0.0)
        .map(|r| r.powi(2))
        .sum::<f64>()
        / n;
    let downside_std = downside_var.sqrt();
    if downside_std == 0.0 {
        return 0.0;
    }
    (mean - risk_free_rate) / downside_std * 252.0_f64.sqrt()
}

fn compute_drawdown(equity: &[f64]) -> (Vec<f64>, f64, usize, usize) {
    let len = equity.len();
    let mut dd = vec![0.0; len];
    let mut peak = equity[0];
    let mut max_dd = 0.0_f64;
    let mut current_dur: usize = 0;
    let mut max_dur: usize = 0;

    for i in 0..len {
        if equity[i] > peak {
            peak = equity[i];
            if current_dur > max_dur {
                max_dur = current_dur;
            }
            current_dur = 0;
        } else {
            dd[i] = if peak > 0.0 {
                (peak - equity[i]) / peak
            } else {
                0.0
            };
            current_dur += 1;
        }
        if dd[i] > max_dd {
            max_dd = dd[i];
        }
    }
    if current_dur > max_dur {
        max_dur = current_dur;
    }
    (dd, max_dd, current_dur, max_dur)
}

/// Simple regime detection using ADX-like measure.
fn compute_regimes(closes: &[f64], highs: &[f64], lows: &[f64], window: usize) -> Vec<String> {
    let len = closes.len();
    let mut regimes = vec!["unknown".to_string(); len];

    for i in window..len {
        let w = &closes[i - window..=i];
        let mean: f64 = w.iter().sum::<f64>() / window as f64;
        let var: f64 = w.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / window as f64;
        let std = var.sqrt();
        let cv = if mean > 0.0 { std / mean } else { 0.0 };

        // Average true range ratio
        let atr_ratio = if i > 0 {
            let tr: f64 = (highs[i] - lows[i]).max((highs[i] - closes[i - 1]).abs()).max((lows[i] - closes[i - 1]).abs());
            if closes[i] > 0.0 { tr / closes[i] } else { 0.0 }
        } else {
            0.0
        };

        // Trend detection: price direction consistency
        let up_count = (1..=window)
            .filter(|&j| closes[i - j + 1] > closes[i - j])
            .count();
        let trend_strength = (up_count as f64 / window as f64 - 0.5).abs() * 2.0;

        if atr_ratio > 0.02 || cv > 0.03 {
            regimes[i] = "volatile".to_string();
        } else if trend_strength > 0.65 {
            regimes[i] = "trending".to_string();
        } else {
            regimes[i] = "ranging".to_string();
        }
    }
    regimes
}
