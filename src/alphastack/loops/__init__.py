"""Loop systems for AlphaStack multi-agent architecture.

Implements the core cognitive loops that drive agent behavior:
- ReAct: Reasoning + Acting for dynamic decision-making
- Reflection: Self-critique and continuous improvement
- Deliberation: Multi-agent consensus building
- Learning: Continuous model and strategy adaptation
- HITL: Human-in-the-Loop for oversight and progressive autonomy
"""

from alphastack.loops.react_loop import ReActLoop, ReActStep
from alphastack.loops.reflection_loop import ReflectionLoop, TradeReview
from alphastack.loops.deliberation_loop import DeliberationLoop, DeliberationResult
from alphastack.loops.learning_loop import LearningLoop, AdaptationSignal
from alphastack.loops.hitl_loop import HumanInTheLoop, ApprovalRequest, AutonomyLevel

__all__ = [
    "ReActLoop",
    "ReActStep",
    "ReflectionLoop",
    "TradeReview",
    "DeliberationLoop",
    "DeliberationResult",
    "LearningLoop",
    "AdaptationSignal",
    "HumanInTheLoop",
    "ApprovalRequest",
    "AutonomyLevel",
]
