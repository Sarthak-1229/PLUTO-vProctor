"""Core authentication workflow service: registration, login, rotation, reset, verification."""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.models import CandidateProfile, OneTimeToken, RefreshToken, User
from backend.app.services.security_service import (
    create_access_token,
    emit_one_time_token_event,
    equalize_unknown_user_timing,
    generate_opaque_token,
    hash_password,
    hash_token,
    normalize_email,
    record_audit_event,
    utcnow_naive,
    validate_password_strength,
    verify_password,
)


def serialize_user(user: User) -> Dict[str, Any]:
    """Serialize public user attributes without leaking credentials or internal counters."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": bool(user.is_active),
        "email_verified": bool(user.email_verified),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _issue_one_time_token(
    db: Session,
    *,
    user: User,
    purpose: str,
    ttl_delta: datetime.timedelta,
) -> str:
    """Invalidate older unused tokens for (user, purpose) and mint a new hashed single-use token."""
    now = utcnow_naive()
    db.query(OneTimeToken).filter(
        OneTimeToken.user_id == user.id,
        OneTimeToken.purpose == purpose,
        OneTimeToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    raw_token = generate_opaque_token(32)
    expires_at = now + ttl_delta
    row = OneTimeToken(
        id=f"ott_{uuid.uuid4().hex[:16]}",
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
        created_at=now,
    )
    db.add(row)
    db.flush()
    emit_one_time_token_event(
        {
            "purpose": purpose,
            "user_id": user.id,
            "email": user.email,
            "raw_token": raw_token,
            "expires_at": expires_at.isoformat(),
        }
    )
    return raw_token


def _mint_session_tokens(
    db: Session,
    *,
    user: User,
    family_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, int, str, str]:
    """Create access JWT, persisted hashed refresh token, and fresh CSRF token."""
    access_token, expires_in = create_access_token(
        user_id=user.id,
        role=user.role,
        token_version=user.token_version,
    )
    raw_refresh = generate_opaque_token(48)
    csrf_token = generate_opaque_token(24)
    now = utcnow_naive()
    rt = RefreshToken(
        id=f"rtok_{uuid.uuid4().hex[:16]}",
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        rotation_family_id=family_id or f"fam_{uuid.uuid4().hex[:16]}",
        expires_at=now + datetime.timedelta(days=int(settings.REFRESH_TOKEN_EXPIRE_DAYS)),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] or None,
        created_at=now,
    )
    db.add(rt)
    db.flush()
    return access_token, expires_in, raw_refresh, csrf_token


def register_candidate(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new candidate account with default candidate role and empty DB profile."""
    normalized = normalize_email(email)
    clean_name = full_name.strip()
    if len(clean_name) < 2:
        raise AppError(status_code=422, code="invalid_name", message="Full name must be at least 2 characters.")

    validate_password_strength(password)

    existing = db.query(User).filter(User.email == normalized).first()
    if existing is not None:
        raise AppError(status_code=409, code="email_exists", message="An account with this email already exists.")

    now = utcnow_naive()
    user = User(
        id=f"usr_{uuid.uuid4().hex[:16]}",
        email=normalized,
        password_hash=hash_password(password),
        full_name=clean_name,
        role="candidate",
        is_active=True,
        email_verified=False,
        failed_login_attempts=0,
        token_version=0,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()

    profile = CandidateProfile(
        id=f"cprof_{uuid.uuid4().hex[:16]}",
        user_id=user.id,
        experience_years=0.0,
        technical_skills_json=[],
        preferred_roles_json=[],
        education_details_json=[],
        experience_summary_json=[],
        portfolio_links_json={},
        profile_completed=False,
        created_at=now,
        updated_at=now,
    )
    db.add(profile)

    _issue_one_time_token(
        db,
        user=user,
        purpose="email_verify",
        ttl_delta=datetime.timedelta(hours=int(settings.EMAIL_VERIFY_EXPIRE_HOURS)),
    )
    access_token, expires_in, raw_refresh, csrf_token = _mint_session_tokens(
        db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    record_audit_event(
        db,
        action="auth.register",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_role=user.role,
        details={"email": normalized},
        ip_address=ip_address,
    )
    db.commit()
    return {
        "user": serialize_user(user),
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "raw_refresh": raw_refresh,
        "csrf_token": csrf_token,
    }


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
    portal: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Authenticate candidate or administrator strictly honoring separate login portals."""
    normalized = normalize_email(email)
    now = utcnow_naive()
    user = db.query(User).filter(User.email == normalized).first()

    if user is None:
        equalize_unknown_user_timing(password)
        record_audit_event(
            db,
            action="auth.login_failed",
            resource_type="user",
            details={"email": normalized, "portal": portal, "reason": "unknown_account"},
            ip_address=ip_address,
            commit=True,
        )
        raise AppError(status_code=401, code="invalid_credentials", message="Invalid email or password.")

    if not user.is_active:
        record_audit_event(
            db,
            action="auth.login_failed",
            resource_type="user",
            resource_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
            details={"portal": portal, "reason": "inactive"},
            ip_address=ip_address,
            commit=True,
        )
        raise AppError(status_code=403, code="account_inactive", message="Account is disabled.")

    if user.locked_until is not None and user.locked_until > now:
        raise AppError(
            status_code=423,
            code="account_locked",
            message="Account temporarily locked due to repeated failed login attempts. Try again later or reset your password.",
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
        event_action = "auth.login_failed"
        if user.failed_login_attempts >= int(settings.MAX_FAILED_LOGIN_ATTEMPTS):
            user.locked_until = now + datetime.timedelta(minutes=int(settings.LOCKOUT_MINUTES))
            event_action = "auth.account_locked"
        record_audit_event(
            db,
            action=event_action,
            resource_type="user",
            resource_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
            details={"portal": portal, "failed_attempts": user.failed_login_attempts},
            ip_address=ip_address,
        )
        db.commit()
        if event_action == "auth.account_locked":
            raise AppError(
                status_code=423,
                code="account_locked",
                message="Account temporarily locked due to repeated failed login attempts.",
            )
        raise AppError(status_code=401, code="invalid_credentials", message="Invalid email or password.")

    # Portal separation AFTER verifying password so role membership is never leaked on wrong passwords.
    if portal == "admin" and user.role not in ("admin", "super_admin"):
        record_audit_event(
            db,
            action="auth.admin_portal_denied",
            resource_type="user",
            resource_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
            details={"portal": portal},
            ip_address=ip_address,
            commit=True,
        )
        raise AppError(
            status_code=403,
            code="admin_required",
            message="Administrator privileges are required for this portal.",
        )
    if portal == "candidate" and user.role != "candidate":
        record_audit_event(
            db,
            action="auth.candidate_portal_denied",
            resource_type="user",
            resource_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
            details={"portal": portal},
            ip_address=ip_address,
            commit=True,
        )
        raise AppError(
            status_code=403,
            code="use_admin_portal",
            message="Administrators must sign in through the dedicated admin login portal.",
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    access_token, expires_in, raw_refresh, csrf_token = _mint_session_tokens(
        db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    record_audit_event(
        db,
        action="auth.login_success",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_role=user.role,
        details={"portal": portal},
        ip_address=ip_address,
    )
    db.commit()
    return {
        "user": serialize_user(user),
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "raw_refresh": raw_refresh,
        "csrf_token": csrf_token,
    }


def rotate_refresh_session(
    db: Session,
    *,
    raw_refresh: Optional[str],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Rotate refresh cookie cleanly and revoke the entire family if token reuse is detected."""
    if not raw_refresh:
        raise AppError(status_code=401, code="missing_refresh_token", message="Refresh session cookie is missing.")

    now = utcnow_naive()
    token_digest = hash_token(raw_refresh)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_digest).first()
    if rt is None:
        raise AppError(status_code=401, code="invalid_refresh_token", message="Invalid refresh session.")

    if rt.revoked_at is not None or rt.replaced_by_id is not None:
        # Refresh token reuse detected -> compromise mitigation: revoke entire token family and invalidate active access tokens!
        db.query(RefreshToken).filter(
            RefreshToken.rotation_family_id == rt.rotation_family_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now}, synchronize_session=False)
        reused_user = db.query(User).filter(User.id == rt.user_id).first()
        if reused_user is not None:
            reused_user.token_version = int(reused_user.token_version or 0) + 1
        record_audit_event(
            db,
            action="auth.refresh_reuse_detected",
            resource_type="refresh_token",
            resource_id=rt.id,
            actor_user_id=rt.user_id,
            details={"rotation_family_id": rt.rotation_family_id},
            ip_address=ip_address,
            commit=True,
        )
        raise AppError(status_code=401, code="refresh_token_reused", message="Refresh session revoked due to reuse detection.")

    if rt.expires_at <= now:
        rt.revoked_at = now
        db.commit()
        raise AppError(status_code=401, code="refresh_token_expired", message="Refresh session has expired.")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if user is None or not user.is_active:
        rt.revoked_at = now
        db.commit()
        raise AppError(status_code=401, code="unauthorized", message="Account is inactive.")

    access_token, expires_in, new_raw_refresh, csrf_token = _mint_session_tokens(
        db,
        user=user,
        family_id=rt.rotation_family_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    new_row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_token(new_raw_refresh))
        .first()
    )
    rt.revoked_at = now
    rt.replaced_by_id = new_row.id if new_row else None
    db.commit()
    return {
        "user": serialize_user(user),
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "raw_refresh": new_raw_refresh,
        "csrf_token": csrf_token,
    }


def logout_session(
    db: Session,
    *,
    raw_refresh: Optional[str],
    current_user: Optional[User],
    ip_address: Optional[str] = None,
) -> None:
    """Revoke refresh token and bump token_version so active access tokens become invalid."""
    now = utcnow_naive()
    target_user = current_user
    if raw_refresh:
        rt = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw_refresh)).first()
        if rt is not None:
            rt.revoked_at = rt.revoked_at or now
            if target_user is None:
                target_user = db.query(User).filter(User.id == rt.user_id).first()

    if target_user is not None:
        target_user.token_version = int(target_user.token_version or 0) + 1
        record_audit_event(
            db,
            action="auth.logout",
            resource_type="user",
            resource_id=target_user.id,
            actor_user_id=target_user.id,
            actor_role=target_user.role,
            ip_address=ip_address,
        )
    db.commit()


def request_password_reset(db: Session, *, email: str, ip_address: Optional[str] = None) -> None:
    """Issue a hashed single-use password reset token if account exists and is active."""
    normalized = normalize_email(email)
    user = db.query(User).filter(User.email == normalized).first()
    if user is None or not user.is_active:
        return
    _issue_one_time_token(
        db,
        user=user,
        purpose="password_reset",
        ttl_delta=datetime.timedelta(minutes=int(settings.PASSWORD_RESET_EXPIRE_MINUTES)),
    )
    record_audit_event(
        db,
        action="auth.password_reset_requested",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_role=user.role,
        ip_address=ip_address,
    )
    db.commit()


def reset_password_with_token(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
    ip_address: Optional[str] = None,
) -> None:
    """Verify hashed reset token, update Argon2id password, and revoke all existing sessions."""
    validate_password_strength(new_password)
    now = utcnow_naive()
    row = (
        db.query(OneTimeToken)
        .filter(
            OneTimeToken.token_hash == hash_token(raw_token),
            OneTimeToken.purpose == "password_reset",
        )
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise AppError(status_code=400, code="invalid_reset_token", message="Password reset token is invalid or expired.")

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None or not user.is_active:
        raise AppError(status_code=400, code="invalid_reset_token", message="Password reset token is invalid.")

    row.used_at = now
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.token_version = int(user.token_version or 0) + 1
    user.updated_at = now

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)

    record_audit_event(
        db,
        action="auth.password_reset_completed",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_role=user.role,
        ip_address=ip_address,
    )
    db.commit()


def verify_email_with_token(
    db: Session,
    *,
    raw_token: str,
    ip_address: Optional[str] = None,
) -> User:
    """Consume single-use hashed verification token and mark user email_verified=True."""
    now = utcnow_naive()
    row = (
        db.query(OneTimeToken)
        .filter(
            OneTimeToken.token_hash == hash_token(raw_token),
            OneTimeToken.purpose == "email_verify",
        )
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise AppError(status_code=400, code="invalid_verify_token", message="Verification token is invalid or expired.")

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise AppError(status_code=400, code="invalid_verify_token", message="Verification token is invalid.")

    row.used_at = now
    user.email_verified = True
    user.updated_at = now
    record_audit_event(
        db,
        action="auth.email_verified",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_role=user.role,
        ip_address=ip_address,
    )
    db.commit()
    return user

