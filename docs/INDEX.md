# PLUTO vProctor — Master Documentation Index & Knowledge Map

**Document Version:** 1.0  
**Product Version:** 0.1.0  
**Platform:** Multimodal AI Video Interview & Proctoring Platform  
**Last Updated:** November 2026  

---

## 1. Quick Navigation & Roles

PLUTO vProctor's documentation suite is organized by user persona and technical domain:

```text
[ PLUTO vProctor Documentation Suite ]
├── 1. User & Operator Manuals (Candidates, Admins, Local Operators)
├── 2. Technical Specifications (Architecture, API, Database Schema, Security)
├── 3. Scientific Benchmarks & AI Methodology (Algorithms, Scoring, Gaze, ASR)
├── 4. Quality Gates & Implementation History (Phases 1-6 & Batches 1-5 Reports)
├── 5. Audits, Limitations & Release Verification (Checklist, Audit, Backlog)
└── 6. Deployment Readiness & Cloud Architecture (Secret Scan, Dependency Inventory, Config, Readiness)
```

---

## 2. User & Operational Manuals

Practical step-by-step documentation for users and platform maintainers:

| Document | Target Audience | Primary Focus & Description |
|---|---|---|
| **[Candidate User Manual](file:///D:/_TY/MDM/PLUTO-vProctor/docs/CANDIDATE_USER_MANUAL.md)** | Job Candidates, Students, Practice Learners | Complete 20-section guide: account registration, profile management, resume upload, universal recommendations, 7-step self-practice wizard, hosted recruiter rooms, proctoring guidelines, scoring dossiers, PDF export, and privacy rights. |
| **[Administrator User Manual](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ADMIN_USER_MANUAL.md)** | Recruiters, Examiners, System Administrators | 25-section operational guide: dedicated admin login (`/admin/login`), candidate governance, search/filter, candidate details & resume inspection, session history, super-admin safeguards, full question-set lifecycle (create, edit, delete, JSON import), room scheduling, live controls (advance, skip, pause, resume, end), completed room evaluation access, and inline video playback. |
| **[Troubleshooting Guide](file:///D:/_TY/MDM/PLUTO-vProctor/docs/TROUBLESHOOTING.md)** | Technical Support, Operators, Developers | Diagnostic guide organized into 6 operational categories (Installation, Auth/RBAC, Resumes, Interviews/Telemetry, AI Models, Reports/Question Sets) with Symptoms, Likely Causes, Diagnostic Steps, Safe Resolutions, and File Paths. |
| **[Local Operator Runbook](file:///D:/_TY/MDM/PLUTO-vProctor/docs/LOCAL_OPERATOR_RUNBOOK.md)** | Platform Operators, Evaluators | Runbook for Windows execution: environment setup, directory layout, `.env` config, schema initialization, `run_dev.bat` startup, health checks (`/api/health`, `/api/ready`), Ollama/Whisper model management, atomic SQLite backups, media backups, disaster recovery, and shutdown. |

---

## 3. Core Technical Specifications

Formal system engineering specifications:

| Document | Scope | Description |
|---|---|---|
| **[System Architecture](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ARCHITECTURE.md)** | Full System Architecture | Complete v2 system architecture detailing frontend, FastAPI gateway, 14 routers, WebRTC signaling, MediaPipe iris/head pose pipeline, Faster-Whisper disfluency pipeline, 4-bucket monotonic scoring, and 5 Mermaid flowcharts. |
| **[API Reference Specification](file:///D:/_TY/MDM/PLUTO-vProctor/docs/API.md)** | REST & WebSocket Interfaces | Comprehensive reference documenting all 60+ REST endpoints and the real-time WebRTC WebSocket signaling hub (`/api/rooms/{id}/ws`), including request payloads, response schemas, error codes, and RBAC rules. |
| **[Database Schema & ER Specification](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DATABASE_SCHEMA.md)** | Persistence Layer | Complete 22-table reference with column types, primary keys, foreign keys, unique constraints, nullability, indices, deletion cascades, and an accurate Mermaid ER diagram. |
| **[Security & Threat Model](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SECURITY.md)** | Platform Security | Detailed specification of 14 security domains: Argon2id hashing, 15-min JWT, refresh token rotation with reuse detection, double-submit CSRF, RBAC, IDOR prevention, admin safety locks, magic-byte upload validation, rate limits, and audit logs. |
| **[Known Limitations](file:///D:/_TY/MDM/PLUTO-vProctor/docs/KNOWN_LIMITATIONS.md)** | Engineering Boundaries | Documents current boundaries: local Windows execution, desktop-only video proctoring, in-memory rate limiting, and future PostgreSQL deployment requirements. |

---

## 4. Scientific Benchmarks & AI Methodology

Underlying machine learning benchmarks, scoring mathematics, and fairness evaluations:

| Document | Subject | Description |
|---|---|---|
| **[Algorithms Specification](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ALGORITHMS.md)** | Core Algorithmic Library | Mathematical specification of Trie prefix search, 0/1 Knapsack duration budgeting, MMR diversification, BM25 keyword matching, MinHash Jaccard similarity, and Levenshtein edit distance. |
| **[Scoring Methodology](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SCORING.md)** | 4-Bucket Scoring Engine | Detailed rubric weighting: Technical Depth (35%), Communication (25%), Proctoring Integrity (25%), and Resume Relevance (15%), plus monotonic timeline deduction math. |
| **[Gaze Benchmark](file:///D:/_TY/MDM/PLUTO-vProctor/docs/GAZE_BENCHMARK.md)** | Computer Vision Accuracy | Benchmark report on MediaPipe Tasks Vision FaceLandmarker (478 landmarks), iris vector angle calculation, and One-Euro jitter filter performance. |
| **[ASR Benchmark](file:///D:/_TY/MDM/PLUTO-vProctor/docs/ASR_BENCHMARK.md)** | Speech-to-Text Performance | Benchmark comparison of local Faster-Whisper (CPU int8) vs Deepgram and AssemblyAI, measuring word error rates and inference latency. |
| **[Fairness & Bias Evaluation](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FAIRNESS.md)** | Ethical AI & Bias Auditing | Audits demographic parity, lighting invariance, accent robustness, and neutral baseline subtraction to eliminate hardware bias. |
| **[Dataset & Catalog Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DATASET_REPORT.md)** | Technical Question Catalog | Statistical analysis of the 1,799 verified interview questions across domains, difficulties, estimated durations, and skill clusters. |

---

## 5. Implementation Reports & Quality Gates

Historical development records and autonomous verification logs:

### Phase 1–6 Foundation Reports:
- **[Phase 1 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_1_IMPLEMENTATION_REPORT.md):** Algorithmic foundation, Knapsack MMR, and dataset ingestion.
- **[Phase 2 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_2_IMPLEMENTATION_REPORT.md):** Multimodal pipelines, Faster-Whisper ASR, and MediaPipe face mesh.
- **[Phase 3 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_3_IMPLEMENTATION_REPORT.md):** Candidate authentication, profiles, and multi-resume library.
- **[Phase 4 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_4_IMPLEMENTATION_REPORT.md):** Real-time hosted rooms, WebRTC signaling, and lobby orchestration.
- **[Phase 5 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_5_IMPLEMENTATION_REPORT.md):** Universal job recommendations, learning roadmaps, and admin analytics.
- **[Phase 6 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PHASE_6_IMPLEMENTATION_REPORT.md):** Production hardening, security headers, rate limiting, and GDPR deletion.

### Product Completion Batches:
- **[Batch 1 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/BATCH_1_IMPLEMENTATION_REPORT.md):** Report routing, deep linking (`/report/:sessionId`), and IDOR protection.
- **[Batch 2 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/BATCH_2_IMPLEMENTATION_REPORT.md):** Complete admin question-set lifecycle: array parsing, interactive builder, edit modal, 409 conflict-safe delete, and JSON file import.
- **[Batch 3 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/BATCH_3_IMPLEMENTATION_REPORT.md):** Admin candidate governance, search/filter, candidate details & resumes modal, session history drawer, super-admin role modification safeguards, completed room report access, and global completed interview browser.
- **[Batch 4 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/BATCH_4_IMPLEMENTATION_REPORT.md):** Authoring Candidate User Manual, Admin User Manual, Troubleshooting Guide, and Local Operator Runbook.
- **[Batch 5 Implementation Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/BATCH_5_IMPLEMENTATION_REPORT.md):** Technical specification documentation overhaul, README rewrite, API reference, Database Schema ER, Security architecture, and Master Documentation Index.

---

## 6. Audit & Release Verification

- **[Final Release Candidate Audit](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_RELEASE_CANDIDATE_AUDIT.md):** Definitive post-Batch 5 release-readiness review classifying all subsystems and recommending graduation to controlled deployment testing.
- **[Final Product Completion Audit](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_PRODUCT_COMPLETION_AUDIT.md):** Comprehensive 62-point audit verifying candidate experience, administrative capabilities, interview functionality, AI intelligence, security, and documentation.
- **[Final Product Completion Backlog](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_PRODUCT_COMPLETION_BACKLOG.md):** Implementation roadmap tracking all five approved remediation batches through completion.
- **[Final Verification Checklist](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_VERIFICATION_CHECKLIST.md):** Quality gate checklist verifying all 198 backend tests and 21 frontend tests.
- **[Final Project Release Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/FINAL_PROJECT_RELEASE_REPORT.md):** Executive release summary certifying product completeness for local development.

---

## 7. Deployment Readiness & Cloud Architecture

Pre-deployment verification, runtime dependencies, configuration references, and cloud feasibility assessments:

| Document | Target Audience | Primary Focus & Description |
|---|---|---|
| **[Secret Scanning Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SECRET_SCAN_REPORT.md)** | Security Engineers, DevOps, Compliance | Investigation of previous exit code 1 (PowerShell parser error), deep scan of 824 files via [scripts/scan_secrets.py](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/scan_secrets.py), classification of 2 synthetic test fixtures, confirmation of 0 live secrets, and cloud secret injection guidelines. |
| **[Deployment Dependency Inventory](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_DEPENDENCY_INVENTORY.md)** | Infrastructure Engineers, Cloud Architects | Complete technical breakdown of all 14 runtime components (Frontend, FastAPI, PostgreSQL, Redis, Worker, Ollama, Qwen2.5:3b, Faster-Whisper, MediaPipe, FFmpeg, Recording Storage, Resume Storage, WebRTC Signaling, STUN/TURN) with compute, storage, network boundaries, and failure impacts. |
| **[Deployment Configuration Reference](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_CONFIGURATION_REFERENCE.md)** | System Administrators, Site Reliability Engineers | Exhaustive reference of all environment variables from `Settings` and `.env.example`, categorized by Mandatory, Feature Flags, Optional, and Dev-only, plus production `.env` template and fail-fast validation behavior. |
| **[Pre-Deployment Readiness Report](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PRE_DEPLOYMENT_READINESS_REPORT.md)** | Engineering Leadership, Cloud Architects | Cloud compatibility assessment across AWS (100% native), Zoho Catalyst (severe ORM/GPU constraints), and Hybrid AWS + Zoho; subsystem classification (managed vs. dedicated vs. persistent); and recommended 2-phase AWS rollout architecture. |

