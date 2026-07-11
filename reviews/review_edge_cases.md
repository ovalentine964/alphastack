# Alpha Stack — Edge Case Review

> **Reviewer:** Edge Case Review Agent  
> **Date:** 2026-07-11  
> **Scope:** Validate how the Alpha Strategy handles flash crashes, news events, broker disconnection, weekend gaps, black swan events, and identify unaddressed edge cases  
> **Documents Reviewed:** strategy_enhancement_steps13to16.md, research_financial_crises.md, architecture_risk.md, fix_platform_consolidation.md

---

## 1. Flash Crash Handling

### What's Covered

The system has **strong flash crash detection and response**:

- **Black Swan Detector** monitors price velocity — triggers if any pair moves >3% in <5 minutes (1-second tick loop, independent of all other systems)
- **ATR explosion detection** — triggers when current ATR > 5× the 14-period baseline
- **Spread blowout detection** — triggers when spread > 10× normal
- **Liquidity evaporation detection** — triggers when order book depth < 10% of normal
- **Requires 2+ simultaneous triggers** to activate — reduces false positives
- **Auto-execute: CLOSE_ALL_POSITIONS at market** once activated
- **4-hour cooldown** post-activation before any trading resumes
- **Circuit Breaker Layer 1** has slippage breaker (>0.5% slippage pauses entries) and spread breaker (>3× normal blocks new orders)

### Verdict: ✅ WELL HANDLED

The architecture directly addresses the 2010 Flash Crash scenario (liquidity withdrawal, stub quotes) and the 2015 ETF Flash Crash (opening auction gaps). The 1-second independent monitoring loop is the correct design — flash crashes demand sub-minute detection.

### Gap Identified

**No recovery logic for flash crashes that recover.** The 2010 Flash Crash recovered within 36 minutes. The current system closes all positions and halts for 4 hours minimum. A flash-crash-then-recovery scenario means the system sells at the bottom and doesn't re-enter until the move has fully reversed.

**Recommendation:** Add a "flash crash recovery" path — if price returns to within 1× ATR of pre-crash levels within 60 minutes, and spreads/liquidity normalize, allow re-entry at 25% size with human approval. This prevents the worst outcome: selling the exact bottom of a temporary dislocation.

---

## 2. News Event Handling (NFP, CPI, FOMC)

### What's Covered

A **three-phase news protocol** is defined in architecture_risk.md:

- **Pre-event (T-60 to T-0):** Flag positions, tighten stops, partial close, block new entries at T-5, full blackout at T-0
- **During event:** All automated trading paused, existing stops remain at broker, monitoring only
- **Post-event (T+5 to T+30):** Assess conditions, gradual resume (50% → 75% → 100% size)
- **Classification system:** CRITICAL (NFP, CPI, FOMC → 15-min blackout), HIGH (GDP, employment → 10-min), MEDIUM (PMI → 5-min), LOW (housing data → no blackout)
- **Extension logic:** If spreads/volatility don't normalize, blackout extends in 15-min increments

The strategy document (Step 14) adds nuance:
- T-30: Tighten SL on positions in profit >1R
- T-5: Close 50% of positions with profit <1R, widen remaining SL to 2× ATR

### Verdict: ✅ WELL HANDLED

The protocol is thorough and research-backed. The 65% adverse excursion statistic for open positions during high-impact news is correctly accounted for.

### Gaps Identified

**1. Calendar integration not specified.** The `NewsEventHandler` class assumes an `EconomicCalendar` object exists, but no design for this component is provided. Where does the calendar data come from? Is it a paid API (e.g., Forex Factory, Investing.com, Bloomberg)? What happens if the calendar feed is delayed or has incorrect impact ratings?

**2. No handling of surprise/unscheduled events.** The protocol handles scheduled events (NFP, FOMC). It does NOT handle:
- Emergency central bank rate decisions (e.g., COVID emergency cut)
- Geopolitical突发事件 (war declarations, assassination, coup)
- Flash crashes triggered by news leaks before the official release

**3. Post-news re-entry logic is vague.** "T+10min: If spreads normalized → resume with 50% size" — but what constitutes "normalized"? Is it 1.5× average spread? 2×? This needs a concrete threshold.

**4. No handling of news during illiquid sessions.** An NFP release at 13:30 UTC during the London-NY overlap has deep liquidity. A surprise BOJ intervention at 00:30 UTC during the Asia session has thin liquidity. The protocol doesn't differentiate.

**Recommendation:**
- Define the calendar data source and fallback (if feed is down, default to BLACKOUT for all pairs)
- Add an "unscheduled event" trigger based on NLP sentiment velocity (>3σ negative in <1 hour) — already mentioned in research_financial_crises.md but not implemented in the code
- Define spread normalization as <1.5× average for at least 3 consecutive 1-minute candles
- Add session-aware liquidity scaling: during Asia session, double the blackout duration

---

## 3. Broker Disconnection During a Trade

### What's Covered

**Circuit Breaker Layer 4 (System Level):**
- Exchange connectivity loss >30 seconds → close all positions on that exchange
- Data feed anomaly → cross-validate with backup feeds, halt if inconsistent
- Order rejection rate >10% → pause all trading
- Latency spike >10× normal → cancel all open orders
- Event bus failure → enter safe mode, close all positions

**Recovery:** Broker reconnects → 60s stability check → auto-reset

### Verdict: ⚠️ PARTIALLY HANDLED — CRITICAL GAPS

### Gaps Identified

**1. What happens DURING the 30-second window?** If a broker disconnects while a position is open and price is moving against the trade, the system waits 30 seconds before acting. In a fast market (e.g., during NFP), 30 seconds can mean 50+ pips of adverse movement on EUR/USD.

**2. No backup broker failover.** The architecture shows MT5, cTrader, and OANDA adapters. But there's no logic for: "Primary broker disconnected → route close order to backup broker." The system simply closes on the disconnected broker (which may not execute since it's disconnected).

**3. No handling of partial disconnection.** Brokers can have:
- Quote feed alive but order execution dead
- Order execution alive but quote feed stale
- Connection alive but server-side delays (requote, off-quotes)
The system treats disconnection as binary (connected/disconnected) when reality is a spectrum.

**4. No handling of broker-side issues.** What if:
- The broker's server is up but rejecting all orders ("no connection to server")?
- The broker is in maintenance mode (scheduled or emergency)?
- The broker has widened spreads to 100× normal (effectively illiquid)?
- The broker has changed leverage/margin requirements mid-session?

**5. The 30-second timeout assumes the system can detect disconnection.** What if the connection appears alive but is actually a zombie connection (TCP keepalive passes but no data flows)? This is common with some MT5 implementations.

**6. No position reconciliation after reconnect.** After a 30-second disconnect and reconnect, how does the system verify that the position state matches reality? What if a stop-loss was hit at the broker during the disconnect but the system doesn't know?

**Recommendation:**
- Reduce the connectivity timeout to 10 seconds for positions with unrealized loss >0.5R
- Implement heartbeat-based zombie detection (send ping, expect pong within 5s, 3 failures = dead)
- After reconnect, immediately query broker for actual position state and reconcile
- If primary broker is disconnected and positions are open, alert human immediately (don't wait 30s)
- Define a "degraded broker" state: connected but spreads >5× or rejection rate >5% → treat as disconnected for new entries but keep existing stops alive

---

## 4. Weekend Gap Handling

### What's Covered

**Friday close protocol (20:00 UTC):**
- High-impact weekend event expected → close 100% of all positions
- Normal weekend:
  - Positions in profit >2R → close 50%, trail rest
  - Positions in profit 1-2R → close 75%, trail rest
  - Positions at BE or loss → close 100%

**Monday Asian open protocol:**
- Gap > 2× ATR(14) against position → assess thesis validity, close if invalid, adjust SL if valid
- Gap in favor → consider partial profit on gap fill expectation

**Data points:**
- EUR/USD average weekend gap: 15-25 pips (normal), 50-100+ pips (news events)
- GBP/JPY average weekend gap: 30-50 pips (normal), 100-200+ pips (news events)

### Verdict: ✅ WELL HANDLED

The Friday close protocol is sensible and conservative. Closing losing positions before the weekend is correct — weekend gaps are asymmetric (they tend to gap against retail positioning).

### Gaps Identified

**1. No definition of "high-impact weekend event."** The protocol says "close 100% if high-impact weekend event expected" but doesn't define what qualifies. Is it G7 meetings? Elections? Referendums? OPEC meetings? This needs a concrete list or calendar integration.

**2. No handling of holiday gaps.** Monday isn't the only gap risk. Market holidays (e.g., US bank holidays where forex is thin, Japanese holidays causing JPY flash crashes) create similar gap risks mid-week. The protocol only addresses weekend gaps.

**3. No handling of Monday gap-through-stop scenarios.** If EUR/USD closes at 1.0850 with a stop at 1.0820, and Monday opens at 1.0750 (gap through stop), the fill will be at 1.0750, not 1.0820. The protocol mentions assessing the gap but doesn't quantify the slippage risk or account for it in position sizing.

**4. Trail stop behavior over weekend is undefined.** "Trail rest" — but how? The trailing stop is calculated based on live price action. Over the weekend, there IS no price action. Does the system set the trailing stop at Friday's close level? At the last ATR-based level? This is ambiguous.

**Recommendation:**
- Define a "weekend risk calendar" with specific event categories (elections, G7, OPEC, central bank meetings) and default to "close all" for any category 2+ event
- Add mid-week holiday awareness: if a major market (US, UK, Japan) is on holiday, apply reduced position sizing and wider stops 24h before
- Quantify gap-through-stop risk: if the distance from current price to SL is < 2× average weekend gap, reduce position size by 50%
- Define trailing stop behavior: set trailing stop to the Friday close level minus 1.5× Friday's ATR, held static over the weekend

---

## 5. Black Swan Event Handling

### What's Covered

**Detection (8 triggers, 2+ required):**
1. VIX spike >40% in 1 hour
2. ATR > 5× baseline
3. Spread > 10× normal
4. Cross-asset correlation > 0.95
5. Order book depth < 10% of normal
6. Price move > 3% in < 5 minutes
7. Stablecoin depeg > 2%
8. Major exchange halts withdrawals

**Response Protocol:**
1. Close ALL positions at market (auto-execute)
2. If execution impossible → set widest emergency stop, contact broker
3. Post-event: Wait 4h minimum, assess (VIX < 30, spreads normal), paper trade 18h, resume at 25% size on day 2, gradual normalization over 7 days

**Historical scenario library:**
- Swiss Franc Unpeg 2015 (EUR/CHF -30%)
- COVID Crash 2020 (S&P -34%, VIX 82)
- Asian Crisis 1997 (currencies -50-85%)
- LUNA Collapse 2022 (-99.99%)
- Flash Crash 2010 (-9.2% in 5 min)

**Hypothetical scenarios:**
- US-China conflict
- US debt default
- Crypto exchange hack (>$1B)
- Quantum computing crypto break

### Verdict: ✅ STRONG — BEST-IN-CLASS

This is the most thoroughly addressed edge case. The 8-trigger detection system, the requirement for 2+ simultaneous triggers (reducing false positives), the auto-execute close-all protocol, and the detailed recovery procedure are all excellent.

### Gaps Identified

**1. "Close all at market" assumes market exists.** The Swiss Franc depeg had literally NO BID between 1.20 and 0.85. The system sends a market close order, but if there's no counterparty, the order doesn't fill. The protocol acknowledges this ("If execution impossible → set widest possible SL") but the fallback is vague. What IS the widest possible SL? How does the system determine it? And who contacts the broker?

**2. No negative balance protection awareness.** In the 2015 CHF event, retail clients owed money to brokers. The system assumes max loss = position size, but in extreme events, loss can exceed position size. The architecture doesn't account for negative balance scenarios.

**3. No handling of market halt/circuit breakers at exchange level.** If the NYSE halts trading (circuit breaker triggered), or a crypto exchange goes into "maintenance mode," the system can't close positions. The protocol says "close all" but doesn't handle the case where closing is impossible.

**4. The 2-trigger minimum may be too slow.** Consider: a geopolitical event (war declaration) causes a 4% move in 3 minutes. The price velocity trigger fires (trigger 6). But spreads haven't blown out yet (spread is still 2× normal, not 10×). VIX hasn't spiked yet (it takes time for VIX to reflect). Only 1 trigger = no activation. The system waits until a second trigger fires, by which time the move may be 8%+.

**5. No inter-exchange correlation for crypto.** If Binance goes down but Bybit is still live, the system should be able to hedge on Bybit. The architecture doesn't cross-reference exchange health for failover.

**Recommendation:**
- Define "emergency SL" as entry price minus 10× ATR(14) — a level that should only be hit in genuine black swan events
- Add negative balance protection: if margin utilization > 50% and black swan triggers activate, reduce position sizes BEFORE the close-all to minimize negative balance risk
- Add exchange halt detection as a standalone trigger (not requiring a second trigger)
- Consider a "single-trigger emergency" mode: if any single trigger exceeds 2× its threshold (e.g., VIX spikes 80% in 1 hour, or price moves 6% in 5 minutes), activate immediately without waiting for a second trigger
- Implement cross-exchange health monitoring for crypto: if one exchange fails, route close orders to any live exchange with the same pair

---

## 6. Edge Cases NOT Addressed

### 6.1 Data Feed Corruption / Stale Data

**Scenario:** The price feed delivers stale prices (same price for 30 seconds during active market) or corrupted data (sudden 10% jump that immediately reverts — a "phantom tick").

**Impact:** The black swan detector could trigger on a phantom tick. Or, stale prices could prevent the system from detecting a real move.

**Current handling:** The architecture mentions "data feed anomaly → cross-validate with backup feeds, halt if inconsistent." But no implementation details exist. What constitutes a "backup feed"? How is cross-validation performed? What if both feeds are corrupted?

**Recommendation:** Implement a tick-level sanity check: reject any tick that moves > 3× current ATR in a single tick. Cross-validate across at least 2 independent feed providers. If feeds diverge by > 0.5% on the same pair, halt trading on that pair.

---

### 6.2 Broker Slippage Beyond Expected

**Scenario:** The system calculates position size based on a 30-pip SL. The actual fill on the SL is 80 pips due to slippage. The actual loss is 2.67× the planned R.

**Impact:** The 2% per-trade risk becomes 5.3%. The 4% daily loss limit could be breached by a single trade.

**Current handling:** The slippage circuit breaker (>0.5% slippage pauses new entries) exists but only prevents FUTURE entries. It doesn't retroactively adjust the risk calculations for the already-slipped trade.

**Recommendation:** After every fill, recalculate actual R based on actual fill price vs. actual SL fill. If actual R exceeds 1.5× planned R, flag the trade for the Journal Agent and adjust the daily P&L accordingly. If a single trade exceeds 3× planned R, trigger a review.

---

### 6.3 Time Sync / Clock Drift

**Scenario:** The system clock is 2 seconds ahead of the broker's clock. News blackout starts 2 seconds early. A trade entered during those 2 seconds gets hit by the news event.

**Impact:** Minor for most cases, but critical for news blackouts and session-based rules.

**Current handling:** Not addressed anywhere.

**Recommendation:** Synchronize system clock with NTP. Use broker server time (not local time) for all time-based rules. Add a 1-minute buffer before and after scheduled events.

---

### 6.4 Strategy Degradation / Edge Decay

**Scenario:** The strategy's win rate degrades from 68% to 52% over 3 months due to changing market conditions (e.g., regime shift from trending to ranging). The Kelly Criterion still calculates positive expected value, but barely.

**Impact:** The system keeps trading, slowly bleeding capital through transaction costs on a barely-positive edge.

**Current handling:** The Journal Agent tracks rolling 20-trade expectancy. The Performance Analytics Agent alerts when win rate drops below 45%. But these are reactive, not proactive.

**Recommendation:** Implement a "strategy health score" that combines:
- Rolling 30-trade expectancy trend (is it declining?)
- Win rate trend (declining over 3+ months?)
- Sharpe ratio trend
If the strategy health score drops below a threshold for 2+ weeks, auto-reduce to 50% size and flag for human review. Don't wait for win rate to hit 45%.

---

### 6.5 Multi-Platform State Inconsistency

**Scenario:** The desktop (embedded server) and mobile (cloud server) both show open positions, but the desktop shows a position that was closed 5 minutes ago on mobile. The user tries to close it on desktop and gets an error, or worse, opens a duplicate position.

**Impact:** Phantom positions, duplicate orders, incorrect risk calculations.

**Current handling:** The platform consolidation document describes server-authoritative state and WebSocket sync. But the embedded server and cloud server are separate instances. If the desktop is in embedded mode and the mobile is in cloud mode, they have separate databases.

**Recommendation:** This is the most significant architectural gap. Either:
- The embedded server must sync with the cloud server (bidirectional replication), OR
- The desktop must always connect to the cloud server (abandoning the offline-first model for trading), OR
- A "primary server" election must occur (one server is always authoritative, others are read-only replicas)

The current architecture allows two independent servers to both believe they're authoritative, which is a recipe for state divergence.

---

### 6.6 Regulatory / Compliance Edge Cases

**Scenario:** The system trades a pair that becomes restricted (e.g., a country imposes capital controls, or a broker removes a pair from trading). Or, the system violates a position limit imposed by the broker or regulator.

**Impact:** Orders rejected, positions force-closed at unfavorable prices, potential regulatory penalties.

**Current handling:** Not addressed.

**Recommendation:** Monitor broker announcements for pair removals/restrictions. Implement broker-imposed position limits as hard caps alongside the system's own limits. If a pair becomes restricted, auto-close all positions on that pair within 24 hours.

---

### 6.7 Concurrent Agent Conflicts

**Scenario:** The Risk Agent says "close the position" (drawdown limit), but the Trade Management Agent says "hold, the setup is still valid" (structure intact). Both send commands to the Execution Agent simultaneously.

**Impact:** Race condition — which command wins? If the TM Agent's "hold" command arrives first, the position stays open against the Risk Agent's judgment.

**Current handling:** The architecture defines a priority hierarchy (P0: Risk Agent > P1: Execution > P2: Strategy). But there's no implementation of a command queue or mutex for conflicting commands on the same position.

**Recommendation:** Implement a position-level command lock. When the Risk Agent issues a close command, it acquires the lock. The TM Agent's hold command is rejected because the lock is held. Commands are processed in priority order, not arrival order.

---

### 6.8 AI/ML Model Failure Modes

**Scenario:** The LSTM/Transformer model for TP prediction encounters a market condition it has never seen (e.g., a new type of crisis). It outputs a prediction with 95% confidence that is catastrophically wrong.

**Impact:** The system takes a large position based on the model's confident-but-wrong prediction.

**Current handling:** Not addressed. The model outputs are used directly for trade decisions.

**Recommendation:** Implement model uncertainty estimation. If the model's prediction is outside the distribution of its training data (OOD detection), flag it and fall back to rule-based decisions. Never allow a single model's output to override the hard risk limits.

---

### 6.9 Network Partition in Multi-Server Setup

**Scenario:** The embedded server (desktop) and cloud server (mobile) lose connectivity with each other. Both continue operating independently. Both open positions based on the same signal.

**Impact:** Double the intended position size, double the risk.

**Current handling:** Not addressed. The platform consolidation document doesn't discuss split-brain scenarios.

**Recommendation:** Implement a distributed lock or leader election. Only one server can execute trades at any time. If the other server can't reach the leader, it enters read-only mode.

---

### 6.10 Cascading Circuit Breaker Failure

**Scenario:** The circuit breaker system itself fails (bug in the `CircuitBreakerSystem` class, event bus failure, or the breaker-checking loop crashes). Trading continues without any circuit breaker protection.

**Impact:** Unlimited losses — no daily drawdown limit, no position stops, no regime-based sizing.

**Current handling:** The architecture mentions "event bus failure → enter safe mode, close all positions." But what if the circuit breaker PROCESS crashes (not the event bus)?

**Recommendation:** Implement a watchdog process that monitors the circuit breaker loop. If the breaker doesn't check in within 60 seconds, the watchdog triggers a system halt. The watchdog should be an independent process (not in the same codebase as the circuit breaker).

---

## Summary Scorecard

| Edge Case | Coverage | Quality | Criticality |
|-----------|----------|---------|-------------|
| Flash crashes | ✅ Full | Strong | HIGH |
| News events (NFP, CPI, FOMC) | ⚠️ Mostly | Strong | HIGH |
| Broker disconnection | ⚠️ Partial | Adequate | CRITICAL |
| Weekend gaps | ✅ Full | Strong | MEDIUM |
| Black swan events | ✅ Full | Excellent | CRITICAL |
| Data feed corruption | ❌ Missing | — | HIGH |
| Slippage beyond expected | ⚠️ Partial | Weak | HIGH |
| Clock drift | ❌ Missing | — | LOW |
| Strategy degradation | ⚠️ Partial | Adequate | MEDIUM |
| Multi-platform state sync | ❌ Missing | — | CRITICAL |
| Regulatory/compliance | ❌ Missing | — | MEDIUM |
| Agent command conflicts | ❌ Missing | — | HIGH |
| AI model failure modes | ❌ Missing | — | HIGH |
| Network partition | ❌ Missing | — | CRITICAL |
| Circuit breaker self-failure | ❌ Missing | — | CRITICAL |

---

## Priority Recommendations (Ranked)

1. **CRITICAL — Multi-server state consistency.** Two independent servers can both execute trades. This is the single biggest architectural risk. Implement leader election or single-authoritative-server design before any live trading.

2. **CRITICAL — Broker disconnection during fast markets.** Reduce timeout from 30s to 10s for losing positions. Implement zombie connection detection. Add position reconciliation after reconnect.

3. **CRITICAL — Circuit breaker watchdog.** An independent watchdog process that halts the system if the circuit breaker loop stops running.

4. **HIGH — Agent command conflict resolution.** Implement position-level command locks with priority ordering.

5. **HIGH — Data feed validation.** Tick-level sanity checks, multi-feed cross-validation, phantom tick rejection.

6. **HIGH — Black swan single-trigger emergency.** Allow activation on a single trigger if it exceeds 2× threshold.

7. **HIGH — AI model uncertainty.** OOD detection and fallback to rule-based decisions.

8. **MEDIUM — Flash crash recovery path.** Don't sell the bottom of a temporary dislocation without a recovery mechanism.

9. **MEDIUM — Strategy health monitoring.** Proactive edge-decay detection before win rate hits 45%.

10. **LOW — Clock synchronization.** NTP sync and broker-time-based rules.

---

*"The edge cases that kill you are the ones you didn't think to test."*

---

> **Document maintained by:** Edge Case Review Agent  
> **Review cadence:** After any system change that touches risk management, execution, or agent communication  
> **Next review:** Before any live capital deployment
