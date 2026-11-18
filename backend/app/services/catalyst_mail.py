"""Zoho Catalyst Mail delivery adapter for verification and password-reset emails.

Uses the native `zcatalyst_sdk` Email component (`catalyst_app.email().send_mail(...)`)
when `CATALYST_MAIL_FROM` is configured in Catalyst AppSail Environment Variables.
Never raises to callers so authentication endpoints remain resilient if mail is unconfigured.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from backend.app.config import settings
from backend.app.services.catalyst_context import get_catalyst_app, get_last_request_origin

logger = logging.getLogger("pluto.catalyst_mail")


def send_catalyst_token_email(event: Dict[str, Any]) -> bool:
    """Deliver one-time verification or password-reset emails via Zoho Catalyst Mail."""
    from_email = (settings.CATALYST_MAIL_FROM or "").strip()
    if not from_email:
        return False

    to_email = str(event.get("email") or "").strip()
    purpose = str(event.get("purpose") or "").strip()
    raw_token = str(event.get("raw_token") or "").strip()
    if not to_email or not raw_token:
        return False

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return False

    base_url = (settings.APP_PUBLIC_URL or get_last_request_origin() or "").rstrip("/")

    if purpose == "password_reset":
        reset_url = f"{base_url}/reset-password?token={raw_token}" if base_url else ""
        subject = "PLUTO vProctor — Password Reset Instructions"
        link_block = (
            f'<p><a href="{reset_url}" style="display:inline-block;padding:10px 18px;background:#FFE600;color:#000;font-weight:bold;text-decoration:none;border:2px solid #000;border-radius:8px;">Reset Your Password</a></p>'
            if reset_url
            else ""
        )
        content = (
            "<h2>PLUTO vProctor Password Reset</h2>"
            "<p>We received a request to reset your PLUTO vProctor password.</p>"
            f"{link_block}"
            f"<p><strong>Reset Token:</strong> <code>{raw_token}</code></p>"
            "<p>This token expires shortly and can only be used once. If you did not request this, you may safely ignore this email.</p>"
        )
    elif purpose == "email_verify":
        subject = "Welcome to PLUTO vProctor — Verify Your Email"
        content = (
            "<h2>Welcome to PLUTO vProctor</h2>"
            "<p>Thank you for creating your candidate account on PLUTO vProctor.</p>"
            f"<p><strong>Verification Token:</strong> <code>{raw_token}</code></p>"
            "<p>You can sign in immediately and start your resume screening and mock interview practice.</p>"
        )
    else:
        return False

    try:
        mail_obj = {
            "from_email": from_email,
            "to_email": [to_email],
            "subject": subject,
            "content": content,
            "html_mode": True,
            "display_name": "PLUTO vProctor",
        }
        catalyst_app.email().send_mail(mail_obj)
        logger.info("Sent Zoho Catalyst Mail (%s) to %s", purpose, to_email)
        return True
    except Exception as exc:
        logger.warning("Zoho Catalyst Mail send failed for %s (%s): %s", purpose, to_email, exc)
        return False
