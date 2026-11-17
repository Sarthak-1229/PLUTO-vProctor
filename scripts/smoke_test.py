#!/usr/bin/env python3
"""
PLUTO vProctor — Deployment Smoke Test
======================================
Hits critical health, readiness and API endpoints after deployment.

Usage (local):
    python scripts/smoke_test.py

Usage (against Catalyst AppSail):
    PLUTO_BASE_URL=https://your-appsail.catalyst.zohocloud.com python scripts/smoke_test.py

Exit code 0 = all checks passed. Non-zero = at least one check failed.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("PLUTO_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "15"))

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m⚠\033[0m"


def check(label: str, url: str, expected_status: int = 200, json_key: str = None):
    """Perform a single HTTP GET check and report result."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            if status == expected_status:
                detail = ""
                if json_key:
                    try:
                        data = json.loads(body)
                        detail = f" [{json_key}={data.get(json_key, '?')}]"
                    except Exception:
                        pass
                print(f"  {PASS}  {label}{detail}")
                return True
            else:
                print(f"  {FAIL}  {label} — expected HTTP {expected_status}, got {status}")
                return False
    except urllib.error.HTTPError as exc:
        if exc.code == expected_status:
            print(f"  {PASS}  {label}")
            return True
        print(f"  {FAIL}  {label} — HTTP {exc.code}: {exc.reason}")
        return False
    except Exception as exc:
        print(f"  {FAIL}  {label} — {exc}")
        return False


def main():
    print(f"\n{'='*60}")
    print(f"  PLUTO vProctor — Smoke Test")
    print(f"  Target: {BASE_URL}")
    print(f"{'='*60}\n")

    start = time.monotonic()
    results = []

    # ── Core health endpoints ─────────────────────────────────────
    print("Core Health:")
    results.append(check("GET /health",        f"{BASE_URL}/health",       json_key="status"))
    results.append(check("GET /ready",          f"{BASE_URL}/ready",        json_key="status"))
    results.append(check("GET /api/health",     f"{BASE_URL}/api/health",   json_key="status"))

    # ── API availability ──────────────────────────────────────────
    print("\nAPI Endpoints:")
    results.append(check("GET /api/jobs",       f"{BASE_URL}/api/jobs"))
    results.append(check("GET /api/questions (sample set)", f"{BASE_URL}/api/questions/sets"))

    # ── Auth routes exist (expect 401/403 without token) ─────────
    print("\nAuth Guards (expect 401/403):")
    results.append(check("GET /api/sessions (unauthenticated)", f"{BASE_URL}/api/sessions", expected_status=401))

    # ── Frontend static assets served? ───────────────────────────
    # Only meaningful when frontend is served by the same host (local dev).
    # On Catalyst, frontend is on Web Client Hosting and backend is AppSail.
    if BASE_URL.startswith("http://127") or BASE_URL.startswith("http://localhost"):
        print("\nFrontend (local only):")
        results.append(check("GET / (SPA root)", f"{BASE_URL}/", expected_status=200))

    elapsed = time.monotonic() - start
    passed = sum(results)
    failed = len(results) - passed

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed  ({elapsed:.2f}s)")
    print(f"{'='*60}\n")

    if failed:
        print(f"  {FAIL}  SMOKE TEST FAILED — {failed} check(s) did not pass.\n")
        sys.exit(1)
    else:
        print(f"  {PASS}  All checks passed. Deployment looks healthy.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
