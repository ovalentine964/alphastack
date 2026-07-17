import sys, asyncio
sys.path.insert(0, "/app/src")
from alphastack.ai.model_client import AlphaModel

async def test():
    m = AlphaModel()
    print(f"Provider: {m.provider}")
    print(f"Model: {m.model}")
    avail = await m.is_available()
    print(f"Available: {avail}")
    response = await m.chat("Say hello")
    print(f"Response: {response[:200]}")

asyncio.run(test())
