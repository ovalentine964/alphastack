#!/usr/bin/env python3
"""Set Fly.io secrets via GraphQL API — avoids CLI truncation issues.

Usage:
    python scripts/set_flyio_secrets.py FLY_TOKEN AI_API_KEY=nvapi-xxx AI_MODEL=minimaxai/minimax-m3

Or read from .env file:
    python scripts/set_flyio_secrets.py FLY_TOKEN --env .env
"""

import sys
import json
import httpx

APP_NAME = "alphastack-api"
FLY_API = "https://api.fly.io/graphql"


def set_secrets(token: str, secrets: dict[str, str]) -> dict:
    """Set secrets on a Fly.io app via GraphQL mutation."""
    mutation = """
    mutation($input: SetSecretsInput!) {
        setSecrets(input: $input) {
            release {
                id
                version
                status
            }
        }
    }
    """
    # Build secrets list
    secrets_input = [{"key": k, "value": v} for k, v in secrets.items()]

    variables = {
        "input": {
            "appId": APP_NAME,
            "secrets": secrets_input,
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = httpx.post(FLY_API, json={"query": mutation, "variables": variables},
                      headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_secrets(token: str) -> dict:
    """List existing secrets (names only, not values)."""
    query = """
    query($appName: String!) {
        app(name: $appName) {
            secrets {
                name
                digest
                createdAt
            }
        }
    }
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(FLY_API, json={"query": query, "variables": {"appName": APP_NAME}},
                      headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def restart_machines(token: str) -> dict:
    """Restart all machines for the app."""
    mutation = """
    mutation($appName: String!) {
        restartApp(input: {appId: $appName}) {
            app { id name }
        }
    }
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(FLY_API, json={"query": mutation, "variables": {"appName": APP_NAME}},
                      headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) < 3:
        print("Usage: python set_flyio_secrets.py FLY_TOKEN KEY=VALUE [KEY=VALUE ...]")
        print("       python set_flyio_secrets.py FLY_TOKEN --env .env")
        sys.exit(1)

    token = sys.argv[1]
    secrets = {}

    if sys.argv[2] == "--env":
        env_file = sys.argv[3] if len(sys.argv) > 3 else ".env"
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    secrets[k.strip()] = v.strip().strip('"').strip("'")
    else:
        for arg in sys.argv[2:]:
            if "=" in arg:
                k, v = arg.split("=", 1)
                secrets[k.strip()] = v.strip()

    if not secrets:
        print("No secrets to set!")
        sys.exit(1)

    print(f"Setting {len(secrets)} secrets on {APP_NAME}...")
    for k in secrets:
        val = secrets[k]
        print(f"  {k} = {val[:8]}...{val[-4:]}" if len(val) > 16 else f"  {k} = {val}")

    # List existing secrets
    try:
        existing = list_secrets(token)
        existing_names = [s["name"] for s in existing.get("data", {}).get("app", {}).get("secrets", [])]
        print(f"\nExisting secrets: {existing_names}")
    except Exception as e:
        print(f"Warning: could not list existing secrets: {e}")

    # Set secrets
    try:
        result = set_secrets(token, secrets)
        if "errors" in result:
            print(f"\n❌ Errors: {json.dumps(result['errors'], indent=2)}")
            sys.exit(1)
        release = result.get("data", {}).get("setSecrets", {}).get("release", {})
        print(f"\n✅ Secrets set! Release v{release.get('version', '?')} — {release.get('status', '?')}")
    except Exception as e:
        print(f"\n❌ Failed to set secrets: {e}")
        sys.exit(1)

    # Restart machines
    try:
        print("\nRestarting machines...")
        restart_result = restart_machines(token)
        print(f"✅ Restarted: {restart_result.get('data', {}).get('restartApp', {}).get('app', {}).get('name', APP_NAME)}")
    except Exception as e:
        print(f"Warning: restart failed (secrets are set, restart manually): {e}")


if __name__ == "__main__":
    main()
