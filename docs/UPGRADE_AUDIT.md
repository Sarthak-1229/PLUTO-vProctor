# PLUTO vProctor v2 — Phase 0 Upgrade Audit

**Audit Date:** 2026-11-11 / 2026-11-12  
**Repository:** `D:\_TY\MDM\PLUTO-vProctor` (`main`)  
**Phase Status:** Phase 0 Complete (Read-only audit + backups + verified restore drill + baseline; awaiting user approval before cleanup or v2 changes)  
**Target Specs Reviewed:** `PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/*`, `antigravity/*`, `SEVEN_STEP_EXECUTION_MANUAL.md`, `prompts/ANTIGRAVITY_MASTER_PROMPT.md`

---

## 1. Repository Reality Check vs Supplied Reference (`PLUTO-vproctor.md` & `README.md`)

Cross-checking the desktop reference [`PLUTO-vproctor.md`](file:///C:/Users/Sarthak/Desktop/PLUTO-vproctor.md) and [`README.md`](file:///D:/_TY/MDM/PLUTO-vProctor/README.md) against actual files on disk revealed strong structural fidelity in the core v1 pipelines alongside **9 concrete documentation/implementation discrepancies** and **6 latent codebase bugs**:

| Area | Claimed in Reference / README | Observed Reality in Repo | Severity |
|---|---|---|---|
| **Job Catalog Size** | `README.md:10` says **"50+ roles"** (`PLUTO-vproctor.md:53` correctly says `12`). | [`backend/app/data/jobs.json`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/data/jobs.json) and `pluto.db` contain **`12` roles across `6` companies** (`min_experience_years` is `2–4`, zero fresher `0–1` yr roles). | Doc Drift / v2 Scope |
| **Algorithms Count** | `README.md:29` says **"15 hand-implemented algorithms"**. | `backend/app/algorithms/` has **`17` Python files** (`16` non-ML algorithmic modules + [`ml_models.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/algorithms/ml_models.py)). | Minor Doc Drift |
| **Spec Document Count** | `PLUTO-vproctor.md:243` says **`docs/spec/*.md` (12 specs)**. | `docs/spec/` contains **`11` `.md` files**. | Minor Doc Drift |
| **Fillers Dictionary Usage** | `PLUTO-vproctor.md:179` says `fillers.json` is `"loaded by legacy utilities/tests"`. | Live pipelines load [`config/disfluency.json`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/config/disfluency.json); [`fillers.json`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/data/fillers.json) is only referenced by offline CLI [`diagnose_recording.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/scripts/diagnose_recording.py). | Minor Doc Drift |
| **Alembic Migrations** | `PLUTO-vproctor.md:111` & `README.md:24` describe Alembic baseline schema tracking. | [`866ba5fa0eae_initial_schema.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/versions/866ba5fa0eae_initial_schema.py) has empty `pass` bodies in `upgrade()` and `downgrade()`. Running `alembic upgrade head` on a fresh PostgreSQL DB creates **0 tables**. | **P0 Migration Gap** |
| **Redis Worker Queue** | `README.md:25` & `docker-compose.yml` deploy a `pluto-worker` container with `REDIS_URL`. | [`job_queue.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/services/job_queue.py) uses an **in-process `asyncio.Queue` and in-memory dicts** (`_jobs`, `_session_to_job`); it never connects to Redis. Separate `worker` containers do not receive `backend` jobs. | **P1 Prod Architecture Gap** |
| **Frontend Lint & CI Gate** | All CI gates pass in `.github/workflows/ci.yml`. | `.github/workflows/ci.yml` omits `npm --prefix frontend run lint`; `oxlint` currently fails with **`27` errors and `74` warnings** because [`App.jsx:30-32`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/src/App.jsx#L28-L60) returns early before 27 React hooks (`rules-of-hooks`). | **P1 Quality Bug** |
| **Live DB Isolation** | Dev database holds user sessions and seeded corpus. | Tests (`test_e2e_flow.py`, `test_resume_screening.py`, `test_phase_f_production.py`) import `SessionLocal` directly against [`pluto.db`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/pluto.db) and `storage/` — **64 of 78** DB sessions (`82%`) are test-fixture runs! | **P0 Test Hygiene Bug** |
| **Pre-Existing Runtime Bugs** | Platform works cleanly end-to-end. | Observed directly in code:<br>1. [`config.py:19`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/config.py#L19): `DEBUG: bool` without `env_prefix` crashes if Windows/IDE shell exports `DEBUG=WARN`.<br>2. [`interview.py:40`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/routers/interview.py#L34-L41): `get_gaze_config()` calls `json.load(f)` without importing `json`.<br>3. [`ScreeningStep.jsx:26,47`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/src/components/ScreeningStep.jsx#L25-L48): compares `0..100` `fit_score` against `0..1` `pass_threshold` (`0.65`), approving rejected scores (`>= 0.65`).<br>4. [`question_service.py:286`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/services/question_service.py#L278-L290): reinstantiates `SentenceTransformer("all-MiniLM-L6-v2")` on every follow-up call; MMR line 192 uses `cand_embeddings[0]` instead of job/resume query vector.<br>5. [`main.py:84`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/main.py#L84): deprecated `@app.on_event("startup")`.<br>6. `SessionQuestion` and `ProctoringEvent` lack secondary DB indexes on `session_id`. | **P1 Correctness & Perf** |

---

## 2. Database & Storage Inventory (`pluto.db` & `storage/`)

### SQLite Database (`backend/app/pluto.db`)
- **Size:** `1,679,360` bytes (`1.60 MiB`)
- **Integrity:** `PRAGMA integrity_check` -> `ok`
- **Referential Integrity:** `0` orphaned rows in `session_questions`, `proctoring_events`, or `reports`
- **Secondary Indexes:** `session_questions` (`[]`) and `proctoring_events` (`[]`) have no indexes on `session_id` or `t_start`/`order_index`

| Table | Row Count | Notes |
|---|---:|---|
| `alembic_version` | 1 | Stamped `866ba5fa0eae` (empty migration script) |
| `companies` | 6 | Seeded from `backend/app/data/jobs.json` |
| `jobs` | 12 | All 2–4+ yr roles; missing fresher/entry-level (`0–1` yr) roles |
| `questions` | 1,799 | `train=1258`, `val=269`, `test=272`; `0` duplicate question texts; `QuestionService` currently reads `questions.json`, not DB |
| `sessions` | 78 | **64 test-fixture rows** (`Alex Vance`: 46, `Sam Taylor`: 18) + **14 real candidate rows** (`Sarthak Bhosale`) |
| `session_questions` | 311 | 215 belong to test-fixture sessions, 96 to `Sarthak Bhosale` |
| `proctoring_events` | 108 | All 108 belong to `Sarthak Bhosale` analyzed sessions (`0` in fixture sessions) |
| `reports` | 16 | 11 belong to test-fixture sessions, 5 to `Sarthak Bhosale` |

#### Real Candidate Sessions Preserved (`Sarthak Bhosale`, 14 sessions)
- **`ANALYZED` (5):** `sess_305e6f6df1d8` (score `56.5`, 67 events, video), `sess_590c1ae11450` (score `61.8`, no video), `sess_ce7da3c8cfb1` (score `82.2`, 2 events, video + 4 diagnostic sidecars), `sess_8e09181852e5` (score `78.6`, 18 events, video), `sess_668507482898` (score `69.9`, 21 events, video).
- **`RECORDED` (2):** `sess_943976e7b33e` (139 MB `.webm`, 16 questions), `sess_e21c4d5c2020` (51 MB `.webm`, 8 questions).
- **`IN_PROGRESS` (3):** `sess_d4bc4191952f`, `sess_9e2e13f7f701`, `sess_e769caf89bc9`.
- **`CREATED` (4 abandoned pre-interview):** `sess_9ef445d97932`, `sess_aab1134a81ca`, `sess_e86a45419cdc`, `sess_5db3615af446`.

### Disk Storage (`storage/`) — Total `102` files (`360,192,632 B` / `343.51 MiB`)
- **`storage/audio/`:** `0` files (`0 B`)
- **`storage/recordings/`:** `11` files (`357,268,416 B` / `340.72 MiB`)
  - `7` `.webm` files (`355,188,945 B`): `6` real `Sarthak Bhosale` recordings (`18.9 MB`–`139.3 MB`, totaling `355,186,893 B` across `4` `ANALYZED` + `2` `RECORDED` sessions) plus **`1` `2,052 B` synthetic EBML stub** (`sess_07dabc6b1375_interview.webm`, `Alex Vance` test session).
  - `4` non-`.webm` diagnostic sidecars for `sess_ce7da3c8cfb1` (`2,079,471 B`): `.diag.16k.wav`, `.diagnostics.json`, `.plot.png`, `.trace.csv` (from manual `diagnose_recording.py` run).
- **`storage/resumes/`:** `91` files (`2,924,216 B` / `2.79 MiB`)
  - `78` files match existing DB `sessions` rows (`64` fixture PDFs `134,006 B` + `14` real candidate PDFs `2,770,252 B`).
  - **`13` orphan files** (`19,958 B`) whose `sess_*` IDs do not exist in `sessions` (from deleted/rolled-back test runs, including `4` `98 B` stub PDFs and `9` `2,174 B` fixture copies).

---

## 3. Repository Structure & v2 Architecture Gaps

Comparing the current v1 codebase against [`PRODUCT_REQUIREMENTS.md`](file:///D:/_TY/MDM/PLUTO-vProctor/PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/PRODUCT_REQUIREMENTS.md), [`ARCHITECTURE_AND_DATA_MODEL.md`](file:///D:/_TY/MDM/PLUTO-vProctor/PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/ARCHITECTURE_AND_DATA_MODEL.md), [`SECURITY_PRIVACY_AND_FAIRNESS.md`](file:///D:/_TY/MDM/PLUTO-vProctor/PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/SECURITY_PRIVACY_AND_FAIRNESS.md), and [`DEPLOYMENT_PLAN.md`](file:///D:/_TY/MDM/PLUTO-vProctor/PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/specs/DEPLOYMENT_PLAN.md):

1. **Identity, Auth & RBAC (Missing completely):**
   - No `User` / auth tables, password hashing (Argon2/bcrypt), JWT/HTTP-only cookies, login/register UI, or role guards (`candidate` vs `admin`).
   - Sensitive endpoints (`/api/settings`, `/api/interview/{sid}/video`, `DELETE /api/interview/{sid}`, `/api/report/{sid}`, `/api/fixtures/save`) are unauthenticated.
   - [`CandidateDashboard.jsx`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/src/components/CandidateDashboard.jsx) reads only browser `localStorage`, losing history across browsers/devices.
2. **Candidate Profile, Manual Entry & Editable Resume Parsing (Missing):**
   - Candidates can only upload PDF/DOCX/TXT in Step 1 (`RoleSelectStep.jsx`); parsed skills/experience/education cannot be manually edited, and candidates without a file cannot enter a manual profile.
3. **Universal Job Recommendations & Entry-Level Catalog (Missing):**
   - Current workflow forces picking 1 job first and scoring resume fit solely against it. No `CandidateProfile -> Ranked Jobs` recommendation engine exists (independent of mode or interview completion), and `jobs.json` lacks fresher/entry-level roles (`0–1` yr).
4. **Admin Interview Rooms, Scheduling, Live Human-Hosted Interviews & Custom Question Sets (Missing):**
   - No `Admin` portal, `Room`, `RoomInvitation`, `QuestionDataset`, `Schedule`/reminders, or multi-participant live room flow (`host` + `candidate`).
   - [`frontend/Dockerfile`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/Dockerfile) Nginx config only proxies `/api/` HTTP paths — lacks WebSocket `Upgrade` headers if real-time room signaling/chat/media coordination uses WS.
   - `QuestionService` loads static `questions.json` from disk on import rather than reading database `questions` / `question_datasets` filtered by room config (while isolating `val`/`test` eval sets per dataset rules).
5. **Proctoring & Retrieval Reliability Gaps:**
   - **Calibration / sleeping / eye-closure exploit:** If a candidate calibrates already slouched/tilted or closes their eyes intermittently/sustained (`blink_score > 0.70` maps only to `LOOK_DOWN` `LOW` in [`gaze_tracker.py:310-323`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/pipelines/gaze_tracker.py#L310-L323), whereas `liveGazeDetector.js:330` explicitly suppresses alerts whenever `blinkScore >= 0.70`!), sustained eye-closure / drowsiness (`> 2s`) is not caught live and receives almost no penalty on server! Also `ScreeningStep.jsx:26` scale bug must be fixed, and `QuestionService.find_nearest_neighbors()` must cache MiniLM instead of loading it per call.
6. **Skill-Development Roadmap & Admin Analytics (Missing):**
   - No post-assessment structured skill roadmap generated from missing job skills, weak Q&A topics, or proctoring/fluency patterns, and no cross-candidate admin analytics dashboard.
7. **Deployment & Migration Hardening:**
   - `docker-compose.yml` hardcodes `POSTGRES_PASSWORD: pluto_password`; Alembic `upgrade()` is empty (`pass`); `job_queue.py` lacks real Redis broker integration or DB job persistence; `backups/` should be added to `.gitignore` once approved.

---

## 4. Recommended Implementation Order (Aligned with Upgrade Pack Phase Plan)

Preserve all working v1 self-practice flows at every step, using Superpowers TDD + GSD planning milestones:

1. **Phase 0 (Current Gate — Complete):** Developer tooling (`ANTIGRAVITY_TOOLING.md`), audit (`UPGRADE_AUDIT.md`), verified backup (`backups/phase0_20261111_235506`), cleanup proposal (`CLEANUP_PROPOSAL.md`), baseline (`UPGRADE_BASELINE.md`). **Stop for explicit user approval.**
2. **Phase 0.5 (Approved Safe Cleanup + Test Isolation):** Execute user-approved cleanup items from `CLEANUP_PROPOSAL.md`; isolate pytest fixtures from production `pluto.db`/`storage/` using `tmp_path` + `dependency_overrides`; add `backups/` to `.gitignore`.
3. **Phase 1 (Foundations, Auth, DB Migrations & Critical Pre-Existing Fixes):** Fix `config.py` (`DEBUG` parsing / prefix tolerance), `interview.py` (`import json`), `App.jsx` hooks (`oxlint` 0 errors), `ScreeningStep.jsx` threshold scale, FastAPI `lifespan`, real initial + v2 Alembic schema (`users`, `candidate_profiles`, `question_datasets`, `rooms`, `invitations`, `schedules`, FK indexes), auth/RBAC (candidate & admin accounts), and GDPR ownership scoping.
4. **Phase 2 (Candidate Profiles, Editable Parsing, Expanded Entry-Level Catalog & Universal Job Recommendations):** Editable resume parser review + manual profile entry, expanded entry-level/fresher job catalog, universal skill+experience+domain+semantic job recommender, and DB-backed candidate dashboard/history.
5. **Phase 3 (Admin Platform: Question Datasets, Rooms, Invites, Scheduling & Analytics):** Admin UI & APIs for uploading/managing/ordering custom question datasets, creating rooms + invitation links/codes + schedules/reminders + room analytics.
6. **Phase 4 (Human-Hosted Room Proctoring & Shared Analysis Pipeline):** Host + candidate live interview room (reusing WebRTC/recording + preflight + calibration + `LiveGazeDetector` + server `VideoAnalysisPipeline`/`AudioAnalysisPipeline` + `ScoringEngine` + `ReportService`), dual-mode unified reports, and mode-aware `SkillRoadmap` generation.
7. **Phase 5 (Question Retrieval, Proctoring Reliability & Performance Hardening):** Singleton MiniLM cache, proper MMR query embedding, sustained eye-closure / drowsiness detection & uncalibrated absolute posture sanity checks, WebM container resilience, Nginx WebSocket proxy, and Postgres/Redis `JobQueue` parity.
8. **Phase 6 (Security, Privacy, Load & Production QA Acceptance):** RBAC/IDOR security regression suite, Docker Postgres clean `alembic upgrade head` smoke verification, full pytest + lint + build + fixture gate + benchmark verification, and `RUNBOOK.md` / `ARCHITECTURE.md` / `API.md` updates.
