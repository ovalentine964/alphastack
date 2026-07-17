import sys, asyncio
sys.path.insert(0, "/app/src")
from alphastack.ai.model_client import AlphaModel

async def test():
    m = AlphaModel()
    print(f"Model: {m.model}")
    print(f"Provider: {m.provider}")
    
    system_prompt = (
        "You are AlphaStack AI, a quantitative trading assistant. "
        "Current market: BTC=$63,185.99 (+0.12% 24h). Portfolio: 0 open positions. "
        "Be helpful, concise, and knowledgeable about markets and trading. "
        "Give actionable insights when asked about trading. Keep responses under 500 words."
    )
    
    avail = await m.is_available()
    print(f"Available: {avail}")
    
    response = await m.chat("How are you", system=system_prompt)
    print(f"Response: {response[:300]}")

asyncio.run(test())
