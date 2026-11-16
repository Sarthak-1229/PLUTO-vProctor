# PLUTO vProctor 🛡️

> **Production-Ready Multimodal AI Video Interview & Proctoring Platform**  
> Automated self-practice simulations and live recruiter-hosted interview rooms with real-time gaze tracking, posture stability monitoring, disfluency acoustic analysis, deterministic rubric scoring, and tamper-evident deduction timeline dossiers.

---

## Table of Contents
1. [Project Overview & Purpose](#1-project-overview--purpose)
2. [Core Capabilities](#2-core-capabilities)
3. [Key Features for Candidates](#3-key-features-for-candidates)
4. [Key Features for Administrators & Recruiters](#4-key-features-for-administrators--recruiters)
5. [Dual-Mode Interview System](#5-dual-mode-interview-system)
6. [Technology Stack](#6-technology-stack)
7. [System Architecture Overview](#7-system-architecture-overview)
8. [Prerequisites & System Requirements](#8-prerequisites--system-requirements)
9. [Windows Local Installation](#9-windows-local-installation)
10. [Environment Configuration (`.env`)](#10-environment-configuration-env)
11. [Database Initialization & Catalog Verification](#11-database-initialization--catalog-verification)
12. [Local AI Model Setup (Ollama & Faster-Whisper)](#12-local-ai-model-setup-ollama--faster-whisper)
13. [Starting the Application](#13-starting-the-application)
14. [Accessing the Candidate & Admin Portals](#14-accessing-the-candidate--admin-portals)
15. [Running Automated Verification Suites](#15-running-automated-verification-suites)
16. [Project Directory Layout](#16-project-directory-layout)
17. [Documentation Index](#17-documentation-index)
18. [Implementation Status & Known Limitations](#18-implementation-status--known-limitations)

---

## 1. Project Overview & Purpose

**PLUTO vProctor** (*Personalized Learning & Unified Test Operations — Virtual Proctor*) is a full-stack, multimodal AI evaluation platform designed to solve two core challenges in remote technical recruiting:
1. **Empowering Candidates:** Providing realistic, automated mock interviews with instant, explainable feedback on technical depth, communication clarity, and camera presence without requiring expensive human interviewers.
2. **Empowering Organizations:** Providing recruiters and examiners with a secure, structured, proctored live room environment featuring synchronized questions, dual-stream WebRTC audio/video, real-time proctoring telemetry alerts, and audit-grade evaluation dossiers.

The platform is designed with a **privacy-first, local-inference architecture**: computer vision, speech transcription, and LLM rubric scoring execute on the local host machine, ensuring candidate biometric data and recordings never leak to third-party public clouds.

---

## 2. Core Capabilities

- **Multimodal Video Proctoring:** Google MediaPipe FaceMesh (478 landmarks, iris mesh 468/473, 3D Euler head pose estimation) with One-Euro adaptive filtering to detect directional gaze diversions, extreme pitch/yaw tilts, and presence consistency at 15+ FPS.
- **Acoustic Disfluency Analysis:** Local Faster-Whisper transcription coupled with custom disfluency detection flagging filled pauses (*"um"*, *"uh"*), phrase hesitations, long pauses ($>3.5\text{s}$), and speech pace (WPM).
- **Deterministic 4-Bucket Scoring:** Explainable evaluation across **Technical Depth (35%)**, **Communication (25%)**, **Proctoring Integrity (25%)**, and **Resume Relevance (15%)**.
- **Monotonic Deduction Timeline:** Every penalty links to an exact millisecond timestamp, rule code, and duration, synchronized with a clickable video scrubber.
- **Algorithmic Assessment Optimization:** 15 custom algorithms including Trie prefix autocomplete, 0/1 Knapsack duration budgeting, Maximal Marginal Relevance (MMR) question diversification, BM25 keyword relevance, and MinHash near-duplicate filtering over a curated library of 1,799 verified technical questions.
- **Enterprise Security & Governance:** Argon2id password hashing, rotating JWT refresh token families, double-submit CSRF tokens, strict RBAC (`candidate`, `admin`, `super_admin`), and immutable audit logging.

---

## 3. Key Features for Candidates

- **Authentication & Self-Service:** Registration, secure login, password reset flow, and session persistence.
- **Candidate Profile & Skill Management:** Detailed professional profile management with manual skill chip editing, portfolio links, and target career roles.
- **Multi-Resume Library:** Upload and store multiple resumes (PDF, DOCX, TXT) with magic-byte binary header validation (up to 5 MB). Set primary active resume, review parsed text, and launch practice sessions directly.
- **Universal Pre-Interview Job Recommendations:** Instant match score (0–100%) and skills gap analysis (matching skills vs missing skills) against technical jobs without taking an interview first.
- **7-Step Self-Practice Wizard:** Interactive workflow: Role Selection $\to$ Screening Fit & Consent $\to$ Hardware Check $\to$ 5-Second Center Gaze Calibration $\to$ Mock Interview with TTS Audio Prompter $\to$ Multimodal Processing $\to$ Evaluation Dossier.
- **Dynamic Learning Roadmaps:** Personalized readiness grade, historical score growth curves, domain competency breakdowns, and targeted practice milestone drills.
- **Report Deep-Linking & PDF Export:** Permanent direct access to `/report/:sessionId`, printable layout, and official PDF dossier download.
- **GDPR Privacy & Erasure:** One-click permanent erasure of session recordings and candidate profile records.

---

## 4. Key Features for Administrators & Recruiters

- **Dedicated Admin Portal (`/admin/login`):** Portal isolation and server-side RBAC enforcement.
- **Candidate Account Governance:** Interactive accounts console with live text search, role filtering, candidate profile inspection, and interview history drawer.
- **Super-Admin Role Management Safeguards:** Role mutation modal requiring a mandatory justification reason ($\ge 5$ characters), self-demotion prevention, and automated protection locks preventing lockout of the last active administrator or super-administrator.
- **Question-Set Lifecycle Management:** Interactive question builder, JSON editor, versioned editing, 409 conflict-safe deletion (blocks deletion of sets assigned to ongoing rooms; safely nullifies FK on completed rooms), and JSON file import with preview modal.
- **Room Scheduling & Candidate Invitations:** Configuring proctoring presets (Standard, Strict, Lenient), duration limits, candidate assignments, generating 9-character join codes and 256-bit URL invite tokens.
- **Live Interview Orchestration:** Host control bar (Advance Question, Skip Question, Pause with reason, Resume, and End Interview) with real-time proctoring telemetry alerts feed.
- **Completed Room Auditing & Recordings:** Conclusion banners, report deep-links, PDF dossier export, and inline modal video player streaming `/api/interview/:sessionId/video` with HTTP 206 range-seeking support.
- **Platform Analytics & Audit Trails:** Macro-level hiring funnels, score distributions, and role-change audit records.

---

## 5. Dual-Mode Interview System

PLUTO vProctor operates in two distinct operational modes:

| Dimension | Offline Self-Practice Mode | Administrator-Hosted Recruiter Mode |
|---|---|---|
| **Target User** | Autonomous candidates and learners | Recruiter / Interviewer evaluating a candidate |
| **Authentication Requirement** | Optional (`AUTH_ENABLED=False` out-of-the-box) | Required (`AUTH_ENABLED=True`) |
| **Media Transport** | Local `MediaRecorder` client recording | Peer-to-Peer WebRTC dual-stream audio/video |
| **Question Flow** | AI prompter with client-side speech timers | Host-controlled question advancement and pausing |
| **Question Source** | Knapsack MMR dynamic selection or assigned set | Custom Admin Question Set or system selection |
| **Result Delivery** | Immediate candidate report dossier | Shared evaluation report and admin audit record |

---

## 6. Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.12), Starlette, Pydantic v2, Pydantic-Settings
- **Database ORM:** SQLAlchemy 2.0 with SQLite (local development WAL mode) and Psycopg 3 PostgreSQL compatibility
- **Authentication:** Passlib (Argon2id), PyJWT, ItsDangerous
- **Speech Processing (ASR):** Faster-Whisper (CTranslate2, int8 quantized CPU execution)
- **Computer Vision:** MediaPipe Tasks Vision (`face_landmarker.task`, 478 landmarks, 3D Euler head pose)
- **NLP & Search:** SentenceTransformers (`all-MiniLM-L6-v2`), BM25, RAKE keyword extraction, RapidFuzz
- **Local LLM Engine:** Ollama (`qwen2.5:3b` / `llama3.2`) with deterministic algorithmic rubric fallback

### Frontend
- **Framework:** React 18, Vite 8
- **Styling:** Tailwind CSS 4, Lucide React icons (Neo-brutalist UI theme)
- **Real-Time Client:** Native WebRTC API, WebSocket API, MediaRecorder API
- **Computer Vision (Client):** MediaPipe Vision WebAssembly bundle (`@mediapipe/tasks-vision`)

---

## 7. System Architecture Overview

```mermaid
flowchart TD
    subgraph Client["Frontend Client (React 18 + Vite)"]
        UI_Practice["Self-Practice Wizard"]
        UI_Hosted["Live Hosted Room (WebRTC)"]
        UI_Admin["Admin Console & Room Manager"]
        UI_Candidate["Candidate Profile, Resumes & Roadmap"]
        WASM_Vision["MediaPipe WASM (Gaze & FaceMesh)"]
    end

    subgraph Gateway["FastAPI API Gateway (:8000)"]
        Middleware["Request-ID Correlation & Security Headers"]
        AuthService["Auth & RBAC Service (Argon2id + JWT + CSRF)"]
        RoomManager["Realtime WebSocket Room Manager"]
        JobQueue["Async Background Processing Queue"]
    end

    subgraph AI_Engines["Local AI & Telemetry Pipelines"]
        WhisperEngine["Faster-Whisper (Speech-to-Text & Disfluency)"]
        VisionEngine["Video Pipeline (Gaze Divergence & Head Pose)"]
        ScoringEngine["Monotonic Rubric Scoring Engine"]
        OllamaLocal["Local Ollama Daemon (:11434)"]
    end

    subgraph Persistence["Storage & Data Layer"]
        DB[("SQLite Database (pluto.db)")]
        MediaStorage["Local File Storage (storage/recordings, resumes)"]
    end

    Client <-->|REST API + HTTP/1.1| Gateway
    Client <-->|WebRTC Signaling (ws://)| RoomManager
    Client <-.->|WebRTC P2P Media Stream| Client
    Gateway --> AuthService
    Gateway --> RoomManager
    Gateway --> JobQueue
    JobQueue --> WhisperEngine
    JobQueue --> VisionEngine
    WhisperEngine --> ScoringEngine
    VisionEngine --> ScoringEngine
    OllamaLocal -.-> ScoringEngine
    Gateway --> DB
    Gateway --> MediaStorage
    ScoringEngine --> DB
```

---

## 8. Prerequisites & System Requirements

Ensure the host machine satisfies the following hardware and software requirements:

- **Operating System:** Windows 10/11 64-bit (macOS 12+ and Ubuntu 20.04+ also supported).
- **Python:** Python 3.11 or 3.12 64-bit.
- **Node.js:** Node.js 18.0.0+ and npm 9.0.0+.
- **Web Browser:** Google Chrome 110+ or Chromium Edge 110+.
- **Hardware:**
  - Webcam (720p or 1080p).
  - Microphone.
  - Minimum 4 GB RAM (8 GB recommended for local Faster-Whisper + Ollama).

---

## 9. Windows Local Installation

### Step 1: Clone or Navigate to the Repository
```powershell
cd D:\_TY\MDM\PLUTO-vProctor
```

### Step 2: Set Up Python Virtual Environment
```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### Step 3: Install Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

---

## 10. Environment Configuration (`.env`)

Create or update the `.env` file in the project root:

```ini
# Application Mode
ENVIRONMENT=development
DEBUG=True

# Network Binding
API_HOST=127.0.0.1
API_PORT=8000

# Feature Flags
AUTH_ENABLED=True
HOSTED_ROOMS_ENABLED=True
LIVE_MEDIA_ENABLED=True
MEDIA_TRANSPORT_MODE=p2p

# Local Database & Storage
DATABASE_URL=sqlite:///./backend/app/pluto.db

# Cryptographic Keys (At least 32 characters in development)
SECRET_KEY=dev-secret-key-pluto-vproctor-local-testing-only-minimum-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Local AI Engine
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:3b
WHISPER_MODEL_SIZE=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# WebRTC STUN Servers
STUN_SERVERS=["stun:stun.l.google.com:19302"]
```

---

## 11. Database Initialization & Catalog Verification

PLUTO vProctor stores its data in `backend/app/pluto.db`.

### Initialize Tables (if not present)
```powershell
backend\.venv\Scripts\python.exe -c "from backend.app.db.database import Base, engine; from backend.app.db.models import *; Base.metadata.create_all(bind=engine); print('Database schema ready.')"
```

### Verify Catalog Invariants
Confirm that all 1,799 questions and 14 historical legacy sessions are intact:
```powershell
backend\.venv\Scripts\python.exe -c "from backend.app.db.database import SessionLocal; from backend.app.db.models import User, Job, InterviewSession, Question; db=SessionLocal(); print(f'Users: {db.query(User).count()} | Jobs: {db.query(Job).count()} | Sessions: {db.query(InterviewSession).count()} | Questions: {db.query(Question).count()}'); db.close()"
```

---

## 12. Local AI Model Setup (Ollama & Faster-Whisper)

### 12.1 Ollama (Optional but Recommended)
Ollama powers the generative rubric evaluation. If Ollama is offline, the system automatically falls back to deterministic algorithmic rubric scoring.
1. Download and install Ollama from [ollama.ai](https://ollama.ai).
2. Start the daemon:
   ```powershell
   ollama serve
   ```
3. Pull the recommended evaluation model:
   ```powershell
   ollama pull qwen2.5:3b
   ```

### 12.2 Faster-Whisper
Faster-Whisper runs locally on CPU using int8 quantization. The model (`base.en`, $\approx 140\text{ MB}$) downloads automatically from HuggingFace on the first interview run.

---

## 13. Starting the Application

### Method A: One-Click Startup (Recommended)
Run the automated Windows batch launcher from the project root:
```cmd
run_dev.bat
```
This spawns:
- **FastAPI Backend:** Running on `http://127.0.0.1:8000` with hot-reloading.
- **React Frontend:** Running on `http://localhost:5173`.
- Automatically opens your default web browser to `http://localhost:5173`.

### Method B: Manual Dual-Terminal Startup
#### Terminal 1 (Backend):
```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
#### Terminal 2 (Frontend):
```powershell
cd frontend
npm run dev
```

---

## 14. Accessing the Candidate & Admin Portals

| Portal | Local URL | Role Required | Default Capabilities |
|---|---|---|---|
| **Candidate Portal** | `http://localhost:5173/login` | `candidate` | Practice interviews, resume library, recommendations, learning roadmaps, join rooms. |
| **Admin Portal** | `http://localhost:5173/admin/login` | `admin`, `super_admin` | Room scheduler, live room controls, question sets, candidate governance, session audit. |
| **Swagger API Docs** | `http://127.0.0.1:8000/docs` | Public / Dev | Interactive OpenAPI documentation for all 60+ endpoints. |

---

## 15. Running Automated Verification Suites

Verify all layers of the platform with the automated test commands:

```powershell
# 1. Full Backend Pytest Regression Suite (198 passed)
$env:PYTHONPATH='.'; backend\.venv\Scripts\pytest.exe backend/tests/ -v

# 2. Batch 3 Candidate Governance Integration Tests (9 passed)
$env:PYTHONPATH='.'; backend\.venv\Scripts\pytest.exe backend/tests/test_candidate_governance_and_completed_rooms.py -v

# 3. Batch 2 Question-Set Management Integration Tests (8 passed)
$env:PYTHONPATH='.'; backend\.venv\Scripts\pytest.exe backend/tests/test_question_sets_management.py -v

# 4. Frontend Unit Test Suite (21 passed)
npm --prefix frontend test

# 5. Frontend Linter (0 errors)
npm --prefix frontend run lint

# 6. Frontend Production Build
npm --prefix frontend run build
```

---

## 16. Project Directory Layout

```text
D:\_TY\MDM\PLUTO-vProctor\
├── backend/
│   ├── .venv/                      # Pinned Python 3.12 virtual environment
│   ├── app/
│   │   ├── config.py               # Central settings, thresholds, and paths
│   │   ├── main.py                 # FastAPI application, middleware, lifecycle
│   │   ├── pluto.db                # Primary SQLite database
│   │   ├── db/                     # 22 SQLAlchemy models & database factory
│   │   ├── routers/                # 14 modular REST & WebSocket route handlers
│   │   └── services/               # Multimodal pipelines, FSM, and AI services
│   ├── requirements.txt            # Python dependencies
│   └── tests/                      # 199 backend integration and algorithmic tests
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Client SPA route coordinator & state machine
│   │   ├── components/             # React UI components (Neo-brutalist theme)
│   │   └── utils/                  # AuthClient, InterviewFSM, questionSetUtils
│   ├── tests/                      # Node.js frontend unit tests
│   ├── package.json                # Frontend npm configuration
│   └── vite.config.js              # Vite bundler configuration
├── storage/
│   ├── recordings/                 # Uploaded candidate WebM session videos
│   ├── resumes/                    # Stored PDF, DOCX, TXT candidate resumes
│   └── audio/                      # Temporary extracted WAV audio files
├── datasets/                       # Question catalog dataset (1,799 questions)
├── docs/                           # Comprehensive technical and user documentation
└── run_dev.bat                     # Windows one-click development startup script
```

---

## 17. Documentation Index

Detailed documentation is available in the [`docs/`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/) directory:

- **[Master Completion Tracker (`docs/MASTER_COMPLETION_TRACKER.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/MASTER_COMPLETION_TRACKER.md):** Complete phase-by-phase tracker covering Phases 0–9, Batches 1–5, and Zoho Cloud Staging.
- **[Final Product Audit (`docs/FINAL_PRODUCT_AUDIT.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_PRODUCT_AUDIT.md):** Formal release candidate verification certifying all 62 original product requirements.
- **[Final Test Execution Report (`docs/FINAL_TEST_REPORT.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_TEST_REPORT.md):** Automated test suite results: 198 pytest tests, 21 vitest tests, 0 lint errors, and 6 ML benchmark evaluations.
- **[Security Verification Report (`docs/SECURITY_VERIFICATION_REPORT.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SECURITY_VERIFICATION_REPORT.md):** Threat modeling, Argon2id dummy verify, CSRF double-submit, GDPR erasure, and 0 hardcoded secrets.
- **[Deployment Execution Report (`docs/DEPLOYMENT_EXECUTION_REPORT.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_EXECUTION_REPORT.md):** Staging deployment configuration, Zoho Catalyst package, and one-click dispatch launchers.
- **[Post-Deployment Acceptance Report (`docs/POST_DEPLOYMENT_ACCEPTANCE_REPORT.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/POST_DEPLOYMENT_ACCEPTANCE_REPORT.md):** 15-point acceptance criteria matrix certifying end-to-end user journeys.
- **[Zoho Catalyst Deployment Guide (`deploy/zoho/README.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/deploy/zoho/README.md):** Deployment runbook for Zoho Catalyst AppSail and Web Client Hosting.
- **[Documentation Index (`docs/INDEX.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/INDEX.md):** Complete master index of all project manuals, reports, and technical specifications.
- **[Candidate User Manual (`docs/CANDIDATE_USER_MANUAL.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/CANDIDATE_USER_MANUAL.md):** Comprehensive candidate guide covering registration, resumes, recommendations, self-practice, hosted rooms, scoring dossiers, and privacy.
- **[Administrator User Manual (`docs/ADMIN_USER_MANUAL.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ADMIN_USER_MANUAL.md):** Recruiter guide covering admin login, candidate governance, super-admin safeguards, question sets, room scheduling, and live controls.
- **[Troubleshooting Guide (`docs/TROUBLESHOOTING.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/TROUBLESHOOTING.md):** Diagnostic procedures organized into 6 operational categories with safe resolutions.
- **[Local Operator Runbook (`docs/LOCAL_OPERATOR_RUNBOOK.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/LOCAL_OPERATOR_RUNBOOK.md):** Operational guide for local Windows execution, health checks, backups, disaster recovery, and shutdown.
- **[System Architecture (`docs/ARCHITECTURE.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ARCHITECTURE.md):** Complete architectural specification with Mermaid flowcharts for all subsystems.
- **[API Reference (`docs/API.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/API.md):** Full specification of all 60+ REST routes and WebRTC WebSocket signaling messages.
- **[Database Schema (`docs/DATABASE_SCHEMA.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DATABASE_SCHEMA.md):** Complete 22-table reference with column definitions, constraints, and Mermaid ER diagram.
- **[Security Architecture (`docs/SECURITY.md`)](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SECURITY.md):** 14-domain security specification covering Argon2id, tokens, CSRF, RBAC, IDOR, and audit trails.

---

## 18. Implementation Status & Deployment Readiness

### Verified Capabilities
- All Core ML/CV Proctoring Pipelines (MediaPipe, iris divergence, Faster-Whisper, disfluencies).
- Full Dual-Mode Interview Experience (Offline Self-Practice & Admin-Hosted Rooms).
- Dual-browser WebRTC Peer-to-Peer media streaming (verified via Chrome CDP with 98,728 bytes / 199 RTP packets).
- Complete Candidate Auth & RBAC (Argon2id, Refresh Token rotation families, CSRF double-submit, Portal separation).
- Pre-Interview Universal Job Recommendations and Dynamic Learning Roadmaps.
- Multi-Resume Library with Magic-Byte validation.
- Database Invariants & Migrations (1,799 questions intact, 14 legacy sessions preserved).
- Report Deep-Linking & PDF Dossier export (`/report/:sessionId`).
- Full Admin Question-Set Lifecycle & Candidate Governance.
- Zoho Catalyst Cloud Adapters (QuickML Foundation Models & Stratus S3 Object Storage with multi-layer offline fallback).
- Zero-Error Deployment Validation (`scripts/validate_deployment_package.py` passes 24/24 checks).

### Operational Environments
- **Local Workstation (Offline):** 100% operational on Windows 11 with SQLite (`pluto.db`) and local Ollama (`qwen2.5:3b`).
- **Cloud Staging (Zoho Catalyst):** Configured and packaged for AppSail (FastAPI) and Web Client Hosting (Vite SPA) under an ~$80/month budget envelope (8h/day schedule), supported by external RDS PostgreSQL and Coturn in `ap-south-1`. Launchable via `scripts/deploy_zoho_catalyst.bat` or `.sh`.
- **Desktop Browser Requirement:** Desktop Google Chrome or Microsoft Edge is required for MediaPipe camera proctoring and WebRTC media streaming. Mobile devices are not supported for proctored sessions.
