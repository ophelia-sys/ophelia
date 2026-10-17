//! Deterministic high-performance mathematical kernel for Ophelia.
//!
//! Layer: crates/ophelia_math
//! Contract:
//! - Pure deterministic numerical computation: VWAP, CVD, RVOL, ATR, FVG,
//!   swings, market structure, displacement, breakout, retest, structural stops/targets,
//!   and position sizing.
//! - Zero lookahead, zero hidden state, no IO, strictly causal.
//! - Identical numerical outputs to Ophelia's Python mathematical contract.

use pyo3::prelude::*;

/// Causal Average True Range (ATR) calculated on confirmed closed candle series.
#[pyfunction]
#[pyo3(signature = (highs, lows, closes, period=14))]
pub fn calculate_atr(
    highs: Vec<f64>,
    lows: Vec<f64>,
    closes: Vec<f64>,
    period: usize,
) -> Vec<f64> {
    let n = closes.len();
    if n < 2 || highs.len() != n || lows.len() != n || period == 0 {
        return vec![0.0; n];
    }

    let mut tr = Vec::with_capacity(n);
    tr.push(highs[0] - lows[0]);
    for i in 1..n {
        let hl = highs[i] - lows[i];
        let hc = (highs[i] - closes[i - 1]).abs();
        let lc = (lows[i] - closes[i - 1]).abs();
        let max_val = hl.max(hc).max(lc);
        tr.push(max_val);
    }

    let mut atr = vec![0.0; n];
    if n < period {
        let mean_tr: f64 = tr.iter().sum::<f64>() / (n as f64);
        return vec![mean_tr; n];
    }

    let first_sum: f64 = tr[..period].iter().sum();
    let initial_atr = first_sum / (period as f64);
    atr[period - 1] = initial_atr;

    let p_f64 = period as f64;
    for i in period..n {
        atr[i] = (atr[i - 1] * (p_f64 - 1.0) + tr[i]) / p_f64;
    }

    // Backfill indices prior to period - 1 with initial_atr
    for i in 0..(period - 1) {
        atr[i] = initial_atr;
    }

    atr
}

/// Causal Relative Volume (RVOL) of the latest candle compared to rolling baseline.
#[pyfunction]
#[pyo3(signature = (volumes, period=20))]
pub fn calculate_rvol(volumes: Vec<f64>, period: usize) -> f64 {
    let n = volumes.len();
    if n < period + 1 || period == 0 {
        return 1.0;
    }
    let baseline_slice = &volumes[(n - period - 1)..(n - 1)];
    let sum: f64 = baseline_slice.iter().sum();
    let baseline = sum / (period as f64);
    if baseline <= 1e-9 {
        return 1.0;
    }
    let cur_vol = volumes[n - 1];
    ((cur_vol / baseline) * 100.0).round() / 100.0
}

/// Causal Cumulative Volume Delta (CVD) series from taker buy and total volumes.
#[pyfunction]
#[pyo3(signature = (volumes, taker_buys, opens, closes))]
pub fn calculate_cvd_series(
    volumes: Vec<f64>,
    taker_buys: Vec<f64>,
    opens: Vec<f64>,
    closes: Vec<f64>,
) -> Vec<f64> {
    let n = volumes.len();
    let mut cvd = 0.0;
    let mut result = Vec::with_capacity(n);

    for i in 0..n {
        let vol = volumes.get(i).copied().unwrap_or(0.0);
        let tb = taker_buys.get(i).copied().unwrap_or(0.0);
        let delta = if tb > 0.0 {
            let ts = (vol - tb).max(0.0);
            tb - ts
        } else {
            let c = closes.get(i).copied().unwrap_or(0.0);
            let o = opens.get(i).copied().unwrap_or(0.0);
            if c >= o { vol } else { -vol }
        };
        cvd += delta;
        result.push(cvd);
    }
    result
}

/// Causal Volume Weighted Average Price (VWAP) series.
#[pyfunction]
#[pyo3(signature = (highs, lows, closes, volumes))]
pub fn calculate_vwap_series(
    highs: Vec<f64>,
    lows: Vec<f64>,
    closes: Vec<f64>,
    volumes: Vec<f64>,
) -> Vec<f64> {
    let n = closes.len();
    let mut cum_tp_vol = 0.0;
    let mut cum_vol = 0.0;
    let mut result = Vec::with_capacity(n);

    for i in 0..n {
        let h = highs.get(i).copied().unwrap_or(0.0);
        let l = lows.get(i).copied().unwrap_or(0.0);
        let c = closes.get(i).copied().unwrap_or(0.0);
        let v = volumes.get(i).copied().unwrap_or(0.0);

        let tp = (h + l + c) / 3.0;
        cum_tp_vol += tp * v;
        cum_vol += v;

        let vwap = if cum_vol > 1e-9 {
            cum_tp_vol / cum_vol
        } else {
            c
        };
        result.push(vwap);
    }
    result
}

/// Detect causal swing highs and lows strictly requiring confirmed lookback candles on both sides.
#[pyfunction]
#[pyo3(signature = (highs, lows, lookback=5))]
pub fn detect_swings(
    highs: Vec<f64>,
    lows: Vec<f64>,
    lookback: usize,
) -> (Vec<(usize, f64)>, Vec<(usize, f64)>) {
    let n = highs.len();
    let mut swing_highs = Vec::new();
    let mut swing_lows = Vec::new();

    if n < lookback * 2 + 1 || lows.len() != n || lookback == 0 {
        return (swing_highs, swing_lows);
    }

    for i in lookback..(n - lookback) {
        let mut is_high = true;
        for j in (i - lookback)..=(i + lookback) {
            if j != i && highs[j] > highs[i] {
                is_high = false;
                break;
            }
        }
        if is_high {
            swing_highs.push((i, highs[i]));
        }

        let mut is_low = true;
        for j in (i - lookback)..=(i + lookback) {
            if j != i && lows[j] < lows[i] {
                is_low = false;
                break;
            }
        }
        if is_low {
            swing_lows.push((i, lows[i]));
        }
    }


    (swing_highs, swing_lows)
}

/// Detect Fair Value Gaps (FVG) across candle series.
/// Returns (index, fvg_type, gap_low, gap_high, size_pct).
#[pyfunction]
#[pyo3(signature = (highs, lows, closes, threshold_pct=0.001))]
pub fn detect_fvg(
    highs: Vec<f64>,
    lows: Vec<f64>,
    closes: Vec<f64>,
    threshold_pct: f64,
) -> Vec<(usize, String, f64, f64, f64)> {
    let n = closes.len();
    let mut fvgs = Vec::new();
    if n < 3 {
        return fvgs;
    }

    for i in 2..n {
        let px = closes[i];
        if px <= 0.0 {
            continue;
        }

        // Bullish FVG: Low of candle i > High of candle i-2
        if lows[i] > highs[i - 2] {
            let gap_size = lows[i] - highs[i - 2];
            let size_pct = gap_size / px;
            if size_pct >= threshold_pct {
                fvgs.push((i, "BULLISH_FVG".to_string(), highs[i - 2], lows[i], size_pct));
            }
        }
        // Bearish FVG: High of candle i < Low of candle i-2
        else if highs[i] < lows[i - 2] {
            let gap_size = lows[i - 2] - highs[i];
            let size_pct = gap_size / px;
            if size_pct >= threshold_pct {
                fvgs.push((i, "BEARISH_FVG".to_string(), highs[i], lows[i - 2], size_pct));
            }
        }
    }
    fvgs
}

/// Evaluate candle displacement against causal ATR.
#[pyfunction]
#[pyo3(signature = (opens, highs, lows, closes, atrs, atr_multiplier=1.2))]
pub fn evaluate_displacement(
    opens: Vec<f64>,
    highs: Vec<f64>,
    lows: Vec<f64>,
    closes: Vec<f64>,
    atrs: Vec<f64>,
    atr_multiplier: f64,
) -> Vec<(bool, String, f64)> {
    let n = closes.len();
    let mut result = Vec::with_capacity(n);

    for i in 0..n {
        let o = opens[i];
        let h = highs[i];
        let l = lows[i];
        let c = closes[i];
        let atr = atrs.get(i).copied().unwrap_or(0.0);

        let body = (c - o).abs();
        let range = (h - l).max(1e-9);
        let body_ratio = body / range;

        let is_displaced = atr > 0.0 && body >= atr * atr_multiplier && body_ratio >= 0.55;
        let direction = if c >= o { "BULLISH" } else { "BEARISH" };
        let ratio = if atr > 0.0 { body / atr } else { 0.0 };

        result.push((is_displaced, direction.to_string(), ratio));
    }
    result
}

/// Calculate structural stop loss price and percentage distance.
#[pyfunction]
#[pyo3(signature = (direction, entry_price, swing_level, atr, buffer_mult=0.5, min_dist_pct=0.003, max_dist_pct=0.04))]
pub fn calculate_structural_stops(
    direction: &str,
    entry_price: f64,
    swing_level: f64,
    atr: f64,
    buffer_mult: f64,
    min_dist_pct: f64,
    max_dist_pct: f64,
) -> (f64, f64, String) {
    if entry_price <= 0.0 {
        return (0.0, 0.0, "INVALID_ENTRY".to_string());
    }

    let buffer = atr * buffer_mult;
    let (raw_sl, reason) = if direction == "LONG" {
        let base = if swing_level > 0.0 && swing_level < entry_price {
            swing_level
        } else {
            entry_price - atr * 1.5
        };
        (base - buffer, "STRUCTURAL_SWING_LOW_BUFFERED")
    } else {
        let base = if swing_level > 0.0 && swing_level > entry_price {
            swing_level
        } else {
            entry_price + atr * 1.5
        };
        (base + buffer, "STRUCTURAL_SWING_HIGH_BUFFERED")
    };

    let min_dist = entry_price * min_dist_pct;
    let max_dist = entry_price * max_dist_pct;

    let clamped_sl = if direction == "LONG" {
        let dist = (entry_price - raw_sl).clamp(min_dist, max_dist);
        entry_price - dist
    } else {
        let dist = (raw_sl - entry_price).clamp(min_dist, max_dist);
        entry_price + dist
    };

    let final_dist_pct = ((entry_price - clamped_sl).abs() / entry_price * 10000.0).round() / 100.0;
    (clamped_sl, final_dist_pct, reason.to_string())
}

/// Calculate structural take profit targets (TP1, TP2, TP3) from entry and stop loss.
#[pyfunction]
#[pyo3(signature = (direction, entry_price, sl_price, rr_targets=vec![1.5, 2.5, 4.0]))]
pub fn calculate_structural_targets(
    direction: &str,
    entry_price: f64,
    sl_price: f64,
    rr_targets: Vec<f64>,
) -> Vec<(f64, f64, f64)> {
    let risk = (entry_price - sl_price).abs();
    if entry_price <= 0.0 || risk <= 0.0 {
        return Vec::new();
    }

    let mut result = Vec::with_capacity(rr_targets.len());
    for rr in rr_targets {
        let target_price = if direction == "LONG" {
            entry_price + risk * rr
        } else {
            entry_price - risk * rr
        };
        let dist_pct = ((target_price - entry_price).abs() / entry_price * 10000.0).round() / 100.0;
        result.push((target_price, dist_pct, rr));
    }
    result
}

/// Calculate position sizing from equity, risk percent, entry, and stop loss.
#[pyfunction]
#[pyo3(signature = (equity_usdt, risk_pct, entry_price, sl_price, max_leverage=20.0))]
pub fn calculate_position_sizing(
    equity_usdt: f64,
    risk_pct: f64,
    entry_price: f64,
    sl_price: f64,
    max_leverage: f64,
) -> (f64, f64, f64, f64) {
    if equity_usdt <= 0.0 || entry_price <= 0.0 || sl_price <= 0.0 || entry_price == sl_price {
        return (0.0, 0.0, 0.0, 0.0);
    }

    let risk_usdt = equity_usdt * (risk_pct / 100.0);
    let sl_pct = (entry_price - sl_price).abs() / entry_price;
    if sl_pct <= 0.0 {
        return (0.0, 0.0, 0.0, 0.0);
    }

    // Required notional for desired dollar risk
    let mut notional = risk_usdt / sl_pct;
    let max_notional = equity_usdt * max_leverage;
    if notional > max_notional {
        notional = max_notional;
    }

    let quantity = notional / entry_price;
    let effective_leverage = notional / equity_usdt;
    let margin_allocated = notional / effective_leverage.max(1.0);

    (
        (quantity * 10000.0).round() / 10000.0,
        (notional * 100.0).round() / 100.0,
        (margin_allocated * 100.0).round() / 100.0,
        (effective_leverage * 10.0).round() / 10.0,
    )
}

/// PyO3 Module Definition
#[pymodule]
fn ophelia_math(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_atr, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_rvol, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_cvd_series, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_vwap_series, m)?)?;
    m.add_function(wrap_pyfunction!(detect_swings, m)?)?;
    m.add_function(wrap_pyfunction!(detect_fvg, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_displacement, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_structural_stops, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_structural_targets, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_position_sizing, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_atr_basic() {
        let highs = vec![10.0, 12.0, 11.0, 13.0, 15.0];
        let lows = vec![8.0, 9.0, 9.5, 10.0, 12.0];
        let closes = vec![9.0, 11.0, 10.0, 12.5, 14.0];
        let atr = calculate_atr(highs, lows, closes, 3);
        assert_eq!(atr.len(), 5);
        assert!(atr[4] > 0.0);
    }

    #[test]
    fn test_rvol_basic() {
        let mut vols = vec![100.0; 21];
        vols[20] = 250.0;
        let rvol = calculate_rvol(vols, 20);
        assert!((rvol - 2.5).abs() < 0.01);
    }

    #[test]
    fn test_cvd_series() {
        let vols = vec![10.0, 20.0];
        let tbs = vec![8.0, 5.0];
        let opens = vec![100.0, 101.0];
        let closes = vec![101.0, 100.5];
        let cvd = calculate_cvd_series(vols, tbs, opens, closes);
        assert_eq!(cvd.len(), 2);
        // Bar 0: tb=8, ts=2 -> delta = +6 -> cvd = 6
        assert_eq!(cvd[0], 6.0);
        // Bar 1: tb=5, ts=15 -> delta = -10 -> cvd = -4
        assert_eq!(cvd[1], -4.0);
    }

    #[test]
    fn test_swings() {
        let highs = vec![1.0, 2.0, 5.0, 2.0, 1.0];
        let lows = vec![0.5, 1.0, 3.0, 1.0, 0.5];
        let (sh, sl) = detect_swings(highs, lows, 2);
        assert_eq!(sh.len(), 1);
        assert_eq!(sh[0], (2, 5.0));
        assert_eq!(sl.len(), 0);
    }

    #[test]
    fn test_targets() {
        let targets = calculate_structural_targets("LONG", 100.0, 90.0, vec![1.5, 2.0]);
        assert_eq!(targets.len(), 2);
        assert_eq!(targets[0].0, 115.0);
        assert_eq!(targets[1].0, 120.0);
    }
}
