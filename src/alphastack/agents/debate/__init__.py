"""Multi-agent debate system for AlphaStack trade signal validation.

Three agents debate each trade signal before it reaches the risk agent:
- Bull Agent: argues FOR the trade (supporting evidence)
- Bear Agent: argues AGAINST the trade (contradicting evidence)
- Risk Arbiter: scores both sides and makes final EXECUTE/REJECT/MODIFY call

The debate runs 3 rounds with a hard 2-second budget.
"""

from alphastack.agents.debate.debate_engine import DebateEngine
from alphastack.agents.debate.bull_agent import BullAgent
from alphastack.agents.debate.bear_agent import BearAgent
from alphastack.agents.debate.risk_arbiter import RiskArbiter

__all__ = ["DebateEngine", "BullAgent", "BearAgent", "RiskArbiter"]
