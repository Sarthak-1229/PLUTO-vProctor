# Phase 1 — Stabilize Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden PLUTO vProctor's configuration validation, feature flags, API error conventions, Alembic schema baseline + indexes, CI lint gate, and architectural decision records so v2 auth, recommendations, and hosted WebRTC rooms build on a tested, PostgreSQL-compatible foundation without breaking the existing offline AI interview flow.

**Architecture:** Preserve all existing self-practice API contracts (`/api/jobs`, `/api/resume/*`, `/api/interview/*`, `/api/analysis/*`, `/api/report/*`, `/api/settings`) and SQLite local dev (`run_dev.bat`) while adding additive config validation, unified structured JSON error handlers, Alembic baseline DDL + non-destructive index migrations, feature flags (`AUTH_ENABLED`, `HOSTED_ROOMS_ENABLED`, `LIVE_MEDIA_ENABLED`, `MEDIA_TRANSPORT_MODE`), and documented ADRs (`docs/DECISIONS.md`) covering legacy session claiming and WebRTC P2P + TURN + WebSocket signaling with an SFU extension boundary.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2 / `pydantic-settings`, SQLAlchemy 2.0, Alembic, React 19 / Vite 8 / `oxlint`, GitHub Actions.

**Specs:**
- `PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/antigravity/PHASE_PLAN.md` (Phase 1)
- `PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/ARCHITECTURE_AND_DATA_MODEL.md`
- `PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/DEPLOYMENT_PLAN.md`
- `PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/SECURITY_PRIVACY_AND_FAIRNESS.md`

---

## Global Constraints

- Do not start Phase 2–8 user-facing UI/feature routes inside Phase 1 (keep `AUTH_ENABLED=False` and `HOSTED_ROOMS_ENABLED=False` by default so v1 self-practice mode behaves identically).
- Preserve all local offline AI capabilities (`qwen2.5:3b` Ollama lock, CPU `all-MiniLM-L6-v2`, CPU int8 `faster-whisper`, PyAV + MediaPipe pipelines) and `1,799` curated `questions` dataset provenance.
- Never silently mutate live `backend/app/pluto.db` or `storage/` during test runs (`backend/tests/conftest.py` isolation must hold across all suites).
- All schema migrations must go through Alembic and pass on **both** a copy of existing SQLite `pluto.db` and an empty target database (SQLite/PostgreSQL DDL compatibility).
- Never store secrets, TURN credentials, or JWT signing keys in git; provide clean placeholders in `.env.example`.

## Review Focus

- Empty or non-boolean environment variables (`ENVIRONMENT=""`, `LLM_TIMEOUT_SECONDS=""`, `API_PORT` invalid, missing `SECRET_KEY` when `ENVIRONMENT=production`) must fail fast with a clear actionable startup error when unsafe in production, while remaining permissive for safe local dev defaults.
- Structured API error responses (`HTTPException`, `RequestValidationError`, unhandled `500`) must keep backwards compatibility for any frontend consumer expecting `detail`, while adding standardized `error: { code, message, request_id, details }` without leaking stack traces or PII.
- Alembic `upgrade head` on an *already-existing* SQLite copy of `pluto.db` stamped at `866ba5fa0eae` must NOT fail with `table already exists`, AND running `alembic upgrade head` on a *brand-new empty database* must create all 7 baseline tables cleanly plus new secondary indexes.
- `report_service.py` / `models.py` UTC timestamp replacements (`datetime.now(timezone.utc)`) must produce naive-or-UTC ISO strings accepted cleanly by existing SQLite queries and PDF report formatting without breaking comparisons.
- GitHub Actions CI (`ci.yml`) must enforce `npm --prefix frontend run lint` cleanly alongside `pytest`, `evaluate_fixtures.py --gate-check`, `node --test`, and `vite build`.

---

## Already Completed Before Phase 1 Plan Handoff (Phase 0.5)

- Approved cleanup (`C1`–`C5` + `backups/` gitignored, preserving `C7`, `C8`, `datasets/`, `.agent/`, `backups/phase0_20261111_235506/`).
- `backend/tests/conftest.py` session isolation (`temp_pluto.db` + `temp_storage`, seeded static catalog only).
- High-priority bug fixes: `DEBUG=WARN` coercion in `config.py`, `import json` in `routers/interview.py`, `lifespan` in `main.py`, `_st_model` caching in `QuestionService`, `App.jsx` hooks fix (`oxlint` 0 errors), and `ScreeningStep.jsx` (`screeningUtils.js`) threshold scale fix.

---

### Task 1: Architecture Decision Records (v2 Boundaries & User Decisions)

**Files:**
- Modify: `docs/DECISIONS.md` (append `DECISION-012` through `DECISION-016` after `DECISION-011`)
- Test: doc verification check (`pytest` doc link / non-empty check optional or manual inspection in gate)

**Decisions Locked In (From Specs + User Approvals):**
- `DECISION-012`: Separate RBAC Roles (`candidate`, `admin`, `super_admin`) & Admin-Controlled Legacy Claim Workflow (`sessions.candidate_user_id` nullable; the `14` legacy `Sarthak Bhosale` sessions remain unclaimed until an admin explicitly links them — zero automatic name/email auto-linking).
- `DECISION-013`: Hosted Interview Media Architecture — Initial WebRTC P2P + FastAPI WebSocket signaling + configurable `STUN`/`TURN` servers for external NAT traversal, paired with existing server-side recording upload & multimodal analysis; isolate WebRTC signaling/media client behind a clean `MediaTransportAdapter` boundary extensible to an SFU (e.g., LiveKit) in Phase 6/later without rewriting room orchestration.
- `DECISION-014`: Additive Dual-DB Compatibility — SQLite remains local zero-dependency dev store; PostgreSQL 16 + Redis remain production source of truth managed strictly via idempotent Alembic migrations (`CREATE TABLE IF NOT EXISTS` / inspector-checked baseline).
- `DECISION-015`: Feature-Flagged Modular Rollout (`AUTH_ENABLED`, `HOSTED_ROOMS_ENABLED`, `LIVE_MEDIA_ENABLED`, `MEDIA_TRANSPORT_MODE=p2p|sfu|none`) preserving single-user self-practice flow under explicit dev fallback only when `AUTH_ENABLED=False`.
- `DECISION-016`: Proctoring Fairness & System-Health Separation — hardware/network failures and short blinks/occlusion never silently penalize as misconduct without duration + confidence telemetry and human review hooks.

- [ ] **Step 1:** Append `DECISION-012` through `DECISION-016` to `docs/DECISIONS.md` preserving existing `DECISION-001`..`DECISION-011`.
- [ ] **Step 2:** Verify `docs/DECISIONS.md` formatting and cross-references against `specs/`.

---

### Task 2: Environment Validation, Feature Flags & Transport Settings

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_config_and_errors.py` (create)

**Interfaces:**
- Produces on `Settings`:
  - Feature flags: `AUTH_ENABLED: bool = False`, `HOSTED_ROOMS_ENABLED: bool = False`, `LIVE_MEDIA_ENABLED: bool = False`, `MEDIA_TRANSPORT_MODE: Literal["none", "p2p", "sfu"] = "p2p"`
  - Auth/Security config (validated in production): `SECRET_KEY: str = ""`, `ACCESS_TOKEN_EXPIRE_MINUTES: int = 15`, `REFRESH_TOKEN_EXPIRE_DAYS: int = 7`, `COOKIE_SECURE: bool = False`
  - WebRTC / TURN config: `STUN_SERVERS: List[str] = ["stun:stun.l.google.com:19302"]`, `TURN_SERVER_URLS: List[str] = []`, `TURN_USERNAME: str = ""`, `TURN_CREDENTIAL: str = ""`
  - Methods: `validate_runtime_safety() -> None` (raises clear `RuntimeError` if `ENVIRONMENT == "production"` and `AUTH_ENABLED` without non-default `SECRET_KEY` `>= 32` chars, or `MEDIA_TRANSPORT_MODE == "sfu"` without SFU URL).

- [ ] **Step 1: Write failing tests** in `backend/tests/test_config_and_errors.py`:
  - Assert default dev `Settings()` loads cleanly with `AUTH_ENABLED=False`, `HOSTED_ROOMS_ENABLED=False`, `MEDIA_TRANSPORT_MODE="p2p"`.
  - Assert `Settings(ENVIRONMENT="production", AUTH_ENABLED=True, SECRET_KEY="short").validate_runtime_safety()` raises `RuntimeError`.
  - Assert `Settings(API_PORT=8000, SCORING_WEIGHTS={...})` rejects negative or non-positive scoring weights / out-of-range timeouts.
  - Assert `Settings` parses comma-separated or JSON `TURN_SERVER_URLS`.
- [ ] **Step 2: Run failing tests** (`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_config_and_errors.py -v`) and confirm FAIL.
- [ ] **Step 3: Implement settings fields & validators** in `backend/app/config.py` and document every new env key in `.env.example` (no hardcoded secrets) + invoke `settings.validate_runtime_safety()` inside `main.py` `lifespan`.
- [ ] **Step 4: Re-run tests** and verify PASS.

---

### Task 3: Standardized API Error Conventions (Backwards-Compatible Envelope)

**Files:**
- Create: `backend/app/core/errors.py`
- Modify: `backend/app/main.py` (register exception handlers)
- Test: `backend/tests/test_config_and_errors.py`

**Interfaces:**
- Produces `AppError(HTTPException)` / standardized response payload:
  ```json
  {
    "detail": "Human-readable error message",
    "error": {
      "code": "RESOURCE_NOT_FOUND",
      "message": "Human-readable error message",
      "request_id": "abcd1234",
      "details": null
    }
  }
  ```
  - Keeping top-level `"detail"` preserves 100% compatibility with existing v1 tests & React fetch handlers while giving v2 clients structured `error.code` & `error.request_id`.

- [ ] **Step 1: Write failing tests** verifying:
  - `404` on `/api/interview/nonexistent_id` returns both `detail` and `error.code == "HTTP_404"` + `error.request_id` matching `X-Request-ID` header.
  - Validation `422` error (e.g., invalid body on `/api/settings` `PUT`) returns `detail` plus `error.code == "VALIDATION_ERROR"` and sanitized `error.details`.
  - Unexpected unhandled exception in a test route returns `500` JSON with `error.code == "INTERNAL_ERROR"` and `request_id` without leaking traceback string to client.
- [ ] **Step 2: Watch tests FAIL.**
- [ ] **Step 3: Implement** `backend/app/core/errors.py` and register `HTTPException`, `RequestValidationError`, and catch-all `Exception` handlers in `backend/app/main.py` (ensuring `X-Request-ID` is preserved on exception responses too!).
- [ ] **Step 4: Re-run tests** and verify PASS.

---

### Task 4: Alembic Real Initial Schema + Index Migration + Dual-DB Verification

**Files:**
- Modify: `backend/alembic/versions/866ba5fa0eae_initial_schema.py` (or keep initial stamp and verify base DDL + add migration `0002_baseline_tables_and_indexes.py` using SQLAlchemy Inspector checks so BOTH fresh DB and existing stamped `pluto.db` upgrade cleanly!)
- Modify: `backend/app/db/models.py` (add `index=True` on `SessionQuestion.session_id`, `SessionQuestion.order_index`, `ProctoringEvent.session_id`, `ProctoringEvent.t_start`, `InterviewSession.interview_status`; migrate `datetime.datetime.utcnow` defaults to timezone-aware `lambda: datetime.datetime.now(datetime.timezone.utc)`)
- Modify: `backend/app/services/report_service.py` (replace `datetime.utcnow()` calls with `datetime.now(timezone.utc)`)
- Test: `backend/tests/test_migrations.py` (create)

**Interfaces & Strategy:**
- Existing `backend/app/pluto.db` already has all 7 tables and `alembic_version = '866ba5fa0eae'`, while a fresh Postgres/SQLite DB has 0 tables and no `alembic_version` row!
- Solution:
  1. Populate `866ba5fa0eae_initial_schema.py` `upgrade()` with idempotent `CREATE TABLE` DDL (`sa.inspect(bind).has_table(...)` guard) for all 7 v1 tables so `alembic upgrade head` on a **fresh empty DB** creates every table cleanly AND running on a previously unstamped/partial DB doesn't crash!
  2. Add revision `0002_add_core_indexes` creating the missing secondary indexes (`ix_session_questions_session_id`, `ix_session_questions_order_index`, `ix_proctoring_events_session_id`, `ix_proctoring_events_t_start`, `ix_sessions_interview_status`) guarded by inspector index existence checks (`downgrade()` drops only those indexes cleanly).

- [ ] **Step 1: Write failing tests** in `backend/tests/test_migrations.py`:
  - Fresh empty SQLite DB -> run `alembic upgrade head` -> assert all 7 tables + `alembic_version` exist and `ix_proctoring_events_session_id` / `ix_session_questions_session_id` exist.
  - Copy of pre-existing `866ba5fa0eae`-stamped SQLite DB (having tables without indexes) -> run `alembic upgrade head` -> assert `0` errors, all existing rows preserved verbatim, and new indexes created.
  - Test PostgreSQL dialect SQL compilation (`alembic upgrade head --sql` offline compilation with `postgresql://...`) succeeds with zero SQLite-only types/errors.
- [ ] **Step 2: Run failing tests** and watch them FAIL (`0` tables created on empty DB).
- [ ] **Step 3: Implement** `866ba5fa0eae_initial_schema.py`, `0002_add_core_indexes.py`, `models.py` indexes + UTC defaults, and `report_service.py` UTC fix. (After verified, test upgrade on a copied snapshot of real `pluto.db` BEFORE running `alembic upgrade head` on local `pluto.db`, or leave local `pluto.db` upgrade as explicit Phase 1 verification checkpoint!).
- [ ] **Step 4: Re-run tests** and verify zero SQLAlchemy `utcnow` deprecation warnings remain.

---

### Task 5: CI Workflow & Baseline Verification Gate

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `backend/app/main.py` / `frontend/tests/` (if any remaining lint check adjustments needed)

- [ ] **Step 1:** Update `.github/workflows/ci.yml`:
  - Add `Run Frontend Lint` (`npm --prefix frontend run lint`) before `Build Vite Production Bundle`.
  - Add `node --test frontend/tests/*.js` (covers both `test_interview_fsm.js` and `test_screening_threshold.js`!).
  - Add `alembic check` / clean migration smoke test step in `backend-test-gate`.
- [ ] **Step 2:** Run full Phase 1 verification suite locally:
  - `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v`
  - `backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check`
  - `node --test frontend/tests/*.js`
  - `npm --prefix frontend run lint`
  - `npm --prefix frontend run build`
- [ ] **Step 3:** Confirm workspace `backend/app/pluto.db` (`14` real sessions preserved unless explicit local migration approved) and `storage/` (`24` files) remain intact, update `docs/UPGRADE_BASELINE.md`, and stop at **Phase 1 Gate** for user approval before starting **Phase 2 (Auth, RBAC, Admin Login & Legacy Claim Workflow)**.
