"""Step 2: Market Bias — multi-timeframe trend analysis and higher-timeframe bias."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, Bias, MarketBias
from alphastack.strategy.steps.base import AlphaStackStep


class MarketBiasStep(AlphaStackStep):
    step_number = 2
    step_name = "market_bias"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        # --- Multi-timeframe trend analysis ---
        # Expect closes from multiple timeframes: {tf: [close, ...]}
        tf_data: dict[str, list[float]] = md.get("timeframe_closes", {})

        scores: list[float] = []
        for _tf, closes in tf_data.items():
            if len(closes) < 2:
                continue
            short_ma = sum(closes[-5:]) / min(5, len(closes)) if len(closes) >= 5 else closes[-1]
            long_ma = sum(closes[-20:]) / min(20, len(closes)) if len(closes) >= 20 else closes[-1]
            if long_ma == 0:
                continue
            scores.append((short_ma - long_ma) / long_ma)

        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Trend strength: magnitude of the average score, clamped 0-1
        trend_strength = min(abs(avg_score) * 50, 1.0)

        # --- Higher-timeframe bias ---
        htf_closes: list[float] = md.get("htf_closes", [])
        if len(htf_closes) >= 20:
            htf_short = sum(htf_closes[-5:]) / 5
            htf_long = sum(htf_closes[-20:]) / 20
            htf_score = (htf_short - htf_long) / htf_long if htf_long else 0
        else:
            htf_score = avg_score  # fallback

        htf_bias = Bias.BULLISH if htf_score > 0.001 else (Bias.BEARISH if htf_score < -0.001 else Bias.NEUTRAL)
        bias = Bias.BULLISH if avg_score > 0.001 else (Bias.BEARISH if avg_score < -0.001 else Bias.NEUTRAL)

        market_bias = MarketBias(
            bias=bias,
            trend_strength=trend_strength,
            htf_bias=htf_bias,
        )

        return context.update(bias=market_bias)
