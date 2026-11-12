"""Cryptographic, JWT, rate-limiting, and security audit helpers for Phase 2."""
from __future__ import annotations

import datetime
import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Callable, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.models import AuditLog

logger = logging.getLogger("pluto.security")

_PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
# Dummy Argon2id hash generated once at import so unknown-email login performs real Argon2 verification work.
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("pluto-timing-equalizer-never-matches-!@#987")

_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: Dict[str, deque] = defaultdict(deque)
_TOKEN_SINK: Optional[Callable[[Dict[str, Any]], None]] = None

_REDACT_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "new_password",
        "token",
        "raw_token",
        "access_token",
        "refresh_token",
        "secret",
        "secret_key",
        "authorization",
        "cookie",
        "raw_text",
        "transcript",
    }
)


def utcnow_naive() -> datetime.datetime:
    """Return UTC timestamp stripped of tzinfo to match SQLite/PG columns consistently."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    """Normalize email for canonical lookup and uniqueness."""
    return email.strip().lower()


def validate_password_strength(password: str) -> None:
    """Enforce baseline password length and complexity constraints."""
    if not isinstance(password, str) or len(password) < 10:
        raise AppError(
            status_code=422,
            code="weak_password",
            message="Password must be at least 10 characters long.",
        )
    if len(password) > 128:
        raise AppError(
            status_code=422,
            code="password_too_long",
            message="Password must be at most 128 characters long.",
        )
    has_alpha = bool(re.search(r"[A-Za-z]", password))
    has_digit_or_symbol = bool(re.search(r"[^A-Za-z\s]", password))
    if not (has_alpha and has_digit_or_symbol):
        raise AppError(
            status_code=422,
            code="weak_password",
            message="Password must include both letters and at least one number or symbol.",
        )


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plaintext password against an Argon2id hash cleanly."""
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def equalize_unknown_user_timing(password: str) -> None:
    """Run Argon2 verification work when user record does not exist to reduce timing signals."""
    verify_password(password, _DUMMY_PASSWORD_HASH)


def needs_password_rehash(password_hash: str) -> bool:
    try:
        return bool(_PASSWORD_HASHER.check_needs_rehash(password_hash))
    except InvalidHashError:
        return True


def generate_opaque_token(nbytes: int = 32) -> str:
    """Return high-entropy URL-safe opaque token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Return SHA-256 hex digest of an opaque token for DB persistence."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def constant_time_equals(a: Optional[str], b: Optional[str]) -> bool:
    """Constant-time string comparison safe against timing side-channels."""
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def create_access_token(user_id: str, role: str, token_version: int) -> tuple[str, int]:
    """Mint a short-lived signed JWT access token."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ttl_minutes = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    exp = now + datetime.timedelta(minutes=ttl_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "tv": int(token_version),
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iss": "pluto-vproctor",
        "aud": "pluto-api",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.get_signing_secret(), algorithm="HS256")
    return token, ttl_minutes * 60


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify and decode a signed JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.get_signing_secret(),
            algorithms=["HS256"],
            audience="pluto-api",
            issuer="pluto-vproctor",
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(status_code=401, code="token_expired", message="Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(status_code=401, code="invalid_token", message="Invalid access token.") from exc

    if payload.get("type") != "access" or not payload.get("sub") or "tv" not in payload:
        raise AppError(status_code=401, code="invalid_token", message="Invalid access token claims.")
    return payload


def enforce_rate_limit(bucket: str, limit: int, window_seconds: int) -> None:
    """In-memory sliding-window rate limiter raising HTTP 429 on burst abuse."""
    now = time.monotonic()
    cutoff = now - float(window_seconds)
    with _RATE_LOCK:
        if len(_RATE_BUCKETS) > 500:
            stale_keys = [k for k, q in _RATE_BUCKETS.items() if not q or q[-1] < cutoff]
            for k in stale_keys:
                _RATE_BUCKETS.pop(k, None)
        dq = _RATE_BUCKETS[bucket]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            retry_after = max(1, int(dq[0] + window_seconds - now))
            raise AppError(
                status_code=429,
                code="rate_limited",
                message="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        dq.append(now)


def reset_rate_limits() -> None:
    """Clear rate limiter buckets cleanly for isolated test execution."""
    with _RATE_LOCK:
        _RATE_BUCKETS.clear()


def set_test_token_sink(sink: Optional[Callable[[Dict[str, Any]], None]]) -> None:
    """Register an out-of-band callback (e.g., email sender / test capture) for verification/reset tokens."""
    global _TOKEN_SINK
    _TOKEN_SINK = sink


def emit_one_time_token_event(event: Dict[str, Any]) -> None:
    """Dispatch out-of-band verification/reset token delivery without logging raw tokens."""
    if _TOKEN_SINK is not None:
        _TOKEN_SINK(dict(event))
    logger.info(
        "Issued one-time token event",
        extra={"purpose": event.get("purpose"), "user_id": event.get("user_id")},
    )


def redact_sensitive_fields(value: Any) -> Any:
    """Recursively mask credentials, tokens, and raw PII text before persistence/logging."""
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in value.items():
            key_low = str(k).strip().lower()
            if key_low in _REDACT_KEYS:
                cleaned[str(k)] = "[REDACTED]"
            else:
                cleaned[str(k)] = redact_sensitive_fields(v)
        return cleaned
    if isinstance(value, list):
        return [redact_sensitive_fields(item) for item in value]
    return value


def record_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    """Create an immutable audit log entry with redacted metadata."""
    entry = AuditLog(
        id=f"aud_{uuid.uuid4().hex[:16]}",
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=redact_sensitive_fields(details or {}),
        ip_address=ip_address,
        created_at=utcnow_naive(),
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry

