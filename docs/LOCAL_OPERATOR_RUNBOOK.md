# PLUTO vProctor — Local Operator Runbook

**Document Version:** 1.0  
**Product Version:** 0.1.0  
**Target Audience:** Local Operators, DevSecOps Engineers, Platform Maintainers, Evaluators  
**Last Updated:** November 2026  

---

## Table of Contents
1. [Overview & Operator Responsibilities](#1-overview--operator-responsibilities)
2. [Prerequisites & Development Environment Matrix](#2-prerequisites--development-environment-matrix)
3. [Repository Directory & Storage Layout](#3-repository-directory--storage-layout)
4. [Environment Configuration (`.env`)](#4-environment-configuration-env)
5. [Database Setup & Schema Initialization](#5-database-setup--schema-initialization)
6. [Launching the Application](#6-launching-the-application)
   - 6.1 [One-Click Startup via `run_dev.bat`](#61-one-click-startup-via-run_devbat)
   - 6.2 [Manual Dual-Terminal Launch Procedure](#62-manual-dual-terminal-launch-procedure)
7. [Health Checks & Readiness Verification](#7-health-checks--readiness-verification)
8. [Managing Local AI Dependencies](#8-managing-local-ai-dependencies)
   - 8.1 [Ollama Service & Local LLM](#81-ollama-service--local-llm)
   - 8.2 [Faster-Whisper Speech-to-Text Model](#82-faster-whisper-speech-to-text-model)
   - 8.3 [MediaPipe Vision Bundles](#83-mediapipe-vision-bundles)
9. [Log Inspection, Log Levels & Monitoring](#9-log-inspection-log-levels--monitoring)
10. [Database Backup Procedures](#10-database-backup-procedures)
11. [Storage & Media Backup Procedures](#11-storage--media-backup-procedures)
12. [Disaster Recovery & Restoration Runbook](#12-disaster-recovery--restoration-runbook)
13. [Safe Application Shutdown](#13-safe-application-shutdown)
14. [Operational Recovery Recipes](#14-operational-recovery-recipes)
    - 14.1 [Resolving SQLite Database Locks](#141-resolving-sqlite-database-locks)
    - 14.2 [Clearing Port Conflicts (8000, 5173, 11434)](#142-clearing-port-conflicts-8000-5173-11434)
    - 14.3 [Purging Corrupted Client Caches](#143-purging-corrupted-client-caches)
15. [SQLite (Local Dev) vs PostgreSQL (Deployment) Reference](#15-sqlite-local-dev-vs-postgresql-deployment-reference)

---

## 1. Overview & Operator Responsibilities

As a Local Operator of **PLUTO vProctor**, you are responsible for maintaining the health, availability, performance, and data integrity of the interview proctoring system running on the host machine.

### Key Responsibilities:
- Ensuring the Python virtual environment and Node dependencies are healthy.
- Managing background AI dependencies (Ollama and Faster-Whisper model caches).
- Executing routine backups of the SQLite database (`pluto.db`), interview recordings, and candidate resumes.
- Diagnosing network or port contention and performing graceful shutdowns.

---

## 2. Prerequisites & Development Environment Matrix

| Dependency | Minimum Version | Verified Version | Purpose |
|---|---|---|---|
| **Operating System** | Windows 10 (64-bit) | Windows 11 Pro 64-bit | Host execution platform |
| **Python** | 3.10.x | 3.12.10 | Backend FastAPI application and AI telemetry pipelines |
| **Node.js** | 18.0.0+ | 20.x / 22.x | Frontend build and runtime tooling |
| **npm** | 9.0.0+ | 10.x | Frontend package manager |
| **Git** | 2.35+ | 2.45+ | Version control |
| **Ollama** | 0.3.0+ | 0.3.14+ | Local offline LLM inference daemon |
| **Web Browser** | Chrome 110+ | Chrome 130+ | Dual-stream WebRTC, MediaRecorder, FaceMesh |

---

## 3. Repository Directory & Storage Layout

PLUTO vProctor organizes its files predictably across the project root:

```text
D:\_TY\MDM\PLUTO-vProctor\
├── backend/
│   ├── .venv/                   # Python virtual environment (ignored from git)
│   ├── app/
│   │   ├── config.py            # Central configuration & thresholds
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── pluto.db             # Primary SQLite application database
│   │   ├── db/                  # SQLAlchemy models and session factory
│   │   ├── routers/             # 14 modular REST & WebSocket route handlers
│   │   └── services/            # Proctoring, scoring, and AI services
│   ├── requirements.txt         # Pinned backend dependencies
│   └── tests/                   # Automated pytest integration suites
├── frontend/
│   ├── src/                     # React 18 source code (Vite + Tailwind)
│   │   ├── App.jsx              # Core client routing and interview coordinator
│   │   ├── components/          # Neo-brutalist UI components
│   │   └── utils/               # Auth client, FSM, and question utilities
│   ├── package.json             # Pinned frontend dependencies
│   └── vite.config.js           # Vite development server & reverse proxy
├── storage/                     # Local file-based binary storage
│   ├── recordings/              # Candidate interview WebM recordings
│   ├── resumes/                 # Uploaded candidate resumes (PDF, DOCX, TXT)
│   └── audio/                   # Temporary extracted WAV audio files
├── datasets/                    # Standard question catalog (1,799 questions)
├── docs/                        # Architectural specifications and manuals
└── run_dev.bat                  # Automated local developer startup script
```

---

## 4. Environment Configuration (`.env`)

Configuration parameters are managed through environment variables loaded via `.env` in the project root:

```ini
# =====================================================================
# PLUTO vProctor — Local Operator Environment Configuration
# =====================================================================

# Application Environment (development, test, production)
ENVIRONMENT=development
DEBUG=True

# Host & Network
API_HOST=127.0.0.1
API_PORT=8000

# Feature Flags
AUTH_ENABLED=True
HOSTED_ROOMS_ENABLED=True
LIVE_MEDIA_ENABLED=True
MEDIA_TRANSPORT_MODE=p2p

# Local SQLite Database (Resolved relative to project root)
DATABASE_URL=sqlite:///./backend/app/pluto.db

# Cryptographic Secrets (In development, an ephemeral key is used if left blank)
SECRET_KEY=dev-secret-key-pluto-vproctor-local-testing-only-minimum-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Local AI Engine Settings
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:3b
WHISPER_MODEL_SIZE=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# WebRTC STUN Configuration
STUN_SERVERS=["stun:stun.l.google.com:19302"]
```

---

## 5. Database Setup & Schema Initialization

PLUTO vProctor stores its operational state in SQLite located at `backend/app/pluto.db`.

### 5.1 Initializing Schema on Clean Systems
To initialize all database tables (users, profiles, resumes, rooms, question sets, reports, sessions, audit logs) programmatically:

```powershell
backend\.venv\Scripts\python.exe -c "from backend.app.db.database import Base, engine; from backend.app.db.models import *; Base.metadata.create_all(bind=engine); print('Database schema successfully initialized.')"
```

### 5.2 Verifying Database Invariants
Run the following verification script to confirm database integrity without altering any records:

```powershell
backend\.venv\Scripts\python.exe -c "from backend.app.db.database import SessionLocal; from backend.app.db.models import User, Job, InterviewSession, Question; db=SessionLocal(); print(f'Users: {db.query(User).count()} | Jobs: {db.query(Job).count()} | Sessions: {db.query(InterviewSession).count()} | Questions: {db.query(Question).count()}'); db.close()"
```

> [!NOTE]
> The catalog contains 1,799 vetted technical interview questions and 14 historical legacy sessions that must remain intact.

---

## 6. Launching the Application

### 6.1 One-Click Startup via `run_dev.bat`
The supported and recommended method to launch PLUTO vProctor on Windows is the root batch script:

1. Open PowerShell or Command Prompt in `D:\_TY\MDM\PLUTO-vProctor`.
2. Run:
   ```cmd
   run_dev.bat
   ```
3. **What `run_dev.bat` executes:**
   - Spawns a dedicated console window running the FastAPI backend via uvicorn on `http://127.0.0.1:8000` with hot-reloading.
   - Spawns a second console window running the React Vite development server on `http://localhost:5173`.
   - Waits 3 seconds for port binding and automatically opens `http://localhost:5173` in your default browser.

### 6.2 Manual Dual-Terminal Launch Procedure
If you prefer running services in separate controlled shells:

#### Terminal 1 — Backend API Server:
```powershell
cd D:\_TY\MDM\PLUTO-vProctor
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Terminal 2 — Frontend Client Server:
```powershell
cd D:\_TY\MDM\PLUTO-vProctor\frontend
npm run dev
```

---

## 7. Health Checks & Readiness Verification

Once the servers are launched, verify application health via HTTP probes:

### 7.1 Liveness Probe (`/api/health`)
```powershell
curl http://127.0.0.1:8000/api/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "app_name": "PLUTO vProctor",
  "version": "0.1.0",
  "environment": "development",
  "ollama_endpoint": "http://localhost:11434",
  "model": "qwen2.5:3b"
}
```

### 7.2 Readiness Probe (`/api/ready`)
```powershell
curl http://127.0.0.1:8000/api/ready
```
**Expected Response:**
```json
{
  "status": "ready",
  "database": "connected",
  "storage": "available"
}
```

---

## 8. Managing Local AI Dependencies

PLUTO vProctor runs multimodal AI locally on the host machine to preserve privacy and avoid recurring cloud API fees.

### 8.1 Ollama Service & Local LLM
1. **Check Ollama Status:**
   ```powershell
   curl http://localhost:11434/api/tags
   ```
2. **Start Daemon (if stopped):**
   ```powershell
   ollama serve
   ```
3. **Pull Recommended Model:**
   ```powershell
   ollama pull qwen2.5:3b
   ```
   *(Or `ollama pull llama3.2:3b`)*.

### 8.2 Faster-Whisper Speech-to-Text Model
- Faster-Whisper automatically downloads its quantized model (`base.en`, $\approx 140\text{ MB}$) on the first evaluation run.
- **Model Cache Location:** Windows user directory:
  `C:\Users\<Username>\.cache\huggingface\hub\`
- **Verification Command:**
  ```powershell
  backend\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; model = WhisperModel('base.en', device='cpu', compute_type='int8'); print('Whisper initialized successfully.')"
  ```

### 8.3 MediaPipe Vision Bundles
- MediaPipe FaceMesh and Iris detection bundles are served statically by Vite from `frontend/src/assets/` and `frontend/public/`.
- No separate external daemon is required; vision computation runs client-side in the browser via WebAssembly (WASM).

---

## 9. Log Inspection, Log Levels & Monitoring

### 9.1 Structured Backend Logs
Backend logs use a structured format containing timestamps, log severity, request correlation IDs, and logger component names:
```text
2026-11-14 17:09:55 [INFO] [Req:a8f9c102] pluto.server: GET /api/admin/users -> 200 (14.20ms)
```

### 9.2 Changing Log Verbosity
In `.env`, set `LOG_LEVEL`:
- `DEBUG`: Comprehensive pipeline event logs, token refresh traces, and model timing.
- `INFO`: Standard operational requests and lifecycle transitions (default).
- `WARNING`: Recoverable errors and proctoring threshold alerts.
- `ERROR`: Unhandled exceptions, failed pipeline jobs, and fatal database errors.

---

## 10. Database Backup Procedures

Because SQLite stores all data in a single file (`backend/app/pluto.db`), backups are simple and reliable.

### 10.1 Safe Online Snapshot (Recommended)
Use SQLite's online vacuum/backup command, which safely serializes the database even while transactions are active:

```powershell
# Create backup directory
New-Item -ItemType Directory -Force -Path "D:\_TY\MDM\PLUTO-vProctor\backups"

# Execute atomic snapshot
backend\.venv\Scripts\python.exe -c "import sqlite3; src=sqlite3.connect('backend/app/pluto.db'); dst=sqlite3.connect('backups/pluto_' + __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S') + '.db'); src.backup(dst); dst.close(); src.close(); print('Backup complete.')"
```

### 10.2 Cold Copy Backup
When both backend and test runners are idle:
```powershell
Copy-Item backend\app\pluto.db backups\pluto_cold_copy.db
```

---

## 11. Storage & Media Backup Procedures

Session recordings and uploaded resumes reside in the `storage/` directory.

### 11.1 Backing up Binary Media Files
```powershell
# Archive recordings and resumes into backups directory
Compress-Archive -Path storage\recordings, storage\resumes -DestinationPath "backups\media_storage_backup.zip" -Force
```

---

## 12. Disaster Recovery & Restoration Runbook

If data corruption or accidental file deletion occurs:

### Step 1: Terminate Running Application Instances
```powershell
taskkill /IM python.exe /F
taskkill /IM node.exe /F
```

### Step 2: Restore Database from Backup
```powershell
# Archive the corrupted database for post-mortem analysis
Move-Item backend\app\pluto.db backend\app\pluto_corrupt.db

# Copy healthy backup into place
Copy-Item backups\<backup_filename>.db backend\app\pluto.db
```

### Step 3: Restore Storage Directory
```powershell
Expand-Archive -Path backups\media_storage_backup.zip -DestinationPath storage -Force
```

### Step 4: Verify Schema & Re-run Test Suite
```powershell
$env:PYTHONPATH='.'; backend\.venv\Scripts\pytest.exe backend/tests/test_candidate_governance_and_completed_rooms.py -v
```

---

## 13. Safe Application Shutdown

To prevent incomplete video uploads or half-written database transactions:

1. **Verify No Live Interviews:** Check the Admin Room Manager to confirm no room is in `LIVE` or `PROCESSING` status.
2. **Close Development Windows:** If launched via `run_dev.bat`, simply close the two command windows or press `Ctrl+C` in each window.
3. **Verify Port Clearance:**
   ```powershell
   netstat -ano | findstr :8000
   netstat -ano | findstr :5173
   ```
   Confirm no listening sockets remain active.

---

## 14. Operational Recovery Recipes

### 14.1 Resolving SQLite Database Locks
- **Problem:** `sqlite3.OperationalError: database is locked`.
- **Cause:** A hung python process holds an exclusive write lock on `pluto.db`.
- **Solution:**
  ```powershell
  # 1. Kill any lingering python processes
  taskkill /IM python.exe /F
  # 2. Check and remove orphaned SQLite WAL/SHM lock files if backend is fully stopped
  Remove-Item backend\app\pluto.db-wal -ErrorAction SilentlyContinue
  Remove-Item backend\app\pluto.db-shm -ErrorAction SilentlyContinue
  ```

### 14.2 Clearing Port Conflicts (8000, 5173, 11434)
- **Problem:** `Address already in use`.
- **Solution:**
  ```powershell
  # Find PID occupying port 8000
  $pid8000 = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
  if ($pid8000) { Stop-Process -Id $pid8000 -Force }

  # Find PID occupying port 5173
  $pid5173 = (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue).OwningProcess
  if ($pid5173) { Stop-Process -Id $pid5173 -Force }
  ```

### 14.3 Purging Corrupted Client Caches
- **Problem:** Vite hot-reloading fails or stale JavaScript chunks fail to load.
- **Solution:**
  ```powershell
  cd D:\_TY\MDM\PLUTO-vProctor\frontend
  Remove-Item -Recurse -Force node_modules\.vite
  npm run dev
  ```

---

## 15. SQLite (Local Dev) vs PostgreSQL (Deployment) Reference

> [!IMPORTANT]
> In local development mode, PLUTO vProctor runs exclusively on SQLite (`backend/app/pluto.db`).
> Production deployment configuration is explicitly out of scope for this local runbook. However, operators should note the syntactic differences in connection strings:

| Property | Local Development Mode (Current) | Production Deployment Mode (Future) |
|---|---|---|
| **Driver Engine** | SQLite3 via SQLAlchemy | PostgreSQL via `psycopg` (v3) |
| **Connection String** | `sqlite:///./backend/app/pluto.db` | `postgresql+psycopg://user:pass@host:5432/dbname` |
| **Concurrency Model** | Single-writer / Multi-reader (WAL) | Full MVCC Row-Level Concurrency |
| **Session Lifetime** | Local disk file | Managed Connection Pool |
| **JSON Columns** | Serialized text JSON | Native Binary `JSONB` with GIN indexing |
| **Backup Command** | File copy / SQLite online backup API | `pg_dump -Fc` / Logical replication |
