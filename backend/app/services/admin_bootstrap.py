"""Secure administrator bootstrap service and CLI (no hardcoded default passwords)."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.db.database import SessionLocal
from backend.app.db.models import User
from backend.app.services.security_service import (
    hash_password,
    normalize_email,
    record_audit_event,
    utcnow_naive,
    validate_password_strength,
)


def bootstrap_admin_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str = "PLUTO Administrator",
    role: str = "admin",
) -> User:
    """Create or promote an admin / super_admin user safely."""
    clean_role = role.strip().lower()
    if clean_role not in ("admin", "super_admin"):
        raise AppError(status_code=422, code="invalid_role", message="Bootstrap role must be 'admin' or 'super_admin'.")

    norm_email = normalize_email(email)
    try:
        validate_email(norm_email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise AppError(status_code=422, code="invalid_email", message="Invalid administrator email address.") from exc

    validate_password_strength(password)
    now = utcnow_naive()
    existing = db.query(User).filter(User.email == norm_email).first()

    if existing is None:
        user = User(
            id=f"usr_{uuid.uuid4().hex[:16]}",
            email=norm_email,
            password_hash=hash_password(password),
            full_name=full_name.strip() or "PLUTO Administrator",
            role=clean_role,
            is_active=True,
            email_verified=True,
            failed_login_attempts=0,
            token_version=0,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        record_audit_event(
            db,
            action="admin.bootstrap_created",
            resource_type="user",
            resource_id=user.id,
            details={"email": norm_email, "role": clean_role},
        )
        db.commit()
        db.refresh(user)
        return user

    prev_role = existing.role
    existing.role = clean_role
    existing.password_hash = hash_password(password)
    existing.is_active = True
    existing.email_verified = True
    existing.failed_login_attempts = 0
    existing.locked_until = None
    existing.token_version = int(existing.token_version or 0) + 1
    existing.updated_at = now
    record_audit_event(
        db,
        action="admin.bootstrap_promoted",
        resource_type="user",
        resource_id=existing.id,
        details={"email": norm_email, "previous_role": prev_role, "new_role": clean_role},
    )
    db.commit()
    db.refresh(existing)
    return existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or promote a PLUTO vProctor administrator account.")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--name", default="PLUTO Administrator", help="Display full name")
    parser.add_argument("--role", default="admin", choices=["admin", "super_admin"], help="Admin role")
    parser.add_argument("--password", default="", help="Optional password (prefer PLUTO_ADMIN_PASSWORD or prompt)")
    args = parser.parse_args(argv)

    password = args.password or os.environ.get("PLUTO_ADMIN_PASSWORD", "")
    if not password:
        password = getpass.getpass("Enter administrator password: ")

    db = SessionLocal()
    try:
        user = bootstrap_admin_user(
            db,
            email=args.email,
            password=password,
            full_name=args.name,
            role=args.role,
        )
        print(f"Bootstrapped {user.role} account: id={user.id} email={user.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

