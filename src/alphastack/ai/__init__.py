"""AI reasoning layer — model-agnostic integration for AlphaStack.

Primary interface (new code):

    from alphastack.ai import AlphaModel, ReasoningEngine

Model routing:

    from alphastack.ai import ModelRouter, TaskComplexity, LatencyRequirement

Signal generation:

    from alphastack.ai import SignalGenerator, Signal, SignalSide

Regime detection:

    from alphastack.ai import MarketRegimeDetector, MarketRegime

Sentiment analysis:

    from alphastack.ai import SentimentEngine

AI Pipeline:

    from alphastack.ai import AIStrategyPipeline

Legacy interface (still works):

    from alphastack.ai import MiMoClient, ReasoningEngine
"""

from alphastack.ai.model_client import (
    AlphaModel,
    ReasoningEngine,
    detect_provider,
    resolve_config,
    PROVIDERS,
)
from alphastack.ai.model_router import (
    ModelRouter,
    ModelTier,
    TaskComplexity,
    LatencyRequirement,
    CostTracker,
    TokenBudgetManager,
    ModelConfig,
    AgentRoutingProfile,
)
from alphastack.ai.signals import (
    SignalGenerator,
    Signal,
    SignalSide,
    SignalStrength,
    ConfluenceScorer,
    ConfidenceScorer,
    SMCDetector,
    SupportResistanceDetector,
    compute_rsi,
    compute_macd,
    compute_bollinger_bands,
    compute_atr,
    compute_adx,
    compute_obv,
    compute_stochastic,
    compute_vwap,
    compute_ema,
)
from alphastack.ai.regime import (
    MarketRegimeDetector,
    MarketRegime,
    RegimeState,
    TrendStrength,
    StrategyAdaptation,
)
from alphastack.ai.sentiment import (
    SentimentEngine,
    SentimentPolarity,
    AggregateSentiment,
    NewsSentimentAnalyzer,
    SocialSentimentAnalyzer,
    EconomicCalendarScorer,
)
from alphastack.ai.pipeline import (
    AIStrategyPipeline,
    PipelineResult,
    PipelinePhase,
)

# Backward-compatible alias
MiMoClient = AlphaModel

__all__ = [
    # Model client
    "AlphaModel",
    "MiMoClient",
    "ReasoningEngine",
    "detect_provider",
    "resolve_config",
    "PROVIDERS",
    # Model routing
    "ModelRouter",
    "ModelTier",
    "TaskComplexity",
    "LatencyRequirement",
    "CostTracker",
    "TokenBudgetManager",
    "ModelConfig",
    "AgentRoutingProfile",
    # Signal generation
    "SignalGenerator",
    "Signal",
    "SignalSide",
    "SignalStrength",
    "ConfluenceScorer",
    "ConfidenceScorer",
    "SMCDetector",
    "SupportResistanceDetector",
    "compute_rsi",
    "compute_macd",
    "compute_bollinger_bands",
    "compute_atr",
    "compute_adx",
    "compute_obv",
    "compute_stochastic",
    "compute_vwap",
    "compute_ema",
    # Regime
    "MarketRegimeDetector",
    "MarketRegime",
    "RegimeState",
    "TrendStrength",
    "StrategyAdaptation",
    # Sentiment
    "SentimentEngine",
    "SentimentPolarity",
    "AggregateSentiment",
    "NewsSentimentAnalyzer",
    "SocialSentimentAnalyzer",
    "EconomicCalendarScorer",
    # Pipeline
    "AIStrategyPipeline",
    "PipelineResult",
    "PipelinePhase",
]
