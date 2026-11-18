"""Email delivery service for PLUTO vProctor (Zoho Catalyst Mail primary + optional SMTP fallback).

Uses the native `zcatalyst_sdk` Email component (`catalyst_app.email().send_mail(...)`)
when `CATALYST_MAIL_FROM` is configured in Catalyst AppSail Environment Variables.
Optionally falls back to standard STARTTLS SMTP (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`)
when configured. Never raises to callers so auth endpoints remain resilient.
"""
from __future__ import annotations

import datetime
import logging
import smtplib
import threading
from email.message import EmailMessage
from typing import Any, Dict, Optional

from backend.app.config import settings
from backend.app.services.catalyst_context import get_catalyst_app, get_last_request_origin

logger = logging.getLogger("pluto.catalyst_mail")

_MAIL_LOCK = threading.Lock()
_MAIL_METRICS: Dict[str, Any] = {
    "calls_total": 0,
    "calls_succeeded": 0,
    "calls_failed": 0,
    "last_provider": None,
    "last_purpose": None,
    "last_sent_at": None,
    "last_error": None,
}


def get_mail_metrics() -> Dict[str, Any]:
    """Return safe, non-secret telemetry for email delivery status."""
    cat_from = (settings.CATALYST_MAIL_FROM or "").strip()
    smtp_ok = bool((settings.SMTP_HOST or "").strip() and (settings.SMTP_USER or "").strip() and (settings.SMTP_PASSWORD or "").strip())
    with _MAIL_LOCK:
        return {
            "catalyst_mail_configured": bool(cat_from),
            "smtp_configured": smtp_ok,
            "configured": bool(cat_from or smtp_ok),
            "sender_configured": bool(cat_from or (settings.SMTP_FROM or settings.SMTP_USER or "").strip()),
            **_MAIL_METRICS,
        }


def _record_mail_result(provider: str, purpose: str, ok: bool, error: Optional[str] = None) -> None:
    with _MAIL_LOCK:
        _MAIL_METRICS["calls_total"] += 1
        _MAIL_METRICS["last_provider"] = provider
        _MAIL_METRICS["last_purpose"] = purpose
        if ok:
            _MAIL_METRICS["calls_succeeded"] += 1
            _MAIL_METRICS["last_sent_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            _MAIL_METRICS["last_error"] = None
        else:
            _MAIL_METRICS["calls_failed"] += 1
            _MAIL_METRICS["last_error"] = (error or "")[:240]


def _build_token_email(purpose: str, raw_token: str) -> Optional[tuple[str, str]]:
    base_url = (settings.APP_PUBLIC_URL or get_last_request_origin() or "").rstrip("/")

    if purpose == "password_reset":
        reset_url = f"{base_url}/reset-password?token={raw_token}" if base_url else ""
        subject = "PLUTO vProctor — Reset Your Password"
        cta_html = (
            f'<p style="margin:20px 0;"><a href="{reset_url}" '
            'style="display:inline-block;padding:12px 22px;background:#FFE600;color:#000;'
            'font-weight:900;text-decoration:none;border:2px solid #000;border-radius:10px;">'
            "Reset Password Now &rarr;</a></p>"
            if reset_url
            else ""
        )
        html = (
            '<div style="font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:24px;'
            'background:#FFFFFF;border:3px solid #000;border-radius:16px;color:#111;">'
            '<h2 style="margin:0 0 12px;text-transform:uppercase;">PLUTO vProctor Password Reset</h2>'
            "<p>We received a request to reset the password for your PLUTO vProctor account.</p>"
            f"{cta_html}"
            f'<p>Or paste this single-use reset token on the Reset Password page:</p>'
            f'<p style="background:#F4F0EA;border:2px solid #000;border-radius:8px;padding:10px 14px;'
            f'font-family:monospace;font-size:13px;word-break:break-all;">{raw_token}</p>'
            f'<p style="font-size:12px;color:#555;">This token expires in {int(settings.PASSWORD_RESET_EXPIRE_MINUTES)} minutes '
            "and can only be used once. If you did not request a reset, you can safely ignore this email.</p>"
            "</div>"
        )
        return subject, html

    if purpose == "email_verify":
        login_url = f"{base_url}/login" if base_url else ""
        subject = "Welcome to PLUTO vProctor — Account Created"
        cta_html = (
            f'<p style="margin:20px 0;"><a href="{login_url}" '
            'style="display:inline-block;padding:12px 22px;background:#FFE600;color:#000;'
            'font-weight:900;text-decoration:none;border:2px solid #000;border-radius:10px;">'
            "Open PLUTO vProctor &rarr;</a></p>"
            if login_url
            else ""
        )
        html = (
            '<div style="font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:24px;'
            'background:#FFFFFF;border:3px solid #000;border-radius:16px;color:#111;">'
            '<h2 style="margin:0 0 12px;text-transform:uppercase;">Welcome to PLUTO vProctor</h2>'
            "<p>Your candidate account has been created successfully.</p>"
            f"{cta_html}"
            f'<p style="font-size:12px;color:#555;">Verification Token: <code>{raw_token}</code></p>'
            "</div>"
        )
        return subject, html

    return None


def _send_via_smtp(to_email: str, subject: str, html_body: str, purpose: str) -> bool:
    host = (settings.SMTP_HOST or "").strip()
    user = (settings.SMTP_USER or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip()
    from_addr = (settings.SMTP_FROM or settings.CATALYST_MAIL_FROM or user).strip()
    if not (host and user and password and from_addr):
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"PLUTO vProctor <{from_addr}>"
        msg["To"] = to_email
        msg.set_content("Please view this message in an HTML-capable email client.")
        msg.add_alternative(html_body, subtype="html")

        port = int(settings.SMTP_PORT or 587)
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)

        _record_mail_result("smtp", purpose, True)
        logger.info("Sent SMTP email (%s) to %s", purpose, to_email)
        return True
    except Exception as exc:
        _record_mail_result("smtp", purpose, False, str(exc))
        logger.warning("SMTP email send failed for %s (%s): %s", purpose, to_email, exc)
        return False


def send_catalyst_token_email(event: Dict[str, Any]) -> bool:
    """Deliver one-time verification or password-reset emails via Zoho Catalyst Mail (or SMTP fallback)."""
    to_email = str(event.get("email") or "").strip()
    purpose = str(event.get("purpose") or "").strip()
    raw_token = str(event.get("raw_token") or "").strip()
    if not to_email or not raw_token:
        return False

    built = _build_token_email(purpose, raw_token)
    if built is None:
        return False
    subject, html_content = built

    from_email = (settings.CATALYST_MAIL_FROM or "").strip()
    if from_email:
        catalyst_app = get_catalyst_app(scope="admin")
        if catalyst_app is not None:
            try:
                mail_obj = {
                    "from_email": from_email,
                    "to_email": [to_email],
                    "subject": subject,
                    "content": html_content,
                    "html_mode": True,
                    "display_name": "PLUTO vProctor",
                }
                catalyst_app.email().send_mail(mail_obj)
                _record_mail_result("catalyst_mail", purpose, True)
                logger.info("Sent Zoho Catalyst Mail (%s) to %s", purpose, to_email)
                return True
            except Exception as exc:
                _record_mail_result("catalyst_mail", purpose, False, str(exc))
                logger.warning("Zoho Catalyst Mail send failed for %s (%s): %s", purpose, to_email, exc)

    return _send_via_smtp(to_email, subject, html_content, purpose)
