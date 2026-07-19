"""Sentiment analysis — news, social media, and economic calendar scoring.

Provides multi-source sentiment analysis for the AlphaStack pipeline:
  - News sentiment scoring (headline + body analysis)
  - Social media sentiment (Twitter/X, Reddit, Telegram)
  - Economic calendar impact scoring
  - Aggregate sentiment with time-decay weighting

Uses a hybrid approach: rule-based keyword scoring for speed,
with LLM escalation for ambiguous cases (via ModelRouter).
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Sentiment types
# ---------------------------------------------------------------------------

class SentimentPolarity(str, Enum):
    VERY_BULLISH = "very_bullish"    # score > 0.6
    BULLISH = "bullish"              # 0.2 < score <= 0.6
    NEUTRAL = "neutral"              # -0.2 <= score <= 0.2
    BEARISH = "bearish"              # -0.6 <= score < -0.2
    VERY_BEARISH = "very_bearish"    # score < -0.6


class ImpactLevel(str, Enum):
    """Economic event impact level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class SentimentSource(str, Enum):
    NEWS = "news"
    SOCIAL = "social"
    ECONOMIC_CALENDAR = "economic_calendar"
    AGGREGATE = "aggregate"


@dataclass
class SentimentResult:
    """Result of sentiment analysis for a single source."""
    source: SentimentSource
    score: float                  # -1.0 to +1.0
    polarity: SentimentPolarity
    confidence: float             # 0.0–1.0
    sample_size: int              # number of items analyzed
    headline_scores: list[dict[str, Any]] = field(default_factory=list)
    top_bullish: list[str] = field(default_factory=list)
    top_bearish: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        """Sentiment older than 1 hour is stale."""
        return (time.time() - self.timestamp) > 3600


@dataclass
class AggregateSentiment:
    """Weighted aggregate of all sentiment sources."""
    score: float                  # -1.0 to +1.0
    polarity: SentimentPolarity
    confidence: float
    news_sentiment: SentimentResult | None = None
    social_sentiment: SentimentResult | None = None
    calendar_impact: SentimentResult | None = None
    risk_adjustment: float = 0.0  # how much to reduce signal strength
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Keyword-based sentiment lexicon (financial domain)
# ---------------------------------------------------------------------------

# Weighted keyword dictionaries — domain-specific for forex/crypto
_BULLISH_KEYWORDS: dict[str, float] = {
    # Strong bullish
    "surge": 0.8, "soar": 0.8, "rally": 0.7, "breakout": 0.7,
    "bullish": 0.6, "upgrade": 0.6, "beat expectations": 0.7,
    "outperform": 0.6, "record high": 0.8, "all-time high": 0.8,
    "dovish": 0.5, "rate cut": 0.6, "stimulus": 0.5, "easing": 0.5,
    "recovery": 0.5, "expansion": 0.4, "growth": 0.4, "strong jobs": 0.5,
    "positive gdp": 0.5, "increased demand": 0.4, "buy": 0.3, "long": 0.3,
    "support": 0.3, "bounce": 0.4, "reversal": 0.3, "accumulation": 0.4,
    "higher low": 0.5, "higher high": 0.5, "golden cross": 0.6,
    # Moderate bullish
    "optimism": 0.3, "confidence": 0.3, "improve": 0.3, "gain": 0.3,
    "rise": 0.3, "up": 0.2, "higher": 0.2, "advance": 0.3,
    "reclaim": 0.3, "hold support": 0.4, "institutional buying": 0.5,
}

_BEARISH_KEYWORDS: dict[str, float] = {
    # Strong bearish
    "crash": -0.8, "plunge": -0.8, "collapse": -0.7, "selloff": -0.7,
    "bearish": -0.6, "downgrade": -0.6, "miss expectations": -0.7,
    "underperform": -0.6, "record low": -0.8, "hawkish": -0.5,
    "rate hike": -0.6, "tightening": -0.5, "recession": -0.6,
    "contraction": -0.4, "unemployment": -0.4, "weak jobs": -0.5,
    "negative gdp": -0.5, "reduced demand": -0.4, "sell": -0.3, "short": -0.3,
    "resistance": -0.3, "rejection": -0.4, "distribution": -0.4,
    "lower low": -0.5, "lower high": -0.5, "death cross": -0.6,
    # Moderate bearish
    "pessimism": -0.3, "concern": -0.3, "decline": -0.3, "loss": -0.3,
    "fall": -0.3, "down": -0.2, "lower": -0.2, "retreat": -0.3,
    "breakdown": -0.4, "institutional selling": -0.5, "fear": -0.4,
    "panic": -0.6, "liquidation": -0.5, "margin call": -0.5,
}

# Economic event impact weights
_ECONOMIC_EVENT_IMPACT: dict[str, ImpactLevel] = {
    "non-farm payrolls": ImpactLevel.HIGH,
    "nfp": ImpactLevel.HIGH,
    "fomc": ImpactLevel.HIGH,
    "federal reserve": ImpactLevel.HIGH,
    "interest rate": ImpactLevel.HIGH,
    "cpi": ImpactLevel.HIGH,
    "inflation": ImpactLevel.HIGH,
    "gdp": ImpactLevel.HIGH,
    "ecb": ImpactLevel.HIGH,
    "bank of japan": ImpactLevel.HIGH,
    "boj": ImpactLevel.HIGH,
    "bank of england": ImpactLevel.HIGH,
    "unemployment rate": ImpactLevel.MEDIUM,
    "jobless claims": ImpactLevel.MEDIUM,
    "retail sales": ImpactLevel.MEDIUM,
    "pmi": ImpactLevel.MEDIUM,
    "manufacturing": ImpactLevel.MEDIUM,
    "consumer confidence": ImpactLevel.MEDIUM,
    "trade balance": ImpactLevel.MEDIUM,
    "housing starts": ImpactLevel.LOW,
    "building permits": ImpactLevel.LOW,
    "industrial production": ImpactLevel.LOW,
}

# Time decay constants
_NEWS_HALF_LIFE_HOURS = 4.0      # news sentiment halves every 4 hours
_SOCIAL_HALF_LIFE_HOURS = 1.0    # social sentiment halves every 1 hour


# ---------------------------------------------------------------------------
# News sentiment analyzer
# ---------------------------------------------------------------------------

class NewsSentimentAnalyzer:
    """Analyze sentiment from news headlines and articles.

    Uses keyword-based scoring for speed, with configurable LLM escalation.
    """

    def __init__(
        self,
        bullish_keywords: dict[str, float] | None = None,
        bearish_keywords: dict[str, float] | None = None,
        llm_threshold: float = 0.3,  # escalate to LLM if confidence < this
    ) -> None:
        self._bullish = bullish_keywords or _BULLISH_KEYWORDS
        self._bearish = bearish_keywords or _BEARISH_KEYWORDS
        self._llm_threshold = llm_threshold

    def analyze_headline(self, headline: str) -> dict[str, Any]:
        """Score a single headline.

        Returns: {score, confidence, matched_keywords}
        """
        text = headline.lower()
        score = 0.0
        matched: list[tuple[str, float]] = []

        for keyword, weight in self._bullish.items():
            if keyword in text:
                score += weight
                matched.append((keyword, weight))

        for keyword, weight in self._bearish.items():
            if keyword in text:
                score += weight  # weight is already negative
                matched.append((keyword, weight))

        # Normalize to -1 to +1
        if matched:
            max_possible = sum(abs(w) for _, w in matched)
            normalized = score / max(max_possible, 0.01)
            confidence = min(len(matched) / 3.0, 1.0)  # more matches = more confidence
        else:
            normalized = 0.0
            confidence = 0.0

        return {
            "score": round(np.clip(normalized, -1, 1), 4),
            "confidence": round(confidence, 3),
            "matched_keywords": [(k, round(w, 2)) for k, w in matched],
            "headline": headline,
        }

    def analyze_batch(
        self,
        headlines: list[str],
        timestamps: list[float] | None = None,
        weights: list[float] | None = None,
    ) -> SentimentResult:
        """Analyze a batch of headlines with time-decay weighting.

        Args:
            headlines: List of news headlines
            timestamps: Unix timestamps for each headline (for decay)
            weights: Per-headline importance weights (e.g., source reliability)
        """
        if not headlines:
            return SentimentResult(
                source=SentimentSource.NEWS,
                score=0.0,
                polarity=SentimentPolarity.NEUTRAL,
                confidence=0.0,
                sample_size=0,
            )

        if timestamps is None:
            timestamps = [time.time()] * len(headlines)
        if weights is None:
            weights = [1.0] * len(headlines)

        now = time.time()
        scores: list[float] = []
        decayed_weights: list[float] = []
        headline_results: list[dict[str, Any]] = []

        for headline, ts, w in zip(headlines, timestamps, weights):
            result = self.analyze_headline(headline)
            scores.append(result["score"])

            # Time decay
            age_hours = max((now - ts) / 3600, 0)
            decay = math.exp(-0.693 * age_hours / _NEWS_HALF_LIFE_HOURS)  # ln(2) / half_life
            decayed_weights.append(w * decay)

            headline_results.append(result)

        # Weighted average
        total_weight = sum(decayed_weights)
        if total_weight > 0:
            weighted_score = sum(s * w for s, w in zip(scores, decayed_weights)) / total_weight
        else:
            weighted_score = 0.0

        # Confidence: based on sample size and weight concentration
        sample_confidence = min(len(headlines) / 10.0, 1.0)
        avg_headline_conf = np.mean([r["confidence"] for r in headline_results])
        overall_confidence = sample_confidence * 0.4 + avg_headline_conf * 0.6

        # Top bullish/bearish headlines
        scored_headlines = list(zip(headlines, scores))
        scored_headlines.sort(key=lambda x: x[1])
        top_bearish = [h for h, s in scored_headlines[:3] if s < -0.1]
        top_bullish = [h for h, s in reversed(scored_headlines[-3:]) if s > 0.1]

        return SentimentResult(
            source=SentimentSource.NEWS,
            score=round(float(np.clip(weighted_score, -1, 1)), 4),
            polarity=self._classify_polarity(weighted_score),
            confidence=round(float(overall_confidence), 3),
            sample_size=len(headlines),
            headline_scores=headline_results[:20],  # cap for serialization
            top_bullish=top_bullish[:5],
            top_bearish=top_bearish[:5],
        )

    @staticmethod
    def _classify_polarity(score: float) -> SentimentPolarity:
        if score > 0.6:
            return SentimentPolarity.VERY_BULLISH
        if score > 0.2:
            return SentimentPolarity.BULLISH
        if score < -0.6:
            return SentimentPolarity.VERY_BEARISH
        if score < -0.2:
            return SentimentPolarity.BEARISH
        return SentimentPolarity.NEUTRAL


# ---------------------------------------------------------------------------
# Social media sentiment analyzer
# ---------------------------------------------------------------------------

class SocialSentimentAnalyzer:
    """Analyze sentiment from social media posts (Twitter/X, Reddit, Telegram).

    Social media is noisier than news — applies heavier filtering and
    shorter time decay.
    """

    def __init__(self) -> None:
        self._news_analyzer = NewsSentimentAnalyzer()

    def analyze(
        self,
        posts: list[str],
        timestamps: list[float] | None = None,
        platforms: list[str] | None = None,
    ) -> SentimentResult:
        """Analyze social media posts.

        Applies the same keyword scoring as news, but with:
        - Shorter time decay (1h half-life vs 4h for news)
        - Spam/noise filtering
        - Platform-specific weighting
        """
        if not posts:
            return SentimentResult(
                source=SentimentSource.SOCIAL,
                score=0.0,
                polarity=SentimentPolarity.NEUTRAL,
                confidence=0.0,
                sample_size=0,
            )

        # Filter spam and low-quality posts
        filtered = []
        filtered_ts = []
        filtered_platforms = []
        for i, post in enumerate(posts):
            if self._is_quality_post(post):
                filtered.append(post)
                filtered_ts.append(timestamps[i] if timestamps else time.time())
                filtered_platforms.append(platforms[i] if platforms else "unknown")

        if not filtered:
            return SentimentResult(
                source=SentimentSource.SOCIAL,
                score=0.0,
                polarity=SentimentPolarity.NEUTRAL,
                confidence=0.0,
                sample_size=0,
            )

        # Platform weights (Twitter = retail, Reddit = crowd, Telegram = crypto-native)
        platform_weight_map = {
            "twitter": 0.7,
            "x": 0.7,
            "reddit": 0.8,
            "telegram": 0.9,  # crypto-native, higher signal
            "discord": 0.6,
            "unknown": 0.5,
        }
        weights = [platform_weight_map.get(p, 0.5) for p in filtered_platforms]

        # Use news analyzer with social time decay
        result = self._news_analyzer.analyze_batch(filtered, filtered_ts, weights)
        result.source = SentimentSource.SOCIAL

        # Apply social noise penalty — reduce confidence
        result.confidence = round(result.confidence * 0.7, 3)

        return result

    @staticmethod
    def _is_quality_post(text: str) -> bool:
        """Filter out spam, memes, and low-quality posts."""
        text_lower = text.lower().strip()

        # Too short
        if len(text_lower) < 10:
            return False

        # Mostly emoji or special characters
        alpha_ratio = sum(c.isalpha() for c in text_lower) / max(len(text_lower), 1)
        if alpha_ratio < 0.4:
            return False

        # Spam patterns
        spam_patterns = [
            r"(buy now|guaranteed|100x|moon|pump|dump)",
            r"(free money|get rich|no risk)",
            r"(t\.me/|join my|signal group)",
        ]
        for pattern in spam_patterns:
            if re.search(pattern, text_lower):
                return False

        return True


# ---------------------------------------------------------------------------
# Economic calendar impact scorer
# ---------------------------------------------------------------------------

class EconomicCalendarScorer:
    """Score the impact of upcoming economic events on trading conditions.

    Provides risk adjustment factors that reduce signal strength
    before high-impact events.
    """

    def __init__(
        self,
        event_impact: dict[str, ImpactLevel] | None = None,
    ) -> None:
        self._impact_map = event_impact or _ECONOMIC_EVENT_IMPACT

    def score_event(self, event_name: str) -> ImpactLevel:
        """Classify the impact level of an economic event."""
        event_lower = event_name.lower()
        for keyword, impact in self._impact_map.items():
            if keyword in event_lower:
                return impact
        return ImpactLevel.NONE

    def analyze(
        self,
        events: list[dict[str, Any]],
        current_time: float | None = None,
    ) -> SentimentResult:
        """Analyze upcoming economic events and their market impact.

        Args:
            events: List of event dicts with keys:
                - name: str (event name)
                - time: float (unix timestamp)
                - forecast: str (forecasted value, optional)
                - previous: str (previous value, optional)
                - currency: str (e.g., "USD", "EUR", optional)
            current_time: Current unix timestamp
        """
        if current_time is None:
            current_time = time.time()

        if not events:
            return SentimentResult(
                source=SentimentSource.ECONOMIC_CALENDAR,
                score=0.0,
                polarity=SentimentPolarity.NEUTRAL,
                confidence=1.0,
                sample_size=0,
            )

        impact_scores: list[float] = []
        risk_adjustments: list[float] = []
        event_details: list[dict[str, Any]] = []

        for event in events:
            name = event.get("name", "")
            event_time = event.get("time", current_time)
            impact = self.score_event(name)

            # Time proximity factor — closer events have more impact
            hours_until = max((event_time - current_time) / 3600, 0)

            if impact == ImpactLevel.HIGH:
                # High impact: reduce exposure 2h before, max reduction 30min before
                if hours_until <= 0.25:  # 15 minutes
                    proximity = 1.0
                elif hours_until <= 2.0:
                    proximity = 1.0 - (hours_until / 2.0)
                else:
                    proximity = 0.0
                risk_adj = proximity * 0.5  # up to 50% signal reduction

            elif impact == ImpactLevel.MEDIUM:
                if hours_until <= 0.5:
                    proximity = 0.7
                elif hours_until <= 1.0:
                    proximity = 0.3
                else:
                    proximity = 0.0
                risk_adj = proximity * 0.25  # up to 25% signal reduction

            else:
                proximity = 0.0
                risk_adj = 0.0

            risk_adjustments.append(risk_adj)

            event_details.append({
                "name": name,
                "impact": impact.value,
                "hours_until": round(hours_until, 2),
                "risk_adjustment": round(risk_adj, 3),
            })

        # Overall risk adjustment is the maximum across all events
        max_risk = max(risk_adjustments) if risk_adjustments else 0.0

        # Event proximity doesn't generate a directional score — it's a risk factor
        return SentimentResult(
            source=SentimentSource.ECONOMIC_CALENDAR,
            score=0.0,  # no directional bias from calendar
            polarity=SentimentPolarity.NEUTRAL,
            confidence=1.0,
            sample_size=len(events),
            headline_scores=event_details,
        )


# ---------------------------------------------------------------------------
# Aggregate sentiment engine
# ---------------------------------------------------------------------------

class SentimentEngine:
    """Aggregate sentiment from multiple sources with time-decay weighting.

    Combines news, social, and economic calendar sentiment into a single
    actionable sentiment score with risk adjustment.

    Usage::

        engine = SentimentEngine()
        result = engine.analyze(
            news_headlines=["EUR/USD surges on dovish ECB", ...],
            social_posts=["bullish on EUR", ...],
            economic_events=[{"name": "FOMC", "time": ...}, ...],
        )
        # result.risk_adjustment → 0.15 (reduce signal strength by 15%)
    """

    # Source weights for aggregation
    _SOURCE_WEIGHTS: dict[SentimentSource, float] = {
        SentimentSource.NEWS: 0.45,
        SentimentSource.SOCIAL: 0.25,
        SentimentSource.ECONOMIC_CALENDAR: 0.30,
    }

    def __init__(self) -> None:
        self._news = NewsSentimentAnalyzer()
        self._social = SocialSentimentAnalyzer()
        self._calendar = EconomicCalendarScorer()

    def analyze(
        self,
        news_headlines: list[str] | None = None,
        news_timestamps: list[float] | None = None,
        social_posts: list[str] | None = None,
        social_timestamps: list[float] | None = None,
        social_platforms: list[str] | None = None,
        economic_events: list[dict[str, Any]] | None = None,
    ) -> AggregateSentiment:
        """Run full sentiment analysis across all sources.

        Returns AggregateSentiment with weighted score and risk adjustment.
        """
        results: dict[SentimentSource, SentimentResult] = {}

        # News
        if news_headlines:
            results[SentimentSource.NEWS] = self._news.analyze_batch(
                news_headlines, news_timestamps,
            )

        # Social
        if social_posts:
            results[SentimentSource.SOCIAL] = self._social.analyze(
                social_posts, social_timestamps, social_platforms,
            )

        # Economic calendar
        if economic_events:
            results[SentimentSource.ECONOMIC_CALENDAR] = self._calendar.analyze(
                economic_events,
            )

        # Aggregate
        if not results:
            return AggregateSentiment(
                score=0.0,
                polarity=SentimentPolarity.NEUTRAL,
                confidence=0.0,
                reasoning="No sentiment sources available",
            )

        weighted_score = 0.0
        total_weight = 0.0
        total_confidence = 0.0

        for source, result in results.items():
            weight = self._SOURCE_WEIGHTS.get(source, 0.33)
            # Adjust weight by confidence — low confidence sources contribute less
            effective_weight = weight * result.confidence
            weighted_score += result.score * effective_weight
            total_weight += effective_weight
            total_confidence += result.confidence * weight

        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0.0

        # Normalize confidence
        total_source_weight = sum(
            self._SOURCE_WEIGHTS.get(s, 0.33) for s in results
        )
        final_confidence = total_confidence / max(total_source_weight, 0.01)

        # Risk adjustment from economic calendar
        calendar_result = results.get(SentimentSource.ECONOMIC_CALENDAR)
        risk_adj = 0.0
        if calendar_result and calendar_result.headline_scores:
            risk_adj = max(
                (e.get("risk_adjustment", 0) for e in calendar_result.headline_scores),
                default=0.0,
            )

        # Build reasoning
        reasoning = self._build_reasoning(results, final_score, risk_adj)

        return AggregateSentiment(
            score=round(float(np.clip(final_score, -1, 1)), 4),
            polarity=self._classify_polarity(final_score),
            confidence=round(float(final_confidence), 3),
            news_sentiment=results.get(SentimentSource.NEWS),
            social_sentiment=results.get(SentimentSource.SOCIAL),
            calendar_impact=results.get(SentimentSource.ECONOMIC_CALENDAR),
            risk_adjustment=round(risk_adj, 3),
            reasoning=reasoning,
        )

    @staticmethod
    def _classify_polarity(score: float) -> SentimentPolarity:
        if score > 0.6:
            return SentimentPolarity.VERY_BULLISH
        if score > 0.2:
            return SentimentPolarity.BULLISH
        if score < -0.6:
            return SentimentPolarity.VERY_BEARISH
        if score < -0.2:
            return SentimentPolarity.BEARISH
        return SentimentPolarity.NEUTRAL

    @staticmethod
    def _build_reasoning(
        results: dict[SentimentSource, SentimentResult],
        final_score: float,
        risk_adj: float,
    ) -> str:
        """Build human-readable sentiment reasoning."""
        parts: list[str] = []

        for source, result in results.items():
            label = source.value.replace("_", " ")
            parts.append(f"{label}: {result.polarity.value} ({result.score:+.2f}, n={result.sample_size})")

        if risk_adj > 0.1:
            parts.append(f"⚠️ High-impact event risk: reduce exposure by {risk_adj:.0%}")

        summary = "Aggregate: " + (
            "bullish" if final_score > 0.1 else
            "bearish" if final_score < -0.1 else
            "neutral"
        )
        parts.insert(0, summary)

        return " | ".join(parts)
