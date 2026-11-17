#!/usr/bin/env python3
"""Zoho Catalyst AppSail standard entrypoint alias (app.py)."""
from run import app, port, uvicorn

if __name__ == "__main__":
    print(f"[PLUTO AppSail] Starting via app.py on 0.0.0.0:{port}...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
