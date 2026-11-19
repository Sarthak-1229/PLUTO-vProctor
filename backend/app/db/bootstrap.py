"""Idempotent startup database bootstrap, auto-seeding, admin provisioning, and Zoho Stratus DB sync.

Guarantees that fresh Zoho Catalyst AppSail containers boot with:
- All database tables created
- Companies, job profiles, and the 1,799-question bank seeded automatically
- Optional environment-driven administrator account (never hardcoded in source)
- Automatic Zoho Catalyst Stratus SQLite snapshot restore (on cold start / first request)
  and debounced online SQLite backup sync after writes so users, profiles, resumes,
  sessions, and reports persist across AppSail container restarts.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.config import settings

logger = logging.getLogger("pluto.bootstrap")

_BOOTSTRAP_LOCK = threading.Lock()
_STRATUS_SYNC_LOCK = threading.Lock()
_STRATUS_RESTORE_LOCK = threading.Lock()

_STRATUS_RESTORE_ATTEMPTED = False
_STRATUS_RESTORED_OK = False
_STRATUS_LAST_SYNC_AT: Optional[str] = None
_STRATUS_LAST_SYNC_BYTES: int = 0
_STRATUS_LAST_SYNC_ERROR: Optional[str] = None
_LAST_SYNC_MONO = 0.0

STRATUS_DB_KEY = "db_snapshots/pluto.db"


def _resolve_sqlite_file_path() -> Optional[Path]:
    """Return local filesystem Path for file-backed SQLite DATABASE_URL, else None."""
    url = (settings.DATABASE_URL or "").strip()
    if not url.startswith("sqlite:///"):
        return None
    raw = url[len("sqlite:///") :]
    if not raw or raw == ":memory:":
        return None
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


def get_stratus_db_state() -> Dict[str, Any]:
    """Return non-secret telemetry for Stratus SQLite snapshot persistence."""
    try:
        from backend.app.services.storage_service import storage_service
        telemetry = storage_service.get_stratus_telemetry()
    except Exception:
        telemetry = {}
    return {
        "restore_attempted": _STRATUS_RESTORE_ATTEMPTED,
        "restored_from_stratus": _STRATUS_RESTORED_OK,
        "last_sync_at": _STRATUS_LAST_SYNC_AT,
        "last_sync_bytes": _STRATUS_LAST_SYNC_BYTES,
        "last_sync_error": _STRATUS_LAST_SYNC_ERROR,
        "snapshot_key": STRATUS_DB_KEY,
        "telemetry": telemetry,
    }


def _restore_sqlite_from_stratus(*, force_replace: bool = False) -> bool:
    """Download SQLite snapshot from Zoho Stratus OR Zoho Catalyst File Store + Cache."""
    global _STRATUS_RESTORED_OK
    db_path = _resolve_sqlite_file_path()
    if db_path is None:
        return False

    local_user_count = 0
    if db_path.exists() and db_path.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM users")
            row = cur.fetchone()
            local_user_count = row[0] if row else 0
            conn.close()
        except Exception:
            local_user_count = 0

    if not force_replace and local_user_count > 0:
        return False

    try:
        from backend.app.services.storage_service import storage_service
        from backend.app.services.catalyst_cloud_db import download_db_snapshot_from_filestore

        raw_bytes = None
        source = None
        if storage_service.is_stratus_enabled():
            raw_bytes = storage_service.download_raw_bytes(STRATUS_DB_KEY)
            if raw_bytes:
                source = "Zoho Stratus"

        if not raw_bytes:
            raw_bytes = download_db_snapshot_from_filestore()
            if raw_bytes:
                source = "Zoho Catalyst File Store (Migrating to Stratus)"
                if storage_service.is_stratus_enabled():
                    try:
                        storage_service.upload_raw_bytes(STRATUS_DB_KEY, raw_bytes, content_type="application/x-sqlite3")
                        logger.info("Auto-migrated initial File Store snapshot into Zoho Stratus (%s)", STRATUS_DB_KEY)
                    except Exception:
                        pass

        if not raw_bytes or not raw_bytes.startswith(b"SQLite format 3"):
            return False

        from backend.app.db.database import engine

        db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = db_path.with_suffix(".db.restore_tmp")
        tmp_path.write_bytes(raw_bytes)

        # Protect against restoring an empty/older snapshot over local users
        if local_user_count > 0:
            try:
                tmp_conn = sqlite3.connect(str(tmp_path))
                cur = tmp_conn.cursor()
                cur.execute("SELECT count(*) FROM users")
                row = cur.fetchone()
                cloud_user_count = row[0] if row else 0
                tmp_conn.close()
                if cloud_user_count < local_user_count:
                    logger.info("Preserving local SQLite DB (%d users) over cloud snapshot (%d users).", local_user_count, cloud_user_count)
                    tmp_path.unlink(missing_ok=True)
                    _STRATUS_RESTORED_OK = True
                    return True
            except Exception:
                pass

        engine.dispose()
        tmp_path.replace(db_path)
        _STRATUS_RESTORED_OK = True
        logger.info("Restored SQLite database snapshot from %s (%d bytes).", source, len(raw_bytes))
        return True
    except Exception as exc:
        logger.warning("Cloud SQLite snapshot restore skipped: %s", exc)
        return False


def ensure_stratus_db_restored_once() -> bool:
    """Called on first live Catalyst request once AppSail headers arrive.

    Restores persisted SQLite DB from Zoho Stratus (if bucket configured) or
    automatically from Zoho Catalyst File Store + Cache (zero manual config!),
    and discovers any Zoho Data Store tables for live mirroring.
    Runs at most once per container lifetime.
    """
    global _STRATUS_RESTORE_ATTEMPTED
    if _STRATUS_RESTORE_ATTEMPTED or not _should_auto_seed():
        return False

    with _STRATUS_RESTORE_LOCK:
        if _STRATUS_RESTORE_ATTEMPTED:
            return False

        from backend.app.services.catalyst_context import has_catalyst_headers
        from backend.app.services.storage_service import storage_service
        from backend.app.services.catalyst_cloud_db import refresh_datastore_tables

        if not (has_catalyst_headers() or storage_service.is_stratus_enabled()):
            return False

        _STRATUS_RESTORE_ATTEMPTED = True
        restored = _restore_sqlite_from_stratus(force_replace=True)
        if restored:
            ensure_database_ready()
        else:
            # First ever boot with empty cloud storage: push initial seeded DB snapshot only if local has data
            try:
                from backend.app.db.database import SessionLocal
                from backend.app.db.models import User
                with SessionLocal() as db:
                    if db.query(User).count() > 0:
                        schedule_stratus_sync(force=True)
            except Exception:
                pass

        # Discover any existing Zoho Catalyst Data Store tables and backfill users in background
        def _bg_datastore_check():
            try:
                storage_service.migrate_filestore_to_stratus()
            except Exception:
                pass
            try:
                refresh_datastore_tables(force=True)
                from backend.app.services.catalyst_cloud_db import sync_all_users_to_datastore
                sync_all_users_to_datastore()
            except Exception:
                pass

        threading.Thread(target=_bg_datastore_check, daemon=True).start()
        return restored


def sync_sqlite_to_stratus() -> bool:
    """Create a consistent SQLite online backup and persist to Zoho Stratus and/or File Store."""
    global _STRATUS_LAST_SYNC_AT, _STRATUS_LAST_SYNC_BYTES, _STRATUS_LAST_SYNC_ERROR
    db_path = _resolve_sqlite_file_path()
    if db_path is None or not db_path.exists():
        _STRATUS_LAST_SYNC_ERROR = "SQLite db_path does not exist or invalid"
        return False

    try:
        from backend.app.services.catalyst_context import has_catalyst_headers
        from backend.app.services.storage_service import storage_service
        from backend.app.services.catalyst_cloud_db import upload_db_snapshot_to_filestore

        stratus_on = storage_service.is_stratus_enabled()
        catalyst_on = has_catalyst_headers()
        if not (stratus_on or catalyst_on):
            _STRATUS_LAST_SYNC_ERROR = "Neither Stratus nor Catalyst headers are available for cloud sync"
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

                synced = False
                stratus_ok = False
                filestore_ok = False

                if stratus_on:
                    if storage_service.upload_raw_bytes(
                        STRATUS_DB_KEY,
                        payload,
                        content_type="application/x-sqlite3",
                    ):
                        synced = True
                        stratus_ok = True

                if catalyst_on:
                    if upload_db_snapshot_to_filestore(payload):
                        synced = True
                        filestore_ok = True

                if synced:
                    _STRATUS_LAST_SYNC_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    _STRATUS_LAST_SYNC_BYTES = len(payload)
                    _STRATUS_LAST_SYNC_ERROR = None
                    dest_str = []
                    if stratus_ok:
                        dest_str.append("Zoho Stratus")
                    if filestore_ok:
                        dest_str.append("Zoho File Store")
                    logger.info("Synced SQLite database snapshot to %s (%d bytes).", " + ".join(dest_str), len(payload))
                else:
                    _STRATUS_LAST_SYNC_ERROR = "Failed to upload DB snapshot to both Stratus and File Store"
                return synced
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        _STRATUS_LAST_SYNC_ERROR = str(exc)
        logger.warning("Zoho Cloud SQLite snapshot sync skipped: %s", exc)
        return False


def schedule_stratus_sync(*, force: bool = False) -> None:
    """Trigger a debounced non-blocking SQLite snapshot sync to Zoho Cloud when active."""
    global _LAST_SYNC_MONO
    if not _should_auto_seed():
        return
    try:
        from backend.app.services.catalyst_context import has_catalyst_headers
        from backend.app.services.storage_service import storage_service

        if not (storage_service.is_stratus_enabled() or has_catalyst_headers()):
            return

        now = time.monotonic()
        if not force and (now - _LAST_SYNC_MONO < 3.0):
            return
        _LAST_SYNC_MONO = now
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


def ensure_database_ready() -> Dict[str, Any]:
    """Initialize storage, schema, seed data, and optional bootstrap admin idempotently."""
    with _BOOTSTRAP_LOCK:
        try:
            settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Storage directory creation warning: %s", exc)

        restored = _restore_sqlite_from_stratus(force_replace=False)

        from backend.app.db.database import Base, SessionLocal, engine
        from backend.app.db import models as _models  # noqa: F401

        Base.metadata.create_all(bind=engine)

        summary: Dict[str, Any] = {
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
