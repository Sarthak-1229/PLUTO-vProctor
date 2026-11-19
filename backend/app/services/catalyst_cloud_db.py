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
_DATASTORE_COLUMNS_CACHE: Dict[str, Dict[str, str]] = {}  # lower_table -> {lower_col: exact_col}
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
    """Download latest SQLite DB snapshot from Zoho File Store using Catalyst Cache or folder file discovery."""
    global _FILESTORE_LAST_FILE_ID, _FILESTORE_LAST_ERROR
    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return None

    folder = _ensure_filestore_folder(catalyst_app)
    if folder is None:
        return None

    file_id = cache_get(CACHE_DB_FILE_ID_KEY)

    # If Cache key is missing/cold, inspect File Store folder files directly to find latest snapshot
    if not file_id:
        try:
            from zcatalyst_sdk.types import CredentialUser
            resp = folder._requester.request(
                method="GET",
                path=f"/folder/{folder._id}/file",
                user=CredentialUser.USER,
            )
            file_list = resp.response_json.get("data") or []
            db_files = [
                f for f in file_list
                if isinstance(f, dict) and str(f.get("file_name", "")).startswith("pluto_db_")
            ]
            if db_files:
                db_files.sort(
                    key=lambda x: str(x.get("created_time") or x.get("id") or ""),
                    reverse=True,
                )
                file_id = str(db_files[0].get("id"))
                logger.info(
                    "Discovered latest DB snapshot directly from File Store folder: %s (file_id=%s)",
                    db_files[0].get("file_name"),
                    file_id,
                )
                cache_put(CACHE_DB_FILE_ID_KEY, file_id, expiry_hours=720)
        except Exception as exc:
            logger.debug("Listing File Store folder files skipped: %s", exc)

    if not file_id:
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


def _get_table_columns(catalyst_app, table_name: str) -> Dict[str, str]:
    """Return {lower_col_name: actual_col_name} for user-defined columns in a Data Store table."""
    key = table_name.lower()
    with _STATE_LOCK:
        cached = _DATASTORE_COLUMNS_CACHE.get(key)
    if cached is not None:
        return dict(cached)

    system_cols = {"rowid", "creatorid", "createdtime", "modifiedtime"}
    try:
        cols = catalyst_app.datastore().table(table_name).get_all_columns() or []
        mapping: Dict[str, str] = {}
        for col in cols:
            cname = str(col.get("column_name") or "").strip() if isinstance(col, dict) else ""
            if cname and cname.lower() not in system_cols:
                mapping[cname.lower()] = cname
        with _STATE_LOCK:
            _DATASTORE_COLUMNS_CACHE[key] = mapping
        return dict(mapping)
    except Exception:
        return {}


def _auto_provision_columns_if_missing(catalyst_app, table_name: str) -> Dict[str, str]:
    """Attempt to auto-provision standard Pluto columns on empty Catalyst Data Store tables."""
    key = table_name.lower()
    tbl = catalyst_app.datastore().table(table_name)
    identifier = getattr(tbl, "_identifier", table_name)
    columns_to_create = [
        {"column_name": "user_id", "data_type": "varchar", "max_length": 100},
        {"column_name": "email", "data_type": "varchar", "max_length": 150},
        {"column_name": "full_name", "data_type": "varchar", "max_length": 150},
        {"column_name": "role", "data_type": "varchar", "max_length": 50},
        {"column_name": "password_hash", "data_type": "varchar", "max_length": 255},
        {"column_name": "created_at", "data_type": "varchar", "max_length": 100},
        {"column_name": "data", "data_type": "text"},
    ]
    try:
        from zcatalyst_sdk.types import CredentialUser
        for col in columns_to_create:
            try:
                tbl._requester.request(
                    method="POST",
                    path=f"/table/{identifier}/column",
                    json=col,
                    user=CredentialUser.USER,
                )
            except Exception:
                pass
    except Exception:
        pass

    with _STATE_LOCK:
        _DATASTORE_COLUMNS_CACHE.pop(key, None)
    return _get_table_columns(catalyst_app, table_name)


def lookup_user_in_datastore(email: str) -> Optional[Dict[str, Any]]:
    """Query Zoho Catalyst Data Store PlutoUsers table for user credentials & profile."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return None

    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return None

    tables = refresh_datastore_tables()
    actual_name = tables.get("plutousers")
    if not actual_name:
        return None

    try:
        zcql = catalyst_app.zcql()
        col_map = _get_table_columns(catalyst_app, actual_name)
        email_col = col_map.get("email") or col_map.get("username")

        safe_email = clean_email.replace("'", "''")
        if email_col:
            q = f"SELECT * FROM {actual_name} WHERE {email_col} = '{safe_email}' LIMIT 1"
            rows = zcql.execute_query(q)
            if rows and isinstance(rows, list):
                row_obj = rows[0].get(actual_name) or rows[0]
                # Check if full JSON stored in 'data' column
                data_col = col_map.get("data")
                if data_col and row_obj.get(data_col):
                    try:
                        import json
                        parsed = json.loads(row_obj[data_col])
                        if isinstance(parsed, dict) and parsed.get("password_hash"):
                            return parsed
                    except Exception:
                        pass
                user_id_col = col_map.get("user_id") or "user_id"
                full_name_col = col_map.get("full_name") or "full_name"
                role_col = col_map.get("role") or "role"
                pwd_col = col_map.get("password_hash") or "password_hash"
                created_col = col_map.get("created_at") or "created_at"
                return {
                    "id": row_obj.get(user_id_col) or f"usr_recovered_{int(time.time())}",
                    "email": clean_email,
                    "full_name": row_obj.get(full_name_col) or "Candidate",
                    "role": row_obj.get(role_col) or "candidate",
                    "password_hash": row_obj.get(pwd_col),
                    "created_at": row_obj.get(created_col),
                }

        # If table has a 'data' catch-all column without an explicit email column:
        data_col = col_map.get("data")
        if data_col:
            q = f"SELECT {data_col} FROM {actual_name} LIMIT 100"
            rows = zcql.execute_query(q)
            if rows and isinstance(rows, list):
                import json
                for r in rows:
                    obj = r.get(actual_name) or r
                    raw = obj.get(data_col)
                    if raw:
                        try:
                            parsed = json.loads(raw)
                            if isinstance(parsed, dict) and str(parsed.get("email", "")).lower() == clean_email:
                                return parsed
                        except Exception:
                            pass
        return None
    except Exception as exc:
        logger.debug("Catalyst Data Store user lookup failed: %s", exc)
        return None


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
        col_map = _get_table_columns(catalyst_app, actual_name)
        if not col_map and actual_name.lower() == "plutousers":
            col_map = _auto_provision_columns_if_missing(catalyst_app, actual_name)
        mapped_row: Dict[str, Any] = {}

        # 1. Direct or alias match
        aliases = {
            "user_id": ["user_id", "userid", "id", "candidate_id"],
            "email": ["email", "email_id", "email_address", "username"],
            "full_name": ["full_name", "fullname", "name", "candidate_name"],
            "role": ["role", "user_role", "type"],
            "password_hash": ["password_hash", "password", "hash"],
            "is_active": ["is_active", "active", "status"],
            "created_at": ["created_at", "joined_at", "reg_date"],
        }

        for k, v in row_data.items():
            low_k = k.lower()
            target_col = col_map.get(low_k)
            if not target_col and low_k in aliases:
                for candidate in aliases[low_k]:
                    if candidate in col_map:
                        target_col = col_map[candidate]
                        break
            if target_col:
                mapped_row[target_col] = v

        # 2. JSON catch-all fallback if table has a single generic column (e.g. data / details)
        if not mapped_row:
            import json
            for catch_col in ("data", "json", "payload", "details", "user_data", "user_details"):
                target = col_map.get(catch_col)
                if target:
                    mapped_row[target] = json.dumps(row_data)
                    break

        if not mapped_row:
            with _STATE_LOCK:
                _DATASTORE_LAST_ERROR = (
                    f"Table '{actual_name}' has no matching columns (found: {sorted(col_map.values())}, expected any of: {sorted(row_data.keys())})"
                )
            return False

        tbl = catalyst_app.datastore().table(actual_name)
        actual_unique_col = col_map.get(unique_col.lower())
        existing_row_id = None
        if actual_unique_col:
            try:
                safe_val = str(unique_val).replace("'", "''")
                zcql = catalyst_app.zcql()
                existing = zcql.execute_query(
                    f"SELECT ROWID FROM {actual_name} WHERE {actual_unique_col} = '{safe_val}' LIMIT 1"
                )
                if existing and isinstance(existing, list) and existing[0].get(actual_name, {}).get("ROWID"):
                    existing_row_id = existing[0][actual_name]["ROWID"]
            except Exception:
                existing_row_id = None

        if existing_row_id:
            tbl.update_row({"ROWID": existing_row_id, **mapped_row})
        else:
            tbl.insert_row(mapped_row)

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


def sync_all_users_to_datastore() -> int:
    """Scan local SQLite users and mirror any records into Zoho Data Store PlutoUsers table if columns exist."""
    catalyst_app = get_catalyst_app(scope="admin")
    if catalyst_app is None:
        return 0
    tables = refresh_datastore_tables(force=True)
    actual_name = tables.get("plutousers")
    if not actual_name:
        return 0
    col_map = _get_table_columns(catalyst_app, actual_name)
    if not col_map:
        col_map = _auto_provision_columns_if_missing(catalyst_app, actual_name)
    if not col_map:
        return 0

    count = 0
    try:
        from backend.app.db.database import SessionLocal
        from backend.app.db.models import User

        with SessionLocal() as db:
            users = db.query(User).all()
            for u in users:
                row_data = {
                    "user_id": u.id,
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role,
                    "password_hash": u.password_hash,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else "",
                }
                if mirror_row_to_datastore("PlutoUsers", row_data, "user_id", u.id):
                    count += 1
    except Exception as exc:
        logger.debug("Backfill PlutoUsers skipped: %s", exc)
    return count
