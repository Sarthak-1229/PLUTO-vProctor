"""Zoho Catalyst Cloud DB & Storage Persistence Layer (Cache + File Store + Data Store).

Utilizes 100% native Zoho Catalyst services with zero manual API keys inside AppSail:
1. Zoho Catalyst Cache (`app.cache().segment()`):
   - Stores live DB snapshot pointer (`pluto_latest_db_file_id`) and live runtime metrics
     (immediately visible under Catalyst Console -> Cloud Scale -> Cache -> Default).
2. Zoho Catalyst File Store (`app.filestore()`):
   - Automatically creates the `pluto_database` folder on first boot (zero manual setup!)
   - Persists consistent online SQLite backups (`pluto.db`) so registered users, profiles,
     resumes, interview sessions, and reports survive container sleep and redeploys!
3. Zoho Catalyst Data Store (`app.datastore()` + `app.zcql()`):
   - Auto-detects PLUTO tables (`PlutoUsers`, `PlutoJobs`, `PlutoSessions`, `PlutoReports`)
     when created in Catalyst Console -> Cloud Scale -> Data Store, and live-mirrors records
     in background threads so you can browse/query them directly in Zoho Data Store.
"""
from __future__ import annotations

import datetime
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.services.catalyst_context import get_catalyst_app

logger = logging.getLogger("pluto.catalyst_db")

FILESTORE_FOLDER_NAME = "pluto_database"
CACHE_DB_FILE_ID_KEY = "pluto_latest_db_file_id"
CACHE_STATS_KEY = "pluto_system_status"

_STATE_LOCK = threading.Lock()
_FILESTORE_FOLDER_ID: Optional[str] = None
_FILESTORE_LAST_FILE_ID: Optional[str] = None
_FILESTORE_LAST_SYNC_AT: Optional[str] = None
_FILESTORE_LAST_ERROR: Optional[str] = None
_CACHE_ACTIVE: bool = False
_CACHE_LAST_ERROR: Optional[str] = None

_DATASTORE_TABLES_CACHE: Dict[str, str] = {}  # lower_name -> exact table_name
_DATASTORE_TABLES_CHECKED_AT: float = 0.0
_DATASTORE_SYNCED_ROWS: int = 0
_DATASTORE_LAST_ERROR: Optional[str] = None


def get_cloud_db_status() -> Dict[str, Any]:
    """Return safe, non-secret telemetry for Catalyst Cache, File Store, and Data Store."""
    with _STATE_LOCK:
        return {
            "cache_active": _CACHE_ACTIVE,
            "cache_last_error": _CACHE_LAST_ERROR,
            "filestore_folder": FILESTORE_FOLDER_NAME,
            "filestore_folder_id": _FILESTORE_FOLDER_ID,
            "filestore_last_file_id": _FILESTORE_LAST_FILE_ID,
            "filestore_last_sync_at": _FILESTORE_LAST_SYNC_AT,
            "filestore_last_error": _FILESTORE_LAST_ERROR,
            "datastore_tables_detected": sorted(_DATASTORE_TABLES_CACHE.values()),
            "datastore_synced_rows": _DATASTORE_SYNCED_ROWS,
            "datastore_last_error": _DATASTORE_LAST_ERROR,
        }


# ---------------------------------------------------------------------------
# 1. Zoho Catalyst Cache
# ---------------------------------------------------------------------------

def cache_put(key: str, value: str, expiry_hours: int = 48) -> bool:
    """Put or update a string key in Zoho Catalyst Default Cache segment."""
    global _CACHE_ACTIVE, _CACHE_LAST_ERROR
    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return False
    try:
        segment = catalyst_app.cache().segment()
        try:
            segment.update(key, str(value), expiry=expiry_hours)
        except Exception:
            segment.put(key, str(value), expiry=expiry_hours)
        with _STATE_LOCK:
            _CACHE_ACTIVE = True
            _CACHE_LAST_ERROR = None
        return True
    except Exception as exc:
        with _STATE_LOCK:
            _CACHE_LAST_ERROR = str(exc)[:200]
        logger.debug("Catalyst Cache put failed for %s: %s", key, exc)
        return False


def cache_get(key: str) -> Optional[str]:
    """Retrieve a string value from Zoho Catalyst Default Cache segment."""
    global _CACHE_ACTIVE, _CACHE_LAST_ERROR
    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return None
    try:
        segment = catalyst_app.cache().segment()
        val = segment.get_value(key)
        with _STATE_LOCK:
            _CACHE_ACTIVE = True
            _CACHE_LAST_ERROR = None
        return str(val) if val is not None and str(val).strip() else None
    except Exception as exc:
        msg = str(exc)
        # Missing key still proves cache service is reachable
        if "not found" in msg.lower() or "no value" in msg.lower() or "404" in msg:
            with _STATE_LOCK:
                _CACHE_ACTIVE = True
                _CACHE_LAST_ERROR = None
        else:
            with _STATE_LOCK:
                _CACHE_LAST_ERROR = msg[:200]
        return None


# ---------------------------------------------------------------------------
# 2. Zoho Catalyst File Store (Zero-Setup Permanent DB Snapshot Store)
# ---------------------------------------------------------------------------

def _ensure_filestore_folder(catalyst_app) -> Optional[Any]:
    """Return or auto-create the `pluto_database` folder in Zoho Catalyst File Store."""
    global _FILESTORE_FOLDER_ID, _FILESTORE_LAST_ERROR
    try:
        filestore = catalyst_app.filestore()
        with _STATE_LOCK:
            cached_id = _FILESTORE_FOLDER_ID
        if cached_id:
            return filestore.folder(cached_id)

        folders = filestore.get_all_folders() or []
        for f in folders:
            details = f.to_dict() if hasattr(f, "to_dict") else {}
            if str(details.get("folder_name", "")).strip().lower() == FILESTORE_FOLDER_NAME:
                fid = str(details.get("id"))
                with _STATE_LOCK:
                    _FILESTORE_FOLDER_ID = fid
                    _FILESTORE_LAST_ERROR = None
                return filestore.folder(fid)

        created = filestore.create_folder(FILESTORE_FOLDER_NAME)
        details = created.to_dict() if hasattr(created, "to_dict") else {}
        fid = str(details.get("id"))
        with _STATE_LOCK:
            _FILESTORE_FOLDER_ID = fid
            _FILESTORE_LAST_ERROR = None
        logger.info("Auto-created Zoho Catalyst File Store folder '%s' (id=%s)", FILESTORE_FOLDER_NAME, fid)
        return filestore.folder(fid)
    except Exception as exc:
        with _STATE_LOCK:
            _FILESTORE_LAST_ERROR = str(exc)[:200]
        logger.warning("Catalyst File Store folder init failed: %s", exc)
        return None


def upload_db_snapshot_to_filestore(payload: bytes) -> bool:
    """Upload SQLite snapshot to Zoho Catalyst File Store & save latest file_id in Cache."""
    global _FILESTORE_LAST_FILE_ID, _FILESTORE_LAST_SYNC_AT, _FILESTORE_LAST_ERROR
    if not payload or not payload.startswith(b"SQLite format 3"):
        return False

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return False

    folder = _ensure_filestore_folder(catalyst_app)
    if folder is None:
        return False

    old_file_id = None
    with _STATE_LOCK:
        old_file_id = _FILESTORE_LAST_FILE_ID
    if not old_file_id:
        old_file_id = cache_get(CACHE_DB_FILE_ID_KEY)

    tmp_fd, tmp_name = tempfile.mkstemp(prefix="pluto_fs_", suffix=".db")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_bytes(payload)
        snap_name = f"pluto_db_{int(time.time())}.db"
        with open(tmp_path, "rb") as fh:
            meta = folder.upload_file(snap_name, fh)
        new_file_id = str(meta.get("id")) if isinstance(meta, dict) and meta.get("id") else None
        if not new_file_id:
            return False

        cache_put(CACHE_DB_FILE_ID_KEY, new_file_id, expiry_hours=720)
        cache_put(
            CACHE_STATS_KEY,
            f"synced_at={datetime.datetime.now(datetime.timezone.utc).isoformat()}|bytes={len(payload)}|file_id={new_file_id}",
            expiry_hours=48,
        )

        with _STATE_LOCK:
            _FILESTORE_LAST_FILE_ID = new_file_id
            _FILESTORE_LAST_SYNC_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()
            _FILESTORE_LAST_ERROR = None

        # Prune previous snapshot file to keep File Store tidy
        if old_file_id and old_file_id != new_file_id:
            try:
                folder.delete_file(old_file_id)
            except Exception:
                pass

        logger.info("Uploaded SQLite DB snapshot to Zoho File Store (file_id=%s, %d bytes).", new_file_id, len(payload))
        return True
    except Exception as exc:
        with _STATE_LOCK:
            _FILESTORE_LAST_ERROR = str(exc)[:200]
        logger.warning("Catalyst File Store DB upload failed: %s", exc)
        return False
    finally:
        tmp_path.unlink(missing_ok=True)


def download_db_snapshot_from_filestore() -> Optional[bytes]:
    """Download latest SQLite DB snapshot from Zoho File Store using Catalyst Cache pointer."""
    global _FILESTORE_LAST_FILE_ID, _FILESTORE_LAST_ERROR
    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return None

    file_id = cache_get(CACHE_DB_FILE_ID_KEY)
    if not file_id:
        # Ensure folder still initializes cleanly so it appears in Console
        _ensure_filestore_folder(catalyst_app)
        return None

    folder = _ensure_filestore_folder(catalyst_app)
    if folder is None:
        return None

    try:
        raw = folder.download_file(file_id)
        if isinstance(raw, (bytes, bytearray)) and bytes(raw).startswith(b"SQLite format 3"):
            with _STATE_LOCK:
                _FILESTORE_LAST_FILE_ID = file_id
                _FILESTORE_LAST_ERROR = None
            logger.info("Restored SQLite DB snapshot from Zoho File Store (file_id=%s, %d bytes).", file_id, len(raw))
            return bytes(raw)
        return None
    except Exception as exc:
        with _STATE_LOCK:
            _FILESTORE_LAST_ERROR = str(exc)[:200]
        logger.warning("Catalyst File Store DB download failed (file_id=%s): %s", file_id, exc)
        return None


# ---------------------------------------------------------------------------
# 3. Zoho Catalyst Data Store Live Mirror (Visible Tables in Catalyst Console)
# ---------------------------------------------------------------------------

def refresh_datastore_tables(*, force: bool = False) -> Dict[str, str]:
    """Discover existing tables in Zoho Catalyst Data Store (cached for 60s)."""
    global _DATASTORE_TABLES_CHECKED_AT, _DATASTORE_LAST_ERROR
    now = time.monotonic()
    with _STATE_LOCK:
        if not force and _DATASTORE_TABLES_CHECKED_AT > 0 and (now - _DATASTORE_TABLES_CHECKED_AT < 60.0):
            return dict(_DATASTORE_TABLES_CACHE)

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return {}

    try:
        tables = catalyst_app.datastore().get_all_tables() or []
        found: Dict[str, str] = {}
        for tbl in tables:
            info = tbl.to_dict() if hasattr(tbl, "to_dict") else {}
            tname = str(info.get("table_name") or "").strip()
            if tname:
                found[tname.lower()] = tname
        with _STATE_LOCK:
            _DATASTORE_TABLES_CACHE.clear()
            _DATASTORE_TABLES_CACHE.update(found)
            _DATASTORE_TABLES_CHECKED_AT = now
            _DATASTORE_LAST_ERROR = None
        return found
    except Exception as exc:
        with _STATE_LOCK:
            _DATASTORE_TABLES_CHECKED_AT = now
            _DATASTORE_LAST_ERROR = str(exc)[:200]
        return {}


def mirror_row_to_datastore(table_name: str, row_data: Dict[str, Any], unique_col: str, unique_val: str) -> bool:
    """Upsert a single sanitized record into a Zoho Catalyst Data Store table if it exists."""
    global _DATASTORE_SYNCED_ROWS, _DATASTORE_LAST_ERROR
    tables = refresh_datastore_tables()
    actual_name = tables.get(table_name.lower())
    if not actual_name:
        return False

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return False

    try:
        safe_val = str(unique_val).replace("'", "''")
        zcql = catalyst_app.zcql()
        existing = zcql.execute_query(
            f"SELECT ROWID FROM {actual_name} WHERE {unique_col} = '{safe_val}' LIMIT 1"
        )
        tbl = catalyst_app.datastore().table(actual_name)
        if existing and isinstance(existing, list) and existing[0].get(actual_name, {}).get("ROWID"):
            row_id = existing[0][actual_name]["ROWID"]
            tbl.update_row({"ROWID": row_id, **row_data})
        else:
            tbl.insert_row(row_data)

        with _STATE_LOCK:
            _DATASTORE_SYNCED_ROWS += 1
            _DATASTORE_LAST_ERROR = None
        return True
    except Exception as exc:
        with _STATE_LOCK:
            _DATASTORE_LAST_ERROR = str(exc)[:200]
        logger.debug("Data Store mirror skipped for %s: %s", actual_name, exc)
        return False


def mirror_async(table_name: str, row_data: Dict[str, Any], unique_col: str, unique_val: str) -> None:
    """Fire-and-forget background Data Store mirror so API latency stays unaffected."""
    threading.Thread(
        target=mirror_row_to_datastore,
        args=(table_name, row_data, unique_col, unique_val),
        daemon=True,
    ).start()
