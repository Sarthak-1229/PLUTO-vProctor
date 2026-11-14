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

### Objectives
Create complete, comprehensive, and professional user documentation for both candidate and administrator personas, plus an operational troubleshooting guide.

### Tasks
- [ ] **4.1 Author Candidate User Manual (`docs/CANDIDATE_USER_MANUAL.md`):**
  - Getting Started: Account Registration, Login, Profile setup.
  - Resume Management: Uploading, parsing, structured field editing, and starting interviews from saved resumes.
  - Universal Job Recommendations: Understanding match scores and skill alignments without taking interviews.
  - Learning Roadmaps: Interpreting readiness grades, growth curves, and skill milestone drills.
  - Self-Practice Interview Walkthrough: 7-step wizard, hardware check, neutral calibration, AI prompter with TTS, and proctoring HUD.
  - Hosted Recruiter Interviews: Entering room codes, waiting room etiquette, WebRTC live video/audio, and following interviewer-controlled questions.
  - Evaluation Reports: Understanding the 4 scoring buckets, 5-axis radar chart, monotonic deduction timeline, synchronized video scrubber, and PDF export.
  - Privacy Rights: How to permanently erase session recordings and data.
- [ ] **4.2 Author Admin User Manual (`docs/ADMIN_USER_MANUAL.md`):**
  - Admin Authentication: Login, super_admin vs admin permissions, portal isolation.
  - Platform Analytics: Reading candidate volumes, practice vs hosted throughput, score distributions, proctoring telemetry, and audit logs.
  - Candidate Governance: Managing accounts, updating roles, and inspecting candidate session histories.
  - Legacy Session Linking: Secure workflow to claim and assign unlinked historical sessions.
  - Question Set Management: Creating custom question sets, importing JSON templates, editing questions, and deleting sets.
  - Interview Room Scheduling: Creating rooms, configuring proctoring strictness presets, assigning candidates, and generating invite codes/links.
  - Live Interview Orchestration: Using Host Flow Controls (Start, Pause, Resume, Advance Question, Skip Question, End & Finalize), watching candidate WebRTC streams, and handling reconnects.
  - Post-Interview Review: Inspecting evaluation reports and downloading candidate dossiers.
- [ ] **4.3 Author Operational Troubleshooting Guide (`docs/TROUBLESHOOTING.md`):**
  - WebRTC & NAT Traversal: Symmetric NAT issues, STUN vs TURN configuration, and corporate firewall UDP blocks.
  - Camera & Microphone Permissions: Chrome site settings, fake media flags for headless testing, and audio device conflicts.
  - Local Ollama LLM: Ensuring Ollama service is running (`qwen2.5:3b`), memory requirements (2.4 GB VRAM), and understanding automatic algorithmic fallbacks when Ollama is offline.
  - Authentication & Session Issues: Resolving CSRF token mismatches, expired refresh tokens, and rate-limit lockouts.
  - Local Port & Process Conflicts: Handling port 8000 (FastAPI) or 5173 (Vite) collisions.

---

## Batch 5: Technical Specification Documentation Updates

**Priority:** **MEDIUM**  
**Estimated Effort:** ~2.0 hours  
**Prerequisites:** None  

### Objectives
Update all technical reference documentation so that developers, auditors, and future contributors have exact, up-to-date specifications of the v2 platform.

### Tasks
- [ ] **5.1 Update Project README (`README.md`):**
  - Overhaul root README with complete PLUTO vProctor v2 capabilities (Dual-mode, Auth & RBAC, Hosted WebRTC Rooms, Roadmaps, Admin Console).
  - Include quick start commands for both offline mode and enterprise multi-user mode.
  - Document all environment variables and configuration switches (`AUTH_ENABLED`, `SECRET_KEY`, `MEDIA_TRANSPORT_MODE`, `OLLAMA_BASE_URL`).
- [ ] **5.2 Update API Reference Specification (`docs/API.md`):**
  - Document all 14 active API routers with request/response schemas:
    - `/api/auth/*`
    - `/api/candidate/*`
    - `/api/candidate/roadmap`
    - `/api/resumes/*`
    - `/api/jobs/*`
    - `/api/rooms/*` (including WebSocket signaling message schema)
    - `/api/admin/*` (analytics, users, legacy sessions, audit logs, question sets, rooms)
    - `/api/interview/*`
    - `/api/analysis/*`
    - `/api/report/*`
    - `/api/settings/*`
  - Document standard error envelope schema (`{"error": {"code", "message", "request_id", "details"}}`).
- [ ] **5.3 Author Database Schema & ER Diagram (`docs/DATABASE_SCHEMA.md`):**
  - Complete Mermaid ER diagram showing all 22 database tables and foreign keys.
  - Data dictionary detailing each table's columns, types, indexes, and nullability constraints.
  - Migration history and invariant preservation rules.
- [ ] **5.4 Author Enterprise Security Specification (`docs/SECURITY.md`):**
  - Document the 14 security domains implemented in Phase 2 and Phase 6:
    - Password hashing (Argon2id) & timing attack defense
    - Refresh token rotation & family-level reuse revocation
    - Double-submit CSRF cookie tokens
    - Role-based access control & portal separation
    - IDOR protection & data scoping
    - High-entropy invitation tokens
    - WebSocket handshake authorization
    - Magic-byte file upload validation
    - Video recording access control
    - Rate limiting
    - Correlation tracking (`X-Request-ID`) & security headers
    - Production runtime safety validation
    - GDPR/CCPA synchronous deletion
    - Audit logging
- [ ] **5.5 Update Architecture Document (`docs/ARCHITECTURE.md`):**
  - Modernize architectural diagram and text to include WebRTC signaling, WebSocket transport adapter, dual database support, and background job queue.

---

## Summary of Effort and Recommended Order

| Batch | Description | Priority | Est. Hours | Target Deliverable |
|---|---|---|---|---|
| **Batch 1** | Frontend Routing & Report Deep-Linking | **HIGH** | 1.5 hrs | `authClient.js`, `App.jsx`, `LiveInterviewRoom.jsx` |
| **Batch 2** | Admin Question Sets Management | **HIGH** | 2.5 hrs | `AdminRoomManager.jsx`, `question_sets.py` |
| **Batch 3** | Admin Candidate Governance & Session Browser | **HIGH** | 2.5 hrs | `AdminConsolePage.jsx`, `AdminRoomManager.jsx` |
| **Batch 4** | Core User Manuals & Troubleshooting Guide | **HIGH** | 2.5 hrs | `CANDIDATE_USER_MANUAL.md`, `ADMIN_USER_MANUAL.md`, `TROUBLESHOOTING.md` |
| **Batch 5** | Technical Specification Documentation Updates | **MEDIUM** | 2.0 hrs | `README.md`, `API.md`, `DATABASE_SCHEMA.md`, `SECURITY.md`, `ARCHITECTURE.md` |
| **TOTAL** | | | **11.0 hrs** | **100% Product Completion** |
