"""Minimal test server — just FastAPI + health check."""
import os
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok", "port": os.environ.get("PORT", "8000")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
