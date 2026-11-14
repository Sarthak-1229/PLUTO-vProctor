# PLUTO vProctor — Final Product Completion Backlog

**Project:** PLUTO vProctor  
**Date:** 2026-11-14  
**Purpose:** Actionable, prioritized implementation batches to resolve all partial and missing items identified in the Final Product Completion Audit.  
**Constraint:** Deployment is explicitly out of scope. Work is strictly confined to local application completion, UI connectivity, and documentation.

---

## Batch Overview & Execution Roadmap

```
+-----------------------------------------------------------------------------------+
|                        BATCH 1: Routing & Deep-Linking Fixes                      |
|         (Report URL routing, SPA direct link resolution, live room report link)   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                  BATCH 2: Admin Question Sets Management Completion               |
|      (Array response fix, DELETE UI, PUT endpoint & edit modal, JSON file import) |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               BATCH 3: Admin Candidate Governance & Session Browser               |
|   (User search/filter, role update UI, completed room report link, session browser)|
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                  BATCH 4: Core User Manuals & Operational Guides                  |
|          (Candidate User Manual, Admin User Manual, Troubleshooting Runbook)      |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|              BATCH 5: Technical Specification Documentation Updates               |
|        (Updated API.md, Updated README.md, Database Schema ERD, Security.md)      |
+-----------------------------------------------------------------------------------+
```

---

## Batch 1: Frontend Routing & Report Deep-Linking Remediation

**Priority:** **CRITICAL / HIGH**  
**Estimated Effort:** ~1.5 hours  
**Status:** **COMPLETED** (Verified via unit & integration tests)  
**Prerequisites:** None  

### Objectives
Resolve the defect where navigating directly to or refreshing on `/report/:sessionId` drops the user into Step 1 (Role Selection) instead of opening the forensic dossier report.

### Tasks
- [x] **1.1 Update Route Guard (`frontend/src/utils/authClient.js`):**
  - Add pattern matching for `/report/:sessionId` in `resolveRouteAccess`.
  - Return `{ allowed: true, redirectTo: null, view: 'report', sessionId: matchedId }`.
  - Enforce authentication if `authEnabled=True` (redirecting unauthenticated users to `/login`).
- [x] **1.2 Mount Report View in SPA Root (`frontend/src/App.jsx`):**
  - Handle `routeGuard.view === 'report'`.
  - Fetch `/api/report/${routeGuard.sessionId}` on mount if not cached.
  - Render `StandaloneReportContainer` with loading state, 403 Access Denied, 404 Not Found, and `ReportView` presentation.
- [x] **1.3 Fix Live Room Navigation (`frontend/src/components/LiveInterviewRoom.jsx`):**
  - Updated line 710 to trigger internal SPA client navigation (`onNavigate('/report/' + snapshot.active_session_id)`) while preserving href for new tabs.
- [x] **1.4 Verification:**
  - Automated tests in `frontend/tests/test_auth_routing.js` verify route parsing and RBAC across candidates, admins, offline, and error paths.
  - Automated integration tests in `backend/tests/test_report_deep_linking.py` verify 200 OK for own report, 403 Forbidden for IDOR attempts, 401 Unauthorized, and 404 Not Found.

---

## Batch 2: Admin Question-Sets Management Completion

**Priority:** **HIGH**  
**Estimated Effort:** ~2.5 hours  
**Status:** **COMPLETED** (Verified via unit & integration tests)  
**Prerequisites:** None  

### Objectives
Fix the response shape mismatch that currently prevents existing question sets from rendering, and implement complete lifecycle management (Delete, Edit, and File Import).

### Tasks
- [x] **2.1 Fix Array Response Parsing (`frontend/src/components/AdminRoomManager.jsx`):**
  - Reconciled response shape in `loadRoomsAndSets()` using `parseQuestionSetsResponse()` supporting both direct array `[...]` and `{ question_sets: [...] }`.
  - Populates dropdown and list immediately upon load.
- [x] **2.2 Implement Delete Question Set UI Action (`frontend/src/components/AdminRoomManager.jsx`):**
  - Added trash icon button and confirmation dialog.
  - Returns 409 Conflict if active rooms are in progress.
  - Safely nullifies FK on past rooms without deleting historical room records or copied questions.
- [x] **2.3 Implement Backend Update Endpoint (`backend/app/routers/question_sets.py`):**
  - Added `PUT /api/admin/question-sets/{qset_id}` accepting updated name, description, and items.
  - Implemented `update_question_set()` in `question_set_service.py` with payload validation, checksum recomputation, version bump, and audit logging.
- [x] **2.4 Implement Edit Question Set UI Modal (`frontend/src/components/AdminRoomManager.jsx`):**
  - Added edit icon button on question set cards.
  - Opens modal with pre-filled name, description, and interactive questions builder for easy modification.
- [x] **2.5 Add Question Set JSON File Import (`frontend/src/components/AdminRoomManager.jsx`):**
  - Added JSON file picker and Import Preview Modal.
  - Validates syntax, validates question structures, and allows name/description adjustments before final commit.
- [x] **2.6 Verification:**
  - Automated integration tests in `backend/tests/test_question_sets_management.py` (8 passed).
  - Automated frontend unit tests in `frontend/tests/test_question_sets.js` (10 passed, total 21 passed).
  - Production build and lint passed.

---

## Batch 3: Admin Candidate Governance & Completed Interviews Browser

**Priority:** **HIGH**  
**Estimated Effort:** ~2.5 hours  
**Prerequisites:** Batch 1 (for report links)  
**Status:** **COMPLETED** (Report: `docs/BATCH_3_IMPLEMENTATION_REPORT.md`)

### Objectives
Empower administrators to govern accounts, search candidates, adjust roles, and browse all completed interviews across the platform.

### Tasks
- [x] **3.1 Search & Filter in Accounts Tab (`frontend/src/components/AdminConsolePage.jsx`):**
  - Added live search input filtering users by name or email.
  - Added role filter dropdown (`all`, `candidate`, `admin`, `super_admin`).
- [x] **3.2 User Role Management UI (`frontend/src/components/AdminConsolePage.jsx`):**
  - Added role modification modal restricted to super admins.
  - Requires justification reason (>= 5 chars) and explicit confirmation before dispatching `POST /api/admin/users/{uid}/role`.
  - Enforced server-side checks: self-demotion blocked, last active admin protection, last active super admin protection, and full audit logging.
- [x] **3.3 Candidate History & Details Inspection (`frontend/src/components/AdminConsolePage.jsx`):**
  - Added "Inspect" button opening candidate details modal with profile info and uploaded resumes (`GET /api/admin/users/{uid}`).
  - Added "History" button opening interview session history modal with mode badges, scores, direct report links, and recording playback (`GET /api/admin/users/{uid}/history`).
- [x] **3.4 Completed Room Report Link in Room Manager (`frontend/src/components/AdminRoomManager.jsx`):**
  - When `room.status === 'COMPLETED'`, renders rich conclusion banner with candidate info, score, and grade.
  - Added "View Evaluation Report" button (`/report/${room.active_session_id}`).
  - Added "PDF Dossier" link (`/api/report/${room.active_session_id}/pdf`).
  - Added "Play Recording" button opening inline modal video player.
- [x] **3.5 All Completed Sessions Browser (`frontend/src/components/AdminConsolePage.jsx`):**
  - Added "Completed Interviews" browser tab querying `GET /api/admin/interviews`.
  - Supports search, mode filter (`all`, `hosted`, `self_practice`), score badge, direct report deep-linking, and inline video playback.
- [x] **3.6 Verification:**
  - Automated integration tests in `backend/tests/test_candidate_governance_and_completed_rooms.py` (9 passed).
  - Full backend test suite passing (198 passed, 1 skipped).
  - Frontend unit tests (21 passed), linter (0 errors), and production build passing.

---

## Batch 4: Core User Manuals & Operational Runbooks

**Priority:** **HIGH**  
**Estimated Effort:** ~2.5 hours  
**Prerequisites:** None  
**Status:** **COMPLETED** (Report: `docs/BATCH_4_IMPLEMENTATION_REPORT.md`)

### Objectives
Create complete, comprehensive, and professional user documentation for candidate, administrator, and local operator personas, plus an operational troubleshooting guide.

### Tasks
- [x] **4.1 Author Candidate User Manual (`docs/CANDIDATE_USER_MANUAL.md`):**
  - 20 sections covering: account registration, login, profile editing, multi-resume library, universal recommendations, 7-step self-practice wizard, hosted room joining, permissions, proctoring guidelines, scoring dossiers, PDF export, roadmaps, candidate dashboard, troubleshooting, and GDPR data erasure.
- [x] **4.2 Author Admin User Manual (`docs/ADMIN_USER_MANUAL.md`):**
  - 25 sections covering: RBAC tiers (`candidate`, `admin`, `super_admin`), dedicated admin login (`/admin/login`), candidate governance, search/filter, profile/resume inspection, session histories, super-admin role modification safeguards, full question-set lifecycle (create, edit, 409 conflict-safe delete, JSON import), room scheduling, candidate invitation tokens, live interview controls (advance, skip, pause, resume, end), completed room evaluation access, inline recording playback, platform analytics, and audit logs.
- [x] **4.3 Author Operational Troubleshooting Guide (`docs/TROUBLESHOOTING.md`):**
  - Detailed diagnostic guide covering 6 major categories: Installation & Startup, Authentication & RBAC, Resumes & Recommendations, Interviews & Telemetry, AI Models & Ollama, Reports & Question Sets.
  - Formatted with Symptoms, Likely Causes, Diagnostic Steps, Safe Resolutions, and Relevant File Paths.
- [x] **4.4 Author Local Operator Runbook (`docs/LOCAL_OPERATOR_RUNBOOK.md`):**
  - Comprehensive guide covering local Windows setup, directory structure, `.env` configuration, database initialization and integrity checks, `run_dev.bat` startup, health probes, Ollama & Faster-Whisper lifecycle, structured logs, atomic database backups, media storage backups, disaster recovery recipes, safe shutdown, and SQLite vs PostgreSQL architectural reference.

---

## Batch 5: Technical Specification Documentation Updates

**Priority:** **MEDIUM**  
**Estimated Effort:** ~2.0 hours  
**Prerequisites:** None  
**Status:** **COMPLETED** (Report: `docs/BATCH_5_IMPLEMENTATION_REPORT.md`)

### Objectives
Update all technical reference documentation so that developers, auditors, and future contributors have exact, up-to-date specifications of the v2 platform.

### Tasks
- [x] **5.1 Update Project README (`README.md`):**
  - Completely overhauled root README with 18 detailed sections covering dual-mode operations, candidate/admin workflows, tech stack, architecture flowchart, local Windows installation, `.env` config, catalog verification, AI setup, automated test commands, directory layout, documentation index, and known limitations.
- [x] **5.2 Update API Reference Specification (`docs/API.md`):**
  - Documented all 14 active API routers and 60+ endpoints with request/response schemas, error codes, and RBAC rules.
  - Documented real-time WebRTC WebSocket signaling hub (`/api/rooms/{id}/ws`) with token authentication and message types.
- [x] **5.3 Author Database Schema & ER Diagram (`docs/DATABASE_SCHEMA.md`):**
  - Created complete 22-table reference with column types, primary keys, foreign keys, unique constraints, nullability, indices, deletion cascades, and an accurate Mermaid ER diagram.
- [x] **5.4 Author Enterprise Security Specification (`docs/SECURITY.md`):**
  - Documented all 14 security domains implemented across the codebase: Argon2id, 15-min JWT, refresh token rotation with reuse detection, double-submit CSRF, RBAC, IDOR prevention, admin safety locks, magic-byte upload validation, rate limits, security headers, and audit logs.
- [x] **5.5 Update Architecture Document (`docs/ARCHITECTURE.md`):**
  - Completely updated architecture specification with 17 sections and 5 Mermaid flowcharts covering system boundaries, frontend, FastAPI gateway, 14 routers, WebRTC signaling, MediaPipe iris/head pose pipeline, Faster-Whisper disfluency pipeline, 4-bucket monotonic scoring, Knapsack MMR, local storage, job queue, and SQLite/PostgreSQL compatibility.
- [x] **5.6 Create Master Documentation Index (`docs/INDEX.md`):**
  - Created centralized documentation index categorized by user persona and technical domain, linking all manuals, specs, benchmarks, reports, audits, and checklists.

---

## Summary of Effort and Recommended Order

| Batch | Description | Priority | Est. Hours | Target Deliverable | Status |
|---|---|---|---|---|---|
| **Batch 1** | Frontend Routing & Report Deep-Linking | **HIGH** | 1.5 hrs | `authClient.js`, `App.jsx`, `LiveInterviewRoom.jsx` | **COMPLETED** |
| **Batch 2** | Admin Question Sets Management | **HIGH** | 2.5 hrs | `AdminRoomManager.jsx`, `question_sets.py` | **COMPLETED** |
| **Batch 3** | Admin Candidate Governance & Session Browser | **HIGH** | 2.5 hrs | `AdminConsolePage.jsx`, `AdminRoomManager.jsx` | **COMPLETED** |
| **Batch 4** | Core User Manuals & Troubleshooting Guide | **HIGH** | 2.5 hrs | `CANDIDATE_USER_MANUAL.md`, `ADMIN_USER_MANUAL.md`, `TROUBLESHOOTING.md`, `LOCAL_OPERATOR_RUNBOOK.md` | **COMPLETED** |
| **Batch 5** | Technical Specification Documentation Updates | **MEDIUM** | 2.0 hrs | `README.md`, `API.md`, `DATABASE_SCHEMA.md`, `SECURITY.md`, `ARCHITECTURE.md`, `INDEX.md` | **COMPLETED** |
| **TOTAL** | | | **11.0 hrs** | **100% Product Completion** | **ALL COMPLETED** |
