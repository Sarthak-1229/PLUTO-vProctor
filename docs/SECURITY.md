# PLUTO vProctor — Comprehensive Security & Threat Model Specification

**Document Version:** 1.0  
**Product Version:** 0.1.0  
**Security Baseline:** Multi-Tier RBAC, Cryptographic Tokens, On-Device AI Privacy  
**Last Updated:** November 2026  

---

## Table of Contents
1. [Security Architecture & Principles](#1-security-architecture--principles)
2. [14 Core Security Domains & Defense Mechanisms](#2-14-core-security-domains--defense-mechanisms)
   - 2.1 [Password Hashing (Argon2id)](#21-password-hashing-argon2id)
   - 2.2 [JWT Access Token Lifecycle](#22-jwt-access-token-lifecycle)
   - 2.3 [Refresh Token Rotation & Family Reuse Detection](#23-refresh-token-rotation--family-reuse-detection)
   - 2.4 [Double-Submit Cookie CSRF Protection](#24-double-submit-cookie-csrf-protection)
   - 2.5 [Role-Based Access Control (RBAC)](#25-role-based-access-control-rbac)
   - 2.6 [Candidate Data Isolation & IDOR Prevention](#26-candidate-data-isolation--idor-prevention)
   - 2.7 [Administrative Safeguards & Lockout Protection](#27-administrative-safeguards--lockout-protection)
   - 2.8 [Real-Time WebSocket Authentication](#28-real-time-websocket-authentication)
   - 2.9 [High-Entropy Room Codes & Invitation Tokens](#29-high-entropy-room-codes--invitation-tokens)
   - 2.10 [Binary Magic-Byte Upload Validation](#210-binary-magic-byte-upload-validation)
   - 2.11 [Recording Access Authorization & HTTP Range Streaming](#211-recording-access-authorization--http-range-streaming)
   - 2.12 [Brute-Force & Rate-Limiting Defenses](#212-brute-force--rate-limiting-defenses)
   - 2.13 [Security Headers & Request Correlation](#213-security-headers--request-correlation)
   - 2.14 [Immutable Security Audit Logging](#214-immutable-security-audit-logging)
3. [Data Retention, Privacy & GDPR Deletion Rights](#3-data-retention-privacy--gdpr-deletion-rights)
4. [Known Security Limitations & Boundary Assumptions](#4-known-security-limitations--boundary-assumptions)

---

## 1. Security Architecture & Principles

PLUTO vProctor is architected with a **defense-in-depth, privacy-first** security model:
1. **Local Biometric Boundary:** Candidate video frames and facial landmarks never leave the local processing environment. No cloud computer vision or external AI APIs receive candidate biometric data.
2. **Zero Implicit Trust:** Every API endpoint independently validates access tokens, user active status, token revocation versions, and resource ownership.
3. **Auditability:** All privileged operations (role mutations, session claims, room orchestrations) generate permanent, tamper-evident audit records.

---

## 2. 14 Core Security Domains & Defense Mechanisms

### 2.1 Password Hashing (Argon2id)
- **Mechanism:** User passwords are encrypted using Argon2id (`passlib.hash.argon2`), the winner of the Password Hashing Competition.
- **Parameters:** Memory cost: 65,536 KiB, Time cost: 3 iterations, Parallelism: 4 lanes.
- **Implementation:** `backend/app/services/auth_service.py` (`hash_password`, `verify_password`).
- **Verification Tests:** `backend/tests/test_phase5_candidate_admin_experience.py::test_password_hashing_argon2id`.

### 2.2 JWT Access Token Lifecycle
- **Mechanism:** Short-lived HMAC-SHA256 (`HS256`) JSON Web Tokens containing `sub` (user ID), `role`, `tv` (token version), and `exp` claims.
- **Lifetime:** Strictly 15 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`).
- **Storage:** Kept exclusively in client memory; never persisted to localStorage or sessionStorage.
- **Implementation:** `backend/app/services/auth_service.py` (`create_access_token`, `decode_access_token`).
- **Verification Tests:** `backend/tests/test_phase5_candidate_admin_experience.py::test_jwt_access_token_expiration`.

### 2.3 Refresh Token Rotation & Family Reuse Detection
- **Mechanism:** Long-lived 256-bit cryptographically secure random tokens stored hashed in `refresh_tokens`. Delivered to clients via an HTTP-only, SameSite=Lax cookie.
- **Rotation:** Upon refresh (`POST /api/auth/refresh`), the used token is revoked, and a new token is issued in the same `rotation_family_id`.
- **Reuse Detection (Compromise Guard):** If an already-revoked refresh token is presented, the entire token family is immediately revoked, forcing all active sessions for that family to re-authenticate.
- **Implementation:** `backend/app/services/auth_service.py` (`rotate_refresh_token`).
- **Verification Tests:** `backend/tests/test_phase5_candidate_admin_experience.py::test_refresh_token_rotation_and_reuse_defense`.

### 2.4 Double-Submit Cookie CSRF Protection
- **Mechanism:** A readable cookie `pluto_csrf_token` is set on login. All state-changing requests (`POST`, `PUT`, `DELETE`) must echo this token in the `X-CSRF-Token` header.
- **Timing Protection:** Verified using constant-time string comparison (`hmac.compare_digest`).
- **Implementation:** `backend/app/routers/auth.py` (`verify_csrf_token`), `frontend/src/utils/authClient.js`.
- **Verification Tests:** `frontend/tests/test_auth_routing.js::parses CSRF cookie values safely`.

### 2.5 Role-Based Access Control (RBAC)
- **Hierarchy:** Three explicit tiers: `candidate` < `admin` < `super_admin`.
- **Server Enforcement:** FastAPI dependencies `require_roles("admin", "super_admin")` and `require_super_admin` guard all privileged endpoints.
- **Implementation:** `backend/app/services/authorization.py`.
- **Verification Tests:** `backend/tests/test_candidate_governance_and_completed_rooms.py::test_candidate_data_isolation_and_unauthorized_access`.

### 2.6 Candidate Data Isolation & IDOR Prevention
- **Mechanism:** Insecure Direct Object Reference (IDOR) protection. When accessing candidate documents (`/api/resumes/{id}`, `/api/report/{id}`, `/api/interview/{id}/video`), the backend enforces `enforce_session_access()`: candidates can only access their own records (`candidate_user_id == current_user.id`), while administrators are granted operational access.
- **Implementation:** `backend/app/services/authorization.py` (`enforce_session_access`).
- **Verification Tests:** `backend/tests/test_candidate_governance_and_completed_rooms.py::test_recording_access_authorization_and_idor`.

### 2.7 Administrative Safeguards & Lockout Protection
- **Self-Demotion Lock:** Super-admins cannot demote their own account.
- **Last Admin Lock:** System counts total active admins. If $\le 1$, demoting the last admin is blocked (`400 Bad Request`).
- **Last Super-Admin Lock:** Demoting the last super-admin is blocked (`400 Bad Request`).
- **Mandatory Justification:** Every role mutation requires a human-readable reason ($\ge 5$ characters) stored in audit logs.
- **Implementation:** `backend/app/routers/admin.py` (`update_user_role`).
- **Verification Tests:** `backend/tests/test_candidate_governance_and_completed_rooms.py::test_last_active_admin_and_super_admin_protection`.

### 2.8 Real-Time WebSocket Authentication
- **Mechanism:** WebSocket connection `/api/rooms/{id}/ws` authenticates via query token `?token=...`.
- **Token Claims Verification:** Verifies signature, expiration, active user status, and token version (`tv`). Unauthorized attempts are rejected with WebSocket close code `1008 Policy Violation`.
- **Implementation:** `backend/app/routers/rooms.py` (`room_websocket_endpoint`).
- **Verification Tests:** `backend/tests/test_e2e_hosted_interview_flow.py::test_e2e_hosted_interview_lifecycle`.

### 2.9 High-Entropy Room Codes & Invitation Tokens
- **Mechanism:** Room creation generates two distinct credentials:
  - 9-character room code (e.g. `K7M-99P-Q2X`) with custom alphabet excluding confusing characters (`0`, `O`, `1`, `I`).
  - 256-bit URL-safe invitation token (`secrets.token_urlsafe(32)`).
- **Storage:** Only SHA-256 hashes (`room_code_hash`, `invite_token_hash`) are stored in the database.
- **Implementation:** `backend/app/services/room_service.py` (`generate_room_credentials`).
- **Verification Tests:** `backend/tests/test_e2e_hosted_interview_flow.py`.

### 2.10 Binary Magic-Byte Upload Validation
- **Mechanism:** File uploads are validated by inspecting binary header magic bytes rather than trusting client file extensions:
  - PDF: Must begin with `%PDF-` (`0x25 0x50 0x44 0x46`).
  - DOCX: Must begin with PK zip header (`0x50 0x4B 0x03 0x04`).
- **Size Limit:** Maximum file size strictly enforced at 5 MB for resumes, 2 MB for question-set JSON files.
- **Implementation:** `backend/app/services/resume_service.py` (`validate_resume_upload`).
- **Verification Tests:** `backend/tests/test_phase_f_production.py::test_resume_upload_size_and_mime_validation`.

### 2.11 Recording Access Authorization & HTTP Range Streaming
- **Mechanism:** Video recordings stored in `storage/recordings/` are served via `GET /api/interview/{id}/video` through `enforce_session_access()`.
- **Streaming:** Implements byte-range headers (`Range: bytes=start-end`) returning `206 Partial Content`. Unauthorized candidate requests return `403 Forbidden`.
- **Implementation:** `backend/app/routers/interview.py` (`stream_video`).
- **Verification Tests:** `backend/tests/test_candidate_governance_and_completed_rooms.py::test_recording_access_authorization_and_idor`.

### 2.12 Brute-Force & Rate-Limiting Defenses
- **Mechanism:** Account lockout after 5 consecutive failed login attempts (`MAX_FAILED_LOGIN_ATTEMPTS = 5`) for 15 minutes (`LOCKOUT_MINUTES = 15`).
- **Implementation:** `backend/app/services/auth_service.py` (`handle_failed_login`).
- **Verification Tests:** `backend/tests/test_phase5_candidate_admin_experience.py::test_account_lockout_after_failed_logins`.

### 2.13 Security Headers & Request Correlation
- **Headers:** Attached to every response via middleware: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `X-XSS-Protection`.
- **Correlation ID:** Every request receives an `X-Request-ID` header tracked across all structured logs.
- **Implementation:** `backend/app/main.py` (`RequestIDMiddleware`).
- **Verification Tests:** `backend/tests/test_phase_f_production.py::test_security_headers_and_request_id`.

### 2.14 Immutable Security Audit Logging
- **Mechanism:** Privileged events write immutable audit records to `audit_logs` capturing actor ID, role, action, target resource ID, and JSON details.
- **Implementation:** `backend/app/services/audit_service.py`, `backend/app/db/models.py`.
- **Verification Tests:** `backend/tests/test_candidate_governance_and_completed_rooms.py::test_role_management_permissions_and_audit`.

---

## 3. Data Retention, Privacy & GDPR Deletion Rights

PLUTO vProctor provides built-in mechanisms to satisfy candidate privacy and data protection rights:

- **Local Data Retention:** Telemetry and video recordings reside in local storage for a configurable retention window (`RETENTION_DAYS = 30`).
- **Right to Erasure (Article 17 GDPR):**
  - **Session Deletion:** Invoking `DELETE /api/interview/{id}` permanently deletes the WebM recording from disk and purges the session database record.
  - **Complete Account Purge:** Candidates can delete their account via `DELETE /api/candidate/profile`, which permanently wipes the user account, profile records, uploaded resumes, recommendations, and refresh tokens.
- **Implementation:** `backend/app/routers/candidate.py`, `backend/app/routers/interview.py`.
- **Verification Tests:** `backend/tests/test_phase_f_production.py::test_complete_data_deletion_purge`.

---

## 4. Known Security Limitations & Boundary Assumptions

1. **In-Memory Rate Limiting:** The current rate-limiting token bucket is maintained in-process memory. Restarting the backend process resets rate-limit counters.
2. **Local File Storage:** In local development mode, resumes and recordings are stored directly on the host file system under `storage/`. File permissions rely on host OS user isolation.
3. **HTTP Development Cookie Flag:** In development mode (`ENVIRONMENT=development`), cookies use `COOKIE_SECURE=False` to support `http://localhost:5173`. In production deployments, `COOKIE_SECURE=True` is strictly required.
4. **Self-Signed Certificates / HTTPS:** WebRTC camera permissions require either `localhost` loopback or a secure HTTPS context. Testing over a local area network IP requires configuring local SSL certificates.
