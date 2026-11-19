"""Unified Storage Service for PLUTO vProctor.

Supports three clean modes:
1. Zoho Catalyst Native SDK Stratus (Preferred on AppSail):
   Uses `zcatalyst_sdk` (`catalyst_app.stratus().bucket(STRATUS_BUCKET)`) with zero
   manual access keys or OAuth secrets required — just set `STRATUS_BUCKET`.
2. Direct Stratus REST / S3-compatible Mode:
   Uses `STRATUS_ENDPOINT` + `STRATUS_BUCKET` + `STRATUS_ACCESS_KEY` (supports both
   `Zoho-oauthtoken` and Basic auth) with graceful local fallback.
3. Local Workstation Mode (Default):
   Direct file persistence in `settings.STORAGE_DIR` (resumes, recordings, reports).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

from backend.app.config import settings
from backend.app.services.catalyst_context import get_catalyst_app

logger = logging.getLogger("pluto.storage")


class StorageService:
    """Manages file storage across local disk and Zoho Catalyst Stratus."""

    def __init__(self):
        self.local_root = settings.STORAGE_DIR
        self.stratus_endpoint = settings.STRATUS_ENDPOINT.rstrip("/")
        self.stratus_bucket = settings.STRATUS_BUCKET.strip()
        self.stratus_access_key = settings.STRATUS_ACCESS_KEY.strip()
        self.stratus_secret_key = settings.STRATUS_SECRET_KEY.strip()
        self.stratus_region = settings.STRATUS_REGION.strip()

    def _bucket_name(self) -> str:
        return (self.stratus_bucket or settings.STRATUS_BUCKET or "").strip()

    def _endpoint(self) -> str:
        return (self.stratus_endpoint or settings.STRATUS_ENDPOINT or "").rstrip("/")

    def _access_key(self) -> str:
        return (self.stratus_access_key or settings.STRATUS_ACCESS_KEY or "").strip()

    def _secret_key(self) -> str:
        return (self.stratus_secret_key or settings.STRATUS_SECRET_KEY or "").strip()

    def _get_sdk_bucket(self):
        """Return native Zoho Catalyst SDK Stratus Bucket instance if available."""
        bucket_name = self._bucket_name()
        catalyst_app = get_catalyst_app(scope="admin")
        if catalyst_app is None:
            return None

        # Auto-discover or auto-create Stratus bucket inside Catalyst AppSail
        if not bucket_name:
            try:
                buckets = catalyst_app.stratus().list_buckets() or []
                if buckets:
                    b = buckets[0]
                    discovered = getattr(b, "_bucket_name", None) or (b.get_name() if hasattr(b, "get_name") else None)
                    if discovered:
                        self.stratus_bucket = discovered
                        bucket_name = discovered
                        logger.info("Auto-discovered existing Zoho Catalyst Stratus bucket: %s", discovered)
            except Exception as exc:
                logger.debug("Stratus bucket auto-discovery skipped: %s", exc)

        if not bucket_name:
            # Attempt to auto-create 'pluto-storage' bucket via Catalyst Stratus API
            try:
                from zcatalyst_sdk.types import CredentialUser, RequestMethod
                default_name = "pluto-storage"
                catalyst_app.stratus()._requester.request(
                    method=RequestMethod.POST,
                    path="/bucket",
                    json={"bucket_name": default_name},
                    user=CredentialUser.ADMIN,
                )
                self.stratus_bucket = default_name
                bucket_name = default_name
                logger.info("Auto-created Zoho Catalyst Stratus bucket: %s", default_name)
            except Exception as exc:
                logger.debug("Auto-creating Stratus bucket skipped: %s", exc)

        if not bucket_name:
            return None

        try:
            return catalyst_app.stratus().bucket(bucket_name)
        except Exception as exc:
            logger.debug("Catalyst SDK Stratus bucket init failed for '%s': %s", bucket_name, exc)
            return None

    def is_rest_stratus_enabled(self) -> bool:
        """Return True if direct REST Stratus endpoint + bucket + key are configured."""
        return bool(self._endpoint() and self._bucket_name() and self._access_key())

    def is_sdk_stratus_enabled(self) -> bool:
        """Return True if native Catalyst SDK Stratus bucket is configured and reachable."""
        return bool(self._bucket_name() and self._get_sdk_bucket() is not None)

    def is_stratus_enabled(self) -> bool:
        """Return True if either native Catalyst SDK Stratus or REST Stratus is enabled."""
        return self.is_sdk_stratus_enabled() or self.is_rest_stratus_enabled()

    def _get_local_path(self, subfolder: str, filename: str) -> Path:
        """Resolve and ensure local directory exists."""
        root = self.local_root or settings.STORAGE_DIR
        target_dir = root / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / filename

    def upload_raw_bytes(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> bool:
        """Upload raw bytes directly to Zoho Stratus (SDK first, then REST fallback)."""
        sdk_bucket = self._get_sdk_bucket()
        if sdk_bucket is not None:
            try:
                res = sdk_bucket.put_object(
                    key,
                    content,
                    options={"overwrite": "true", "content_type": content_type},
                )
                return bool(res)
            except Exception as exc:
                logger.warning("Catalyst SDK Stratus put_object failed for %s: %s", key, exc)

        if self.is_rest_stratus_enabled():
            return self._upload_to_stratus(key, content)

        return False

    def download_raw_bytes(self, key: str) -> Optional[bytes]:
        """Download raw bytes directly from Zoho Stratus (SDK first, then REST fallback)."""
        sdk_bucket = self._get_sdk_bucket()
        if sdk_bucket is not None:
            try:
                data = sdk_bucket.get_object(key)
                if isinstance(data, (bytes, bytearray)) and len(data) > 0:
                    return bytes(data)
            except Exception as exc:
                logger.debug("Catalyst SDK Stratus get_object miss/error for %s: %s", key, exc)

        if self.is_rest_stratus_enabled():
            try:
                url = f"{self._endpoint()}/{self._bucket_name()}/{key}"
                headers = {}
                auth = None
                if self._secret_key():
                    auth = (self._access_key(), self._secret_key())
                elif self._access_key():
                    headers["Authorization"] = f"Zoho-oauthtoken {self._access_key()}"
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(url, headers=headers, auth=auth)
                    if resp.status_code == 200:
                        return resp.content
            except Exception as exc:
                logger.warning("Stratus REST download error for %s: %s", key, exc)

        return None

    def delete_remote_object(self, key: str) -> bool:
        """Delete an object from Zoho Stratus (SDK first, then REST fallback)."""
        sdk_bucket = self._get_sdk_bucket()
        if sdk_bucket is not None:
            try:
                sdk_bucket.delete_object(key)
                return True
            except Exception as exc:
                logger.warning("Catalyst SDK Stratus delete_object failed for %s: %s", key, exc)

        if self.is_rest_stratus_enabled():
            try:
                url = f"{self._endpoint()}/{self._bucket_name()}/{key}"
                headers = {}
                auth = None
                if self._secret_key():
                    auth = (self._access_key(), self._secret_key())
                elif self._access_key():
                    headers["Authorization"] = f"Zoho-oauthtoken {self._access_key()}"
                with httpx.Client(timeout=10.0) as client:
                    client.delete(url, headers=headers, auth=auth)
                return True
            except Exception as exc:
                logger.warning("Stratus REST delete error for %s: %s", key, exc)

        return False

    def save_file(self, subfolder: str, filename: str, content: bytes) -> str:
        """Persist a file locally and replicate to Zoho Stratus if configured.

        Returns the relative key (e.g., 'recordings/sess_123.webm') when Stratus is active,
        or local path string otherwise.
        """
        local_path = self._get_local_path(subfolder, filename)
        local_path.write_bytes(content)

        if self.is_stratus_enabled():
            key = f"{subfolder}/{filename}"
            self.upload_raw_bytes(key, content)
            return key

        return str(local_path)

    def _upload_to_stratus(self, key: str, content: bytes) -> bool:
        """Upload byte buffer to Zoho Catalyst Stratus REST endpoint."""
        try:
            url = f"{self._endpoint()}/{self._bucket_name()}/{key}"
            headers = {
                "Content-Type": "application/octet-stream",
                "x-amz-acl": "private",
            }
            auth = None
            if self._secret_key():
                auth = (self._access_key(), self._secret_key())
            elif self._access_key():
                headers["Authorization"] = f"Zoho-oauthtoken {self._access_key()}"
            with httpx.Client(timeout=30.0) as client:
                resp = client.put(url, content=content, headers=headers, auth=auth)
                return resp.status_code in {200, 201, 204}
        except Exception as exc:
            logger.warning("[StorageService] Stratus REST upload error for %s (local copy intact): %s", key, exc)
            return False

    def get_file_bytes(self, subfolder: str, filename: str) -> Optional[bytes]:
        """Read file bytes from local disk, falling back to Zoho Stratus."""
        local_path = (self.local_root or settings.STORAGE_DIR) / subfolder / filename
        if local_path.exists() and local_path.is_file():
            return local_path.read_bytes()

        if self.is_stratus_enabled():
            key = f"{subfolder}/{filename}"
            return self.download_raw_bytes(key)

        return None

    def get_file_path(self, subfolder: str, filename: str) -> Optional[Path]:
        """Return local file Path if present on disk (hydrating from Stratus if missing locally)."""
        local_path = (self.local_root or settings.STORAGE_DIR) / subfolder / filename
        if local_path.exists() and local_path.is_file():
            return local_path
        if self.is_stratus_enabled():
            remote = self.download_raw_bytes(f"{subfolder}/{filename}")
            if remote:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(remote)
                return local_path
        return None

    def get_presigned_url(self, subfolder: str, filename: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """Generate or return a download URL for a file in Stratus object storage.

        Returns None in local workstation mode (where media is served directly via REST endpoints).
        """
        if not self.is_stratus_enabled():
            return None
        key = f"{subfolder}/{filename}"
        if self._endpoint():
            return f"{self._endpoint()}/{self._bucket_name()}/{key}"
        sdk_bucket = self._get_sdk_bucket()
        if sdk_bucket is not None:
            return f"{sdk_bucket.bucket_domain}/{key}"
        return None

    def delete_file(self, subfolder: str, filename: str) -> bool:
        """Delete file from both local storage and Zoho Stratus."""
        success = True
        local_path = (self.local_root or settings.STORAGE_DIR) / subfolder / filename
        if local_path.exists():
            try:
                local_path.unlink()
            except Exception as exc:
                logger.warning("[StorageService] Error deleting local file %s: %s", local_path, exc)
                success = False

        if self.is_stratus_enabled():
            self.delete_remote_object(f"{subfolder}/{filename}")

        return success

    def delete_candidate_data(self, video_filenames: list[str], resume_keys: list[str]) -> bool:
        """GDPR Right to Erasure: Purge all candidate recordings and resumes."""
        all_deleted = True
        for vf in video_filenames:
            if vf:
                if not self.delete_file("recordings", vf):
                    all_deleted = False

        for rk in resume_keys:
            if rk:
                if not self.delete_file("resumes", rk):
                    all_deleted = False

        return all_deleted

    def migrate_filestore_to_stratus(self) -> bool:
        """Migrate legacy Zoho Catalyst File Store database snapshot to Zoho Stratus (pre-Oct 2026 EOL)."""
        if not self.is_stratus_enabled():
            return False
        try:
            from backend.app.services.catalyst_cloud_db import download_db_snapshot_from_filestore

            existing_stratus = self.download_raw_bytes("db_snapshots/pluto.db")
            if existing_stratus and isinstance(existing_stratus, (bytes, bytearray)) and bytes(existing_stratus).startswith(b"SQLite format 3"):
                return True

            raw = download_db_snapshot_from_filestore()
            if raw and isinstance(raw, (bytes, bytearray)) and bytes(raw).startswith(b"SQLite format 3"):
                ok = self.upload_raw_bytes("db_snapshots/pluto.db", bytes(raw), content_type="application/x-sqlite3")
                if ok:
                    logger.info("Successfully migrated SQLite DB snapshot from deprecated File Store to Zoho Stratus (%d bytes).", len(raw))
                    return True
            return False
        except Exception as exc:
            logger.debug("File Store to Stratus migration skipped: %s", exc)
            return False


storage_service = StorageService()
