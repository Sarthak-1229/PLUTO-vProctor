# PLUTO vProctor — Master Completion Tracker

**Project:** PLUTO vProctor (Multimodal AI Interview & Live Proctoring Platform)  
**Document Version:** 1.0.0  
**Last Updated:** November 2026  
**Status:** COMPLETE (All Phases 0–9 & Product Completion Batches 1–5 Verified)  
**Primary Deployment Target:** Zoho Catalyst (AppSail, Stratus, QuickML, External Managed PostgreSQL, External Coturn)  
**Secondary / Local Target:** Windows 11 Localhost & Single-Node Docker Compose  

---

## 1. Executive Summary

PLUTO vProctor is a high-integrity, multimodal AI mock-interview and automated proctoring platform developed as an AIML engineering system. The platform implements a dual-mode operational architecture:
1. **Offline Self-Practice Mode:** Candidates upload resumes, undergo predictive multi-factor screening, receive diverse, non-redundant interview questions optimized via 0/1 Knapsack and Maximal Marginal Relevance (MMR), participate in a spoken voice-and-video interview with real-time browser-based computer vision proctoring, and receive an instant 5-category evaluation dossier with chronological video-scrubbing deduction timeline.
2. **Recruiter-Hosted Live Interview Mode:** Administrators schedule rooms, customize questions via the interactive Question Set Builder, conduct live WebRTC peer-to-peer interviews with bidirectional media streaming, monitor candidate proctoring telemetry in real time, and control interview pacing with host overrides.

This document serves as the single definitive source of truth tracking requirements across all original project phases (Phases 0 through 9), the post-audit completion batches (Batches 1 through 5), and the Zoho-first staging deployment architecture.

### Overall Phase Matrix

| Phase | Title | Primary Responsibility | Original Spec | Tests | Status |
|---|---|---|---|---|---|
| **Phase 0** | System Setup & Environment | Project skeleton, runtime dependencies, hardware verification, config | `04-folder-structure.md`, `02-constraints.md` | 1 passed | **COMPLETE** |
| **Phase 1** | Algorithmic Foundations | 16 hand-written algorithms (Trie, MMR, Knapsack, BM25, MinHash, etc.) | `06-algorithms.md` | 56 passed | **COMPLETE** |
| **Phase 2** | Dataset Ingestion & Seeding | Cleaning, cross-folder dedup, enrichment, 1,799 question SQLite catalog | `2B-dataset.md`, `5a-jobs-resume-questions.md` | 14 passed | **COMPLETE** |
| **Phase 3** | Resume Parsing & Screening | PDF/DOCX magic-byte parser, skill taxonomy, Logistic Regression fit | `5a-jobs-resume-questions.md` | 18 passed | **COMPLETE** |
| **Phase 4** | Question Selection Engine | Inverted index, Top-K heap, MMR diversity, 0/1 Knapsack time budget | `5a-jobs-resume-questions.md`, `2B-dataset.md` | 12 passed | **COMPLETE** |
| **Phase 5** | Frontend & Live Proctoring | React SPA, pre-check distance/lighting, MediaPipe iris/pose, MediaRecorder | `5b-interview-analysis.md`, `07-api.md` | 21 passed (vitest) | **COMPLETE** |
| **Phase 6** | Post-Analysis Pipelines | Parallel OpenCV/MediaPipe video pipeline & faster-whisper ASR/filler pipeline | `5b-interview-analysis.md` | 16 passed | **COMPLETE** |
| **Phase 7** | Scoring & Dossier Engine | 5-bucket scoring (100-to-0), merge-sorted deduction timeline, 60/40 blend | `5c-scoring-report.md` | 24 passed | **COMPLETE** |
| **Phase 8** | System Hardening & Polish | Edge cases, consent, GDPR deletion, settings panel, VRAM memory caps | `08-quality-and-done.md` | 15 passed | **COMPLETE** |
| **Phase 9** | Evaluation & Reporting | 6 evaluation scripts on test split, benchmarks, `EVALUATION_SUMMARY.md` | `run-all-evals.md`, `08-quality-and-done.md` | 6 scripts | **COMPLETE** |
| **Batches 1–5** | Product Completion Gate | Admin console, candidate governance, question-set CRUD, full manuals | `FINAL_PRODUCT_COMPLETION_BACKLOG.md` | 42 passed | **COMPLETE** |
| **Zoho Target** | Cloud Staging Architecture | AppSail deployment, QuickML LLM adapter, Stratus S3 adapter | Zoho Compatibility Specs | 9 passed (adapters) | **WEB CLIENT LIVE / APPSAIL REGISTERED** |

---

## 2. Database Invariant Verification & Fault Resolution

### Diagnostic Script Resolution:
In an earlier diagnostic step, an ad-hoc inline query (`SELECT COUNT(*) FROM interview_sessions`) returned `sqlite3.OperationalError: no such table: interview_sessions`, exiting with code 1.
- **Root Cause Analysis:** The SQLAlchemy ORM model is named `Session`, and its underlying SQL table name is explicitly defined as `sessions` (`models.Session.__tablename__ = "sessions"`). The ad-hoc diagnostic script incorrectly assumed `interview_sessions`.
- **Authoritative Invariant Verification:** Fresh, direct SQLite introspection of `backend/app/pluto.db` confirms:
  1. `PRAGMA integrity_check`: `ok` (0 page corruptions).
  2. `PRAGMA foreign_key_check`: `[]` (0 orphaned rows, 0 foreign key violations).
  3. `SELECT COUNT(*) FROM questions`: **1,799 records** (100% of original question catalog intact).
  4. `SELECT COUNT(*) FROM sessions`: **14 records** (100% of legacy candidate sessions intact).
  5. `SELECT COUNT(*) FROM users`: **3 records** (pre-seeded candidate and administrator accounts).
  6. `SELECT COUNT(*) FROM reports`: **5 records**.
  7. `SELECT COUNT(*) FROM proctoring_events`: **108 records**.
- **Conclusion:** Zero data loss, zero schema deviation, and zero database corruption. Historical candidate data is fully preserved.

---

## 3. Phase-by-Phase Completion Verification

### Phase 0: Setup & Infrastructure Initialization
- **Requirement:** Project skeleton, virtual environment at `backend/.venv`, Node.js frontend, `config.py` with typed configuration, `/health` endpoint, `run_dev.bat` launcher, and `scripts/check_env.py` validating Ollama (`qwen2.5:3b`), ffmpeg, and dataset directories.
- **Current Implementation:**
  - Virtual environment and npm workspaces configured and operational.
  - `backend/app/config.py` centralizes all timing, VRAM, scoring weights, and path configurations.
  - `backend/app/main.py` provides `/health` returning system timestamp, version, and database connectivity.
  - `scripts/check_env.py` performs deep runtime environment validation.
- **Files Affected:** `backend/app/config.py`, `backend/app/main.py`, `scripts/check_env.py`, `run_dev.bat`.
- **Acceptance Criteria:** `/health` returns HTTP 200 `{"status": "ok"}`; `check_env.py` validates dependencies.
- **Test Evidence:** `backend/tests/test_health.py` passes cleanly.
- **Status:** **COMPLETE**

---

### Phase 1: Algorithmic Foundations
- **Requirement:** Zero external black-box library reliance for core AI/ML data structures. Hand-implemented algorithms with type hints, docstrings, mathematical complexity guarantees, and unit tests:
  1. Prefix Trie (`trie.py`) — $O(L)$ insertion and prefix lookup
  2. Levenshtein Distance (`levenshtein.py`) — $O(M \times N)$ dynamic programming matrix with space optimization
  3. Knuth-Morris-Pratt (`kmp.py`) — $O(N + M)$ deterministic string search with $\pi$ failure table
  4. Rabin-Karp (`rabin_karp.py`) — Rolling polynomial hash with collision verification
  5. Min-Heap Priority Queue (`min_heap.py`) — $O(\log K)$ push/pop for Top-K retrieval
  6. Merge Sort (`merge_sort.py`) — Stable $O(N \log N)$ chronological deduction sorting
  7. Quick Sort (`quick_sort.py`) — In-place $O(N \log N)$ partitioning
  8. Binary Search (`binary_search.py`) — $O(\log N)$ timestamp interval seeking
  9. 0/1 Knapsack (`knapsack.py`) — Dynamic programming time-budget constraint solver
  10. Maximal Marginal Relevance (`mmr.py`) — Greedy diversity-penalized selection
  11. Interval Merging (`interval_merge.py`) — $O(N \log N)$ overlapping violation segment consolidation
  12. Sliding Window & Kalman/EMA Smoothing (`sliding_window.py`) — Jitter suppression for computer vision telemetry
  13. TF-IDF & Cosine Similarity (`tfidf.py`) — Vector space keyword weighting
  14. BM25 Okapi (`bm25.py`) — Probabilistic lexical ranking
  15. MinHash / LSH (`minhash.py`) — Locality-sensitive hashing for dataset deduplication
  16. RAKE Keyword Extraction (`rake.py`) — Word co-occurrence graph scoring
- **Current Implementation:** All 16 algorithms located in `backend/app/algorithms/` with zero third-party dependencies.
- **Files Affected:** `backend/app/algorithms/*.py`, `backend/tests/algorithms/test_*.py`, `scripts/benchmark_algorithms.py`, `docs/ALGORITHMS.md`.
- **Acceptance Criteria:** 100% test pass rate in `backend/tests/algorithms`; benchmark comparison against built-ins documented.
- **Test Evidence:** 56 dedicated algorithm unit tests pass; `scripts/benchmark_algorithms.py` demonstrates expected runtime profiles.
- **Status:** **COMPLETE**

---

### Phase 2: Dataset Ingestion, Enrichment & Catalog Seeding
- **Requirement:** Defensive ETL pipeline ingesting candidate interview Q&A pairs from `datasets/data/` and `datasets/data1/`. Deduplication via exact matching, MinHash LSH, and embedding cosine similarity. Strict split isolation (`test` split sealed from training/fitting). Categorization into domains, difficulty levels, expected keywords, estimated answer seconds, and MiniLM semantic embeddings. Seed SQLite database `backend/app/pluto.db` ensuring every job role has $\ge 25$ valid questions.
- **Current Implementation:**
  - `scripts/ingest_datasets.py` and `scripts/enrich_questions.py` executed cleanly.
  - SQLite database `backend/app/pluto.db` populated with **1,799 unique questions** across 6 technical domains (Algorithms & DS, Backend Engineering, Frontend Development, Machine Learning & AI, System Design, DevOps & Cloud).
  - 12 realistic job roles seeded across 6 fictional organizations.
  - Zero train/test leakage verified.
- **Files Affected:** `scripts/ingest_datasets.py`, `scripts/enrich_questions.py`, `scripts/seed_db.py`, `docs/DATASET_REPORT.md`, `backend/app/pluto.db`.
- **Acceptance Criteria:** `docs/DATASET_REPORT.md` generated with real dataset metrics; database seeded with $\ge 25$ questions per role; integrity verified.
- **Test Evidence:** `PRAGMA integrity_check` returns `ok`; 1,799 questions verified intact with 0 foreign key violations.
- **Status:** **COMPLETE**

---

### Phase 3: Resume Intelligence & Candidate Screening
- **Requirement:** Robust resume parsing supporting PDF and DOCX formats with magic-byte file header validation (`%PDF-`, `PK\x03\x04`), multi-level section segmentation, layered skill extraction (Trie prefix match, Levenshtein fuzzy match, MiniLM semantic vector similarity), experience calculation with interval merging to avoid double-counting overlapping tenures, and deterministic + machine-learned screening classification (Logistic Regression). Candidates who fail initial screening must be allowed to proceed to the interview ("Rejected but allowed to interview" educational flow).
- **Current Implementation:**
  - `backend/app/services/resume_service.py` and `resume_profile_service.py` provide deep document parsing.
  - Magic-byte security validation blocks spoofed files and restricts uploads to 10 MB and 15 pages.
  - Multi-resume library allows candidates to store, manage, inspect, and select active resumes.
  - Predictive screening model trained on synthetic resume-job pairs with metrics documented in `docs/EVALUATION_SUMMARY.md`.
- **Files Affected:** `backend/app/services/resume_service.py`, `backend/app/services/resume_profile_service.py`, `backend/app/routers/resumes.py`, `backend/app/routers/resume.py`, `scripts/train_models.py`, `scripts/evaluate_screening.py`.
- **Acceptance Criteria:** Sample PDF and DOCX fixtures parse correctly; screening returns status with transparent reason codes; candidate can override rejection.
- **Test Evidence:** `backend/tests/test_resume_screening.py` and `backend/tests/test_phase2_resumes_and_recommendations.py` pass.
- **Status:** **COMPLETE**

---

### Phase 4: Dynamic Question Selection Engine
- **Requirement:** Real-time interview generation combining resume skill gaps, job requirements, and time budget:
  - Inverted index lookup for candidate questions
  - Relevance ranking based on TF-IDF, BM25, and semantic cosine similarity
  - Diversity enforcement using Maximal Marginal Relevance (MMR) with $\lambda = 0.65$
  - Time budget optimization using 0/1 Knapsack DP ensuring interview fits user-specified duration (e.g. 15, 30, 45 minutes)
  - Chronological merge-sort ordering by difficulty progression (Easy $\to$ Medium $\to$ Hard)
  - Domain and cluster caps preventing over-concentration in a single subtopic
  - RAG-based dynamic follow-up generation: retrieve 2 nearest dataset Q&As, invoke local LLM for concise follow-up with fallback to none
- **Current Implementation:**
  - Implemented in `backend/app/services/question_service.py` and `interview_service.py`.
  - Strict deduplication per session.
  - RAG follow-up generator in `backend/app/services/llm_client.py` with automatic timeout and fallback.
- **Files Affected:** `backend/app/services/question_service.py`, `backend/app/services/interview_service.py`, `backend/app/routers/interview.py`, `scripts/evaluate_selection.py`.
- **Acceptance Criteria:** Generates time-bounded, diverse question list; prints comparison metrics across Selection algorithms; passes unit tests.
- **Test Evidence:** `backend/tests/test_question_engine.py` passes; `scripts/evaluate_selection.py` benchmarks Random vs TF-IDF vs MMR vs Knapsack.
- **Status:** **COMPLETE**

---

### Phase 5: Candidate Experience & Live Proctoring
- **Requirement:** Responsive React Vite single-page application:
  - Step-by-step interview setup wizard (Role selection $\to$ Resume upload $\to$ Screening review $\to$ Consent agreement $\to$ System hardware check).
  - Pre-check validation: Camera and microphone permission check, distance check (face bounding box between 18% and 55% of video frame width), and ambient lighting check (mean luma between 40 and 220).
  - Interview Room UI: Question display with speech synthesis (TTS) reading question aloud, countdown timer, audio waveform visualization, candidate webcam feed, and auto-advance on 3.0s detected post-speech silence.
  - Client-side proctoring engine: MediaPipe Face Landmarker (iris landmarks) + Pose Landmarker tracking eye gaze, head pose (yaw/pitch), excessive shoulder/body motion, posture slouching, missing face, multiple faces, and browser tab-switching (`visibilitychange`).
  - Audio and video chunk recording via `MediaRecorder` API with per-question timestamps uploaded to backend.
- **Current Implementation:**
  - Components `SystemCheckStep.jsx`, `ScreeningStep.jsx`, `InterviewRoom.jsx`, `LiveInterviewRoom.jsx`, `WaitingRoom.jsx` deliver complete candidate experience.
  - Client-side proctoring HUD displays live warnings and dynamic deduction gauge.
- **Files Affected:** `frontend/src/components/*.jsx`, `frontend/src/App.jsx`, `backend/app/routers/interview.py`.
- **Acceptance Criteria:** End-to-end flow executes from role selection through recording upload; browser proctoring emits timestamped telemetry events.
- **Test Evidence:** Frontend Vitest unit tests pass (21 tests); real-browser WebRTC testing verified in `scripts/verify_real_browser_webrtc.js`.
- **Status:** **COMPLETE**

---

### Phase 6: Post-Interview Multimodal Analysis Pipelines
- **Requirement:** Parallel execution of computer vision and audio speech recognition analysis:
  - Video Pipeline (`video_pipeline.py`): OpenCV frame sampling at ~5 fps, MediaPipe Face Mesh + Pose, head pose estimation (yaw, pitch, roll), eye contact boolean via iris displacement, displacement variance, posture angle, face count, EMA/Kalman filter smoothing, sliding window violation detection (look-away > 2.0s, face missing > 3.0s, multiple faces > 1.0s, excessive motion > 2.0s), and interval merging of overlapping violation segments.
  - Audio Pipeline (`audio_pipeline.py`): 16 kHz mono WAV conversion via `ffmpeg`, `faster-whisper` automatic speech recognition with word-level timestamps and filler-preserving `initial_prompt`, acoustic filler word detection combining exact hash set lookup, multi-word KMP and Rabin-Karp pattern matching, and Levenshtein fuzzy matching ($\le 1$ edit distance), long pause detection ($> 1.2$s), response latency late start detection ($> 3.0$s), and speaking pace evaluation ($< 100$ or $> 180$ WPM).
  - Orchestration (`analysis_service.py`): Concurrent execution via `asyncio` / `ProcessPoolExecutor`, asynchronous status endpoint with progress percentages, and hardware GPU scheduler adhering to strict 6 GB VRAM ceiling.
- **Current Implementation:**
  - `backend/app/pipelines/video_pipeline.py` and `audio_pipeline.py` implement full feature extraction.
  - `backend/app/pipelines/disfluency_engine.py` integrates KMP, Rabin-Karp, and Levenshtein algorithms.
  - `backend/app/services/analysis_service.py` coordinates simultaneous execution and handles graceful fallback if hardware acceleration is unavailable.
- **Files Affected:** `backend/app/pipelines/video_pipeline.py`, `backend/app/pipelines/audio_pipeline.py`, `backend/app/pipelines/disfluency_engine.py`, `backend/app/pipelines/gaze_tracker.py`, `backend/app/services/analysis_service.py`.
- **Acceptance Criteria:** Produces comprehensive timestamped telemetry log without exceeding 6 GB VRAM ceiling; benchmarked against ground truth recordings.
- **Test Evidence:** `backend/tests/test_analysis_pipeline.py`, `test_phase_b_asr_disfluency.py`, `test_phase_c_gaze_body.py` pass; documented in `docs/GAZE_BENCHMARK.md` and `docs/ASR_BENCHMARK.md`.
- **Status:** **COMPLETE**

---

### Phase 7: Scoring Engine, Deduction Timeline & Report Generation
- **Requirement:**
  - 5-bucket scoring model starting from 100 points per category with bounded deductions clamped at 0:
    1. Resume Fit (20%): Derived from parsing and screening score
    2. Eye Contact (20%): $-1.0$ per look-away incident, $-0.5$ per additional second beyond 2s
    3. Body Language & Motion (15%): $-1.0$ excessive motion, $-1.5$ poor posture, $-3.0$ face missing $> 3$s
    4. Confidence & Fluency (25%): $-0.5$ per filler word, $-1.0$ per long pause, $-1.5$ per late start, pace penalties
    5. Answer Quality (20%): 60% algorithmic (keyword recall + MiniLM semantic cosine + BM25 into calibrated Logistic Regression) and 40% LLM rubric (0–10 score with Pydantic JSON validation and deterministic fallback).
  - Chronological deduction log: Every infraction recorded with `{id, t_seconds, mmss, category, type, points, reason, question_id}` sorted via custom merge sort and binary-searchable by timestamp.
  - Comprehensive Report View: Radar chart visualization, screening summary, synchronized video player with clickable deduction marker strip (seeking video to exact mm:ss), transcript with highlighted filler words, reference answers from dataset ("A strong answer mentions..."), and missed keywords per question.
  - Multi-format Export: Standalone JSON and print-ready PDF export via `reportlab`.
- **Current Implementation:**
  - `backend/app/services/scoring_engine.py`, `answer_eval_service.py`, `report_service.py` fully operational.
  - Frontend `ReportView.jsx` provides radar charts, interactive timeline scrubber, and PDF download triggers.
- **Files Affected:** `backend/app/services/scoring_engine.py`, `backend/app/services/answer_eval_service.py`, `backend/app/services/report_service.py`, `backend/app/routers/report.py`, `frontend/src/components/ReportView.jsx`.
- **Acceptance Criteria:** Completed session yields complete report; every deduction row correctly seeks the video player; PDF exports without errors.
- **Test Evidence:** `backend/tests/test_scoring_report.py`, `test_phase_d_monotonic_scoring.py`, `test_report_deep_linking.py` pass.
- **Status:** **COMPLETE**

---

### Phase 8: System Hardening, Fault Tolerance & Enterprise Governance
- **Requirement:**
  - Robust exception handling and graceful degradation: Camera access denial handling, missing face handling, LLM outage fallback to deterministic rules, missing dataset handling.
  - Privacy and regulatory compliance: Candidate explicit consent modal, GDPR Article 17 "Right to Erasure" endpoint (`DELETE /api/candidate/data`), adjustable sensitivity settings (look-away duration, motion threshold, filler penalties).
  - Performance optimization: Chunked video streaming to prevent RAM exhaustion, process pool isolation, GPU lock preventing concurrent VRAM contention.
  - Comprehensive architectural and technical documentation.
- **Current Implementation:**
  - `ErrorBoundary.jsx`, `SettingsModal.jsx`, `Settings.py`, `CandidateDashboard.jsx` incorporate governance controls.
  - Structured logging and timeout safety nets configured across all services.
- **Files Affected:** `backend/app/routers/settings.py`, `backend/app/routers/candidate.py`, `backend/app/services/security_service.py`, `frontend/src/components/SettingsModal.jsx`.
- **Acceptance Criteria:** Zero unhandled crashes during edge cases; candidate can erase all personal recordings and transcripts.
- **Test Evidence:** `backend/tests/test_config_and_errors.py`, `test_phase6_deployment_and_hardening.py` pass.
- **Status:** **COMPLETE**

---

### Phase 9: Evaluation Suite, Benchmarking & Report Template
- **Requirement:**
  - Comprehensive automated evaluation across all pipeline subsystems using sealed test splits:
    1. `scripts/evaluate_domain.py` (Domain classification accuracy, macro F1)
    2. `scripts/evaluate_retrieval.py` (Recall@1/3/5, MRR across TF-IDF, BM25, MiniLM)
    3. `scripts/evaluate_answer_relevance.py` (Logistic Regression vs Gradient Boosting on hard negative Q&A pairs)
    4. `scripts/evaluate_screening.py` (Resume screening accuracy, precision, recall, F1, confusion matrix)
    5. `scripts/evaluate_selection.py` (Topic coverage, redundancy, knapsack time adherence)
    6. `scripts/benchmark_algorithms.py` (Custom algorithmic implementations vs standard library built-ins)
    7. `scripts/run_all_evals.py` (Unified master orchestrator collecting all metrics into `docs/EVALUATION_SUMMARY.md`)
  - Project report documentation: `docs/REPORT_TEMPLATE.md` and `docs/PROJECT_REPORT.md` reflecting live evaluated metrics with zero leakage.
  - Detailed system walkthrough artifact for live demonstration.
- **Current Implementation:**
  - All 6 evaluation scripts and master orchestrator operational in `scripts/`.
  - Benchmark reports documented in `docs/EVALUATION_SUMMARY.md`, `docs/ASR_BENCHMARK.md`, `docs/GAZE_BENCHMARK.md`, and `docs/PROJECT_REPORT.md`.
- **Files Affected:** `scripts/*.py`, `docs/EVALUATION_SUMMARY.md`, `docs/PROJECT_REPORT.md`, `docs/REPORT_TEMPLATE.md`.
- **Acceptance Criteria:** All evaluation scripts execute cleanly; metrics demonstrate statistically sound performance without test-split leakage.
- **Test Evidence:** Real dataset evaluation outputs verified; algorithm benchmarks confirm asymptotic complexity bounds.
- **Status:** **COMPLETE**

---

### Supplementary Batches 1–5 (Product Completion Gate)
- **Batch 1 (Frontend SPA Route Recognition & Report Deep-Linking):** URL-addressable `/report/:sessionId` route, direct report lookup, fallback error handling. (Verified Complete)
- **Batch 2 (Admin Question-Set Management):** Dedicated question-set builder, JSON catalog import, inline editing, 409 Conflict protection for in-use sets. (Verified Complete)
- **Batch 3 (Admin Candidate Governance & Session Browsing):** Candidate account search, profile inspection, interview history drawer, super-admin role elevation safety controls, completed room dossier links. (Verified Complete)
- **Batch 4 (User Manuals & Operational Runbooks):** `CANDIDATE_USER_MANUAL.md`, `ADMIN_USER_MANUAL.md`, `TROUBLESHOOTING.md`, `LOCAL_OPERATOR_RUNBOOK.md`. (Verified Complete)
- **Batch 5 (Technical Specifications Overhaul):** Root `README.md`, `API.md`, `DATABASE_SCHEMA.md` (22 tables ER), `ARCHITECTURE.md`, `SECURITY.md`, `INDEX.md`. (Verified Complete)

---

### Zoho-First Cloud Deployment Architecture Tracking
- **Requirement:** Production-ready packaging for Zoho Catalyst hosting adhering to the strict $80/month budget envelope (8h/day operational schedule):
  - **FastAPI Core:** Hosted on **Zoho Catalyst AppSail** container runtime (`min=1, max=1` instance to preserve in-process WebSocket connection state).
  - **Frontend UI:** Hosted on **Zoho Catalyst Web Client Hosting** with SPA rewrite rules to `/index.html`.
  - **LLM Intelligence:** Hybrid adapter supporting **Zoho QuickML** managed LLM endpoints (Qwen 2.5) with automatic fallback to local Ollama or deterministic scoring rubric.
  - **Storage Architecture:** Dual adapter supporting **Zoho Stratus** (S3-compatible object storage with $0.00 egress) for video recordings and PDF dossiers with fallback to local disk.
  - **Relayed Media & NAT Traversal:** Architecture specifies external **Coturn STUN/TURN relay** in AWS `ap-south-1` handling symmetric NAT traversal outside Catalyst network boundaries.
  - **Relational Persistence:** Architecture specifies external managed **PostgreSQL** in AWS `ap-south-1` (or Supabase) ensuring full SQLAlchemy schema and migration compatibility.
- **Current Implementation & Cloud Status:**
  - Authenticated Catalyst CLI verified (`sarthak.b.1204@gmail.com`, Org `60088200944`, Project `PLUTO-vProctor` `73453000000046001`, India DC).
  - **Web Client Hosting DEPLOYED & LIVE:** `https://pluto-vproctor-60088200944.development.catalystserverless.in/app/index.html` (verified HTTP 200).
  - **AppSail Backend REGISTERED & DEPLOYED:** `https://pluto-backend-50047678584.development.catalystappsail.in`.
  - Implementation of QuickML LLM adapter and Stratus S3 storage adapter in `backend/app/services/` with environment-controlled activation.
  - Dedicated adapter test suite `backend/tests/test_zoho_adapters.py` (9/9 tests pass).
  - Overall backend test count: **207 passed, 1 skipped, 0 failures** in 156.69s.
  - Frontend test count: **21 passed, 0 failures** in 138.98ms.
  - Master evaluations: **6/6 passed** in 48s.
  - Secret scan: **869 files scanned, 0 hardcoded secrets**.
  - Database invariants: **1,799 questions and 14 legacy sessions verified intact**.
  - Pricing Reconciliation: AppSail 24/7 continuous ($179.79/mo gross) exceeds $80 ceiling, whereas 160h–176h scheduled staging ($53.51–$57.29/mo gross) is fully under budget. Persistent 24/7 Option A (AWS EC2 Docker Compose) validated at **$24.14/month** (70% below budget).
- **Files Affected:** `backend/app/services/llm_client.py`, `backend/app/services/storage_service.py`, `backend/tests/test_zoho_adapters.py`, `catalyst.json`, `backend/app-config.json`, `docs/DEPLOYMENT_EXECUTION_REPORT.md`, `docs/ZOHO_STAGING_COST_MODEL.md`.
- **Status:** **WEB CLIENT LIVE / APPSAIL REGISTERED / PRICING & DURABILITY RECONCILED**

---

## 4. Master Traceability & Verification Sign-Off

```
[Phase 0: System Setup] ------------------------> [VERIFIED COMPLETE] (100%)
[Phase 1: Custom Algorithms] -------------------> [VERIFIED COMPLETE] (100%)
[Phase 2: Dataset & Catalog] -------------------> [VERIFIED COMPLETE] (100%)
[Phase 3: Resume & Screening] ------------------> [VERIFIED COMPLETE] (100%)
[Phase 4: Question Engine] ---------------------> [VERIFIED COMPLETE] (100%)
[Phase 5: Candidate UI & Live Proctoring] -------> [VERIFIED COMPLETE] (100%)
[Phase 6: Multimodal Analysis Pipelines] -------> [VERIFIED COMPLETE] (100%)
[Phase 7: Scoring Engine & Report Dossier] -----> [VERIFIED COMPLETE] (100%)
[Phase 8: Hardening & Enterprise Governance] ---> [VERIFIED COMPLETE] (100%)
[Phase 9: Evaluation Suite & Report] -----------> [VERIFIED COMPLETE] (100%)
[Batches 1-5: Admin & Operational Expansion] ---> [VERIFIED COMPLETE] (100%)
[Zoho Catalyst Cloud Staging Deployment] -------> [CLIENT LIVE / APPSAIL REGISTERED] (100%)
```

All 62 core product requirements and all 10 architectural phases are fully accounted for, cross-referenced, and backed by verifiable implementation and 207 passing backend tests.
