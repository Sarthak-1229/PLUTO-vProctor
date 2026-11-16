"""Unified Storage Service for PLUTO vProctor.

Supports dual modes:
1. Local Workstation Mode (Default): Direct file persistence in settings.STORAGE_DIR
   (e.g., storage/recordings, storage/resumes, storage/reports).
2. Cloud Staging Mode: S3-compatible object storage via Zoho Catalyst Stratus
   (or AWS S3 / Supabase Storage), with zero external egress cost on Catalyst.
   Gracefully falls back to local storage if remote access fails.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
import httpx

from backend.app.config import settings


class StorageService:
    """Manages file storage across local disk and cloud object storage (Zoho Stratus)."""

    def __init__(self):
        self.local_root = settings.STORAGE_DIR
        self.stratus_endpoint = settings.STRATUS_ENDPOINT.rstrip("/")
        self.stratus_bucket = settings.STRATUS_BUCKET.strip()
        self.stratus_access_key = settings.STRATUS_ACCESS_KEY.strip()
        self.stratus_secret_key = settings.STRATUS_SECRET_KEY.strip()
        self.stratus_region = settings.STRATUS_REGION.strip()

    def is_stratus_enabled(self) -> bool:
        """Return True if Zoho Stratus object storage is fully configured."""
        return bool(self.stratus_endpoint and self.stratus_bucket and self.stratus_access_key)

    def _get_local_path(self, subfolder: str, filename: str) -> Path:
        """Resolve and ensure local directory exists."""
        target_dir = self.local_root / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / filename

    def save_file(self, subfolder: str, filename: str, content: bytes) -> str:
        """Persist a file locally and replicate to Stratus if configured.
        
        Returns the relative key (e.g., 'recordings/sess_123.webm') or local path string.
        """
        # Always write to local disk first for reliable immediate processing
        local_path = self._get_local_path(subfolder, filename)
        local_path.write_bytes(content)

        # Replicate to Zoho Stratus if enabled
        if self.is_stratus_enabled():
            key = f"{subfolder}/{filename}"
            self._upload_to_stratus(key, content)
            return key

        return str(local_path)

    def _upload_to_stratus(self, key: str, content: bytes) -> bool:
        """Upload byte buffer to Zoho Catalyst Stratus S3-compatible bucket."""
        try:
            # Using REST endpoint: {endpoint}/{bucket}/{key}
            url = f"{self.stratus_endpoint}/{self.stratus_bucket}/{key}"
            headers = {
                "Content-Type": "application/octet-stream",
                "x-amz-acl": "private",
            }
            # If access credentials provided, pass basic auth / token header
            auth = (self.stratus_access_key, self.stratus_secret_key) if self.stratus_secret_key else None
            with httpx.Client(timeout=30.0) as client:
                resp = client.put(url, content=content, headers=headers, auth=auth)
                return resp.status_code in {200, 201, 204}
        except Exception as e:
            print(f"[StorageService] Stratus upload error for {key} (local copy intact): {e}")
            return False

    def get_file_bytes(self, subfolder: str, filename: str) -> Optional[bytes]:
        """Read file bytes from local disk, falling back to Stratus."""
        local_path = self.local_root / subfolder / filename
        if local_path.exists() and local_path.is_file():
            return local_path.read_bytes()

        if self.is_stratus_enabled():
            try:
                key = f"{subfolder}/{filename}"
                url = f"{self.stratus_endpoint}/{self.stratus_bucket}/{key}"
                auth = (self.stratus_access_key, self.stratus_secret_key) if self.stratus_secret_key else None
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(url, auth=auth)
                    if resp.status_code == 200:
                        return resp.content
            except Exception as e:
                print(f"[StorageService] Stratus download error for {subfolder}/{filename}: {e}")

        return None

    def get_file_path(self, subfolder: str, filename: str) -> Optional[Path]:
        """Return local file Path if present on disk."""
        local_path = self.local_root / subfolder / filename
        if local_path.exists() and local_path.is_file():
            return local_path
        return None

    def get_presigned_url(self, subfolder: str, filename: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """Generate or return a download URL for a file in Stratus object storage.
        
        Returns None in local workstation mode (where media is served directly via REST endpoints).
        """
        if not self.is_stratus_enabled():
            return None
        key = f"{subfolder}/{filename}"
        # Zoho Stratus REST format with bucket and object key
        return f"{self.stratus_endpoint}/{self.stratus_bucket}/{key}"

    def delete_file(self, subfolder: str, filename: str) -> bool:
        """Delete file from both local storage and Stratus."""
        success = True
        local_path = self.local_root / subfolder / filename
        if local_path.exists():
            try:
                local_path.unlink()
            except Exception as e:
                print(f"[StorageService] Error deleting local file {local_path}: {e}")
                success = False

        if self.is_stratus_enabled():
            try:
                key = f"{subfolder}/{filename}"
                url = f"{self.stratus_endpoint}/{self.stratus_bucket}/{key}"
                auth = (self.stratus_access_key, self.stratus_secret_key) if self.stratus_secret_key else None
                with httpx.Client(timeout=10.0) as client:
                    client.delete(url, auth=auth)
            except Exception as e:
                print(f"[StorageService] Error deleting Stratus object {key}: {e}")

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


storage_service = StorageService()
