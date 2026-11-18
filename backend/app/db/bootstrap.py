"""Idempotent startup database bootstrap, auto-seeding, admin provisioning, and Stratus snapshot sync.

Guarantees that fresh cloud containers (e.g., Zoho Catalyst AppSail) boot with:
- All database tables created
- Companies, job profiles, and the 1,799-question bank seeded automatically
- Optional environment-driven administrator account (never hardcoded in source)
- Optional Zoho Catalyst Stratus SQLite snapshot restore/backup for persistence across cold starts
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional

from backend.app.config import settings

logger = logging.getLogger("pluto.bootstrap")

_BOOTSTRAP_LOCK = threading.Lock()
_STRATUS_SYNC_LOCK = threading.Lock()


def _resolve_sqlite_file_path() -> Optional[Path]:
    """Return local filesystem Path for file-backed SQLite DATABASE_URL, else None."""
    url = (settings.DATABASE_URL or "").strip()
    if not url.startswith("sqlite:///"):
        return None
    raw = url[len("sqlite:///") :]
    if not raw or raw == ":memory:":
        return None
    # Handle sqlite:////tmp/pluto.db -> /tmp/pluto.db on POSIX, or relative/absolute Windows paths
    return Path(raw)


def _should_auto_seed() -> bool:
    """Avoid mutating isolated pytest databases while seeding real runtime environments."""
    if not getattr(settings, "AUTO_SEED_DB", True):
        return False
    if settings.ENVIRONMENT.strip().lower() == "test":
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def restore_sqlite_from_stratus_if_needed() -> bool:
    """Restore SQLite snapshot from Zoho Stratus if local DB file does not exist yet."""
    db_path = _resolve_sqlite_file_path()
    if db_path is None:
        return False
    if db_path.exists() and db_path.stat().st_size > 0:
        return False

    try:
        from backend.app.services.storage_service import storage_service

        if not storage_service.is_stratus_enabled():
            return False

        raw_bytes = storage_service.get_file_bytes("db_snapshots", "pluto.db")
        if not raw_bytes or not raw_bytes.startswith(b"SQLite format 3"):
            return False

        db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = db_path.with_suffix(".db.restore_tmp")
        tmp_path.write_bytes(raw_bytes)
        tmp_path.replace(db_path)
        logger.info("Restored SQLite database snapshot from Zoho Stratus (%d bytes).", len(raw_bytes))
        return True
    except Exception as exc:
        logger.warning("Stratus SQLite snapshot restore skipped: %s", exc)
        return False


def sync_sqlite_to_stratus() -> bool:
    """Create a consistent SQLite online backup and upload it to Zoho Stratus if enabled."""
    db_path = _resolve_sqlite_file_path()
    if db_path is None or not db_path.exists():
        return False

    try:
        from backend.app.services.storage_service import storage_service

        if not storage_service.is_stratus_enabled():
            return False

        with _STRATUS_SYNC_LOCK:
            tmp_fd, tmp_name = tempfile.mkstemp(prefix="pluto_snap_", suffix=".db")
            os.close(tmp_fd)
            tmp_path = Path(tmp_name)
            try:
                src = sqlite3.connect(str(db_path))
                dst = sqlite3.connect(str(tmp_path))
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()
                payload = tmp_path.read_bytes()
                ok = storage_service._upload_to_stratus("db_snapshots/pluto.db", payload)
                if ok:
                    logger.info("Synced SQLite database snapshot to Zoho Stratus (%d bytes).", len(payload))
                return ok
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Stratus SQLite snapshot sync skipped: %s", exc)
        return False


_LAST_SYNC_TS = 0.0


def schedule_stratus_sync() -> None:
    """Trigger a debounced non-blocking SQLite snapshot sync to Zoho Stratus when enabled."""
    global _LAST_SYNC_TS
    try:
        from backend.app.services.storage_service import storage_service

        if not storage_service.is_stratus_enabled():
            return
        import time

        now = time.monotonic()
        if now - _LAST_SYNC_TS < 5.0:
            return
        _LAST_SYNC_TS = now
        threading.Thread(target=sync_sqlite_to_stratus, daemon=True).start()
    except Exception:
        pass


def _seed_jobs_and_companies(db) -> Dict[str, int]:
    """Idempotently seed companies and jobs from backend/app/data/jobs.json if missing."""
    from backend.app.db.models import Company, Job

    jobs_file = settings.APP_DIR / "data" / "jobs.json"
    if not jobs_file.exists():
        logger.warning("jobs.json not found at %s; skipping job seed.", jobs_file)
        return {"companies": 0, "jobs": 0}

    existing_companies = {row[0] for row in db.query(Company.id).all()}
    existing_jobs = {row[0] for row in db.query(Job.id).all()}

    with open(jobs_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    added_companies = 0
    for c in data.get("companies", []):
        if c["id"] not in existing_companies:
            db.add(
                Company(
                    id=c["id"],
                    name=c["name"],
                    industry=c.get("industry", "Technology"),
                    description=c.get("description", ""),
                )
            )
            added_companies += 1
    if added_companies:
        db.commit()

    added_jobs = 0
    for j in data.get("jobs", []):
        if j["id"] not in existing_jobs:
            db.add(
                Job(
                    id=j["id"],
                    title=j["title"],
                    company=j["company"],
                    company_id=j.get("company_id"),
                    required_skills=j.get("required_skills", []),
                    preferred_skills=j.get("preferred_skills", []),
                    min_experience_years=j.get("min_experience_years", 0),
                    education_levels=j.get("education_levels", []),
                    skill_weights=j.get("skill_weights", {}),
                    question_domains=j.get("question_domains", []),
                    pass_threshold=j.get("pass_threshold", 0.65),
                )
            )
            added_jobs += 1
    if added_jobs:
        db.commit()

    return {"companies": added_companies, "jobs": added_jobs}


def _seed_questions(db) -> int:
    """Idempotently bulk-seed the question bank if the questions table is empty."""
    from backend.app.db.models import Question

    if db.query(Question.id).first() is not None:
        return 0

    questions_file = settings.PROCESSED_DATA_DIR / "questions.json"
    if not questions_file.exists():
        logger.warning("questions.json not found at %s; skipping question seed.", questions_file)
        return 0

    with open(questions_file, "r", encoding="utf-8") as f:
        questions_list = json.load(f)

    q_objs = [
        Question(
            id=q["id"],
            question=q["question"],
            answer=q["answer"],
            split=q.get("split", "train"),
            source_folder=q.get("source_folder", ""),
            type=q.get("type", "explain"),
            spoken_ok=q.get("spoken_ok", True),
            skills=q.get("skills", []),
            domain=q.get("domain", "General"),
            cluster_id=q.get("cluster_id", 0),
            difficulty=q.get("difficulty", 1),
            expected_keywords=q.get("expected_keywords", []),
            ideal_answer_summary=q.get("ideal_answer_summary", q["answer"]),
            est_seconds=q.get("est_seconds", 70),
        )
        for q in questions_list
    ]
    if q_objs:
        db.bulk_save_objects(q_objs)
        db.commit()
    return len(q_objs)


def _ensure_bootstrap_admin(db) -> bool:
    """Provision initial admin account from environment variables without hardcoding secrets."""
    email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip()
    password = (settings.BOOTSTRAP_ADMIN_PASSWORD or "").strip()
    if not email or not password:
        return False

    from backend.app.db.models import User
    from backend.app.services.admin_bootstrap import bootstrap_admin_user
    from backend.app.services.security_service import normalize_email, verify_password

    norm_email = normalize_email(email)
    existing = db.query(User).filter(User.email == norm_email).first()
    if (
        existing is not None
        and existing.role in ("admin", "super_admin")
        and existing.is_active
        and verify_password(password, existing.password_hash)
    ):
        return False

    try:
        user = bootstrap_admin_user(
            db,
            email=norm_email,
            password=password,
            full_name=(settings.BOOTSTRAP_ADMIN_NAME or "PLUTO Administrator").strip(),
            role="super_admin",
        )
        logger.info("Provisioned bootstrap administrator account: %s (role=%s)", user.email, user.role)
        return True
    except Exception as exc:
        logger.error("Failed to provision bootstrap admin account: %s", exc)
        return False


def ensure_database_ready() -> Dict[str, int | bool]:
    """Initialize storage, schema, seed data, and optional bootstrap admin idempotently."""
    with _BOOTSTRAP_LOCK:
        try:
            settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Storage directory creation warning: %s", exc)

        restored = restore_sqlite_from_stratus_if_needed()

        from backend.app.db.database import Base, SessionLocal, engine
        from backend.app.db import models as _models  # noqa: F401

        Base.metadata.create_all(bind=engine)

        summary: Dict[str, int | bool] = {
            "restored_from_stratus": restored,
            "companies_seeded": 0,
            "jobs_seeded": 0,
            "questions_seeded": 0,
            "admin_bootstrapped": False,
        }

        if not _should_auto_seed():
            return summary

        db = SessionLocal()
        try:
            counts = _seed_jobs_and_companies(db)
            summary["companies_seeded"] = counts["companies"]
            summary["jobs_seeded"] = counts["jobs"]
            summary["questions_seeded"] = _seed_questions(db)
            summary["admin_bootstrapped"] = _ensure_bootstrap_admin(db)
            if any(
                [
                    summary["companies_seeded"],
                    summary["jobs_seeded"],
                    summary["questions_seeded"],
                    summary["admin_bootstrapped"],
                ]
            ):
                logger.info("Database bootstrap complete: %s", summary)
        finally:
            db.close()

        return summary
