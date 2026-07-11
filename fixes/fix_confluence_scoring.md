# Unified Confluence Scoring System — Fix

**Date:** 2026-07-11
**Author:** Confluence Scoring Fix Agent
**Status:** Definitive — supersedes scoring sections in steps 5-8 and steps 9-12 reports
**Severity:** CRITICAL — resolves the #2 medium issue from review_2_strategy.md

---

## 1. The Problem

Two incompatible scoring systems exist:

| System | Location | Type | Scale | Max |
|--------|----------|------|-------|-----|
| **A** | Steps 5-8, §7.3 | Point-based | 0–130+ | Unbounded |
| **B** | Steps 9-12, §10.1 | Weighted | 0.00–1.00 | 1.00 |

System A produces raw signal scores. System B expects normalized 0–1 weights. **There is no bridge between them.** An implementer cannot answer: *"My SMC score is 95 from System A — what does that contribute to System B's 0.25 SMC weight?"*

---

## 2. The Fix: One System, Three Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 1: RAW SIGNAL SCORING                      │
│              (Each step produces a 0–100 sub-score)                  │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Step 5   │  │ Step 6   │  │ Step 7   │  │ Step 8   │            │
│  │ S/R      │  │ Liquidity│  │ SMC      │  │ RSI      │            │
│  │ 0–100    │  │ 0–100    │  │ 0–100    │  │ 0–100    │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │              │              │              │                  │
├───────┴──────────────┴──────────────┴──────────────┴────────────────┤
│                    LAYER 2: CATEGORY SCORES (0.0–1.0)                │
│              (Normalize each step's raw score to 0–1)                │
│                                                                      │
│  SR_score/100  Liq_score/100  SMC_score/100  RSI_score/100          │
│       │              │              │              │                  │
│       ├──────────────┼──────────────┼──────────────┤                  │
│       │         Also include:                                        │
│       │         • Kill Zone (0 or 1)                                  │
│       │         • Candlestick (0–1, from Step 9)                     │
│       │         • Volume (0–1, from Step 6)                          │
│       │         • News/Fundamental (0–1, from Step 1)                │
│       │                                                              │
├───────┴──────────────────────────────────────────────────────────────┤
│                    LAYER 3: WEIGHTED CONFLUENCE SCORE                 │
│              (Single number: 0.00–1.00)                              │
│                                                                      │
│  FINAL = Σ (Category_Score × Weight)                                 │
│  Range: 0.00 – 1.00                                                  │
│  Thresholds: <0.35 NO TRADE | 0.35–0.49 C | 0.50–0.64 B |           │
│              0.65–0.79 A | 0.80+ A+                                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1: Raw Signal Scoring (per Step)

Each step produces a **0–100 raw score**. This replaces System A's unbounded point accumulation with a consistent, capped scale.

### 3.1 Step 5 — S/R Score (0–100)

| Component | Max Points | Calculation |
|-----------|-----------|-------------|
| Level quality (touches × recency × TF diversity) | 40 | `min(40, touch_count × recency_weight × tf_mult)` |
| Volume profile alignment (POC/VAH/VAL proximity) | 25 | `25 if within 0.25 ATR of POC/VAH/VAL, else decay` |
| Multi-TF confluence | 20 | `2 TFs=10, 3 TFs=15, 4+ TFs=20` |
| Institutional level (GEX/dark pool/OI) | 15 | `15 if institutional data confirms, 0 if unavailable` |

**Capped at 100.** Excess points do not carry over.

### 3.2 Step 6 — Liquidity Score (0–100)

| Component | Max Points | Calculation |
|-----------|-----------|-------------|
| Liquidity pool depth (heatmap score) | 30 | `min(30, heatmap_score × 0.3)` |
| Sweep classification (real vs fake) | 30 | `30 if real sweep (confidence >0.65), 0 if fake, 15 if ambiguous` |
| Order flow alignment (delta, absorption) | 25 | `delta_aligned=15, absorption=10` |
| On-chain data (crypto) or institutional flow | 15 | `15 if data available and supportive, 0 otherwise` |

**Capped at 100.**

### 3.3 Step 7 — SMC Score (0–100)

This is where System A's point-based scoring lives. **Normalize it to 0–100.**

| Pattern | Raw Points | Normalized (÷ max possible × 100) |
|---------|-----------|-------------------------------------|
| Order Block | +30 | Part of raw total |
| Fair Value Gap | +20 | Part of raw total |
| BOS (continuation) | +25 | Part of raw total |
| CHoCH (reversal) | +30 | Part of raw total |
| Breaker Block | +20 | Part of raw total |
| Mitigation Block | +15 | Part of raw total |
| Liquidity Sweep (from Step 6) | +25 | Part of raw total |

**Bonuses (added to raw total):**
- OB + FVG overlap: +15
- BOS/CHoCH + OB: +20
- Liquidity Sweep + OB: +25
- Multi-TF alignment: +15 per additional TF
- Volume confirmation: +10

**Normalization:**
```
Theoretical maximum = 30 + 20 + 25 + 30 + 20 + 15 + 25 + 15 + 20 + 25 + 15 + 10 = 250
SMC_score = min(100, raw_total / 250 × 100)
```

**Practical maximum:** A realistic high-confluence setup scores ~120–150 raw → 48–60 normalized. This is fine — it means SMC alone (weight 0.25) contributes 0.12–0.15 to the final score, leaving room for other signals.

### 3.4 Step 8 — RSI Score (0–100)

| Component | Max Points | Calculation |
|-----------|-----------|-------------|
| Multi-TF RSI alignment | 35 | `abs(alignment_score) / 1.0 × 35` (alignment is ±1.0) |
| Divergence detection | 30 | `30 × divergence_strength` (strength is 0–1) |
| Composite momentum extreme | 20 | `20 if composite <25 or >75, 10 if <40 or >60` |
| ML signal confidence | 15 | `ml_probability × 15` |

**Capped at 100.**

### 3.5 Step 9 — Candlestick Score (0–100)

| Component | Max Points | Calculation |
|-----------|-----------|-------------|
| Pattern base score | 40 | Per reliability table: Morning Star=40, Engulfing=35, Hammer=30, etc. |
| Volume multiplier | 25 | `base × (volume_ratio > 1.5 ? 1.4 : volume_ratio > 1.2 ? 1.2 : 0.7)`, capped at 25 |
| Context multiplier | 20 | `+15 at OB/liquidity zone, +10 at fib level, +10 RSI divergence, cap 20` |
| Failure flags (penalty) | -15 | `-5 per failure signal (max 3 flags = -15)` |

**Capped at 100. Floor at 0.**

### 3.6 Step 1 — News/Fundamental Score (0–100)

| Component | Max Points | Calculation |
|-----------|-----------|-------------|
| Sentiment alignment | 50 | `FinBERT probability × 50` |
| Macro bias agreement | 30 | `30 if macro bias matches trade direction` |
| Event risk filter | 20 | `20 if no high-impact events within 2h, 0 if event pending` |

**Capped at 100.**

### 3.7 Volume Score (0–100)

Derived from Step 6's order flow data, reused as a standalone category:

| Component | Max Points | Calculation |
|-----------|-----------|-------------|
| Volume vs 20-period average | 50 | `min(50, volume_ratio / 2.0 × 50)` |
| Delta alignment | 30 | `30 if cumulative delta matches direction` |
| Institutional flow confirmation | 20 | `20 if large trade / iceberg / absorption detected` |

**Capped at 100.**

---

## 4. Layer 2: Category Scores (0.0–1.0)

Normalize each raw score:

```
Category_Score = Raw_Score / 100
```

| Category | Raw Source | Category Score |
|----------|-----------|----------------|
| S/R Quality | Step 5 raw | SR_score / 100 |
| Liquidity | Step 6 raw | Liq_score / 100 |
| SMC Structure | Step 7 raw | SMC_score / 100 |
| RSI/Momentum | Step 8 raw | RSI_score / 100 |
| Candlestick | Step 9 raw | Candle_score / 100 |
| Kill Zone | Step 3 (binary) | 1.0 if in kill zone, 0.0 if not |
| Volume | Volume raw | Vol_score / 100 |
| News/Fundamental | Step 1 raw | News_score / 100 |

---

## 5. Layer 3: Weighted Confluence Score

### 5.1 Weights

```
CONFLUENCE_SCORE = Σ (Category_Score × Weight)

| Category             | Weight | Rationale                                      |
|----------------------|--------|-------------------------------------------------|
| SMC Structure        | 0.25   | Highest predictive value (research-backed)      |
| Liquidity            | 0.20   | Smart money footprint, second-highest signal    |
| Kill Zone            | 0.15   | Institutional flow windows — timing matters     |
| Candlestick          | 0.15   | Entry timing signal, volume-weighted            |
| S/R Quality          | 0.10   | Structural context (merged into SMC when overlapping) |
| RSI/Momentum         | 0.05   | Confirmation only — weakest standalone signal   |
| Volume               | 0.05   | Validates the move — necessary but not sufficient |
| News/Fundamental     | 0.05   | Directional filter — low weight, high impact when misaligned |
|                      |        |                                                 |
| TOTAL                | 1.00   | ✅ Verified                                     |
```

### 5.2 Why These Weights Differ from Both Original Systems

**System B's original weights** assigned RSI 0.10 and had no S/R category (it was folded into SMC). Our fix:
- **S/R gets its own 0.10 weight** because Steps 5-8 treat it as a full independent step with its own scoring. Folding it into SMC hides its contribution.
- **RSI drops to 0.05** because the review found it's the weakest standalone signal — it's a confirmation filter, not a primary driver.
- **Volume gets 0.05** as its own category instead of being bundled — it validates but doesn't generate signals.

**System A's original points** had no weighting at all — every SMC sub-signal contributed equally. Our fix normalizes them to 0–100 first, then applies the 0.25 SMC weight.

### 5.3 The Critical Rule (Preserved from Original)

```
IF any of [SMC, Liquidity, Kill Zone] has category_score == 0:
    MAXIMUM confluence_score = 0.60 (cap)
    Rationale: You can't trade without structure, liquidity, or timing.
```

### 5.4 Score → Trade Decision Mapping

```
CONFLUENCE_SCORE    GRADE    ACTION                  RISK (% of account)
─────────────────   ─────    ─────────────────────   ───────────────────
0.80 – 1.00         A+       FULL TRADE              1.5% (max)
0.65 – 0.79         A        STANDARD TRADE          1.0%
0.50 – 0.64         B        REDUCED TRADE           0.5%
0.35 – 0.49         C        PAPER TRADE / SKIP      0% (log only)
< 0.35              F        NO TRADE                0% (log only)

Hard cap: Never exceed 2% per trade, 6% total open exposure.
```

---

## 6. Complete Flow: Signal → Score → Trade

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE SCORING FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─── STEP 1: News/Fundamental ──────────────────────────────────────┐  │
│  │  FinBERT + Macro + Event filter → News_raw (0–100)                │  │
│  └────────────────────────────┬──────────────────────────────────────┘  │
│                               │                                          │
│  ┌─── STEP 5: S/R Detection ──┤──────────────────────────────────────┐  │
│  │  Fractal + VolProfile +    │  SR_raw (0–100)                      │  │
│  │  Institutional + ML        │                                       │  │
│  └────────────────────────────┤                                       │  │
│                               │                                        │  │
│  ┌─── STEP 6: Liquidity ──────┤──────────────────────────────────────┐  │
│  │  Heatmap + Order Flow +    │  Liq_raw (0–100)                     │  │
│  │  Sweep Classifier          │  Vol_raw (0–100) ← extracted         │  │
│  └────────────────────────────┤                                       │  │
│                               │                                        │  │
│  ┌─── STEP 7: SMC Patterns ──┤──────────────────────────────────────┐  │
│  │  OB + FVG + BOS/CHoCH +    │  SMC_raw (0–100)                     │  │
│  │  Breaker + Confluence      │  [normalized from point system]      │  │
│  └────────────────────────────┤                                       │  │
│                               │                                        │  │
│  ┌─── STEP 8: RSI ────────────┤──────────────────────────────────────┐  │
│  │  Adaptive thresholds +     │  RSI_raw (0–100)                     │  │
│  │  Multi-TF + Divergence     │                                       │  │
│  └────────────────────────────┤                                       │  │
│                               │                                        │  │
│  ┌─── STEP 3: Kill Zone ──────┤──────────────────────────────────────┐  │
│  │  Session detection         │  KZ = 1.0 or 0.0                     │  │
│  └────────────────────────────┤                                       │  │
│                               │                                        │  │
│  ┌─── STEP 9: Candlestick ────┤──────────────────────────────────────┐  │
│  │  Pattern + Volume +        │  Candle_raw (0–100)                  │  │
│  │  Context + Failure flags   │                                       │  │
│  └────────────────────────────┘                                       │  │
│                               │                                        │  │
│  ┌────────────────────────────▼──────────────────────────────────────┐  │
│  │                    NORMALIZE (÷ 100)                               │  │
│  │                                                                    │  │
│  │  SR    = SR_raw / 100          (0.0 – 1.0)                        │  │
│  │  Liq   = Liq_raw / 100         (0.0 – 1.0)                        │  │
│  │  SMC   = SMC_raw / 100         (0.0 – 1.0)                        │  │
│  │  RSI   = RSI_raw / 100         (0.0 – 1.0)                        │  │
│  │  Candle= Candle_raw / 100      (0.0 – 1.0)                        │  │
│  │  KZ    = 1.0 or 0.0            (binary)                           │  │
│  │  Vol   = Vol_raw / 100         (0.0 – 1.0)                        │  │
│  │  News  = News_raw / 100        (0.0 – 1.0)                        │  │
│  └────────────────────────────┬──────────────────────────────────────┘  │
│                               │                                          │
│  ┌────────────────────────────▼──────────────────────────────────────┐  │
│  │                    WEIGHTED SUM                                    │  │
│  │                                                                    │  │
│  │  SCORE = SMC×0.25 + Liq×0.20 + KZ×0.15 + Candle×0.15             │  │
│  │        + SR×0.10 + RSI×0.05 + Vol×0.05 + News×0.05               │  │
│  │                                                                    │  │
│  │  IF any of [SMC, Liq, KZ] == 0: SCORE = min(SCORE, 0.60)          │  │
│  └────────────────────────────┬──────────────────────────────────────┘  │
│                               │                                          │
│  ┌────────────────────────────▼──────────────────────────────────────┐  │
│  │                    GRADE & DECIDE                                  │  │
│  │                                                                    │  │
│  │  SCORE ≥ 0.80  → A+ → Full trade (1.5% risk)                      │  │
│  │  SCORE ≥ 0.65  → A  → Standard trade (1.0% risk)                  │  │
│  │  SCORE ≥ 0.50  → B  → Reduced trade (0.5% risk)                   │  │
│  │  SCORE ≥ 0.35  → C  → Paper trade / skip                          │  │
│  │  SCORE < 0.35  → F  → No trade                                    │  │
│  │                                                                    │  │
│  │  → Step 11: Position Sizing (uses grade as multiplier)             │  │
│  │  → Step 12: Stop Loss (uses structure from S/R + SMC)              │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Worked Example

**Setup:** EUR/USD long, London session

### Layer 1: Raw Scores

| Step | Signal | Raw Score | Calculation |
|------|--------|-----------|-------------|
| 5 (S/R) | H4 support at 1.0850, 4 touches, D1 confluence | **72** | touches=20, vol_profile=18, multi_tf=19, institutional=15 |
| 6 (Liquidity) | Buy-side sweep below 1.0840 (real, conf 0.8) | **68** | pool_depth=18, sweep_real=30, delta=15, on_chain=5 (no data) |
| 7 (SMC) | H4 OB (30) + FVG overlap (15) + BOS (25) + volume (10) | **80** | raw=80, normalized: 80/250×100=**32** → but cap at 100, so **32** |
| 8 (RSI) | Multi-TF alignment=0.4 (14), no divergence (0), composite=38 (10), ML=0.6 (9) | **33** | 14+0+10+9=33 |
| 9 (Candle) | Bullish engulfing at OB (35), volume 1.6x (20), at OB zone (15) | **70** | 35+20+15=70 |
| 3 (Kill Zone) | London open (08:00 UTC) | **1.0** | Binary |
| Volume | Volume 1.6x avg (40), delta bullish (30), no inst flow (0) | **70** | 40+30+0=70 |
| 1 (News) | Sentiment bullish 0.7 (35), macro agrees (30), no events (20) | **85** | 35+30+20=85 |

### Layer 2: Category Scores

| Category | Raw | Normalized |
|----------|-----|------------|
| SMC | 32 | 0.32 |
| Liquidity | 68 | 0.68 |
| Kill Zone | — | 1.00 |
| Candlestick | 70 | 0.70 |
| S/R | 72 | 0.72 |
| RSI | 33 | 0.33 |
| Volume | 70 | 0.70 |
| News | 85 | 0.85 |

### Layer 3: Weighted Score

```
SCORE = 0.32×0.25 + 0.68×0.20 + 1.00×0.15 + 0.70×0.15
      + 0.72×0.10 + 0.33×0.05 + 0.70×0.05 + 0.85×0.05

      = 0.080 + 0.136 + 0.150 + 0.105
      + 0.072 + 0.017 + 0.035 + 0.043

      = 0.638
```

**Grade: B** (0.50–0.64) → Reduced trade at 0.5% risk.

**Why not A?** SMC score is low (32/100) — only one OB with FVG overlap and BOS. RSI is weak (33/100). The setup has good structure and liquidity but lacks strong SMC pattern confluence and momentum confirmation.

**What would push it to A?**
- Add a CHoCH or liquidity sweep + OB combo → SMC raw → ~120 → normalized 48 → +0.04 to score
- RSI divergence detected → RSI raw → ~60 → +0.014 to score
- That gets to ~0.69 → Grade A → Standard 1% trade

---

## 8. Implementation: Single Function

```python
def calculate_confluence_score(
    sr_raw: float,        # Step 5 output (0-100)
    liq_raw: float,       # Step 6 output (0-100)
    smc_raw: float,       # Step 7 output (raw points, unnormalized)
    rsi_raw: float,       # Step 8 output (0-100)
    candle_raw: float,    # Step 9 output (0-100)
    kill_zone: bool,      # Step 3 output
    volume_raw: float,    # From Step 6 order flow (0-100)
    news_raw: float,      # Step 1 output (0-100)
    smc_max: float = 250  # Theoretical max for SMC raw points
) -> dict:
    """
    Unified confluence scoring. Returns score, grade, and breakdown.
    """
    # Layer 2: Normalize
    sr     = min(sr_raw, 100) / 100
    liq    = min(liq_raw, 100) / 100
    smc    = min(smc_raw / smc_max * 100, 100) / 100
    rsi    = min(rsi_raw, 100) / 100
    candle = min(candle_raw, 100) / 100
    kz     = 1.0 if kill_zone else 0.0
    vol    = min(volume_raw, 100) / 100
    news   = min(news_raw, 100) / 100

    # Layer 3: Weighted sum
    score = (
        smc    * 0.25 +
        liq    * 0.20 +
        kz     * 0.15 +
        candle * 0.15 +
        sr     * 0.10 +
        rsi    * 0.05 +
        vol    * 0.05 +
        news   * 0.05
    )

    # Critical rule: top-3 gate
    if smc == 0 or liq == 0 or kz == 0:
        score = min(score, 0.60)

    # Grade
    if score >= 0.80:
        grade, risk = "A+", 0.015
    elif score >= 0.65:
        grade, risk = "A", 0.010
    elif score >= 0.50:
        grade, risk = "B", 0.005
    elif score >= 0.35:
        grade, risk = "C", 0.0  # paper trade
    else:
        grade, risk = "F", 0.0  # no trade

    return {
        "score": round(score, 4),
        "grade": grade,
        "risk_pct": risk,
        "breakdown": {
            "smc": round(smc, 4),
            "liquidity": round(liq, 4),
            "kill_zone": kz,
            "candlestick": round(candle, 4),
            "sr_quality": round(sr, 4),
            "rsi_momentum": round(rsi, 4),
            "volume": round(vol, 4),
            "news_fundamental": round(news, 4),
        },
        "gated": smc == 0 or liq == 0 or kz == 0,
    }
```

---

## 9. Migration Notes

### What Changes from System A (Steps 5-8)

| Before | After |
|--------|-------|
| SMC points accumulate unbounded (0–130+) | SMC raw capped at 100 via normalization |
| Thresholds: <40 no trade, 40-60 small, 60-80 standard, 80+ large | Thresholds moved to Layer 3 (final score) |
| S/R, Liquidity, RSI scored independently with own scales | All normalized to 0–100, then 0–1 |

### What Changes from System B (Steps 9-12)

| Before | After |
|--------|-------|
| 7 weighted categories | 8 weighted categories (S/R extracted from SMC, Volume from Liquidity) |
| SMC weight 0.25 (includes S/R) | SMC 0.25 + S/R 0.10 (separated) |
| RSI weight 0.10 | RSI weight 0.05 (downgraded — confirmation only) |
| No explicit normalization from Steps 5-8 | Clear Layer 1→2→3 pipeline |
| Kill Zone 0.15 | Kill Zone 0.15 (unchanged) |

### Backward Compatibility

- All original signal detection logic (Steps 5-8) is **unchanged**. Only the output format changes from raw points to 0–100.
- Steps 11-12 (position sizing, stop loss) consume the **grade** (A+/A/B/C/F) exactly as before.
- The 2%/6%/4% risk framework is **unchanged**.

---

## 10. Summary

| Item | Before (Broken) | After (Fixed) |
|------|-----------------|---------------|
| Scoring systems | 2 incompatible systems | 1 unified system, 3 layers |
| SMC raw score | Unbounded 0–130+ | Normalized 0–100 |
| Step 5-8 → Step 10 bridge | None defined | Layer 1→2→3 pipeline |
| Weights sum | System B: 1.0 ✅, System A: N/A | 1.00 ✅ verified |
| Trade thresholds | Ambiguous (two sets) | One set: 0.35/0.50/0.65/0.80 |
| Critical gate rule | Only in System B | Preserved in unified system |
| Implementation | Unclear | Single function, copy-paste ready |

---

*This document is the authoritative confluence scoring reference. When in conflict with steps 5-8 or steps 9-12 reports, this document wins.*
