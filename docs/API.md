# PLUTO vProctor: Comprehensive API Reference Specification

**Document Version:** 2.0  
**Product Version:** 0.1.0  
**Base URL:** `http://127.0.0.1:8000`  
**Interactive Docs:** `http://127.0.0.1:8000/docs` (OpenAPI Swagger) | `http://127.0.0.1:8000/redoc` (ReDoc)  
**Last Updated:** November 2026  

---

## Table of Contents
1. [Global Conventions & Security Architecture](#1-global-conventions--security-architecture)
2. [Authentication & Account Management](#2-authentication--account-management)
3. [Candidate Profiles & Skill Portfolio](#3-candidate-profiles--skill-portfolio)
4. [Multi-Resume Library & Parsing](#4-multi-resume-library--parsing)
5. [Job Catalog & Universal Recommendations](#5-job-catalog--universal-recommendations)
6. [Self-Practice Interview Lifecycle](#6-self-practice-interview-lifecycle)
7. [Telemetry Analysis Pipeline](#7-telemetry-analysis-pipeline)
8. [Evaluation Reports & PDF Export](#8-evaluation-reports--pdf-export)
9. [Candidate Learning Roadmap & Analytics](#9-candidate-learning-roadmap--analytics)
10. [Admin Question-Set Management](#10-admin-question-set-management)
11. [Admin Room Scheduling & Lifecycle](#11-admin-room-scheduling--lifecycle)
12. [Candidate Room Joining & Lobby Snapshot](#12-candidate-room-joining--lobby-snapshot)
13. [Realtime WebSocket Room Signaling & WebRTC](#13-realtime-websocket-room-signaling--webrtc)
14. [Admin Candidate Governance & Role Management](#14-admin-candidate-governance--role-management)
15. [Admin Platform Analytics & Interview Browser](#15-admin-platform-analytics--interview-browser)
16. [System Liveness, Readiness & Presets](#16-system-liveness-readiness--presets)

---

## 1. Global Conventions & Security Architecture

### 1.1 Authentication & Token Header
- **Access Tokens:** Signed via HMAC-SHA256 (`HS256`). Issued with 15-minute validity. Pass in the HTTP `Authorization` header:
  ```http
  Authorization: Bearer <access_token>
  ```
- **Refresh Tokens:** High-entropy 256-bit random tokens stored hashed in `refresh_tokens`. Delivered to clients via an HTTP-only, SameSite=Lax cookie named `pluto_refresh_token` (7-day validity).
- **CSRF Protection:** State-changing requests (`POST`, `PUT`, `DELETE`, `PATCH`) must supply the `X-CSRF-Token` header matching the readable cookie `pluto_csrf_token`.

### 1.2 Request-ID Correlation & Security Headers
Every HTTP response carries the following standard headers:
```http
X-Request-ID: <8-char-uuid>
X-Response-Time-MS: <float>
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### 1.3 Error Envelope Format
When an API error occurs, the server returns an RFC 7807-compatible error response:
```json
{
  "detail": "Descriptive human-readable error message",
  "request_id": "a8f9c102"
}
```

---

## 2. Authentication & Account Management

### `POST /api/auth/register`
- **Purpose:** Registers a new candidate account.
- **Auth:** None (Public).
- **Request Body:**
  ```json
  {
    "email": "candidate@example.com",
    "password": "StrongPassword123!",
    "full_name": "Jane Doe"
  }
  ```
- **Response (`201 Created`):**
  ```json
  {
    "user": {
      "id": "usr_9f82...",
      "email": "candidate@example.com",
      "full_name": "Jane Doe",
      "role": "candidate",
      "is_active": true
    },
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 900
  }
  ```
- **Errors:** `400 Bad Request` (Email already registered, password < 8 characters).

### `POST /api/auth/login`
- **Purpose:** Authenticates user via Argon2id password hash verification.
- **Auth:** None (Public).
- **Request Body:**
  ```json
  {
    "email": "candidate@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response (`200 OK`):** Returns serialized user and sets `pluto_refresh_token` HTTP-only cookie.
- **Errors:** `401 Unauthorized` (Invalid email or password), `403 Forbidden` (Account locked due to 5 consecutive failed attempts).

### `POST /api/auth/admin/login`
- **Purpose:** Authenticates admin and super-admin users for portal isolation.
- **Auth:** None.
- **Errors:** `403 Forbidden` if authenticated user has role `candidate`.

### `POST /api/auth/refresh`
- **Purpose:** Silently rotates the refresh token family and issues a new access token.
- **Auth:** Valid `pluto_refresh_token` HTTP-only cookie + `X-CSRF-Token` header.
- **Response (`200 OK`):** `{"access_token": "...", "token_type": "bearer", "expires_in": 900}`.
- **Errors:** `401 Unauthorized` (Invalid, expired, or reused refresh token).

### `POST /api/auth/logout`
- **Purpose:** Revokes active refresh token and clears auth cookies.
- **Auth:** Authenticated user.
- **Response (`200 OK`):** `{"status": "logged_out"}`.

### `GET /api/auth/me`
- **Purpose:** Returns current authenticated user metadata and role.
- **Auth:** `Bearer <access_token>`.
- **Response (`200 OK`):** Serialized user dictionary.

### `POST /api/auth/forgot-password`
- **Purpose:** Initiates password reset by issuing a 30-minute one-time token.
- **Request Body:** `{"email": "user@example.com"}`.
- **Response (`200 OK`):** `{"status": "reset_token_issued"}`.

### `POST /api/auth/reset-password`
- **Purpose:** Consumes one-time token and updates password hash.
- **Request Body:** `{"token": "raw_token_string", "new_password": "NewStrongPassword123!"}`.
- **Response (`200 OK`):** `{"status": "password_updated"}`.

---

## 3. Candidate Profiles & Skill Portfolio

### `GET /api/candidate/profile`
- **Purpose:** Retrieves authenticated candidate's profile details.
- **Auth:** `candidate`, `admin`, `super_admin`.
- **Response (`200 OK`):**
  ```json
  {
    "id": "cp_1082...",
    "user_id": "usr_9f82...",
    "full_name": "Jane Doe",
    "headline": "Full Stack Engineer",
    "phone": "+1-555-0199",
    "location": "San Francisco, CA",
    "bio": "Passionate backend developer with 4 years experience.",
    "technical_skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker"],
    "preferred_roles": ["Backend Engineer", "Full Stack Developer"],
    "portfolio_links": {
      "github": "https://github.com/janedoe",
      "linkedin": "https://linkedin.com/in/janedoe"
    },
    "profile_completed": true
  }
  ```

### `PUT /api/candidate/profile`
- **Purpose:** Updates candidate profile attributes.
- **Auth:** `candidate`.
- **Request Body:** Accepts partial or complete fields from profile schema.
- **Response (`200 OK`):** Updated profile record.

---

## 4. Multi-Resume Library & Parsing

### `GET /api/resumes`
- **Purpose:** Lists all resumes uploaded by the authenticated candidate.
- **Auth:** `candidate`.
- **Response (`200 OK`):** List of resume records with metadata, upload date, file size, and `is_active` flag.

### `POST /api/resumes/upload`
- **Purpose:** Uploads, validates magic bytes, and parses a resume file.
- **Auth:** `candidate`.
- **Request:** Multipart form data (`file: UploadFile`, optional `label: str`).
- **Validation:** Enforces maximum size 5 MB. Rejects corrupted binary headers. Allowed MIME types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`.
- **Response (`201 Created`):** Serialized resume object with parsed skills, experience, and contact info.

### `GET /api/resumes/{resume_id}`
- **Purpose:** Retrieves parsed resume text and detected structured fields.
- **Auth:** Owner or Admin. Enforces IDOR protection (`403 Forbidden` if owned by another candidate).

### `DELETE /api/resumes/{resume_id}`
- **Purpose:** Permanently deletes resume record and removes disk file from `storage/resumes/`.
- **Auth:** Owner or Admin.
- **Response (`200 OK`):** `{"status": "deleted", "id": "..."}`.

### `POST /api/resumes/{resume_id}/start-session`
- **Purpose:** Launches an interview screening session directly from a stored resume.
- **Request Form:** `job_id: str`.
- **Response (`200 OK`):** Initializes session and returns `{"session_id": "...", "screening_status": "APPROVED", ...}`.

---

## 5. Job Catalog & Universal Recommendations

### `GET /api/jobs`
- **Purpose:** Retrieves all verified engineering job profiles.
- **Auth:** Public / Authenticated.
- **Response (`200 OK`):** Array of job profiles with required skills, experience, and pass thresholds.

### `GET /api/jobs/search?q={query}`
- **Purpose:** Prefix and fuzzy autocomplete search across jobs using Trie index.

### `GET /api/candidate/recommendations`
- **Purpose:** Universal pre-interview job recommendation engine.
- **Auth:** `candidate`.
- **Description:** Computes composite match scores against all catalog jobs using active resume skills or manual profile skills.
- **Response (`200 OK`):**
  ```json
  [
    {
      "job_id": "swe_backend",
      "title": "Senior Backend Engineer",
      "company": "Nexus Systems",
      "match_score": 88.5,
      "matched_skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
      "missing_skills": ["Kubernetes", "Redis"],
      "explanation": "Strong alignment in core backend frameworks; missing container orchestration experience."
    }
  ]
  ```

---

## 6. Self-Practice Interview Lifecycle

### `POST /api/resume/screen`
- **Purpose:** Screens uploaded or submitted resume against target job requirements.
- **Request Form:** `job_id: str`, `file: UploadFile` or profile text payload.
- **Response (`200 OK`):**
  ```json
  {
    "session_id": "sess_a8f9c102...",
    "job_id": "swe_backend",
    "screening_fit": 0.85,
    "status": "APPROVED",
    "details": {
      "matched_skills": ["Python", "FastAPI"],
      "missing_skills": ["Redis"]
    }
  }
  ```

### `POST /api/interview/{sid}/start`
- **Purpose:** Initializes mock interview session with neutral gaze calibration baseline and proctoring preset.
- **Request Body:**
  ```json
  {
    "calibration": {
      "iris_center_x": 0.495,
      "iris_center_y": 0.502,
      "pitch_offset": 2.1,
      "yaw_offset": -1.4
    },
    "preset_name": "standard"
  }
  ```
- **Response (`200 OK`):** Returns ordered question items selected via Knapsack MMR algorithm.

### `POST /api/interview/{sid}/question/{order_index}/answer`
- **Purpose:** Submits candidate audio transcript and timing for question index.
- **Request Body:**
  ```json
  {
    "transcript": "In Python, the Global Interpreter Lock ensures...",
    "start_time_sec": 12.4,
    "end_time_sec": 78.2,
    "tts_windows": [[12.4, 15.0]]
  }
  ```
- **Response (`200 OK`):** `{"status": "recorded"}`.

### `POST /api/interview/{sid}/recording`
- **Purpose:** Uploads finalized WebM video recording of the interview session.
- **Request:** Multipart form data (`file: UploadFile`). Saved to `storage/recordings/{sid}_hosted.webm`.
- **Response (`200 OK`):** `{"status": "saved", "filename": "..."}`.

### `GET /api/interview/{sid}/video`
- **Purpose:** Streams session video recording.
- **Auth:** Authorized candidate (owner) or Admin.
- **HTTP Features:** Fully supports `Range: bytes=start-end` returning `206 Partial Content` for bufferless seeking.

### `DELETE /api/interview/{sid}`
- **Purpose:** GDPR data erasure. Permanently deletes recording file from disk and erases session records.
- **Auth:** Session owner or Admin.

---

## 7. Telemetry Analysis Pipeline

### `POST /api/analysis/{sid}/run`
- **Purpose:** Enqueues parallel multimodal video and audio analysis pipelines in background workers.
- **Auth:** Session owner or Admin.
- **Response (`200 OK`):** `{"status": "queued", "session_id": "..."}`.

### `GET /api/analysis/{sid}/status`
- **Purpose:** Polls analysis pipeline progress.
- **Response (`200 OK`):**
  ```json
  {
    "status": "PROCESSING",
    "stage": "Analyzing multimodal video & audio telemetry...",
    "video_pct": 65,
    "audio_pct": 80
  }
  ```
  *(Status transitions to `COMPLETED` when scoring is finalized).*

---

## 8. Evaluation Reports & PDF Export

### `GET /api/report/{sid}`
- **Purpose:** Retrieves complete evaluation report dossier.
- **Auth:** Session owner or Admin (strictly blocks IDOR access).
- **Response (`200 OK`):**
  ```json
  {
    "session_id": "sess_a8f9c102...",
    "candidate_name": "Jane Doe",
    "job_title": "Senior Backend Engineer",
    "overall_score": 87.5,
    "grade": "A",
    "readiness_label": "Strongly Qualified",
    "category_scores": {
      "technical_depth": 88.0,
      "communication": 85.0,
      "proctoring_integrity": 92.0,
      "resume_relevance": 82.0
    },
    "radar_metrics": {
      "technical_accuracy": 88.0,
      "clarity": 85.0,
      "environmental_integrity": 92.0,
      "response_structure": 84.0,
      "domain_alignment": 82.0
    },
    "deductions_timeline": [
      {
        "t_start": 45.2,
        "t_end": 48.5,
        "category": "gaze",
        "points_deducted": 1.5,
        "reason": "Gaze off-screen: 3.3s"
      }
    ],
    "questions": [...]
  }
  ```

### `GET /api/report/{sid}/pdf`
- **Purpose:** Generates and downloads official PDF evaluation dossier.
- **Response (`200 OK`):** Binary `application/pdf` stream.

---

## 9. Candidate Learning Roadmap & Analytics

### `GET /api/candidate/analytics`
- **Purpose:** Cumulative metrics: total interviews, mean scores, proctoring trends.
- **Auth:** `candidate`.

### `GET /api/candidate/roadmap`
- **Purpose:** Generates growth curves, readiness grades (A/B/C/D), domain strengths/weaknesses, and concrete practice milestone drills.
- **Auth:** `candidate`.

---

## 10. Admin Question-Set Management

### `GET /api/admin/question-sets`
- **Purpose:** Lists question sets owned by admin (or all sets for super-admin).
- **Auth:** `admin`, `super_admin`.
- **Response (`200 OK`):** Direct list of question set summaries.

### `POST /api/admin/question-sets`
- **Purpose:** Creates custom question set with structured items.
- **Auth:** `admin`, `super_admin`.
- **Request Body:** Name, description, target domain, and array of questions.

### `GET /api/admin/question-sets/{id}`
- **Purpose:** Retrieves question set with all ordered questions.

### `PUT /api/admin/question-sets/{id}`
- **Purpose:** Replaces items, increments version, recomputes SHA-256 checksum, logs update.
- **Auth:** Set owner or `super_admin`.

### `DELETE /api/admin/question-sets/{id}`
- **Purpose:** Deletes question set.
- **Conflict Handling:** Returns `409 Conflict` if set is actively used by a room in `LOBBY`, `LIVE`, or `PAUSED`. Safely nullifies FK on completed rooms without deleting historical room questions.

### `POST /api/admin/question-sets/import`
- **Purpose:** Imports question set from JSON payload. Supports `?dry_run=true` validation.

### `POST /api/admin/question-sets/import-file`
- **Purpose:** Multipart upload of `.json` file (up to 2 MB) with schema validation.

---

## 11. Admin Room Scheduling & Lifecycle

### `POST /api/admin/rooms`
- **Purpose:** Schedules new interview room.
- **Auth:** `admin`, `super_admin`.
- **Request Body:**
  ```json
  {
    "title": "Jane Doe — Senior Backend Round",
    "question_set_id": "qs_a8f9...",
    "proctoring_preset": "standard",
    "duration_seconds": 2700,
    "assigned_candidate_id": "usr_9f82..."
  }
  ```
- **Response (`201 Created`):** Returns room details with plaintext 9-character join code and 256-bit URL invite token.

### `GET /api/admin/rooms`
- **Purpose:** Lists active and completed rooms with candidate information, scores, report availability, and recording links.

### `POST /api/admin/rooms/{id}/{action}`
- **Supported Actions:** `start`, `pause`, `resume`, `advance`, `skip`, `end`.
- **Description:** Advances room FSM state and broadcasts real-time transition to connected peers.

---

## 12. Candidate Room Joining & Lobby Snapshot

### `POST /api/rooms/join`
- **Purpose:** Validates 9-character code or invite token and assigns candidate participant record.
- **Request Body:** `{"room_code": "ABC-123-XYZ", "display_name": "Jane Doe"}`.
- **Response (`200 OK`):** `{"room_id": "rm_...", "status": "LOBBY", "session_id": "..."}`.

### `GET /api/rooms/{id}/snapshot`
- **Purpose:** Authoritative state snapshot for reconnecting clients.
- **Response (`200 OK`):** Room status, current question ordinal, sequence version, timer values.

---

## 13. Realtime WebSocket Room Signaling & WebRTC

### `WS /api/rooms/{room_id}/ws?token={access_token}`
- **Purpose:** Bidirectional WebSocket connection for state synchronization and WebRTC signaling.
- **Authentication:** Validated via query parameter `token`. Rejects with close code `1008 Policy Violation` if token is invalid, expired, or user is not a participant.

#### Inbound Client Messages:
1. **Heartbeat:** `{"type": "ping"}` $\to$ server replies `{"type": "pong"}`.
2. **WebRTC Signal:**
   ```json
   {
     "type": "webrtc.signal",
     "target_user_id": "usr_host_123",
     "signal_type": "offer",
     "payload": { "type": "offer", "sdp": "v=0..." }
   }
   ```
   *(Supported `signal_type`: `offer`, `answer`, `ice_candidate`).*

#### Outbound Server Events:
1. **Room Snapshot:** `{"type": "room.snapshot", "snapshot": {...}, "occupants": [...]}`
2. **Peer Joined:** `{"type": "participant.joined", "user_id": "...", "role": "..."}`
3. **Peer Left:** `{"type": "participant.left", "user_id": "..."}`
4. **State Transition:** `{"type": "room.state_changed", "new_status": "LIVE", "sequence_version": 3}`
5. **Question Advanced:** `{"type": "room.question_changed", "ordinal": 2, "question": {...}}`

---

## 14. Admin Candidate Governance & Role Management

### `GET /api/admin/users`
- **Purpose:** Lists registered accounts with query parameters `?search=...`, `?role=...`, `?limit=...`, `?offset=...`.
- **Response (`200 OK`):** User list with attached `interview_count` and `has_profile` flags.

### `GET /api/admin/users/{uid}`
- **Purpose:** Full candidate profile inspection, resumes list, and aggregate stats.

### `GET /api/admin/users/{uid}/history`
- **Purpose:** Retrieves candidate's complete interview history (practice & hosted) with direct dossier and recording links.

### `POST /api/admin/users/{uid}/role`
- **Purpose:** Elevates or demotes user role (`candidate` $\leftrightarrow$ `admin` $\leftrightarrow$ `super_admin`).
- **Auth:** `super_admin` only.
- **Request Body:** `{"new_role": "admin", "reason": "Promoted to backend team recruiter"}`.
- **Safety Safeguards:**
  - `HTTP 400 Bad Request` if target is self (`cannot_demote_self`).
  - `HTTP 400 Bad Request` if target is the last active administrator (`cannot_demote_last_admin`).
  - `HTTP 400 Bad Request` if target is the last active super-administrator (`cannot_demote_last_super_admin`).
  - Writes permanent audit record to `audit_logs`.

---

## 15. Admin Platform Analytics & Interview Browser

### `GET /api/admin/analytics/overview`
- **Purpose:** Platform-wide throughput, pass rates, score distributions, and proctoring violation frequencies.
- **Auth:** `admin`, `super_admin`.

### `GET /api/admin/interviews`
- **Purpose:** Global completed interviews browser with search, mode filters (`all`, `hosted`, `self_practice`), and pagination.

---

## 16. System Liveness, Readiness & Presets

### `GET /api/health`
- **Purpose:** Liveness health probe reporting app version, environment, and Ollama connectivity.

### `GET /api/ready`
- **Purpose:** Readiness probe verifying SQLite database connectivity (`SELECT 1`) and storage directory availability.

### `GET /api/settings`
- **Purpose:** Returns active proctoring strictness presets (Standard, Strict, Lenient) with gaze angles and penalty weights.
