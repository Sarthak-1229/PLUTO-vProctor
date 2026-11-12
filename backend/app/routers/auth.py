"""Authentication router: candidate & admin login, registration, refresh cookies, password reset."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.auth_service import (
    authenticate_user,
    logout_session,
    register_candidate,
    request_password_reset,
    reset_password_with_token,
    rotate_refresh_session,
    serialize_user,
    verify_email_with_token,
)
from backend.app.services.authorization import get_current_user, get_optional_user
from backend.app.services.security_service import constant_time_equals, enforce_rate_limit, normalize_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=16, max_length=256)
    new_password: str = Field(..., min_length=10, max_length=128)


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=16, max_length=256)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "unknown"


def _set_session_cookies(response: Response, raw_refresh: str, csrf_token: str) -> None:
    refresh_max_age = int(settings.REFRESH_TOKEN_EXPIRE_DAYS) * 86400
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh,
        max_age=refresh_max_age,
        httponly=True,
        secure=bool(settings.COOKIE_SECURE),
        samesite=settings.COOKIE_SAMESITE,
        path="/api/auth",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=refresh_max_age,
        httponly=False,
        secure=bool(settings.COOKIE_SECURE),
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(key=settings.REFRESH_COOKIE_NAME, path="/api/auth")
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, path="/")


def _require_csrf_match(request: Request) -> None:
    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("x-csrf-token")
    if not constant_time_equals(csrf_cookie, csrf_header):
        raise AppError(status_code=403, code="csrf_validation_failed", message="CSRF validation failed.")


@router.get("/config")
def get_auth_config():
    """Return runtime v2 feature flags required by the SPA shell."""
    return {
        "auth_enabled": bool(settings.AUTH_ENABLED),
        "hosted_rooms_enabled": bool(settings.HOSTED_ROOMS_ENABLED),
        "live_media_enabled": bool(settings.LIVE_MEDIA_ENABLED),
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Register a new candidate account (strictly candidate role only)."""
    ip = _client_ip(request)
    enforce_rate_limit(f"auth:register:ip:{ip}", limit=15, window_seconds=300)

    result = register_candidate(
        db,
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, result["raw_refresh"], result["csrf_token"])
    return {
        "user": result["user"],
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "expires_in": result["expires_in"],
    }


@router.post("/login")
def login_candidate(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate a candidate account on the candidate portal."""
    ip = _client_ip(request)
    norm_email = normalize_email(str(payload.email))
    enforce_rate_limit(f"auth:login:ip:{ip}", limit=30, window_seconds=300)
    enforce_rate_limit(f"auth:login:acct:{norm_email}", limit=15, window_seconds=300)

    result = authenticate_user(
        db,
        email=norm_email,
        password=payload.password,
        portal="candidate",
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, result["raw_refresh"], result["csrf_token"])
    return {
        "user": result["user"],
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "expires_in": result["expires_in"],
    }


@router.post("/admin/login")
def login_admin(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate an administrator on the dedicated admin portal."""
    ip = _client_ip(request)
    norm_email = normalize_email(str(payload.email))
    enforce_rate_limit(f"auth:admin_login:ip:{ip}", limit=20, window_seconds=300)
    enforce_rate_limit(f"auth:admin_login:acct:{norm_email}", limit=10, window_seconds=300)

    result = authenticate_user(
        db,
        email=norm_email,
        password=payload.password,
        portal="admin",
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, result["raw_refresh"], result["csrf_token"])
    return {
        "user": result["user"],
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "expires_in": result["expires_in"],
    }


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Rotate HttpOnly refresh session cookie with double-submit CSRF verification."""
    _require_csrf_match(request)
    ip = _client_ip(request)
    enforce_rate_limit(f"auth:refresh:ip:{ip}", limit=60, window_seconds=300)

    try:
        result = rotate_refresh_session(
            db,
            raw_refresh=request.cookies.get(settings.REFRESH_COOKIE_NAME),
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
        )
    except AppError:
        _clear_session_cookies(response)
        raise

    _set_session_cookies(response, result["raw_refresh"], result["csrf_token"])
    return {
        "user": result["user"],
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "expires_in": result["expires_in"],
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Invalidate refresh session and active access tokens."""
    if request.cookies.get(settings.REFRESH_COOKIE_NAME) and current_user is None:
        _require_csrf_match(request)
    elif request.cookies.get(settings.CSRF_COOKIE_NAME):
        _require_csrf_match(request)

    logout_session(
        db,
        raw_refresh=request.cookies.get(settings.REFRESH_COOKIE_NAME),
        current_user=current_user,
        ip_address=_client_ip(request),
    )
    _clear_session_cookies(response)
    return {"status": "logged_out"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's sanitized identity."""
    return {"user": serialize_user(current_user)}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Initiate password reset without leaking whether the email is registered."""
    ip = _client_ip(request)
    norm_email = normalize_email(str(payload.email))
    enforce_rate_limit(f"auth:forgot:ip:{ip}", limit=10, window_seconds=300)
    enforce_rate_limit(f"auth:forgot:acct:{norm_email}", limit=5, window_seconds=300)

    request_password_reset(db, email=norm_email, ip_address=ip)
    return {
        "message": "If an account with that email exists, password reset instructions have been issued.",
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Complete password reset using single-use hashed token and revoke prior sessions."""
    ip = _client_ip(request)
    enforce_rate_limit(f"auth:reset:ip:{ip}", limit=15, window_seconds=300)

    reset_password_with_token(
        db,
        raw_token=payload.token,
        new_password=payload.new_password,
        ip_address=ip,
    )
    _clear_session_cookies(response)
    return {"status": "password_updated"}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    """Verify email address using single-use hashed verification token."""
    ip = _client_ip(request)
    enforce_rate_limit(f"auth:verify:ip:{ip}", limit=30, window_seconds=300)
    user = verify_email_with_token(db, raw_token=payload.token, ip_address=ip)
    return {"email_verified": bool(user.email_verified), "user": serialize_user(user)}

