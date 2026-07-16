"""Minimal startup test — catches import/init errors."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ.setdefault("ALPHASTACK_JWT_SECRET", "test")

errors = []

def test(name, fn):
    try:
        fn()
        print(f"  ✅ {name}")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  ❌ {name}: {e}")

print("=== AlphaStack Startup Test ===\n")

print("1. Core imports:")
test("ccxt", lambda: __import__("ccxt"))
test("fastapi", lambda: __import__("fastapi"))
test("uvicorn", lambda: __import__("uvicorn"))
test("pydantic", lambda: __import__("pydantic"))
test("jwt", lambda: __import__("jwt"))

print("\n2. Monkey-patch:")
test("s10_confluence", lambda: (
    __import__("alphastack.strategy.steps.s10_confluence", fromlist=["_WEIGHTS"]),
    setattr(sys.modules["alphastack.strategy.steps.s10_confluence"], "_WEIGHTS",
            getattr(sys.modules["alphastack.strategy.steps.s10_confluence"], "_DEFAULT_WEIGHTS", {}))
    if not hasattr(sys.modules["alphastack.strategy.steps.s10_confluence"], "_WEIGHTS") else None
))

print("\n3. AlphaStack modules:")
for mod in [
    "alphastack.strategy.context",
    "alphastack.strategy.pipeline",
    "alphastack.agents.orchestrator.graph",
    "alphastack.agents.orchestrator.state",
    "alphastack.agents.strategy.agent",
    "alphastack.agents.risk.agent",
    "alphastack.agents.news.agent",
    "alphastack.agents.execution.agent",
    "alphastack.agents.reflection.agent",
    "alphastack.core.events",
    "alphastack.brokers.registry",
    "alphastack.api.rest.deps",
    "alphastack.security.validators",
    "alphastack.agi.memory",
    "alphastack.agi.planning",
    "alphastack.engine.loop",
    "alphastack.integrations.telegram_bot",
    "alphastack.agents.debate.debate_engine",
    "alphastack.agents.reflection.pre_trade",
    "alphastack.agents.reflection.post_trade",
]:
    test(mod, lambda m=mod: __import__(m, fromlist=[""]))

print("\n4. Telegram deps:")
test("telegram", lambda: __import__("telegram"))
test("telegram.ext", lambda: __import__("telegram.ext"))

print(f"\n{'='*40}")
if errors:
    print(f"\n❌ {len(errors)} errors found:")
    for e in errors:
        print(f"  - {e}")
else:
    print("\n✅ All tests passed!")
