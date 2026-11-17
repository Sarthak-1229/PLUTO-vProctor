# PLUTO vProctor — Deployment Package README

> This document explains what is in the deployment package and what to do with each piece.

---

## What Gets Deployed

PLUTO vProctor has two parts:

| Part | What It Is | Where It Goes |
|---|---|---|
| **Frontend** | The React web app (HTML, CSS, JavaScript) | Zoho Catalyst **Web Client Hosting** |
| **Backend** | The Python/FastAPI server | Zoho Catalyst **AppSail** |

---

## Frontend Deployment Package

**Folder:** `frontend/dist/`

This is the **built** version of the React app. You build it with:

```
cd frontend
npm run build
```

The `dist/` folder is then uploaded to Web Client Hosting via:

```
catalyst webclient deploy
```

**Important:** The `dist/` folder is auto-generated and is excluded from Git. Always run `npm run build` before deploying.

**What is inside `frontend/dist/`:**

```
frontend/dist/
├── index.html          ← Entry point for the SPA
├── assets/
│   ├── index-*.js      ← Bundled JavaScript (all React code)
│   └── index-*.css     ← Bundled CSS (Tailwind styles)
└── ...
```

**What NOT to upload:**
- `frontend/node_modules/` — development dependencies, not needed in production
- `frontend/src/` — source code, only the built `dist/` is deployed
- `frontend/.env.production` — secrets, set via environment not by upload

---

## Backend Deployment Package

**Folder:** `backend/`

The backend is deployed as source code. AppSail installs dependencies and runs the server.

**Key files:**

```
backend/
├── app/
│   ├── main.py                  ← FastAPI entry point
│   ├── config.py                ← All settings (reads from env vars)
│   ├── routers/                 ← API route handlers
│   ├── services/                ← Business logic
│   ├── pipelines/               ← Video/audio/gaze analysis
│   ├── data/
│   │   ├── questions/           ← 1,799 question JSON files (deployed)
│   │   ├── processed/           ← ML model files (*.joblib) if present
│   │   └── face_landmarker.task ← MediaPipe model (large — 10 MB)
│   └── alembic/                 ← Database migration scripts
├── requirements.txt             ← Python dependencies
└── Dockerfile                   ← Container config (for reference)
```

**What AppSail does automatically:**
1. Reads `catalyst.json` to find the backend source folder
2. Installs `pip install -r requirements.txt`
3. Runs: `uvicorn backend.app.main:app --host 0.0.0.0 --port $X_ZOHO_CATALYST_LISTEN_PORT`

**What NOT to upload / what is excluded:**
- `backend/.venv/` — virtual environment (AppSail creates its own)
- `backend/app/pluto.db` — the local SQLite database (not deployed; AppSail uses ephemeral SQLite or you configure an external DB)
- `backend/.env` — real secrets (set as AppSail environment variables instead)
- `storage/` — local file uploads (configure Stratus S3 storage for hosted mode)

---

## Catalyst Configuration Files

| File | Purpose |
|---|---|
| `catalyst.json` | Master Catalyst project config — links AppSail and Web Client Hosting |
| `backend/app-config.json` | AppSail-specific config (startup command, stack version) |
| `backend/.env.hosted.example` | Template for AppSail environment variables |
| `frontend/.env.production.example` | Template for the frontend production build |

---

## Environment Variables — What You MUST Set

Before deploying, set these in the **Catalyst Console → AppSail → Environment Variables**:

| Variable | Required? | How to Get It |
|---|---|---|
| `SECRET_KEY` | ✅ REQUIRED | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | ✅ REQUIRED | Your Web Client Hosting domain, as a JSON array: `["https://..."]` |
| `ENVIRONMENT` | Set in catalyst.json | Already set to `staging` |
| `DEBUG` | Set in catalyst.json | Already set to `false` |
| `STRATUS_*` | Optional (for file uploads) | From Catalyst Console → Stratus bucket settings |

---

## Quick Reference — Deployment Commands

```powershell
# 1. Authenticate
catalyst login

# 2. Build frontend
cd frontend
npm install
npm run build
cd ..

# 3. Deploy backend
catalyst appsail deploy

# 4. Deploy frontend
catalyst webclient deploy

# 5. Smoke test (after deployment)
$env:PLUTO_BASE_URL = "https://YOUR_APPSAIL_URL.catalyst.zohocloud.com"
python scripts/smoke_test.py
```

---

## Local Development (No Catalyst Required)

```powershell
# Backend
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm run dev
```

Access at: `http://localhost:5173`
