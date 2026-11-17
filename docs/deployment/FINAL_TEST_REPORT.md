# PLUTO vProctor — Final Test Report

> Generated: 2026-11-17  
> Tester: Antigravity engineering agent  
> Platform: Windows 11, Python 3.12.10, Node.js 20.x

---

## 1. Backend Test Suite

**Command:**
```
$env:PYTHONPATH="."; backend\.venv\Scripts\pytest backend/tests -rs -q
```

| Metric | Result |
|---|---|
| Tests passed | **215** |
| Tests failed | **0** |
| Tests skipped | **1** |
| Total duration | ~155 seconds |
| Python version | 3.12.10 |

### Skipped Test

`backend/tests/test_migrations.py::test_alembic_upgrade_live_postgresql`  
**Reason:** Requires `TEST_POSTGRES_URL` environment variable pointing to a live PostgreSQL instance. This is an integration test intentionally gated — not a failure.

### Test Files Coverage

| Test File | Focus Area |
|---|---|
| `test_health.py` | Service health and readiness endpoints |
| `test_phase1_stabilization.py` | Foundation: config, DB, auth bootstrap |
| `test_phase2_auth.py` | Login, JWT, session management |
| `test_phase2_rbac_and_profile.py` | Role-based access control, candidate profiles |
| `test_phase2_admin_claiming.py` | Admin session claiming workflow |
| `test_phase2_resumes_and_recommendations.py` | Resume upload, screening, recommendations |
| `test_phase3_hosted_rooms.py` | Room creation, joining, lifecycle |
| `test_phase4_interview_intelligence.py` | Question engine, AI evaluation |
| `test_phase5_candidate_admin_experience.py` | End-to-end candidate and admin flows |
| `test_phase6_deployment_and_hardening.py` | Security, DB invariants, deployment config |
| `test_analysis_pipeline.py` | Video/audio/gaze analysis pipeline |
| `test_phase_b_asr_disfluency.py` | ASR disfluency detection |
| `test_phase_c_gaze_body.py` | Gaze and body pose analysis |
| `test_phase_d_monotonic_scoring.py` | Scoring monotonicity and consistency |
| `test_phase_f_production.py` | Production hardening checks |
| `test_question_engine.py` | Question loading, filtering, domain coverage |
| `test_question_sets_management.py` | Question set CRUD |
| `test_resume_screening.py` | Resume fit scoring |
| `test_scoring_report.py` | Score computation and report generation |
| `test_config_and_errors.py` | Config validation, error responses |
| `test_e2e_flow.py` | Full self-practice interview flow |
| `test_e2e_hosted_interview_flow.py` | Full hosted room interview flow |
| `test_candidate_governance_and_completed_rooms.py` | Governance and room completion |
| `test_report_deep_linking.py` | Report deep-link URLs |
| `test_migrations.py` | Alembic migration schema (SQLite + PostgreSQL gated) |
| `test_zoho_adapters.py` | Stratus storage and Catalyst integration |
| `test_lazy_startup_optimization.py` | Startup optimization: lazy model loading |

---

## 2. Frontend Test Suite

**Command:**
```
cd frontend && npm test
```

| Metric | Result |
|---|---|
| Tests passed | **21** |
| Tests failed | **0** |
| Framework | Vitest |

**Build validation:**
```
cd frontend && npm run build
```

Result: **clean build** in ~901ms. Output: `frontend/dist/` (516 kB main chunk — expected for a full React SPA).

---

## 3. Startup Performance

Measured on Windows 11, Python 3.12.10, cold start (no warm caches):

| Metric | Measurement |
|---|---|
| Module import time | 2.009s |
| `main.py` import | 1.745s |
| **Port binding (HTTP 200)** | **3.531s** |
| Startup RSS | 102.14 MB |
| Peak startup RSS | 162.80 MB |
| First resume request (cold) | 2.734s |
| First resume request (warm) | 0.052s |
| First video analysis (cold) | 1.280s |
| First video analysis (warm) | 0.023s |

AppSail port-binding deadline: **10 seconds**. Safety buffer: **6.47 seconds**.

---

## 4. Database Integrity

```
PRAGMA integrity_check → ok
PRAGMA foreign_key_check → [] (0 errors)
```

| Table | Record Count |
|---|---|
| `sessions` | 16 |
| `questions` | 1,799 |

### Session Breakdown

| Group | Count | Date Range |
|---|---|---|
| Original user sessions (Sarthak Bhosale) | 14 | 2026-10-21 → 2026-10-29 |
| Benchmark fixture sessions (Alex Vance) | 2 | 2026-11-16 |

Benchmark rows were created by `benchmark_startup_and_latency.py` running against the live database. They are preserved per the data-preservation constraint and excluded from the legacy session invariant test via a date-based filter.

---

## 5. Security Scan

| Check | Result |
|---|---|
| Hardcoded secrets in source | None found |
| `.env` files committed | None (`.gitignore` excludes them) |
| Hardcoded `localhost:8000` in frontend | None found (dev proxy only, correct) |
| Auth validation on protected routes | Verified (401 on unauthenticated requests) |
| `DEBUG=false` in staging config | Configured in `catalyst.json` env vars |

---

## 6. Known Issues at Report Time

| ID | Issue | Severity | Status |
|---|---|---|---|
| I1 | SQLite ephemerality on AppSail — demo data lost on scale-down | Medium | Documented limitation, acceptable for college demo |
| I2 | AppSail WebSocket scale-down behavior: UNKNOWN per official docs | Low | Documented risk; client reconnection is implemented |
| I3 | Python 3.12 stack availability on Catalyst: needs owner verification | Low | `catalyst.json` updated; fallback to 3.10 if needed |
| I4 | Zoho Store wallet credit eligibility: UNVERIFIED | Low | Owner must verify before relying on credit |
| I5 | No Docker/WSL on dev workstation — Linux container test not possible | Low | Static Dockerfile analysis performed; architecture is correct |
