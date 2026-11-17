#!/usr/bin/env python3
"""
PLUTO vProctor — Generate Zoho Catalyst Deployment ZIPs
=======================================================
Creates deployment-ready ZIP archives for:
  1. Zoho Catalyst AppSail (Backend): deploy/packages/appsail-backend.zip
  2. Zoho Catalyst Web Client Hosting (Frontend): deploy/packages/frontend-webclient.zip

Usage:
    python scripts/build_deployment_zips.py
"""

import os
import sys
import zipfile
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = ROOT_DIR / "deploy" / "packages"
DEPLOY_DIR.mkdir(parents=True, exist_ok=True)


def build_frontend():
    dist_dir = ROOT_DIR / "frontend" / "dist"
    index_file = dist_dir / "index.html"

    if not index_file.exists():
        print("[*] frontend/dist/index.html not found. Building frontend...")
        try:
            subprocess.run(["npm", "run", "build"], cwd=ROOT_DIR / "frontend", check=True, shell=True)
        except Exception as exc:
            print(f"[ERROR] Failed to build frontend: {exc}")
            return None

    out_zip = DEPLOY_DIR / "frontend-webclient.zip"
    print(f"[*] Packaging Frontend Web Client -> {out_zip.relative_to(ROOT_DIR)}...")

    count = 0
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dist_dir):
            for f in files:
                p = Path(root) / f
                arcname = p.relative_to(dist_dir)
                zf.write(p, arcname)
                count += 1

    size_mb = out_zip.stat().st_size / (1024 * 1024)
    print(f"  ✓ Packaged {count} files ({size_mb:.2f} MB)")
    return out_zip


def build_backend():
    backend_dir = ROOT_DIR / "backend"
    out_zip = DEPLOY_DIR / "appsail-backend.zip"
    print(f"[*] Packaging Backend AppSail -> {out_zip.relative_to(ROOT_DIR)}...")

    ignore_dirs = {".venv", "venv", "__pycache__", ".pytest_cache", "tests", "storage", ".git"}
    ignore_exts = {".pyc", ".pyo", ".db", ".sqlite3"}
    ignore_files = {"pluto.db"}

    count = 0
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(backend_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for f in files:
                p = Path(root) / f
                if p.suffix in ignore_exts or p.name in ignore_files or p.name.endswith(".pyc"):
                    continue
                arcname = p.relative_to(backend_dir)
                zf.write(p, arcname)
                count += 1

    size_mb = out_zip.stat().st_size / (1024 * 1024)
    print(f"  ✓ Packaged {count} files ({size_mb:.2f} MB)")
    return out_zip


def main():
    print(f"\n{'='*60}")
    print("  PLUTO vProctor — Building Zoho Catalyst Deployment Packages")
    print(f"{'='*60}\n")

    f_zip = build_frontend()
    b_zip = build_backend()

    print(f"\n{'='*60}")
    print("  ZIP Files Ready for Zoho Catalyst Upload:")
    print(f"{'='*60}")
    if f_zip:
        print(f"  • Frontend (Web Client Hosting): {f_zip}")
    if b_zip:
        print(f"  • Backend (AppSail Service):     {b_zip}")
    print()


if __name__ == "__main__":
    main()
