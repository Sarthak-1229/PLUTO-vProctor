# PLUTO vProctor 🛡️

> **Production-Ready Multimodal AI Video Interview & Proctoring Platform**  
> High-precision eye contact tracking, disfluency detection, deterministic monotonic scoring, and traceable deduction timeline reports. Runs on consumer hardware (Windows, 6 GB VRAM) and cloud Docker stacks.

---

## 🌟 The 9 Core Capabilities

1. **Role & Company Selection:** Choose from 50+ roles with instant Trie prefix autocomplete.
2. **Resume Parsing & Skill Scoring:** Parses PDF/DOCX resumes, detects skills and experience, and calculates screening fit.
3. **Screening Assessment with "Proceed Anyway" Override:** Transparent gap analysis with candidate override capabilities.
4. **Time-Bounded Diversified Questions:** 0/1 Knapsack duration budgeting and MMR diversification from 1,799 verified technical Q&A pairs.
5. **AI Interviewer with TTS Prompter & Audio Waveform:** Spoken questions with real-time text captions, listening state, and distance guides.
6. **Continuous Eye Contact Monitoring:** Directional look-away detection (`LOOK_DOWN`, `LOOK_SIDE`, `LOOK_UP`) at 15+ FPS with One-Euro adaptive filtering.
7. **Parallel Multimodal Processing:** Concurrent video frame mesh and audio track analysis scheduled via an asynchronous worker queue.
8. **Disfluency & Hesitation Engine:** Detects acoustic filled-pauses ("umm", "uh"), hesitation phrases, speech pauses (>1.5s), and speaking pace (WPM).
9. **Traceable Timeline Report & Video Scrubber:** Complete score reconstruction where every point penalty links to an exact second in the interview video recording.

---

## 🏗️ Architecture & Technology Stack

- **Backend:** FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic migrations, SQLite / PostgreSQL 16.
- **Worker & Queue:** Asynchronous `JobQueue` with GPU mutual-exclusion lock, retries, and Redis 7 broker support.
- **Speech-to-Text (ASR):** Pluggable `ASRProvider` interface auto-detecting Deepgram, AssemblyAI, and local Faster-Whisper (CPU int8).
- **Vision Proctoring:** Google MediaPipe Tasks Vision (`face_landmarker.task`, 478 landmarks, iris mesh 468/473, 3D Euler head pose).
- **Frontend:** React 19, Vite 8, Tailwind CSS 4, Lucide React, MediaPipe WebAssembly vision bundle.
- **Algorithms:** 15 hand-implemented algorithms (Trie, Knapsack, MMR, BM25, MinHash, Levenshtein, One-Euro Filter, Interval Merge).

---

## 🚀 Quick Start

### 1. Local Development (One-Click)
```cmd
run_dev.bat
```
- **Backend API:** `http://127.0.0.1:8000` (Swagger UI: `http://127.0.0.1:8000/docs`)
- **Frontend Web:** `http://localhost:5173`

### 2. Docker Compose Deployment
```bash
# Start all 5 services (backend, worker, postgres, redis, frontend)
docker compose up -d --build

# Verify container health
docker compose ps
```

### 3. Running Test Suites & Quality Gates
```bash
# 1. Backend Test Suite (118+ tests)
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# 2. Ground-Truth Fixture Evaluation Gate
backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check

# 3. Frontend FSM Unit Tests
node --test frontend/tests/test_interview_fsm.js

# 4. Frontend Production Build
npm --prefix frontend run build
```

---

## 📊 Evaluation & Diagnostic Tooling

### Diagnostic CLI
Inspect any candidate recording for container errors, noise floor, raw ASR word confidence, fillers, and gaze plots:
```bash
backend\.venv\Scripts\python.exe backend/scripts/diagnose_recording.py storage/recordings/<session_id>_interview.webm
```

### Ground-Truth Recording Studio
Open your browser to:
👉 **`http://localhost:5173/dev/record-fixture`**  
Record custom fixtures and tag hotkeys in real time (`F` = Filler word, `L` = Look-away start/stop, `P` = Deliberate pause).

---

## 📚 Technical Documentation

- **[Architecture & Engine Design](docs/ARCHITECTURE.md)**
- **[Operational Runbook & Key Rotation](docs/RUNBOOK.md)**
- **[Candidate Privacy & Data Retention](docs/PRIVACY.md)**
- **[AI Ethics & Fairness Charter](docs/FAIRNESS.md)**
- **[Scoring Engine & Monotonic Grading](docs/SCORING.md)**
- **[Gaze Tracking Benchmarks](docs/GAZE_BENCHMARK.md)**
- **[ASR & Disfluency Benchmarks](docs/ASR_BENCHMARK.md)**
