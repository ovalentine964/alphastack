#!/usr/bin/env python3
"""Fix AlphaStack Fly.io deployment — set secrets via GraphQL API."""
import json
import httpx
import sys

FLY_API = "https://api.fly.io/graphql"
APP_NAME = "alphastack"

TOKEN = "FlyV1 fm2_lJPECAAAAAAAFjyfxBBs6BE/DTBG1pdc3FzqTv6twrVodHRwczovL2FwaS5mbHkuaW8vdjGUAJLOABs+rh8Lk7lodHRwczovL2FwaS5mbHkuaW8vYWFhL3YxxDxw4/MoDdZscYwwBirfkhJhPJ6AZ3bUPtvK8d6Io22Zh+cvP3ylJiGKUJLtHK7s4bvWDOwpaJ/MLDl7HUnETk/lV7bVYgiC6SC+gJ84xqxXLe2Z1CWbwzq8FnxPg2U1cclpea42NuEhuakPIzyP5z0OR//f+YB4XzyLxqmrIQuo204honJuKr44nWmbRcQgTF4nuBCsYb6TJo8zQdAy+58go6ek4laJzig8C3JlrQw=,fm2_lJPETk/lV7bVYgiC6SC+gJ84xqxXLe2Z1CWbwzq8FnxPg2U1cclpea42NuEhuakPIzyP5z0OR//f+YB4XzyLxqmrIQuo204honJuKr44nWmbRcQQVSy2XL0nP53Z0dfAWWAmNcO5aHR0cHM6Ly9hcGkuZmx5LmlvL2FhYS92MZgEks5qWNaBzo/w3J8XzgAaE8cKkc4AGhPHDMQQx4i5fYdFOOUKHEOu/AN6kMQg0DV6X8k3o4nXHebLNuZLlFtC1ETTZ4RrY6O2MeBPkvQ="

SECRETS = {
    "AI_API_KEY": "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",
    "AI_PROVIDER": "nvidia",
    "AI_BASE_URL": "https://integrate.api.nvidia.com/v1",
    "AI_MODEL": "minimaxai/minimax-m3",
}

def gql(query, variables=None):
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    resp = httpx.post(FLY_API, json={"query": query, "variables": variables or {}}, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

def list_secrets():
    q = """query($name: String!) { app(name: $name) { secrets { name digest createdAt } } }"""
    return gql(q, {"name": APP_NAME})

def set_secrets(secrets: dict):
    mutation = """mutation($input: SetSecretsInput!) {
        setSecrets(input: $input) { release { id version status } }
    }"""
    secrets_input = [{"key": k, "value": v} for k, v in secrets.items()]
    variables = {"input": {"appId": APP_NAME, "secrets": secrets_input}}
    return gql(mutation, variables)

def resume_app():
    mutation = """mutation($input: ResumeAppInput!) {
        resumeApp(input: $input) { app { id name status } }
    }"""
    return gql(mutation, {"input": {"appId": APP_NAME}})

# --- Execute ---
print("1. Listing existing secrets...")
try:
    existing = list_secrets()
    names = [s["name"] for s in existing.get("data", {}).get("app", {}).get("secrets", [])]
    print(f"   Existing: {names}")
except Exception as e:
    print(f"   Warning: {e}")

print("\n2. Setting secrets...")
for k, v in SECRETS.items():
    masked = v[:8] + "..." + v[-4:] if len(v) > 16 else v
    print(f"   {k} = {masked}")

try:
    result = set_secrets(SECRETS)
    if "errors" in result:
        print(f"   ❌ Errors: {json.dumps(result['errors'], indent=2)}")
        sys.exit(1)
    release = result.get("data", {}).get("setSecrets", {}).get("release", {})
    print(f"   ✅ Release v{release.get('version', '?')} — {release.get('status', '?')}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)

print("\n3. Resuming app...")
try:
    resume = resume_app()
    status = resume.get("data", {}).get("resumeApp", {}).get("app", {}).get("status", "?")
    print(f"   ✅ App status: {status}")
except Exception as e:
    print(f"   ⚠️ Resume failed: {e}")

print("\n✅ Done! Bot should be AI-powered in ~30 seconds.")
