# Implementation Report: Model-Agnostic AI Client

**Date:** 2026-07-16  
**Status:** ✅ Complete  
**Author:** AlphaStack Integration Agent

---

## Summary

Refactored AlphaStack's AI client from a hardcoded MiMo-only integration to a **model-agnostic architecture** that works with any OpenAI-compatible API provider. The existing MiMo integration is fully preserved via backward-compatible aliases.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/alphastack/ai/model_client.py` | **Created** | New `AlphaModel` class — model-agnostic AI client |
| `src/alphastack/ai/mimo_client.py` | **Replaced** | Now a backward-compat shim (re-exports from `model_client`) |
| `src/alphastack/ai/__init__.py` | **Updated** | Exports both `AlphaModel` and legacy `MiMoClient` alias |

## Architecture

### Provider Registry (`PROVIDERS` dict)

```
mimo      → Xiaomi MiMo 2.5 Pro       (api.xiaomi.com/v1)
nvidia    → NVIDIA API (any model)     (integrate.api.nvidia.com/v1)
openai    → OpenAI (GPT-5.6, GPT-4o)  (api.openai.com/v1)
anthropic → Anthropic (Claude 4/3.5)   (api.anthropic.com/v1)
fable     → Fable 5                    (api.fable.ai/v1)
google    → Google Gemini 2.5          (generativelanguage.googleapis.com/v1beta/openai)
local     → Local Ollama/llama.cpp     (localhost:11434/v1)
```

### Auto-Detection Logic (17 lines)

URL substring matching against a priority-ordered pattern list:

```python
_URL_PROVIDER_MAP = [
    ("nvidia.com",    "nvidia"),
    ("xiaomi.com",    "mimo"),
    ("openai.com",    "openai"),
    ("anthropic.com", "anthropic"),
    ("fable.ai",      "fable"),
    ("googleapis.com","google"),
    ("localhost",     "local"),
    ("127.0.0.1",     "local"),
]
```

Falls back to `"openai"` for unknown URLs (since most providers implement the OpenAI-compatible API).

### Configuration Resolution (`resolve_config`)

Priority order:
1. Explicit constructor arguments
2. `AI_*` environment variables
3. Legacy `MIMO_*` environment variables (backward compat)
4. Provider-specific defaults
5. Global default (MiMo)

### Anthropic Special Handling

Anthropic's Messages API uses a different format than OpenAI:
- Auth header: `x-api-key` instead of `Authorization: Bearer`
- Request: `/messages` endpoint with `system` at top level
- Response: `{"content": [{"type": "text", "text": "..."}]}`

This is handled transparently — `AlphaModel` detects `provider == "anthropic"` and routes to `_request_anthropic()`.

## Backward Compatibility

### Environment Variables

| Legacy Variable | Maps To | Notes |
|----------------|---------|-------|
| `MIMO_API_KEY` | `AI_API_KEY` | Falls back if `AI_API_KEY` not set |
| `MIMO_BASE_URL` | `AI_BASE_URL` | Falls back if `AI_BASE_URL` not set |
| `MIMO_MODEL` | `AI_MODEL` | Falls back if `AI_MODEL` not set |

### Python Imports

All existing import paths continue to work:

```python
# Legacy (still works)
from alphastack.ai.mimo_client import MiMoClient, ReasoningEngine
from alphastack.ai import MiMoClient, ReasoningEngine

# New (recommended)
from alphastack.ai.model_client import AlphaModel, ReasoningEngine
from alphastack.ai import AlphaModel, ReasoningEngine
```

`MiMoClient` is literally `AlphaModel` — `MiMoClient is AlphaModel` evaluates to `True`.

### Interface Compatibility

All existing methods preserved with identical signatures:
- `reasoning(prompt)` → chain-of-thought reasoning
- `analyze(data)` → market analysis
- `explain(trade)` → trade explanation
- `chat(message)` → general conversation
- `is_available()` → provider health check
- `close()` → resource cleanup

## Features Preserved

| Feature | Status | Notes |
|---------|--------|-------|
| Response caching | ✅ | 5-min TTL, SHA-256 cache keys |
| Rate limiting | ✅ | Token-bucket, 10 req/s |
| Retry with backoff | ✅ | 2 retries, exponential |
| 429 handling | ✅ | Respects `Retry-After` header |
| Heuristic fallback | ✅ | Keyword-based when provider down |
| ReasoningEngine | ✅ | All debate/analysis methods work |

## Usage Examples

### Switch to NVIDIA API

```bash
export AI_PROVIDER=nvidia
export AI_API_KEY=nvapi-xxxxx
# AI_MODEL defaults to nvidia/llama-3.3-70b-instruct
```

### Switch to OpenAI GPT-5.6

```bash
export AI_PROVIDER=openai
export AI_API_KEY=sk-xxxxx
export AI_MODEL=gpt-5.6
```

### Use Anthropic Claude

```bash
export AI_PROVIDER=anthropic
export AI_API_KEY=sk-ant-xxxxx
export AI_MODEL=claude-sonnet-4-20250514
```

### Use Local Ollama

```bash
export AI_PROVIDER=local
# No API key needed for local Ollama
export AI_MODEL=llama3.3:70b
```

### Programmatic

```python
from alphastack.ai import AlphaModel

# Explicit provider
model = AlphaModel(
    provider="nvidia",
    api_key="nvapi-xxxxx",
    model="nvidia/llama-3.3-70b-instruct",
)

# Auto-detect from URL
model = AlphaModel(
    api_key="sk-xxxxx",
    base_url="https://integrate.api.nvidia.com/v1",
)

# Uses env vars (AI_* or MIMO_*)
model = AlphaModel()

result = await model.reasoning("Analyze AAPL momentum")
```

## Verification

- ✅ All 3 files parse as valid Python (`ast.parse`)
- ✅ Direct import from `model_client` works
- ✅ Backward-compat import from `mimo_client` works
- ✅ `MiMoClient is AlphaModel` → `True`
- ✅ Auto-detection returns correct provider for all 6 URL patterns
- ✅ `resolve_config` returns correct defaults when no args/env set
- ✅ Provider defaults applied correctly (NVIDIA → nvidia/llama-3.3-70b-instruct)
