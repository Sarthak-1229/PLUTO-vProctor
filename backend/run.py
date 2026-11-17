"""Entry point for Zoho Catalyst AppSail deployment.

This script boots the PLUTO vProctor backend in AppSail by:
1. Establishing the `backend` package shim so `from backend.app...` imports succeed.
2. Binding dynamically to `$X_ZOHO_CATALYST_LISTEN_PORT`.
3. Running uvicorn directly from Python to prevent CLI binary lookup failures.
"""

import os
import sys
import types
from pathlib import Path

# Step 1: Ensure 'backend' module is resolvable from the AppSail root directory
_here = Path(__file__).resolve().parent
if "backend" not in sys.modules:
    _backend_mod = types.ModuleType("backend")
    _backend_mod.__path__ = [str(_here)]
    sys.modules["backend"] = _backend_mod

if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

# Step 2: Ensure required core dependencies exist; install if missing
try:
    import uvicorn
    import fastapi
except ImportError:
    print("[PLUTO AppSail] Installing core dependencies from requirements.txt...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(_here / "requirements.txt")])
    import uvicorn
    import fastapi

# Step 3: Import FastAPI application
from backend.app.main import app

if __name__ == "__main__":
    # Zoho Catalyst AppSail injects the listen port via X_ZOHO_CATALYST_LISTEN_PORT
    raw_port = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", "8000")
    try:
        port = int(raw_port)
    except (ValueError, TypeError):
        port = 8000

    print(f"[PLUTO AppSail] Starting Uvicorn on 0.0.0.0:{port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
