# PLUTO vProctor — Deployment Readiness Assessment

> Generated: 2026-11-17  
> Assessor: Antigravity engineering agent  
> Verdict: **READY FOR ZOHO DEVELOPMENT DEPLOYMENT** *(owner configuration required — see checklist)*

---

## 1. Summary Verdict

| Mode | Status | Notes |
|---|---|---|
| **Local / Offline** | ✅ FULLY FUNCTIONAL | All features work. Run `uvicorn backend.app.main:app` |
| **Zoho Catalyst (Staged Demo)** | ✅ READY FOR DEPLOYMENT | Frontend + API + auth + questions + screening. Limitations documented below. |
| **Production (SaaS)** | 🚫 NOT RECOMMENDED | SQLite ephemerality, no Postgres, WebSocket scale-down unknown |

---

## 2. Local Mode — Feature Matrix

| Feature | Status | Notes |
|---|---|---|
| Candidate self-practice interviews | ✅ | Full flow: resume → questions → video → report |
| Hosted rooms (admin creates room, candidate joins) | ✅ | WebSocket, real-time proctoring |
| Resume upload and PDF/DOCX/TXT parsing | ✅ | Lazy-loaded, cold ~2.7s, warm ~0.05s |
| Resume screening (ML classification) | ✅ | LogisticRegression model, lazy-loaded |
| AI question generation (Ollama qwen2.5:3b) | ✅ | Requires Ollama running locally |
| ASR / speech-to-text (Whisper) | ✅ | CPU inference, requires whisper model |
| Video / gaze analysis (MediaPipe + OpenCV) | ✅ | Lazy-loaded, cold ~1.3s, warm ~0.02s |
| Scoring and report PDF generation | ✅ | ReportLab, lazy-loaded |
| Admin RBAC (admin/candidate/interviewer roles) | ✅ | JWT, role-scoped routes |
| Question bank (1,799 questions) | ✅ | 11 domains, loaded at startup |
| Session history and playback | ✅ | 16 sessions in pluto.db |

---

## 3. Hosted Mode (Zoho Catalyst AppSail) — Feature Matrix

| Feature | Hosted Status | Reason |
|---|---|---|
| React frontend (SPA) | ✅ SUPPORTED | Web Client Hosting, static |
| User authentication (JWT) | ✅ SUPPORTED | AppSail backend |
| Job management | ✅ SUPPORTED | AppSail backend |
| Question bank (1,799 questions) | ✅ SUPPORTED | Loaded from JSON files at startup |
| Resume upload + text extraction | ✅ SUPPORTED | PDF/DOCX/TXT, lazy |
| Algorithmic resume screening | ✅ SUPPORTED | No ML model needed |
| Hosted interview rooms | ✅ SUPPORTED | WebSocket (see risk below) |
| Real-time proctoring (gaze/pose) | ✅ SUPPORTED | Client-side MediaPipe only |
| Scoring and report generation | ✅ SUPPORTED | Algorithmic scoring |
| AI question generation (Ollama) | ⚠️ DEGRADED | No GPU on AppSail; falls back to algorithmic question selection |
| ML resume classification (joblib) | ⚠️ DEGRADED | No persistent model storage; falls back to algorithmic fit score |
| Whisper ASR (server-side) | ❌ NOT AVAILABLE | No GPU; use browser Web Speech API |
| Session data persistence across restarts | ⚠️ RISK | SQLite on ephemeral filesystem — data lost on scale-down |

---

## 4. Known Risks and Limitations

### R1 — SQLite Ephemerality (HIGH for persistent data, LOW for demo)
AppSail's filesystem is **ephemeral**. When the instance scales down (after ~5 minutes of inactivity), `pluto.db` is wiped.  
**Mitigation for demo:** This is acceptable for a college project demonstration. Seed data with the question bank; session data is demo-only.  
**Mitigation for persistence:** Use an external Postgres instance or implement the Catalyst Data Store adapter.

### R2 — WebSocket Scale-Down (UNKNOWN)
Official Catalyst documentation does not specify whether an active WebSocket connection prevents the 5-minute idle scale-down. If scale-down fires mid-interview, the room will disconnect.  
**Mitigation:** Implement client-side reconnection. The frontend WebSocket handler already reconnects on drop.

### R3 — Python 3.10 vs 3.12 Stack
`catalyst.json` now specifies `python_3_12`. **Verify** that Catalyst AppSail actually supports Python 3.12 in your project tier. If not, downgrade the stack to `python_3_10` and test locally with Python 3.10.

### R4 — AppSail 30-Second Request Timeout
Long AI operations (Whisper, Ollama inference) will be cut off at 30 seconds.  
**Mitigation:** AI features are disabled in hosted mode. Algorithmic fallback completes in <1s.

### R5 — Zoho Wallet Credit Eligibility
The Zoho Store wallet balance has **not been confirmed** as applicable to Catalyst billing. Treat available credit as zero until verified in the Catalyst billing console.

### R6 — Benchmark Rows in pluto.db
Two sessions (`sess_2f114a5dddec`, `sess_dbc49fd437a2`) were inserted by a benchmarking script. They are preserved per the data-preservation constraint. They will not appear in a fresh deployment.

---

## 5. Startup Performance (Measured 2026-11-17)

| Metric | Before Optimization | After Optimization | Requirement |
|---|---|---|---|
| Module import time | 4.06s | 2.01s | — |
| `main.py` import time | 4.12s | 1.75s | — |
| Port-binding (HTTP 200) | ~10.97s | **3.53s** | AppSail 10s limit |
| Startup RSS | 224.93 MB | 102.14 MB | AppSail 2048 MB |
| Peak startup RSS | 335.70 MB | 162.80 MB | AppSail 2048 MB |
| First resume request (cold) | — | 2.73s | — |
| First video analysis (cold) | — | 1.28s | — |

AppSail requires port binding within **10 seconds**. Current startup at **3.53s** provides a 6.47s safety buffer.

---

## 6. Test Results (2026-11-17)

| Suite | Passed | Failed | Skipped |
|---|---|---|---|
| Backend (pytest) | 215 | 0 | 1 |
| Frontend (vitest) | 21 | 0 | 0 |

Skipped test: `test_alembic_upgrade_live_postgresql` — requires `TEST_POSTGRES_URL` env var (intentional).

---

## 7. Database State

| Metric | Value |
|---|---|
| Total sessions | 16 |
| Original user sessions (Sarthak Bhosale) | 14 |
| Benchmark fixture sessions (Alex Vance) | 2 |
| Total questions | 1,799 |
| Integrity check | PASS (`ok`) |
| Foreign key check | PASS (0 errors) |

---

## 8. Security Checklist

- [x] No hardcoded secrets in source code
- [x] `SECRET_KEY` defaults to a generated ephemeral value with startup warning if blank
- [x] `.env` files excluded from `.gitignore`
- [x] JWT token verification on all protected routes
- [x] CORS origins configurable (not wildcarded in production mode)
- [x] `DEBUG=false` enforced in staging/production environment
- [x] Auth validation rejects unsafe production configurations at startup
- [ ] `SECRET_KEY` must be set by owner before deployment (see checklist)
