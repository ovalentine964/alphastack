"""Deliberation loop for multi-agent consensus in AlphaStack.

Core concept: Multi-step reasoning where multiple agents explicitly
weigh options, debate trade-offs, and reach consensus before committing.

Steps:
1. Generate options (each agent proposes candidates)
2. Evaluate options (cross-agent scoring and debate)
3. Select and justify (consensus mechanism with conflict resolution)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class ConsensusMethod(Enum):
    """Methods for reaching multi-agent consensus."""

    MAJORITY_VOTE = "majority_vote"  # Simple majority
    WEIGHTED_VOTE = "weighted_vote"  # Weight by agent expertise/confidence
    UNANIMOUS = "unanimous"  # All agents must agree
    THRESHOLD = "threshold"  # Configurable agreement threshold
    DELEGATION = "delegation"  # Delegated to highest-confidence agent


class ConflictResolution(Enum):
    """Strategies for resolving agent disagreements."""

    ESCALATE_TO_HUMAN = "escalate_to_human"
    DEFER_TO_RISK = "defer_to_risk"  # Risk agent has veto
    DEFER_TO_EXPERT = "defer_to_expert"  # Most relevant agent decides
    NO_ACTION = "no_action"  # Disagreement = don't trade
    AVERAGE_POSITIONS = "average_positions"  # Blend recommendations


@dataclass
class AgentVote:
    """A single agent's vote on a trade decision.

    Attributes
    ----------
    agent_id : str
        Voting agent's identifier.
    agent_role : str
        Agent's role (e.g., "technical_analyst", "risk_manager").
    option : str
        The option this agent supports.
    confidence : float
        Agent's confidence in its vote (0-1).
    reasoning : str
        Why this agent chose this option.
    weight : float
        Agent's voting weight (based on expertise/reliability).
    """

    agent_id: str
    agent_role: str
    option: str
    confidence: float
    reasoning: str
    weight: float = 1.0


@dataclass
class TradeOption:
    """A candidate trade option for deliberation.

    Attributes
    ----------
    option_id : str
        Unique option identifier.
    description : str
        What this option entails.
    action : str
        The trade action (e.g., "LONG", "SHORT", "HOLD").
    entry : float
        Suggested entry price.
    stop_loss : float
        Suggested stop-loss price.
    take_profit : float
        Suggested take-profit price.
    position_size : float
        Suggested position size (fraction of capital).
    pros : list[str]
        Arguments in favor.
    cons : list[str]
        Arguments against.
    """

    option_id: str
    description: str
    action: str
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_size: float = 0.0
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def average_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)


@dataclass
class DeliberationResult:
    """Result of a multi-agent deliberation.

    Attributes
    ----------
    selected_option : TradeOption
        The option that was selected.
    votes : list[AgentVote]
        All agent votes.
    consensus_reached : bool
        Whether consensus was achieved.
    consensus_method : ConsensusMethod
        Method used to reach decision.
    conflict_resolution : ConflictResolution | None
        If conflicts were resolved, how.
    dissenting_agents : list[str]
        Agents that voted against the selected option.
    all_options : list[TradeOption]
        All options that were considered.
    duration_ms : float
        Total deliberation time.
    """

    selected_option: TradeOption | None = None
    votes: list[AgentVote] = field(default_factory=list)
    consensus_reached: bool = False
    consensus_method: ConsensusMethod = ConsensusMethod.WEIGHTED_VOTE
    conflict_resolution: ConflictResolution | None = None
    dissenting_agents: list[str] = field(default_factory=list)
    all_options: list[TradeOption] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_audit_log(self) -> dict[str, Any]:
        """Export as structured audit log entry."""
        return {
            "selected": self.selected_option.option_id if self.selected_option else None,
            "consensus_reached": self.consensus_reached,
            "consensus_method": self.consensus_method.value,
            "num_votes": len(self.votes),
            "num_options": len(self.all_options),
            "dissenting": self.dissenting_agents,
            "conflict_resolution": (
                self.conflict_resolution.value if self.conflict_resolution else None
            ),
            "duration_ms": self.duration_ms,
            "votes": [
                {
                    "agent": v.agent_id,
                    "role": v.agent_role,
                    "option": v.option,
                    "confidence": v.confidence,
                    "weight": v.weight,
                }
                for v in self.votes
            ],
        }


# ---------------------------------------------------------------------------
# Deliberation Loop
# ---------------------------------------------------------------------------


class DeliberationLoop:
    """Multi-agent deliberation loop for trade decisions.

    Implements the Generate Options → Evaluate → Consensus cycle.

    Usage
    -----
    ```python
    loop = DeliberationLoop(
        consensus_method=ConsensusMethod.WEIGHTED_VOTE,
        conflict_resolution=ConflictResolution.DEFER_TO_RISK,
        agreement_threshold=0.7,
    )

    result = await loop.deliberate(
        context="BTC testing key support at $65,000",
        propose_fn=agent_propose_fn,
        evaluate_fn=agent_evaluate_fn,
    )
    ```
    """

    def __init__(
        self,
        consensus_method: ConsensusMethod = ConsensusMethod.WEIGHTED_VOTE,
        conflict_resolution: ConflictResolution = ConflictResolution.NO_ACTION,
        agreement_threshold: float = 0.7,
        agent_weights: dict[str, float] | None = None,
    ) -> None:
        self.consensus_method = consensus_method
        self.conflict_resolution = conflict_resolution
        self.agreement_threshold = agreement_threshold
        self.agent_weights = agent_weights or {}

    async def deliberate(
        self,
        context: str,
        propose_fn: Callable[..., Awaitable[list[TradeOption]]],
        evaluate_fn: Callable[..., Awaitable[dict[str, list[AgentVote]]]],
        max_rounds: int = 3,
    ) -> DeliberationResult:
        """Run the deliberation loop.

        Parameters
        ----------
        context : str
            Market context for the deliberation.
        propose_fn : Callable
            Async function: (context) → list of TradeOptions.
            Each agent proposes candidate options.
        evaluate_fn : Callable
            Async function: (options, context) → {option_id: [AgentVote]}.
            Agents evaluate and vote on options.
        max_rounds : int
            Maximum deliberation rounds before forcing a decision.

        Returns
        -------
        DeliberationResult
            With selected option and full deliberation record.
        """
        start = time.monotonic()
        result = DeliberationResult(consensus_method=self.consensus_method)

        # Step 1: Generate options
        try:
            options = await propose_fn(context)
            result.all_options = options
        except Exception as e:
            logger.error("Option generation failed: %s", e)
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        if not options:
            logger.warning("No options proposed — no action")
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # Step 2-3: Evaluate and reach consensus (iterative)
        for round_num in range(1, max_rounds + 1):
            logger.info("Deliberation round %d/%d", round_num, max_rounds)

            # Evaluate
            try:
                votes_by_option = await evaluate_fn(options, context)
            except Exception as e:
                logger.error("Evaluation failed at round %d: %s", round_num, e)
                break

            # Collect all votes
            all_votes = []
            for option_votes in votes_by_option.values():
                all_votes.extend(option_votes)
            result.votes = all_votes

            # Score options
            for opt in options:
                opt_votes = votes_by_option.get(opt.option_id, [])
                if opt_votes:
                    weighted_scores = [
                        v.confidence * v.weight for v in opt_votes
                    ]
                    opt.scores["weighted_avg"] = (
                        sum(weighted_scores) / sum(v.weight for v in opt_votes)
                        if opt_votes else 0.0
                    )
                    opt.scores["vote_count"] = len(opt_votes)

            # Check consensus
            consensus = self._check_consensus(options, all_votes)
            if consensus:
                result.selected_option = consensus
                result.consensus_reached = True
                result.dissenting_agents = self._get_dissenters(
                    consensus.option_id, all_votes
                )
                break
        else:
            # Max rounds reached — force decision
            result.selected_option = self._force_decision(options, all_votes)
            result.consensus_reached = False
            if result.selected_option:
                result.dissenting_agents = self._get_dissenters(
                    result.selected_option.option_id, all_votes
                )

        # Resolve conflicts if needed
        if not result.consensus_reached and result.selected_option:
            result.conflict_resolution = self.conflict_resolution
            result.selected_option = self._apply_conflict_resolution(
                result.selected_option, options, all_votes
            )

        result.duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Deliberation completed: consensus=%s, selected=%s, duration=%.0fms",
            result.consensus_reached,
            result.selected_option.option_id if result.selected_option else "none",
            result.duration_ms,
        )
        return result

    # ------------------------------------------------------------------
    # Consensus mechanisms
    # ------------------------------------------------------------------

    def _check_consensus(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """Check if any option has reached consensus."""
        if not options:
            return None

        if self.consensus_method == ConsensusMethod.MAJORITY_VOTE:
            return self._majority_vote(options, votes)
        elif self.consensus_method == ConsensusMethod.WEIGHTED_VOTE:
            return self._weighted_vote(options, votes)
        elif self.consensus_method == ConsensusMethod.THRESHOLD:
            return self._threshold_vote(options, votes)
        elif self.consensus_method == ConsensusMethod.UNANIMOUS:
            return self._unanimous_vote(options, votes)
        elif self.consensus_method == ConsensusMethod.DELEGATION:
            return self._delegation_vote(options, votes)
        return None

    def _majority_vote(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """Simple majority vote."""
        vote_counts: dict[str, int] = {}
        for v in votes:
            vote_counts[v.option] = vote_counts.get(v.option, 0) + 1

        total = len(set(v.agent_id for v in votes))
        for opt in options:
            count = vote_counts.get(opt.option_id, 0)
            if count > total / 2:
                return opt
        return None

    def _weighted_vote(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """Weighted vote based on agent expertise."""
        weighted_scores: dict[str, float] = {}
        total_weight = 0.0

        for v in votes:
            weight = self.agent_weights.get(v.agent_id, v.weight)
            weighted_scores[v.option] = (
                weighted_scores.get(v.option, 0.0) + v.confidence * weight
            )
            total_weight += weight

        if total_weight == 0:
            return None

        for opt in options:
            score = weighted_scores.get(opt.option_id, 0.0)
            if score / total_weight >= self.agreement_threshold:
                return opt
        return None

    def _threshold_vote(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """Vote with configurable agreement threshold."""
        return self._weighted_vote(options, votes)

    def _unanimous_vote(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """All agents must agree."""
        agents = set(v.agent_id for v in votes)
        vote_counts: dict[str, set[str]] = {}
        for v in votes:
            vote_counts.setdefault(v.option, set()).add(v.agent_id)

        for opt in options:
            supporters = vote_counts.get(opt.option_id, set())
            if supporters == agents:
                return opt
        return None

    def _delegation_vote(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """Delegate to the highest-confidence agent."""
        if not votes:
            return None

        best_vote = max(votes, key=lambda v: v.confidence * v.weight)
        for opt in options:
            if opt.option_id == best_vote.option:
                return opt
        return None

    def _force_decision(
        self, options: list[TradeOption], votes: list[AgentVote]
    ) -> TradeOption | None:
        """Force a decision when consensus isn't reached."""
        if not options:
            return None
        # Pick option with highest weighted score
        best = max(options, key=lambda o: o.scores.get("weighted_avg", 0.0))
        return best

    def _get_dissenters(
        self, selected_id: str, votes: list[AgentVote]
    ) -> list[str]:
        """Get list of agents who voted against the selected option."""
        return [
            v.agent_id for v in votes if v.option != selected_id
        ]

    def _apply_conflict_resolution(
        self,
        selected: TradeOption,
        options: list[TradeOption],
        votes: list[AgentVote],
    ) -> TradeOption:
        """Apply conflict resolution strategy."""
        if self.conflict_resolution == ConflictResolution.NO_ACTION:
            # Return a HOLD option
            hold = TradeOption(
                option_id="no_action",
                description="No trade — consensus not reached",
                action="HOLD",
            )
            return hold

        elif self.conflict_resolution == ConflictResolution.DEFER_TO_RISK:
            # Find the risk manager's vote
            risk_votes = [v for v in votes if v.agent_role == "risk_manager"]
            if risk_votes:
                risk_vote = risk_votes[0]
                for opt in options:
                    if opt.option_id == risk_vote.option:
                        return opt

        elif self.conflict_resolution == ConflictResolution.ESCALATE_TO_HUMAN:
            # Mark for human escalation
            selected.description += " [ESCALATED TO HUMAN]"
            return selected

        elif self.conflict_resolution == ConflictResolution.AVERAGE_POSITIONS:
            # Average the position sizes
            trade_options = [o for o in options if o.action in ("LONG", "SHORT")]
            if trade_options:
                avg_size = sum(o.position_size for o in trade_options) / len(trade_options)
                selected.position_size = avg_size
                return selected

        return selected
