#!/usr/bin/env python3
"""Entry point for Zoho Catalyst AppSail deployment.

Boots Uvicorn immediately on `$X_ZOHO_CATALYST_LISTEN_PORT` (<0.5s) to satisfy
AppSail's strict port-binding deadline, while loading the FastAPI application
and bundled Linux cp310 dependencies (`catalyst_libs/`) in a background thread.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import traceback
import types
from pathlib import Path

_here = Path(__file__).resolve().parent

# Step 1: Prepend bundled Linux dependencies directory
_libs_dir = _here / "catalyst_libs"
if _libs_dir.exists() and str(_libs_dir) not in sys.path:
    sys.path.insert(0, str(_libs_dir))

# Step 2: Ensure 'backend' package resolves from the AppSail root directory
if "backend" not in sys.modules:
    _backend_mod = types.ModuleType("backend")
    _backend_mod.__path__ = [str(_here)]
    sys.modules["backend"] = _backend_mod

if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

raw_port = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", "8000")
try:
    port = int(raw_port)
except (ValueError, TypeError):
    port = 8000

_ready_event = threading.Event()
_real_app = None
_job_queue = None
_boot_error: str | None = None
_boot_error_type: str | None = None


def _load_application() -> None:
    global _real_app, _job_queue, _boot_error, _boot_error_type
    try:
        from backend.app.config import settings
        from backend.app.main import app as fastapi_app
        from backend.app.services.job_queue import job_queue

        settings.validate_runtime_safety()
        try:
            settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as storage_exc:
            print(f"[PLUTO AppSail] Storage dir init warning: {storage_exc}", flush=True)
        if "sqlite" in settings.DATABASE_URL:
            from backend.app.db.database import Base, engine
            from backend.app.db import models as _models  # noqa: F401

            Base.metadata.create_all(bind=engine)
        job_queue.start_workers()

        _real_app = fastapi_app
        _job_queue = job_queue
        print("[PLUTO AppSail] FastAPI application loaded and ready.", flush=True)
    except Exception as exc:
        _boot_error_type = type(exc).__name__
        _boot_error = str(exc)
        print(f"[PLUTO AppSail] FATAL startup error: {_boot_error_type}: {_boot_error}", file=sys.stderr, flush=True)
        traceback.print_exc()
    finally:
        _ready_event.set()


async def asgi_bootstrap(scope, receive, send):
    """Lightweight ASGI proxy that binds port immediately and delegates to FastAPI."""
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if _job_queue is not None:
                    try:
                        _job_queue.stop_workers()
                    except Exception:
                        pass
                await send({"type": "lifespan.shutdown.complete"})
                return

    if not _ready_event.is_set():
        await asyncio.to_thread(_ready_event.wait, 25.0)

    if _real_app is not None:
        await _real_app(scope, receive, send)
        return

    # If FastAPI failed to load, return structured 500 JSON (for HTTP) so diagnostics are visible
    if scope["type"] == "http":
        payload = json.dumps(
            {
                "status": "boot_error",
                "error_type": _boot_error_type or "TimeoutError",
                "error": _boot_error or "Application did not finish loading within 25s.",
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def _fallback_diagnostic_server(import_err: Exception) -> None:
    """If uvicorn itself cannot be imported, bind the port with stdlib HTTP server to report why."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    err_payload = json.dumps(
        {
            "status": "uvicorn_import_error",
            "error_type": type(import_err).__name__,
            "error": str(import_err),
            "python_version": sys.version,
            "libs_exists": _libs_dir.exists(),
            "sys_path_head": sys.path[:5],
        }
    ).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_payload)))
            self.end_headers()
            self.wfile.write(err_payload)

    print(f"[PLUTO AppSail] Fallback diagnostic server on 0.0.0.0:{port}: {import_err}", file=sys.stderr, flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    print(f"[PLUTO AppSail] Booting on 0.0.0.0:{port} (Python {sys.version.split()[0]})...", flush=True)
    try:
        import uvicorn
    except Exception as exc:
        traceback.print_exc()
        _fallback_diagnostic_server(exc)
        sys.exit(1)

    threading.Thread(target=_load_application, daemon=True).start()
    uvicorn.run(asgi_bootstrap, host="0.0.0.0", port=port, log_level="info")
