"""Zoho Catalyst AppSail native SDK context and runtime detection.

Captures Catalyst's injected `x-zc-*` request headers on incoming HTTP requests
and initializes `zcatalyst_sdk` cleanly on any request or background thread
without requiring manual OAuth keys or client secrets inside AppSail.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger("pluto.catalyst")

_HEADERS_LOCK = threading.Lock()
_LAST_CATALYST_HEADERS: Dict[str, str] = {}
_LAST_REQUEST_ORIGIN: str = ""


class _HeaderRequestProxy:
    """Minimal request adapter carrying headers for zcatalyst_sdk.initialize(req=...)."""

    def __init__(self, headers: Mapping[str, str]):
        self.headers = dict(headers)


def is_sdk_installed() -> bool:
    """Return True when the official zcatalyst_sdk package is importable."""
    try:
        import zcatalyst_sdk  # noqa: F401
        return True
    except Exception:
        return False


def capture_catalyst_headers(headers: Mapping[str, str], origin_url: str = "") -> bool:
    """Record Catalyst-injected headers (`x-zc-*`) from an incoming AppSail request."""
    global _LAST_REQUEST_ORIGIN
    if origin_url:
        _LAST_REQUEST_ORIGIN = origin_url.rstrip("/")

    zc_headers = {
        k: v for k, v in headers.items()
        if k.lower().startswith("x-zc-") or k.lower().startswith("x-catalyst-") or k.lower() in {"cookie", "authorization"}
    }
    has_catalyst_identity = any(
        k.lower() in {"x-zc-project-key", "x-zc-projectid", "x-zc-admin-cred-token"}
        for k in zc_headers
    )
    if not has_catalyst_identity:
        return False

    with _HEADERS_LOCK:
        _LAST_CATALYST_HEADERS.clear()
        _LAST_CATALYST_HEADERS.update(zc_headers)
    return True


def has_catalyst_headers() -> bool:
    """Return True once AppSail has delivered live Catalyst identity headers."""
    with _HEADERS_LOCK:
        return bool(_LAST_CATALYST_HEADERS)


def get_last_request_origin() -> str:
    """Return the most recently observed public HTTPS origin for email links."""
    return _LAST_REQUEST_ORIGIN


def get_catalyst_app(scope: str = "admin") -> Optional[Any]:
    """Initialize and return a thread-local Zoho Catalyst SDK CatalystApp instance.

    Returns None safely when running outside Zoho Catalyst (e.g., local dev / pytest).
    """
    if not is_sdk_installed():
        return None

    with _HEADERS_LOCK:
        headers_snapshot = dict(_LAST_CATALYST_HEADERS)

    if not headers_snapshot:
        return None

    try:
        import zcatalyst_sdk

        return zcatalyst_sdk.initialize(
            req=_HeaderRequestProxy(headers_snapshot),
            scope=scope,
        )
    except Exception as exc:
        logger.debug("Catalyst SDK initialize skipped/failed: %s", exc)
        return None


def get_catalyst_status() -> Dict[str, Any]:
    """Return safe, non-secret status metadata for Zoho Catalyst services."""
    from backend.app.config import settings

    sdk_ok = is_sdk_installed()
    headers_ok = has_catalyst_headers()
    bucket = (settings.STRATUS_BUCKET or "").strip()
    rest_stratus = bool((settings.STRATUS_ENDPOINT or "").strip() and bucket and (settings.STRATUS_ACCESS_KEY or "").strip())

    if bucket and sdk_ok and headers_ok:
        stratus_mode = "catalyst_sdk"
    elif rest_stratus:
        stratus_mode = "rest_api"
    elif bucket:
        stratus_mode = "bucket_configured_awaiting_catalyst_headers"
    else:
        stratus_mode = "local_only"

    return {
        "sdk_installed": sdk_ok,
        "appsail_runtime": bool(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT")),
        "catalyst_headers_detected": headers_ok,
        "stratus_mode": stratus_mode,
        "stratus_bucket": bucket or None,
        "mail_configured": bool((settings.CATALYST_MAIL_FROM or "").strip()),
        "quickml_configured": bool((settings.QUICKML_ENDPOINT or "").strip() and (settings.QUICKML_API_KEY or "").strip()),
    }
