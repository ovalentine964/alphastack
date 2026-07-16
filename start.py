"""Startup wrapper — catches and logs all errors before launching the app."""
import sys
import os
import traceback

print(f"Python: {sys.version}")
print(f"PORT: {os.environ.get('PORT', 'not set')}")
print(f"JWT_SECRET: {'set' if os.environ.get('ALPHASTACK_JWT_SECRET') else 'NOT SET'}")
print(f"CORS_ORIGINS: {os.environ.get('CORS_ORIGINS', 'not set')}")
print(f"AI_PROVIDER: {os.environ.get('AI_PROVIDER', 'not set')}")

try:
    print("Importing live_server...")
    import live_server
    print("✅ live_server imported successfully")
except Exception as e:
    print(f"❌ IMPORT ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("Starting uvicorn...")
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(live_server.app, host="0.0.0.0", port=port)
except Exception as e:
    print(f"❌ RUNTIME ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
