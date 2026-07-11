# Fix: Drawdown De-Escalation Logic

> **Severity:** HIGH (Gap #3 from risk rules review)
> **Date:** 2026-07-11
> **Status:** FIX READY FOR IMPLEMENTATION
> **Scope:** `DrawdownLimitManager` class in `architecture_risk.md` §3.3

---

## 1. Problem Statement

The `DrawdownLimitManager.update()` method determines stage via `_determine_stage()` which maps drawdown percentage to stage thresholds. When drawdown recovers (e.g., from 15% back to 8%), `_determine_stage()` returns the lower stage, and the transition handler fires — but it only executes **escalation actions** (worsening). There is no de-escalation logic: no recovery condition checks, no waiting periods, no gradual position size restoration.

**Result:** A system that enters BLACK stays in BLACK forever, even if the market fully recovers and equity returns to all-time highs.

### Current Code Gap

```python
# Current: _handle_stage_transition only checks _is_escalation()
if self._is_escalation(old_stage, new_stage):
    # ... escalation actions ...

# MISSING: de-escalation branch
# elif self._is_de_escalation(old_stage, new_stage):
#     # ... recovery validation and gradual unlock ...
```

---

## 2. Fix: Complete `DrawdownLimitManager` with De-Escalation

### 2.1 New State Variables

Add these to `__init__`:

```python
def __init__(self, config: dict):
    self.current_stage = 'GREEN'
    self.high_water_mark = 0.0
    self.stage_entry_time = {}
    self.daily_pnl = 0.0
    self.event_bus = None

    # === NEW: De-escalation state ===
    self.recovery_candidate_stage = None    # Stage we're considering moving to
    self.recovery_start_time = None         # When drawdown first dropped below threshold
    self.recovery_confirmed = False         # Whether sustained condition is met
    self.manual_restart_authorized = False  # For BLACK→RED only
    self.paper_trading_hours_completed = 0  # For BLACK→RED only
    self.position_size_ramp = 1.0           # Gradual ramp multiplier during recovery
    self.recovery_config = config.get('recovery', self._default_recovery_config())
```

### 2.2 Recovery Configuration

```python
def _default_recovery_config(self) -> dict:
    """
    Recovery conditions per transition.
    'wait_hours': minimum time drawdown must stay below threshold
    'drawdown_threshold': max DD% to qualify (one stage lower's max)
    'paper_trading_required': whether paper trading validation is needed
    'manual_authorization': whether human must explicitly approve
    'ramp_steps': number of gradual size-increase steps after transition
    'ramp_interval_hours': hours between each ramp step
    """
    return {
        'BLACK_to_RED': {
            'wait_hours': 24,
            'drawdown_threshold': 0.18,
            'paper_trading_required': True,
            'paper_trading_hours': 24,
            'manual_authorization': True,
            'ramp_steps': 4,
            'ramp_interval_hours': 24,
            'ramp_start_mult': 0.10,   # Start at 10% of RED's normal size
            'ramp_end_mult': 1.00,     # Reach RED's full allowed size
        },
        'RED_to_ORANGE': {
            'wait_hours': 48,
            'drawdown_threshold': 0.12,
            'paper_trading_required': False,
            'manual_authorization': False,
            'ramp_steps': 4,
            'ramp_interval_hours': 12,
            'ramp_start_mult': 0.25,
            'ramp_end_mult': 1.00,
        },
        'ORANGE_to_YELLOW': {
            'wait_hours': 24,
            'drawdown_threshold': 0.07,
            'paper_trading_required': False,
            'manual_authorization': False,
            'ramp_steps': 3,
            'ramp_interval_hours': 8,
            'ramp_start_mult': 0.50,
            'ramp_end_mult': 1.00,
        },
        'YELLOW_to_GREEN': {
            'wait_hours': 12,
            'drawdown_threshold': 0.03,
            'paper_trading_required': False,
            'manual_authorization': False,
            'ramp_steps': 3,
            'ramp_interval_hours': 4,
            'ramp_start_mult': 0.60,
            'ramp_end_mult': 1.00,
        },
    }
```

### 2.3 New `update()` Method with De-Escalation

```python
async def update(self, account: AccountState) -> DrawdownState:
    """Called on every tick/candle. Handles both escalation and de-escalation."""

    # Update high water mark
    if account.equity > self.high_water_mark:
        self.high_water_mark = account.equity

    # Calculate drawdown from HWM
    if self.high_water_mark > 0:
        drawdown_pct = (self.high_water_mark - account.equity) / self.high_water_mark
    else:
        drawdown_pct = 0.0

    # Determine what stage the drawdown *would* map to
    raw_stage = self._determine_stage(drawdown_pct)

    # === ESCALATION: immediate, no waiting ===
    if self._is_escalation(self.current_stage, raw_stage):
        await self._handle_escalation(self.current_stage, raw_stage, drawdown_pct, account)
        self.current_stage = raw_stage
        self.stage_entry_time[raw_stage] = datetime.utcnow()
        # Reset recovery state on escalation
        self._reset_recovery_state()

    # === DE-ESCALATION: gated by sustained recovery ===
    elif self._is_de_escalation(self.current_stage, raw_stage):
        await self._check_recovery(drawdown_pct, account)

    # === SAME STAGE: check if recovery timer should be reset ===
    else:
        # If we were tracking recovery but drawdown spiked back above threshold
        if self.recovery_candidate_stage and drawdown_pct >= self.STAGES[self.current_stage]['max']:
            self._reset_recovery_state()

    # Update daily P&L
    self.daily_pnl = account.equity - account.day_start_equity

    # Update position size ramp if in recovery
    await self._update_position_ramp()

    return DrawdownState(
        current_stage=self.current_stage,
        drawdown_pct=drawdown_pct,
        drawdown_amount=self.high_water_mark - account.equity,
        high_water_mark=self.high_water_mark,
        daily_pnl=self.daily_pnl,
        daily_pnl_pct=self.daily_pnl / account.day_start_equity * 100 if account.day_start_equity > 0 else 0,
        time_in_stage=datetime.utcnow() - self.stage_entry_time.get(self.current_stage, datetime.utcnow()),
        # === NEW fields ===
        recovery_active=self.recovery_candidate_stage is not None,
        recovery_target=self.recovery_candidate_stage,
        recovery_progress=self._recovery_progress(),
        position_size_ramp=self.position_size_ramp,
    )
```

### 2.4 De-Escalation Check Logic

```python
def _is_de_escalation(self, old: str, new: str) -> bool:
    """Check if transition is a de-escalation (improving)."""
    order = ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK']
    return order.index(new) < order.index(old)

def _get_transition_key(self, from_stage: str, to_stage: str) -> str:
    """Get the recovery config key for a transition."""
    return f"{from_stage}_to_{to_stage}"

async def _check_recovery(self, drawdown_pct: float, account: AccountState):
    """
    Check if de-escalation conditions are being met.
    Recovery requires drawdown to stay below the target stage's upper bound
    for a sustained period (wait_hours).
    """

    # Determine the target stage (one level below current)
    order = ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK']
    current_idx = order.index(self.current_stage)
    target_stage = order[current_idx - 1] if current_idx > 0 else 'GREEN'

    transition_key = self._get_transition_key(self.current_stage, target_stage)
    config = self.recovery_config.get(transition_key)

    if not config:
        return  # No recovery config — stay in current stage

    # Check: is drawdown below the target threshold?
    if drawdown_pct >= config['drawdown_threshold']:
        # Drawdown rose back above threshold — reset recovery clock
        if self.recovery_candidate_stage == target_stage:
            self._reset_recovery_state()
        return

    # === BLACK→RED special case: requires manual authorization ===
    if config.get('manual_authorization') and not self.manual_restart_authorized:
        return  # Waiting for human to authorize restart

    # === BLACK→RED special case: paper trading requirement ===
    if config.get('paper_trading_required'):
        if self.paper_trading_hours_completed < config.get('paper_trading_hours', 24):
            return  # Still in paper trading validation

    # Drawdown is below threshold — start or continue recovery timer
    now = datetime.utcnow()

    if self.recovery_candidate_stage != target_stage:
        # First time seeing recovery — start the clock
        self.recovery_candidate_stage = target_stage
        self.recovery_start_time = now
        return

    # Recovery timer is running — check if sustained long enough
    hours_in_recovery = (now - self.recovery_start_time).total_seconds() / 3600

    if hours_in_recovery >= config['wait_hours']:
        # === RECOVERY CONFIRMED — Execute de-escalation ===
        await self._execute_de_escalation(target_stage, config, drawdown_pct, account)

async def _execute_de_escalation(
    self, target_stage: str, config: dict, drawdown_pct: float, account: AccountState
):
    """Execute the actual stage transition downward."""

    old_stage = self.current_stage

    # Update stage
    self.current_stage = target_stage
    self.stage_entry_time[target_stage] = datetime.utcnow()

    # Start position size ramp
    self.position_size_ramp = config.get('ramp_start_mult', 0.50)

    # Publish de-escalation event
    await self.event_bus.publish('risk.drawdown', RiskEvent(
        event_type=RiskEventType.DRAWDOWN_STAGE_CHANGE,
        severity='INFO',
        component='drawdown_manager',
        data={
            'old_stage': old_stage,
            'new_stage': target_stage,
            'drawdown_pct': drawdown_pct,
            'transition_type': 'DE_ESCALATION',
            'recovery_duration_hours': (datetime.utcnow() - self.recovery_start_time).total_seconds() / 3600,
            'ramp_config': {
                'start_mult': config.get('ramp_start_mult'),
                'end_mult': config.get('ramp_end_mult'),
                'steps': config.get('ramp_steps'),
                'interval_hours': config.get('ramp_interval_hours'),
            },
        },
        reasoning=(
            f"Sustained recovery confirmed: drawdown at {drawdown_pct:.1%} "
            f"(below {config['drawdown_threshold']:.0%} threshold for "
            f"{config['wait_hours']}h). De-escalating {old_stage} → {target_stage}. "
            f"Position size ramp starting at {config.get('ramp_start_mult', 0.5):.0%}."
        )
    ))

    # Log alert
    await self.event_bus.publish('risk.alert', {
        'severity': 'INFO',
        'message': (
            f"✅ DRAWDOWN RECOVERY: {old_stage} → {target_stage}\n"
            f"Drawdown: {drawdown_pct:.1%}\n"
            f"Position sizing: ramping from {config.get('ramp_start_mult', 0.5):.0%} "
            f"to {config.get('ramp_end_mult', 1.0):.0%} over "
            f"{config.get('ramp_steps') * config.get('ramp_interval_hours', 12)}h"
        ),
    })

    # Reset recovery tracking
    self.recovery_start_time = None
    self.recovery_candidate_stage = None
```

### 2.5 Gradual Position Size Ramp

```python
async def _update_position_ramp(self):
    """
    Gradually increase position size during recovery.
    Called every update() tick.
    """
    if self.position_size_ramp >= 1.0:
        return  # Ramp complete

    order = ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK']
    current_idx = order.index(self.current_stage)
    target_stage = order[current_idx + 1] if current_idx < len(order) - 1 else self.current_stage

    # Find the config for the stage we just left
    # We need to know which transition we came from to get ramp config
    # Since we're in recovery, we came from a worse stage
    worse_stage = order[current_idx + 1] if current_idx < len(order) - 1 else None
    if not worse_stage:
        return

    transition_key = self._get_transition_key(worse_stage, self.current_stage)
    config = self.recovery_config.get(transition_key, {})

    ramp_steps = config.get('ramp_steps', 3)
    ramp_interval_hours = config.get('ramp_interval_hours', 8)
    ramp_start = config.get('ramp_start_mult', 0.50)
    ramp_end = config.get('ramp_end_mult', 1.00)

    # Calculate how much to increment per step
    step_size = (ramp_end - ramp_start) / ramp_steps if ramp_steps > 0 else 0

    # Check if enough time has passed since stage entry for next step
    time_in_stage = (datetime.utcnow() - self.stage_entry_time.get(self.current_stage, datetime.utcnow())).total_seconds() / 3600
    steps_completed = min(int(time_in_stage / ramp_interval_hours), ramp_steps)

    target_ramp = ramp_start + (step_size * steps_completed)
    self.position_size_ramp = min(target_ramp, ramp_end)

    # Emit event on ramp step change
    if self.position_size_ramp < ramp_end:
        await self.event_bus.publish('risk.drawdown', RiskEvent(
            event_type=RiskEventType.DRAWDOWN_LIMIT_BREACH,
            severity='INFO',
            component='drawdown_manager',
            data={
                'ramp_step': steps_completed,
                'ramp_total_steps': ramp_steps,
                'position_size_ramp': self.position_size_ramp,
            },
            reasoning=f"Recovery ramp step {steps_completed}/{ramp_steps}: size multiplier now {self.position_size_ramp:.0%}"
        ))

def _recovery_progress(self) -> float:
    """Return recovery progress as 0.0–1.0."""
    if not self.recovery_candidate_stage or not self.recovery_start_time:
        return 0.0

    transition_key = self._get_transition_key(self.current_stage, self.recovery_candidate_stage)
    config = self.recovery_config.get(transition_key, {})
    wait_hours = config.get('wait_hours', 24)

    elapsed = (datetime.utcnow() - self.recovery_start_time).total_seconds() / 3600
    return min(elapsed / wait_hours, 1.0) if wait_hours > 0 else 1.0

def _reset_recovery_state(self):
    """Clear all recovery tracking — used when drawdown re-escalates."""
    self.recovery_candidate_stage = None
    self.recovery_start_time = None
    self.recovery_confirmed = False
    self.position_size_ramp = 1.0
```

### 2.6 Manual Authorization Interface (BLACK→RED)

```python
async def authorize_restart(self, operator_id: str, reason: str):
    """
    Called by human operator to authorize BLACK→RED transition.
    Only meaningful when current_stage == 'BLACK'.
    """
    if self.current_stage != 'BLACK':
        return

    self.manual_restart_authorized = True
    self.paper_trading_hours_completed = 0  # Reset paper trading counter

    await self.event_bus.publish('risk.drawdown', RiskEvent(
        event_type=RiskEventType.DRAWDOWN_STAGE_CHANGE,
        severity='WARNING',
        component='drawdown_manager',
        data={
            'operator_id': operator_id,
            'reason': reason,
            'action': 'RESTART_AUTHORIZED',
            'next_step': 'Begin 24h paper trading validation',
        },
        reasoning=f"Manual restart authorized by {operator_id}: {reason}"
    ))

async def record_paper_trading_hour(self):
    """
    Called by the paper trading module each hour of successful paper trading.
    Increments counter; when threshold met, de-escalation timer can begin.
    """
    if not self.manual_restart_authorized:
        return

    self.paper_trading_hours_completed += 1

    config = self.recovery_config.get('BLACK_to_RED', {})
    required = config.get('paper_trading_hours', 24)

    if self.paper_trading_hours_completed >= required:
        await self.event_bus.publish('risk.drawdown', RiskEvent(
            event_type=RiskEventType.DRAWDOWN_STAGE_CHANGE,
            severity='WARNING',
            component='drawdown_manager',
            data={
                'paper_trading_hours': self.paper_trading_hours_completed,
                'status': 'PAPER_TRADING_COMPLETE',
                'next_step': 'Monitoring drawdown for 24h sustained recovery',
            },
            reasoning=f"Paper trading validation complete ({self.paper_trading_hours_completed}h). Now monitoring for sustained recovery."
        ))
```

### 2.7 Updated `get_position_size_multiplier()`

```python
def get_position_size_multiplier(self) -> float:
    """Return the current position size multiplier, including recovery ramp."""
    base_multipliers = {
        'GREEN': 1.00,
        'YELLOW': 0.50,
        'ORANGE': 0.25,
        'RED': 0.10,
        'BLACK': 0.00
    }
    base = base_multipliers[self.current_stage]

    # During recovery, ramp the multiplier
    # The ramp applies as a fraction of the target stage's base multiplier
    if self.position_size_ramp < 1.0 and self.current_stage != 'BLACK':
        return base * self.position_size_ramp

    return base
```

---

## 3. Quantitative Definition of "Sustained Recovery"

The term "sustained recovery" is now precisely defined:

| Metric | Definition |
|--------|-----------|
| **Threshold** | Drawdown % must drop below the target stage's upper bound |
| **Duration** | Must remain below threshold for the full `wait_hours` continuously |
| **Interruption** | Any single tick above threshold resets the entire clock |
| **Validation** | BLACK→RED additionally requires 24h paper trading + human authorization |
| **Gradualism** | After transition, position size ramps up over multiple steps (not instant) |

**Example — ORANGE→YELLOW recovery:**
1. Drawdown drops below 7% (YELLOW upper bound)
2. Clock starts: 0h / 24h
3. After 12h, drawdown spikes to 7.5% → clock resets to 0h
4. Drawdown drops below 7% again → clock restarts
5. After 24h continuous below 7% → transition to YELLOW
6. Position size starts at 50% of YELLOW's normal 0.50× multiplier (0.25×)
7. Every 8h, size increases: 0.25× → 0.33× → 0.42× → 0.50×
8. Full YELLOW sizing reached after 24h ramp

---

## 4. Recovery Timeline Summary

```
BLACK ──[manual restart]──► 24h paper trading ──► DD<18% for 24h ──► RED
  Total minimum: ~49h from authorization

RED ──► DD<12% for 48h ──► ORANGE (ramp 25%→100% over 48h)
  Total minimum: 48h

ORANGE ──► DD<7% for 24h ──► YELLOW (ramp 50%→100% over 24h)
  Total minimum: 24h

YELLOW ──► DD<3% for 12h ──► GREEN (ramp 60%→100% over 12h)
  Total minimum: 12h

FULL RECOVERY (BLACK → GREEN): minimum ~133 hours (~5.5 days)
```

This is intentionally slow. Markets crash in minutes; recovery should take days.

---

## 5. Updated `DrawdownState` Dataclass

```python
@dataclass
class DrawdownState:
    current_stage: str
    drawdown_pct: float
    drawdown_amount: float
    high_water_mark: float
    daily_pnl: float
    daily_pnl_pct: float
    time_in_stage: timedelta
    # === NEW: Recovery fields ===
    recovery_active: bool = False
    recovery_target: str = None       # Stage being recovered to
    recovery_progress: float = 0.0    # 0.0–1.0
    position_size_ramp: float = 1.0   # Current ramp multiplier
```

---

## 6. Updated Config Schema (for `risk_config.yaml`)

```yaml
drawdown:
  stages:
    green:  { max: 0.03, size_mult: 1.00, max_positions: 5 }
    yellow: { max: 0.07, size_mult: 0.50, max_positions: 3 }
    orange: { max: 0.12, size_mult: 0.25, max_positions: 2 }
    red:    { max: 0.18, size_mult: 0.10, max_positions: 1 }
    black:  { max: 1.00, size_mult: 0.00, max_positions: 0 }

  recovery:
    BLACK_to_RED:
      wait_hours: 24
      drawdown_threshold: 0.18
      paper_trading_required: true
      paper_trading_hours: 24
      manual_authorization: true
      ramp_steps: 4
      ramp_interval_hours: 24
      ramp_start_mult: 0.10
      ramp_end_mult: 1.00

    RED_to_ORANGE:
      wait_hours: 48
      drawdown_threshold: 0.12
      paper_trading_required: false
      manual_authorization: false
      ramp_steps: 4
      ramp_interval_hours: 12
      ramp_start_mult: 0.25
      ramp_end_mult: 1.00

    ORANGE_to_YELLOW:
      wait_hours: 24
      drawdown_threshold: 0.07
      paper_trading_required: false
      manual_authorization: false
      ramp_steps: 3
      ramp_interval_hours: 8
      ramp_start_mult: 0.50
      ramp_end_mult: 1.00

    YELLOW_to_GREEN:
      wait_hours: 12
      drawdown_threshold: 0.03
      paper_trading_required: false
      manual_authorization: false
      ramp_steps: 3
      ramp_interval_hours: 4
      ramp_start_mult: 0.60
      ramp_end_mult: 1.00
```

---

## 7. Safety Invariants

These rules are enforced by the fix and must never be violated:

1. **Escalation is always instant.** No waiting period for worsening.
2. **De-escalation is always gated.** Sustained condition + minimum wait.
3. **Interruption resets the clock.** A single tick above threshold restarts the timer.
4. **BLACK→RED requires human.** No automatic restart from system halt.
5. **Recovery ramp is gradual.** Position sizes never jump from 10% to 100%.
6. **Re-escalation cancels recovery.** If drawdown worsens during recovery, all recovery state is discarded.
7. **Ramp applies to the target stage's multiplier.** At YELLOW with 50% ramp: `0.50 × 0.50 = 0.25×` effective size.
8. **Full BLACK→GREEN recovery takes ≥5.5 days.** By design — patience over speed.

---

## 8. Test Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| DD hits 15% → drops to 11% and stays 48h | RED→ORANGE transition, ramp from 25% to 100% over 48h |
| DD hits 15% → drops to 11% → spikes to 13% at hour 30 | Clock resets. Must sustain 48h from new start. |
| DD hits 20% (BLACK) → manual restart → 24h paper → DD<18% 24h | BLACK→RED with ramp |
| DD hits 20% → no manual restart | Stays BLACK forever (correct — requires human) |
| DD hits 8% → drops to 5% for 20h → spikes to 7.5% | ORANGE recovery interrupted at 20h, clock resets |
| DD hits 8% → drops to 5% for 24h → drops to 2% for 12h | ORANGE→YELLOW→GREEN (two successive recoveries) |
| DD at 5% (YELLOW) with ramp at 0.33× | `get_position_size_multiplier()` returns `0.50 × 0.33 = 0.165×` |

---

*Fix authored by: Drawdown De-Escalation Fix Agent*
*Implements: Gap #3 from Risk Rules Review (HIGH severity)*
*Files modified: architecture_risk.md §3.3 (DrawdownLimitManager class)*
