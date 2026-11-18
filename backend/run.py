#!/usr/bin/env python3
"""Entry point for Zoho Catalyst AppSail deployment.

This script boots the PLUTO vProctor backend in AppSail by:
1. Adding bundled Linux Python 3.10 packages (`catalyst_libs/`) to sys.path so startup
   binds the port in <4 seconds with zero runtime pip downloads.
2. Establishing the `backend` package shim so `from backend.app...` imports succeed.
3. Binding dynamically to `$X_ZOHO_CATALYST_LISTEN_PORT`.
4. Running uvicorn directly from Python to prevent CLI binary lookup failures.
"""

import os
import sys
import types
from pathlib import Path

_here = Path(__file__).resolve().parent

# Step 1: Prepend bundled dependencies directory (Linux cp310 wheels)
_libs_dir = _here / "catalyst_libs"
if _libs_dir.exists() and str(_libs_dir) not in sys.path:
    sys.path.insert(0, str(_libs_dir))

# Step 2: Ensure 'backend' module is resolvable from the AppSail root directory
if "backend" not in sys.modules:
    _backend_mod = types.ModuleType("backend")
    _backend_mod.__path__ = [str(_here)]
    sys.modules["backend"] = _backend_mod

if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

# Step 3: Import Uvicorn and FastAPI application
import uvicorn
from backend.app.main import app

raw_port = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", "8000")
try:
    port = int(raw_port)
except (ValueError, TypeError):
    port = 8000

if __name__ == "__main__":
    print(f"[PLUTO AppSail] Starting Uvicorn on 0.0.0.0:{port}...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
