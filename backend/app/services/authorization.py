"""Authentication, role-based access control, and resource ownership dependencies."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.db.models import InterviewSession, Resume, User
from backend.app.services.security_service import decode_access_token

ADMIN_ROLES = ("admin", "super_admin")


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization") or ""
    if not auth_header.strip():
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AppError(
            status_code=401,
            code="invalid_authorization_header",
            message="Authorization header must use Bearer token format.",
        )
    return parts[1].strip()


def resolve_user_from_token(token: str, db: Session) -> User:
    """Decode JWT access token and verify active user and current token_version."""
    payload = decode_access_token(token)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None or not user.is_active:
        raise AppError(status_code=401, code="unauthorized", message="Account is inactive or not found.")
    if int(user.token_version) != int(payload.get("tv", -1)):
        raise AppError(status_code=401, code="token_revoked", message="Session has been logged out or revoked.")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Authenticate Bearer user when Authorization header is present; otherwise return None."""
    token = _extract_bearer_token(request)
    if token is None:
        return None
    return resolve_user_from_token(token, db)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Strictly require an authenticated active user regardless of AUTH_ENABLED."""
    token = _extract_bearer_token(request)
    if token is None:
        raise AppError(status_code=401, code="authentication_required", message="Authentication is required.")
    return resolve_user_from_token(token, db)


def get_user_when_auth_enabled(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Enforce authentication when AUTH_ENABLED=True; preserve anonymous offline mode when False."""
    if settings.AUTH_ENABLED:
        return get_current_user(request, db)
    return get_optional_user(request, db)


def require_roles(*allowed_roles: Any) -> Callable[..., User]:
    """FastAPI dependency requiring authenticated user with one of allowed_roles."""
    flat_roles = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)
    allowed = set(flat_roles)

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise AppError(
                status_code=403,
                code="forbidden_role",
                message="You do not have permission to perform this action.",
            )
        return current_user

    return _dependency


def enforce_session_access(session_obj: Optional[InterviewSession], current_user: Optional[User]) -> InterviewSession:
    """Ensure session exists and current user owns it (or holds admin/super_admin role)."""
    if session_obj is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if settings.AUTH_ENABLED:
        if current_user is None:
            raise AppError(status_code=401, code="authentication_required", message="Authentication is required.")
        if current_user.role in ADMIN_ROLES:
            return session_obj
        if session_obj.candidate_user_id != current_user.id:
            raise AppError(
                status_code=403,
                code="forbidden_session_access",
                message="You are not authorized to access this interview session.",
            )
    elif session_obj.candidate_user_id is not None:
        # Even when AUTH_ENABLED=False, a private account-linked session cannot be accessed anonymously
        # or by another candidate.
        if current_user is None:
            raise AppError(
                status_code=401,
                code="authentication_required",
                message="Authentication is required to access an account-linked session.",
            )
        if current_user.role not in ADMIN_ROLES and session_obj.candidate_user_id != current_user.id:
            raise AppError(
                status_code=403,
                code="forbidden_session_access",
                message="You are not authorized to access this interview session.",
            )
    return session_obj


def enforce_resume_ownership(resume_obj: Optional[Resume], current_user: User) -> Resume:
    """Ensure uploaded resume belongs to current_user or caller is admin."""
    if resume_obj is None:
        raise AppError(status_code=404, code="resume_not_found", message="Resume not found.")
    if current_user.role not in ADMIN_ROLES and resume_obj.user_id != current_user.id:
        raise AppError(
            status_code=403,
            code="forbidden_resume_access",
            message="You are not authorized to access this resume.",
        )
    return resume_obj

