# PLUTO vProctor v2 — Phase 0 Baseline Verification Report

**Recorded:** 2026-11-11 / 2026-11-12  
**Commit / Branch Baseline:** Clean repository prior to v2 feature implementation (plus Phase 0 GSD `.agent/` local install + `docs/` audit files)  
**Isolation Note:** Backend `pytest` was executed against a full temporary copy of `backups/phase0_20261111_235506/pluto.db` + `storage/` (`DATABASE_URL` & `STORAGE_DIR` overridden in `%TEMP%`) so live `pluto.db` (`78` sessions) and `storage/` (`102` files) remained bit-for-bit unmodified during Phase 0.

---

## 1. Environment & Tooling Baseline

| Check | Command | Outcome | Observed Notes |
|---|---|---|---|
| **Env Check** | `backend\.venv\Scripts\python.exe scripts/check_env.py` | **Partial PASS / WARN** | Python `3.12.10` PASS; `datasets/data` & `datasets/data1` PASS; `ffmpeg` NOT in PATH (uses PyAV wheels); Ollama `localhost:11434` currently refused connection (service stopped — deterministic fallbacks exercised). |
| **Config Under Host Env** | `backend\.venv\Scripts\python.exe -c "import backend.app.config"` | **FAIL (Code Bug)** | Fails with `pydantic_core.ValidationError` (`DEBUG`: unable to parse `'WARN'`) when Windows/IDE host shell exports `DEBUG=WARN`, because `Settings` lacks `env_prefix` or `DEBUG` validator. Subsequent Phase 0 test/eval runs cleared `DEBUG` in subprocess env only. |
| **Dev Tooling** | GSD + Superpowers + Context7 | **INSTALLED & VERIFIED** | Recorded in [`docs/ANTIGRAVITY_TOOLING.md`](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ANTIGRAVITY_TOOLING.md). GSD `1.42.3` (`67` skills local), Superpowers `7.0.2` (`15` skills global), Context7 `4.5.0` MCP (`resolve-library-id` & `query-docs` live-verified). |

---

## 2. Test, Lint & Build Suite Baseline

| Suite | Command | Result | Duration | Notes |
|---|---|---|---:|---|
| **Backend Pytest** | `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v` *(temp DB/storage copy, `DEBUG` unset)* | **124 passed, 0 failed, 29 warnings** | `91.73s` | Warnings: FastAPI `@app.on_event("startup")` deprecation (`main.py:84`), Starlette `httpx` deprecation, SQLAlchemy/Python `datetime.utcnow()` deprecation (`models.py`, `report_service.py`). Live `pluto.db` unchanged (`78` sessions). |
| **Frontend FSM Unit Tests** | `node --test frontend/tests/test_interview_fsm.js` | **3 passed, 0 failed** | `169.5 ms` | Covers initial idle transitions, illegal transition blocking, and follow-up loops. |
| **Frontend Lint** | `npm --prefix frontend run lint` (`oxlint`) | **FAILED (`27` errors, `74` warnings)** | `65 ms` | All `27` errors are `react-hooks/rules-of-hooks` in `frontend/src/App.jsx:35-178` caused by early return at `App.jsx:30-32`. Not currently gated in `.github/workflows/ci.yml`. |
| **Frontend Prod Build** | `npm --prefix frontend run build` (`vite build`) | **PASSED** (`1948` modules) | `1.17s` (`4.55s` wall) | Produced `dist/index.html` + bundles (`343.12 kB` JS main, `153.87 kB` vision bundle). |
| **Ground-Truth Fixture Gate** | `backend\.venv\Scripts\python.exe backend/scripts/evaluate_fixtures.py --gate-check` *(with `DEBUG` unset)* | **PASSED** (`CI GATE PASSED`) | `22.17s` | Evaluated `fixture_synth_001.webm` (`15.0s`): Filler `F1=0.0%` (`det=6/1`, `hyp="ahh ahh ahh ahh umm ahh"`), Pause `Recall=100.0%` (`det=3/1`), Look-away `Recall=100.0%` (`False Alarms/min=4.0`), Median Time Error `2.22s` (`p95=2.535s`, CI gate `<=4.0s`), ASR `WER=100.0%` (`ref_words=9`, `hyp_words=6`). Reverted `docs/FIXTURE_EVALUATION.json` afterwards to keep git tree clean. |

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

## 4. Baseline Bugs Flagged Before Phase 1 Starts

1. **`backend/app/config.py` `DEBUG` crash** when Windows/IDE sets non-boolean `DEBUG=WARN` in process env.
2. **`frontend/src/App.jsx` conditional hooks** causing `oxlint` to fail with `27` `rules-of-hooks` errors.
3. **`frontend/src/components/ScreeningStep.jsx:26,47`** comparing `0..100` `fit_score` against `0..1` `pass_threshold` (`0.65`).
4. **`backend/app/routers/interview.py:40`** using `json.load(f)` without importing `json`.
5. **Test suite DB/storage side effects**: `pytest` writes directly to `backend/app/pluto.db` & `storage/` unless env vars are overridden externally.
6. **Empty Alembic initial migration** (`866ba5fa0eae_initial_schema.py` contains only `pass`).

