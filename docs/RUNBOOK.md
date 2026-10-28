# PLUTO vProctor: Operational Runbook

This runbook provides actionable procedures for deploying, operating, diagnosing, and maintaining the PLUTO vProctor platform.

---

## 1. Quick Start Operations

### Local Development (Windows)
Run the root launcher:
```cmd
run_dev.bat
```
This automatically starts:
- FastAPI Backend on `http://127.0.0.1:8000` (Swagger UI at `/docs`)
- Vite React Frontend on `http://localhost:5173`

### Production Docker Compose Stack
```bash
# Start all 5 services (backend, worker, postgres, redis, frontend)
docker compose up -d --build

# Check status of containers
docker compose ps

# View unified structured logs
docker compose logs -f backend worker
```

---

## 2. Diagnosing a Bad Recording

If a candidate reports inaccurate transcription, failed video analysis, or broken timestamps, use the diagnostic CLI:

```bash
backend\.venv\Scripts\python.exe backend/scripts/diagnose_recording.py storage/recordings/<session_id>_interview.webm
```

### Output Produced:
1. **Container & Timestamp Integrity (ffprobe):**
   - Validates if WebM duration is readable.
   - Detects if `fflags +genpts` remuxing is required.
2. **Audio Statistics:**
   - RMS Level, peak clipping, silence ratio, noise floor.
3. **Raw Word-Level ASR Traces:**
   - Displays per-word timestamps, confidence scores, and `no_speech_prob`.
4. **Disfluency Events:**
   - Pinpoints acoustic filled-pauses ("umm", "uh"), pauses, and WPM pace.
5. **Gaze & Pose Traces:**
   - Generates CSV trace and PNG plot showing yaw, pitch, roll, and eye contact over time.

---

## 3. Database Migrations (Alembic)

The platform supports both SQLite (development) and PostgreSQL (production).

```bash
# Check current migration revision
backend\.venv\Scripts\python.exe -m alembic current

# Generate new migration after editing models.py
backend\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_changes"

# Upgrade database to latest revision
backend\.venv\Scripts\python.exe -m alembic upgrade head

# Rollback one revision
backend\.venv\Scripts\python.exe -m alembic downgrade -1
```

---

## 4. API Key Rotation (Zero-Downtime)

PLUTO vProctor supports runtime provider detection without application downtime:

1. **Deepgram:**
   - Generate a new key in Deepgram Console.
   - Update `.env`: `DEEPGRAM_API_KEY=your_new_key`
   - Reload API server or restart container: `docker compose restart backend worker`
2. **AssemblyAI:**
   - Update `.env`: `ASSEMBLYAI_API_KEY=your_new_key`
3. **Zero-Network Fallback:**
   - If keys are omitted or credit runs out, the `ASRProvider` factory automatically falls back to local `faster_whisper` (int8 on CPU) with zero errors.

---

## 5. Health & Observability Endpoints

- **Liveness Health Check:** `GET /api/health`
- **Readiness Dependency Probe:** `GET /api/ready`
- **Queue Depth & Operational Metrics:** `GET /api/analysis/jobs/stats`
- **Correlated Request Tracking:** Every response includes `X-Request-ID` and `X-Response-Time-MS` headers.

