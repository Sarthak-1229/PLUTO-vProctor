# PLUTO vProctor v2 — Phase 1 Implementation & Verification Report

**Date:** 2026-11-12  
**Branch:** `main` (building on commits `67c1ef4` and `aa83ff4`, plus post-review fixes in working tree)  
**Scope:** Phase 0.5 (approved cleanup execution, pytest isolation, high-priority stabilization fixes) + Phase 1 (Stabilize Foundation Tasks 1–5 + Independent Whole-Branch Review Remediation + Live PostgreSQL Integration Verification).  
**Phase Gate Status:** Complete — awaiting explicit user approval before starting Phase 2 (Authentication, RBAC, Admin Login & Legacy Claim Workflow).

---

## 1. Summary of Implemented Phase 1 Work

1. **Architecture Decision Records ([`docs/DECISIONS.md`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DECISIONS.md)):**
   - Recorded `DECISION-012` through `DECISION-016` covering:
     - Multi-user RBAC (`candidate`, `admin`, `super_admin`) and explicit admin-controlled claiming for the `14` legacy `Sarthak Bhosale` sessions (`candidate_user_id IS NULL` — no automatic name/email linking).
     - Human-hosted interview transport using browser WebRTC P2P + FastAPI WebSocket signaling + configurable STUN/TURN with an SFU extension boundary (`MediaTransportAdapter`).
     - Additive, inspector-guarded SQLite/PostgreSQL Alembic migration policy.
     - Feature-flagged rollout (`AUTH_ENABLED`, `HOSTED_ROOMS_ENABLED`, `LIVE_MEDIA_ENABLED`, `MEDIA_TRANSPORT_MODE`) and backwards-compatible API error envelope preserving top-level `"detail"`.
     - Proctoring fairness and system-health diagnostics separation.

2. **Environment Validation, Feature Flags & Runtime Safety ([`backend/app/config.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/config.py), [`.env.example`](file:///D:/_TY/MDM/PLUTO-vProctor/.env.example), [`backend/app/services/job_queue.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/services/job_queue.py)):**
   - Added v2 rollout flags defaulting safely (`AUTH_ENABLED=False`, `HOSTED_ROOMS_ENABLED=False`, `LIVE_MEDIA_ENABLED=False`, `MEDIA_TRANSPORT_MODE="p2p"`, `SFU_URL=""`), JWT/cookie settings, STUN/TURN configuration (`TURN_SERVER_URLS` CSV/JSON/list parser), port bounds (`API_PORT` `1..65535`), timeout bounds (`LLM_TIMEOUT_SECONDS` `(0, 600]`), scoring weight sum checks, `ENVIRONMENT` canonicalization/validation, and `Settings.validate_runtime_safety()` called inside `lifespan` in [`backend/app/main.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/main.py).
   - Fixed event-loop binding across sequential FastAPI `TestClient` lifespans via loop-aware `start_workers()` / `stop_workers()` in `job_queue.py`.

3. **Standardized Error Envelope & Correlation Logging ([`backend/app/core/errors.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/core/errors.py), [`backend/app/main.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/main.py)):**
   - Added `AppError`, `build_error_payload`, and `register_exception_handlers(app, cors_origins=...)` preserving top-level `"detail"` alongside `"error": {"code", "message", "request_id", "details"}` and `X-Request-ID`.
   - Replaced deprecated `@app.on_event("startup")` with `@asynccontextmanager async def lifespan(app)`.

4. **Alembic Baseline Schema, Secondary Indexes & UTC Cleanup ([`backend/alembic/env.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/env.py), [`866ba5fa0eae_initial_schema.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/versions/866ba5fa0eae_initial_schema.py), [`0002_add_core_indexes.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/versions/0002_add_core_indexes.py), [`backend/app/db/models.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/db/models.py), [`backend/app/services/report_service.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/services/report_service.py)):**
   - Replaced empty `866ba5fa0eae` migration bodies with idempotent inspector-guarded DDL (`_has_table`, `context.is_offline_mode()`).
   - Added `0002_add_core_indexes.py` introducing `ix_sessions_interview_status`, `ix_session_questions_session_id`, `ix_session_questions_order_index`, `ix_proctoring_events_session_id`, and `ix_proctoring_events_t_start`.
   - Replaced deprecated `datetime.utcnow()` with `_utcnow_naive()` (`models.py`) and `datetime.now(timezone.utc)` (`report_service.py`).

5. **CI Gates & Packaging ([`.github/workflows/ci.yml`](file:///D:/_TY/MDM/PLUTO-vProctor/.github/workflows/ci.yml), [`backend/requirements.txt`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/requirements.txt), [`frontend/package.json`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/package.json)):**
   - Added `postgres-migration-gate` (`postgres:16-alpine` service) to GitHub Actions CI, added `oxlint` and `npm --prefix frontend test` gates to `frontend-build-gate`, and added `alembic>=1.13.0` + `psycopg[binary]>=3.2.0` (paired with `sqlalchemy>=2.1.0`) to `backend/requirements.txt`.

---

## 2. Independent Code Review Findings & Resolutions

An independent read-only whole-branch review (subagent `bea0f54a`) assessed Phase 0.5 + Phase 1 as **Ready with fixes** and identified 1 Critical, 3 Important, and 2 Minor findings. All Critical, Important, and Minor findings were fixed using TDD (`RED -> GREEN`), along with two additional integration bugs caught during live PostgreSQL testing:

| Severity | Finding | Resolution & Verification |
|---|---|---|
| **Critical #1** | Unhandled `500` responses handled by Starlette `ServerErrorMiddleware` bypassed `CORSMiddleware` and `RequestIDMiddleware`, dropping `Access-Control-Allow-Origin` and security headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `X-Response-Time-MS`). | Shared `SECURITY_HEADERS` and `_build_unhandled_headers()` in [`errors.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/core/errors.py) wired into `register_exception_handlers(app, cors_origins=settings.CORS_ORIGINS)` and `RequestIDMiddleware` (`request.state.start_time`). Verified with `TestClient` + `CORSMiddleware` in [`test_config_and_errors.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/tests/test_config_and_errors.py) (`test_unhandled_exception_returns_sanitized_500_envelope`), checking both allowed and disallowed `Origin` headers. |
| **Important #1** | `alembic` (and PostgreSQL driver) missing from [`backend/requirements.txt`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/requirements.txt). | Added `alembic>=1.13.0`, `psycopg[binary]>=3.2.0`, and `sqlalchemy>=2.1.0`; simplified `.github/workflows/ci.yml` dependency steps. |
| **Important #2** | Unvalidated `ENVIRONMENT` string allowed blank or mistyped values to bypass `validate_runtime_safety()`. | Constrained `ENVIRONMENT` to `Literal["development", "test", "staging", "production"]` with `_normalize_environment` validator normalizing blank/`dev`/`prod`/`testing` and rejecting invalid typos (`config.py`). Cleaned duplicate field declarations. Tested in `test_environment_normalization_and_invalid_value_rejected`. |
| **Important #3** | Structured log formatter emitted `[Req:-]` on unhandled `500` logs (and `extra={"request_id": ...}` collided with `record_factory`, raising `KeyError: "Attempt to overwrite 'request_id' in LogRecord"`). | Introduced `contextvars.ContextVar` `request_id_ctx` in `errors.py` consumed by `record_factory` in `main.py` and temporarily bound in `RequestIDMiddleware` and `unhandled_exception_handler`. Verified in `test_unhandled_exception_returns_sanitized_500_envelope` via `caplog`. |
| **Minor #1** | `node --test frontend/tests/*.js` glob failed under shells without globbing (Windows PowerShell). | Added `"test": "node --test tests/test_interview_fsm.js tests/test_screening_threshold.js"` in [`frontend/package.json`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/package.json) and switched CI to `npm --prefix frontend test`. |
| **Minor #2** | `normalizePassThresholdPct` scaled `<= 0` negative numbers as percentages (`-5` -> `-500%`). | Guarded `passThreshold <= 0` -> `0` and clamped positive percentages to `100` in [`screeningUtils.js`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/src/utils/screeningUtils.js); covered in [`test_screening_threshold.js`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/tests/test_screening_threshold.js). |
| **Live PG Bug #1** | SQLAlchemy `2.1.5` defaults bare `postgresql://` URIs to `PGDialect_psycopg` (`psycopg` v3), so `psycopg2-binary` alone failed with `ModuleNotFoundError: No module named 'psycopg'`. | Switched `backend/requirements.txt` and `.venv` to `psycopg[binary]>=3.2.0` (`psycopg 3.3.8`), matching SQLAlchemy `2.1.5` and CI `postgresql://` URLs cleanly. |
| **Live PG Bug #2** | `backend/alembic/env.py` checked `ALEMBIC_DATABASE_URL` before explicit `config.get_main_option("sqlalchemy.url")`, causing per-test SQLite migrations in `test_migrations.py` to hit PostgreSQL whenever `ALEMBIC_DATABASE_URL` was exported in CI/test env. | Reordered precedence in [`env.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/env.py) so explicit programmatic/INI non-placeholder URL overrides `ALEMBIC_DATABASE_URL`, followed by `settings.DATABASE_URL`. Covered by `test_alembic_explicit_sqlalchemy_url_overrides_env_override`. |

---

## 3. Final Post-Fix Verification Results

All checks below executed **after** the final code edit:

1. **Backend Test Suite (Local SQLite Temp Isolation):**
   - Command: `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v`
   - Result: **`142 passed, 1 skipped, 1 warning in 67.00s`**
   - Skipped case: `backend/tests/test_migrations.py::test_alembic_upgrade_live_postgresql` (skipped locally only when `TEST_POSTGRES_URL` is unset; executed live in item 2 below).

2. **Live Temporary PostgreSQL 16.2 Integration Migration Verification:**
   - Spun up an ephemeral live `PostgreSQL 16.2 on x86_64-pc-mingw64, 64-bit` instance via `pgserver` in `%TEMP%` (`INITIAL tables: []`).
   - With `TEST_POSTGRES_URL` and `ALEMBIC_DATABASE_URL` pointing to that live instance:
     - `pytest backend/tests/test_migrations.py -v` -> **`6 passed, 0 failed, 0 skipped in 2.71s`** (`test_alembic_upgrade_live_postgresql`, `test_alembic_explicit_sqlalchemy_url_overrides_env_override`, fresh SQLite, existing `pluto.db` copy upgrade/downgrade, PG `--sql`, UTC PDF warnings).
     - `alembic current` -> `0002_add_core_indexes (head)`
     - `alembic check` -> `No new upgrade operations detected.`
     - `alembic downgrade base` -> `0002_add_core_indexes -> 866ba5fa0eae ->`
     - `alembic upgrade head` -> `-> 866ba5fa0eae -> 0002_add_core_indexes`
     - `alembic check` -> `No new upgrade operations detected.`
     - Verified all `8` tables (`alembic_version`, `companies`, `jobs`, `proctoring_events`, `questions`, `reports`, `session_questions`, `sessions`) and all `5` secondary indexes on live PostgreSQL 16.2; temp cluster torn down afterward.

3. **Frontend Lint, Unit Tests & Production Build:**
   - `npm --prefix frontend run lint` (`oxlint`): **`0 errors, 73 warnings`** (`91 ms`, `22` files).
   - `npm --prefix frontend test`: **`5 passed, 0 failed`** (`147.89 ms`).
   - `npm --prefix frontend run build`: **`1949 modules transformed, built in 1.16s`**.

4. **Proctoring Fixture CI Gate vs Phase 0 Baseline:**
   - Command: `backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check`
   - Result: **`[CI GATE PASSED] All benchmark thresholds satisfied.`**
   - Comparison on `fixture_synth_001.webm` (`15.0s`):
     - Look-away Recall: **`100.0%`** (Phase 0 baseline: `100.0%`)
     - False Alarms/min: **`4.0`** (Phase 0 baseline: `4.0`)
     - Pause Recall: **`100.0%`** (`det=1/1`; Phase 0 baseline: `100.0%`, `det=3/1`)
     - Median Time Error: **`2.57s`** (`p95=2.921s`, threshold `<= 4.0s`; Phase 0 baseline: `2.22s`, `p95=2.535s`)
     - Filler F1: **`0.0%`** (`P=0.00, R=0.00`); ASR WER: **`200.0%`** (`hyp_words=22` greedy synthetic audio decode). Reverted `docs/FIXTURE_EVALUATION.json` afterwards to avoid committing noisy non-deterministic synthetic Whisper diffs.

5. **Live SQLite Database, Storage & Backups Integrity:**
   - Live [`backend/app/pluto.db`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/pluto.db): `1,679,360` bytes, `PRAGMA integrity_check = ['ok']`, `PRAGMA foreign_key_check = []`, `alembic current = 0002_add_core_indexes (head)`, `alembic check = No new upgrade operations detected.`
   - Row counts unchanged: `sessions=14` (`sarthak_sessions=14`), `session_questions=96`, `proctoring_events=108`, `reports=5`, `questions=1,799`, `jobs=12`, `companies=6`, `alembic_version=1`.
   - All `5` Phase 1 secondary indexes verified present.
   - Live `storage/`: **`24` files** (`10` under `recordings/`, `14` under `resumes/`), **`360,036,616` bytes** — completely untouched.
   - Pre-cleanup Phase 0 backup (`backups/phase0_20261111_235506/pluto.db`): `1,679,360` bytes, SHA-256 `9953817cdabcd05f15c615ed7ffca7aee254f88337e76096c73fc6ca5e53ed3f`, `integrity=['ok']`, `foreign_key_violations=[]`, `manifest.json` present.
   - Pre-migration Phase 1 backup (`backups/phase1_pre_migration_20261112_003756/pluto.db`): `1,679,360` bytes, SHA-256 `09d772ad45ef1d0859bd1aa1bfa841a03caffca68b1987c73c4438609c005ba9`, `integrity=['ok']`, `foreign_key_violations=[]`, `sessions=14`, `alembic_version=['866ba5fa0eae']`.

6. **Offline Self-Practice Workflow Smoke Check (Isolated Temp DB + Storage):**
   - Verified end-to-end API flow on fresh migrated temp DB: `GET /health` (`200`, `development`), `GET /ready` (`200`, `ready`), `GET /api/jobs` (`12` jobs), `GET /api/interview/config/gaze` (`200`), `POST /api/resume/screen` (`200`, `fit_score=6.0`), `POST /api/interview/{sid}/start` & `GET /api/interview/{sid}` (`7` questions selected), `POST /api/interview/{sid}/question/0/answer` (`200`), `GET /api/report/{sid}` (`200`, `overall_score=55.4`), `GET /api/report/{sid}/pdf` (`200`, `2,818` bytes `%PDF`), `DELETE /api/interview/{sid}` (`200`, `deleted`).
   - Verified `backend/app/pluto.db` (`1,679,360` B) and `storage/` (`24` files) remained completely untouched afterward.

---

## 4. Changed Files Inventory (Phase 1 + Review Fixes)

- **Committed in `67c1ef4` / `aa83ff4`:** `backend/app/config.py`, `backend/app/core/__init__.py`, `backend/app/core/errors.py`, `backend/app/db/models.py`, `backend/app/main.py`, `backend/app/routers/interview.py`, `backend/app/services/job_queue.py`, `backend/app/services/question_service.py`, `backend/app/services/report_service.py`, `backend/alembic/env.py`, `backend/alembic/versions/866ba5fa0eae_initial_schema.py`, `backend/alembic/versions/0002_add_core_indexes.py`, `backend/requirements.txt`, `backend/tests/conftest.py`, `backend/tests/test_phase1_stabilization.py`, `backend/tests/test_config_and_errors.py`, `backend/tests/test_migrations.py`, `frontend/src/App.jsx`, `frontend/src/components/ScreeningStep.jsx`, `frontend/src/utils/screeningUtils.js`, `frontend/tests/test_screening_threshold.js`, `frontend/package.json`, `.env.example`, `.github/workflows/ci.yml`, `.gitignore`, `docs/DECISIONS.md`, `docs/UPGRADE_BASELINE.md`, `docs/superpowers/plans/2026-11-12-phase1-stabilize-foundation.md`.
- **Current Working-Tree Review & Live-PG Remediation Edits (on top of `aa83ff4`):**
  - [`.github/workflows/ci.yml`](file:///D:/_TY/MDM/PLUTO-vProctor/.github/workflows/ci.yml)
  - [`backend/alembic/env.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/env.py)
  - [`backend/app/core/errors.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/core/errors.py)
  - [`backend/app/main.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/main.py)
  - [`backend/requirements.txt`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/requirements.txt)
  - [`backend/tests/test_migrations.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/tests/test_migrations.py)
  - [`docs/UPGRADE_BASELINE.md`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/UPGRADE_BASELINE.md)
  - [`docs/PHASE_1_IMPLEMENTATION_REPORT.md`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_1_IMPLEMENTATION_REPORT.md) *(this report)*

---

## 5. Remaining Limitations & Migration Risks

- **GitHub Actions CI Remote Execution:** `.github/workflows/ci.yml` (`postgres-migration-gate` and updated `frontend-build-gate`) has been validated locally against PostgreSQL 16.2 (`pgserver`) and local Node/Vite tooling, but has not yet executed on GitHub Actions remote runners because commits/changes have not been pushed to `origin/main` (`gh auth status` not logged in).
- **Local Ollama Stopped:** Ollama at `http://localhost:11434` is not running on this machine, so local answer evaluation and follow-up paths exercised deterministic offline fallbacks rather than live `qwen2.5:3b` generation.
- **Unclaimed Historical Records (`14` sessions):** All `14` real `Sarthak Bhosale` sessions intentionally remain without user ownership IDs until Phase 2 implements `users`, role-based login, and the admin-controlled claim/linking workflow (`DECISION-012`).
- **Pre-existing Frontend Lint Warnings:** `73` pre-existing `oxlint` warnings remain in legacy media/interview components (`InterviewRoom.jsx`, `liveGazeDetector.js`, etc.); error count is `0`.

