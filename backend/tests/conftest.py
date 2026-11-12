"""Pytest session isolation configuration for PLUTO vProctor.

Redirects DATABASE_URL and STORAGE_DIR to a temporary directory before any
application module initializes its SQLAlchemy engine or settings singleton,
preventing test runs from polluting live backend/app/pluto.db or storage/.
"""
from __future__ import annotations

import atexit
import json
import os
import shutil
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="pluto_pytest_"))
_TEST_DB_PATH = _TEST_ROOT / "test_pluto.db"
_TEST_STORAGE_DIR = _TEST_ROOT / "storage"
for _sub in ("resumes", "recordings", "audio", "reports"):
    (_TEST_STORAGE_DIR / _sub).mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["STORAGE_DIR"] = str(_TEST_STORAGE_DIR)

from backend.app.config import settings  # noqa: E402
from backend.app.db.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.db.models import Company, Job, Question  # noqa: E402

# Defensive sync in case any plugin imported settings/database before conftest
settings.DATABASE_URL = os.environ["DATABASE_URL"]
settings.STORAGE_DIR = _TEST_STORAGE_DIR


def _seed_reference_catalog() -> None:
    """Create schema and seed only static catalog data (companies, jobs, questions)."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Job).count() == 0:
            jobs_file = settings.BASE_DIR / "backend" / "app" / "data" / "jobs.json"
            if jobs_file.exists():
                data = json.loads(jobs_file.read_text(encoding="utf-8"))
                for c in data.get("companies", []):
                    db.merge(Company(**c))
                for j in data.get("jobs", []):
                    db.merge(Job(**j))

        if db.query(Question).count() == 0:
            q_file = settings.PROCESSED_DATA_DIR / "questions.json"
            if q_file.exists():
                questions_data = json.loads(q_file.read_text(encoding="utf-8"))
                valid_cols = {col.name for col in Question.__table__.columns}
                objects = [
                    Question(**{k: v for k, v in item.items() if k in valid_cols})
                    for item in questions_data
                ]
                db.bulk_save_objects(objects)

        db.commit()
    finally:
        db.close()


_seed_reference_catalog()


def _cleanup_test_root() -> None:
    try:
        engine.dispose()
    except Exception:
        pass
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


atexit.register(_cleanup_test_root)


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    _cleanup_test_root()

