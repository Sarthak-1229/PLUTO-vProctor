# PLUTO vProctor v2 — Phase 0 Baseline & Phase 1 Verification Report

**Recorded:** 2026-11-11 (Phase 0 Baseline) / 2026-11-12 (Phase 1 Verified Baseline)  
**Branch Baseline:** `main` (Phase 0 commit baseline `da56946`, Phase 1 foundation + review fixes on top of `aa83ff4`)  
**Isolation Note:** All Phase 1 backend tests and the offline self-practice end-to-end smoke check ran inside isolated temporary directories (`DATABASE_URL` & `STORAGE_DIR` in `%TEMP%` via `backend/tests/conftest.py`), keeping real candidate data in `backend/app/pluto.db` (`14` sessions) and `storage/` (`24` files, `360,036,616` bytes) completely unmodified by test runs.

---

## 1. Environment & Tooling Baseline

| Check | Command | Outcome | Observed Notes |
|---|---|---|---|
| **Env Check (Phase 0)** | `backend\.venv\Scripts\python.exe scripts/check_env.py` | **Partial PASS / WARN** | Python `3.12.10` PASS; `datasets/data` & `datasets/data1` PASS; `ffmpeg` NOT in PATH (uses PyAV wheels); Ollama `localhost:11434` stopped (deterministic offline fallbacks exercised). |
| **Config Under Host Env (Phase 1)** | `backend\.venv\Scripts\python.exe -c "import backend.app.config"` | **PASS (Fixed in Phase 1)** | Host `DEBUG=WARN` and blank/alias `ENVIRONMENT` values now normalize cleanly (`Settings` validators in [`backend/app/config.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/config.py)). |
| **Dev Tooling** | GSD + Superpowers + Context7 | **INSTALLED & VERIFIED** | Recorded in [`docs/ANTIGRAVITY_TOOLING.md`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ANTIGRAVITY_TOOLING.md). GSD `1.42.3` (`67` skills local), Superpowers `7.0.2` (`15` skills global), Context7 `4.5.0` MCP. |

---

## 2. Test, Lint & Build Suite Comparison (Phase 0 vs Phase 1 Final)

| Suite | Command | Phase 0 Baseline | Phase 1 Final Verified Result | Notes |
|---|---|---|---|---|
| **Backend Pytest (Local SQLite Isolation)** | `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v` | `124 passed, 0 failed, 29 warnings` (`91.73s`) | **`142 passed, 1 skipped, 1 warning`** (`67.00s`) | Adds `19` Phase 1 tests (`test_phase1_stabilization.py`, `test_config_and_errors.py`, `test_migrations.py`). The `1` local skip is `test_alembic_upgrade_live_postgresql` when `TEST_POSTGRES_URL` is unset; executed cleanly below against temporary PostgreSQL 16.2. Only remaining warning is Starlette's upstream `httpx2` notice. |
| **Live PostgreSQL 16.2 Migrations** | Temporary `pgserver` PG 16.2 + `TEST_POSTGRES_URL` (`pytest backend/tests/test_migrations.py -v` + CLI `alembic`) | *Not tested live in Phase 0* | **`6 passed, 0 failed, 0 skipped`** (`2.71s`) | Real `PostgreSQL 16.2` cluster created empty (`[]`), ran `alembic upgrade head`, `alembic check`, `alembic downgrade base`, `alembic upgrade head`, `alembic check`; all `7` tables + `alembic_version` + `5` indexes verified. |
| **Frontend Unit Tests** | `npm --prefix frontend test` | `3 passed, 0 failed` | **`5 passed, 0 failed`** (`147.89 ms`) | Covers FSM (`3` tests) and screening threshold normalization/clamp (`2` tests in `tests/test_screening_threshold.js`). |
| **Frontend Lint** | `npm --prefix frontend run lint` (`oxlint`) | **FAILED** (`27` errors, `74` warnings) | **`0 errors, 73 warnings`** (`91 ms`, `22` files) | Fixed all `27` `rules-of-hooks` errors by extracting `<MainApp />` in [`frontend/src/App.jsx`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/src/App.jsx). Legacy warnings deferred to Phase 5/7. |
| **Frontend Prod Build** | `npm --prefix frontend run build` (`vite build`) | `PASSED` (`1948` modules, `1.17s`) | **`PASSED` (`1949` modules, `1.16s`)** | Emits `dist/index.html`, `36.50 kB` CSS, `153.87 kB` vision bundle, `343.46 kB` main JS bundle. |
| **Ground-Truth Fixture Gate** | `backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check` | **PASSED** (`CI GATE PASSED`, `22.17s`) | **PASSED (`CI GATE PASSED`)** | Look-away Recall `100.0%` (`>=2s: 0/1`), False Alarms/min `4.0` (unchanged vs Phase 0), Pause Recall `100.0%` (`det=1/1` vs `3/1` in Phase 0), Median Time Error `2.57s` (`p95=2.921s`, threshold `<=4.0s`; Phase 0 was `2.22s`, `p95=2.535s`), Filler `F1=0.0%`, ASR `WER=200.0%` on synthetic audio (`hyp_words=22`). Reverted `docs/FIXTURE_EVALUATION.json` afterwards to keep git tree clean. |

---

## 3. ML & Algorithmic Evaluation Baseline

All 5 non-mutating evaluation scripts ran live against the untouched Phase 0 workspace (`DEBUG` unset):

| Component | Script | Live Phase 0 Result | Duration |
|---|---|---|---:|
| **Resume Screening (Test Split, N=200)** | [`scripts/evaluate_screening.py`](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/evaluate_screening.py) | Accuracy `97.50%`, Precision `96.00%`, Recall `85.71%`, F1 `90.57%` (`TN=171, FP=1, FN=4, TP=24`) | `5.64s` |
| **Domain Classification (Test Split, N=272)** | [`scripts/evaluate_domain.py`](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/evaluate_domain.py) | Naive Bayes `70.59%` Acc (`0.5209` Macro F1); LogReg `67.65%` Acc (`0.4704` Macro F1); MiniLM Centroid `66.91%` Acc (`0.6229` Macro F1) | `6.39s` |
| **Q&A Retrieval (Test Split, N=272)** | [`scripts/evaluate_retrieval.py`](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/evaluate_retrieval.py) | MiniLM: `R@1=80.9%`, `R@3=92.6%`, `R@5=96.0%`, `MRR=0.875`; TF-IDF: `R@1=63.2%`, `MRR=0.713`; BM25: `R@1=62.1%`, `MRR=0.704` | `36.42s` |
| **Question Selection (`job_sec_analyst`, pool=1051)** | [`scripts/evaluate_selection.py`](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/evaluate_selection.py) | Random: redundancy `0.132` (`11.5m`); Relevance Only: `0.413` (`9.9m`); Rel+MMR: `0.307` (`11.2m`); Rel+MMR+Knapsack: `6` Qs, `3` domains, `7` skills, redundancy `0.286` (`7.8m`) | `2.79s` |
| **Hand-Written Algorithm Benchmarks** | [`scripts/benchmark_algorithms.py`](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/benchmark_algorithms.py) | Levenshtein `0.646 ms`, KMP `1.223 ms`, Rabin-Karp `5.656 ms`, Top-K `13.604 ms`, MergeSort `9.381 ms`, QuickSort `5.637 ms`, BinarySearch `3.65 µs`, Trie `7.10 µs` vs `117.31 µs`, TF-IDF `0.032 ms` vs `0.809 ms` | `6.18s` |
| **Answer Relevance Classifier** | [`scripts/evaluate_answer_relevance.py`](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/evaluate_answer_relevance.py) | *Not re-run during read-only Phase 0 because it overwrites `answer_relevance_model.joblib`.* Recorded baseline in [`docs/EVALUATION_SUMMARY.md`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/EVALUATION_SUMMARY.md) (`2026-10-21`): LogReg `99.6%` Acc / `99.6%` F1 / `1.000` ROC-AUC; GB `99.8%` Acc / `1.000` ROC-AUC. | `—` |

---

## 4. Baseline Bugs Status (Resolved in Phase 0.5 / Phase 1)

1. ~~**`backend/app/config.py` `DEBUG` crash**~~ -> **RESOLVED:** `_coerce_debug_flag` handles non-boolean shell values (`WARN`), plus `ENVIRONMENT` canonicalization and production fail-fast checks.
2. ~~**`frontend/src/App.jsx` conditional hooks**~~ -> **RESOLVED:** Extracted `<MainApp />`, `oxlint` now reports `0 errors`.
3. ~~**`frontend/src/components/ScreeningStep.jsx:26,47` threshold scale bug**~~ -> **RESOLVED:** Normalized via [`frontend/src/utils/screeningUtils.js`](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/src/utils/screeningUtils.js) with unit tests.
4. ~~**`backend/app/routers/interview.py` missing `import json`**~~ -> **RESOLVED:** Added `import json` and route test for `/api/interview/config/gaze`.
5. ~~**Test suite DB/storage side effects**~~ -> **RESOLVED:** [`backend/tests/conftest.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/tests/conftest.py) isolates every `pytest` run in `%TEMP%`.
6. ~~**Empty Alembic initial migration**~~ -> **RESOLVED:** Inspector-guarded [`866ba5fa0eae_initial_schema.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/versions/866ba5fa0eae_initial_schema.py) + [`0002_add_core_indexes.py`](file:///D:/_TY/MDM/PLUTO-vProctor/backend/alembic/versions/0002_add_core_indexes.py) verified on live SQLite and temporary PostgreSQL 16.2.

---

## 5. Phase 2 Verification & Security Baseline (2026-11-12)

| Suite / Gate | Command | Outcome | Details |
|---|---|---|---|
| **Backend Pytest** | `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v` | **`161 passed, 1 skipped, 1 warning`** (`85.47s`) | All Phase 2 authentication, RBAC, legacy claiming, resume management, and job recommendation tests pass with 100% assertion success. |
| **Live PostgreSQL 16.2 Migrations** | Ephemeral PG 16.2 test harness (`0003_phase2_auth_profiles_rbac`) | **`6 passed, 0 failed`** (`2.44s`) | Clean migration against live PG 16.2 cluster: empty schema -> upgrade head -> alembic check -> downgrade base -> upgrade head -> alembic check. All 17 tables and indexes verified. |
| **Frontend Unit Tests** | `npm --prefix frontend test` | **`9 passed, 0 failed`** (`128ms`) | Added 4 auth and RBAC route guard tests; all 9 tests pass. |
| **Frontend Lint** | `npm --prefix frontend run lint` (`oxlint`) | **`0 errors, 67 warnings`** (`96ms`) | Zero lint errors across all 29 files. |
| **Frontend Prod Build** | `npm --prefix frontend run build` (`vite build`) | **`PASSED`** (`1955` modules, `764ms`) | Clean production assets emitted to `frontend/dist`. |
| **Ground-Truth Proctoring CI Gate** | `backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check` | **`CI GATE PASSED`** | Look-away Recall `100.0%`, Median Time Error `2.07s` (threshold `<= 4.0s`). Zero regression in proctoring ML pipeline. |
| **Live SQLite DB & Legacy Preservation** | SQLite PRAGMA check on `backend/app/pluto.db` | **`PRAGMA integrity_check: ok`, `foreign_key_check: 0 errors`** | All `14` legacy real sessions preserved untouched and unclaimed (`candidate_user_id IS NULL`). `1,799` questions, `12` jobs, `24` storage files intact. |
| **Security Code Review** | Independent whole-branch security audit | **`9/9 findings resolved & verified`** | 1 Critical, 2 High, 3 Medium, 3 Low findings resolved via TDD. |

---

## 6. Final Multi-Phase Verification Baseline (Phases 3–6 Complete — 2026-11-14)

| Suite / Gate | Command | Final Verified Outcome | Detailed Verification Notes |
|---|---|---|---|
| **Full Backend Pytest Suite** | `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v` | **`179 passed, 1 skipped, 1 warning`** (`118.00s`) | Comprehensive coverage across all modules: algorithms, ASR, gaze, monotonic scoring, resume screening, auth/RBAC, rooms/signaling, intelligence, roadmap, deployment & hardening. Single skip is optional live PG test when `TEST_POSTGRES_URL` unset (offline PG DDL compilation passes). |
| **Ground-Truth Proctoring CI Gate** | `backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check` | **`CI GATE PASSED`** | Look-away Recall: `100.0%`, Median Time Error: `2.07s` (threshold `<= 4.0s`), Zero regression in MediaPipe and audio proctoring metrics. |
| **Frontend Unit Tests** | `npm --prefix frontend test -- --run` | **`10 passed, 0 failed`** (`107ms`) | Full verification of auth route guards, RBAC restrictions, CSRF parsing, room protection, InterviewFSM state transitions, and screening thresholds. |
| **Frontend Lint** | `npm --prefix frontend run lint` (`oxlint`) | **`0 errors, 82 warnings`** (`78ms`) | Zero lint errors across 34 files. Legacy React Compiler warnings deferred safely. |
| **Frontend Production Build** | `npm --prefix frontend run build` (`vite build`) | **`PASSED`** (`1960` modules, `667ms`) | Clean production SPA bundles emitted to `frontend/dist`. |
| **Live SQLite Integrity & Schema** | `PRAGMA integrity_check`, `foreign_key_check` | **`integrity: ok`, `fk errors: 0`** | Live database at Alembic revision `0004_phase3_rooms_signaling`. All 22 tables and indexes intact. |
| **Legacy Candidate Data Preservation** | Invariant check on `sessions` table | **`14 / 14 Intact`** | Exactly 14 original real sessions (`Sarthak Bhosale`) preserved untouched, unclaimed (`candidate_user_id IS NULL`), in `self_practice` mode. Question bank: `1,799` items intact. |
| **Container & Reverse Proxy Hardening** | Docker & Nginx configuration inspection | **`Hardened`** | Multi-stage Dockerfile with non-root user `pluto`, Nginx reverse proxy with WebSocket upgrade support for realtime signaling, `/api/health` and `/api/ready` probes verified. |


