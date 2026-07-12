"""Step 1: Fundamental Intelligence — economic calendar, news sentiment, macro regime."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, Bias, FundamentalData
from alphastack.strategy.steps.base import AlphaStackStep


class FundamentalIntelligence(AlphaStackStep):
    step_number = 1
    step_name = "fundamental_intelligence"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        # --- Economic calendar analysis ---
        high_impact = md.get("high_impact_events", [])
        has_red_event = len(high_impact) > 0

        # --- News sentiment ---
        sentiment_raw: float = md.get("news_sentiment", 0.0)  # -1 … +1

        # --- Macro regime detection ---
        # Simplified: use volatility + trend from higher timeframes
        vix_proxy: float = md.get("volatility_index", 0.0)
        if vix_proxy > 25:
            macro_regime = "risk_off"
        elif vix_proxy > 15:
            macro_regime = "mixed"
        else:
            macro_regime = "risk_on"

        # --- Derive fundamental bias ---
        score = sentiment_raw
        if macro_regime == "risk_off":
            score -= 0.2
        elif macro_regime == "risk_on":
            score += 0.1
        if has_red_event:
            score *= 0.5  # dampen conviction near high-impact news

        if score > 0.2:
            bias = Bias.BULLISH
        elif score < -0.2:
            bias = Bias.BEARISH
        else:
            bias = Bias.NEUTRAL

        fundamental = FundamentalData(
            bias=bias,
            news_sentiment=sentiment_raw,
            macro_regime=macro_regime,
            high_impact_events=high_impact,
        )

        return context.update(fundamental=fundamental)
