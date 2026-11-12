# Phase 2 Implementation Plan — Authentication, Accounts & RBAC

**Goal:** Implement secure database-backed candidate and administrator authentication, RBAC and IDOR protection across all protected APIs and SPA routes, candidate profiles, explicit admin-controlled claiming of the 14 legacy `Sarthak Bhosale` sessions with audit logging, secure multi-resume storage with editable confirmed fields, and universal job recommendations requiring no prior interview, while keeping `AUTH_ENABLED=False` offline self-practice backward-compatible.

**Architecture:** Additive SQLAlchemy models + inspector-guarded Alembic migration `0003_phase2_auth_profiles_rbac`, Argon2id password hashing + short-lived JWT access tokens + rotating SHA-256-hashed HttpOnly/SameSite/CSRF refresh cookies + single-use hashed expiring verification/reset tokens, FastAPI dependency-based RBAC/ownership guards, rate-limiting & audit logging, and History-API SPA views (`Login`, `Register`, `Forgot/Reset Password`, `Profile & Resumes`, `Job Recommendations`, `Admin Login`, `Admin Console`) replacing `localStorage` identity/history as source of truth.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic (SQLite + PostgreSQL), `argon2-cffi`, `PyJWT`, `email-validator`, React 19, Vite, Tailwind CSS, `oxlint`, `pytest`, `node --test`.

---

## Task 1: Database Schema & Migration `0003` (Auth, Profiles, Resumes, Role Templates, Audit)
- Add ORM models in `backend/app/db/models.py`: `User`, `CandidateProfile`, `Resume`, `ResumeProfile`, `JobRoleTemplate`, `JobRecommendation`, `RefreshToken`, `OneTimeToken`, `AuditLog`, plus additive `InterviewSession` columns (`candidate_user_id`, `interview_mode`, `room_id`).
- Add inspector-guarded migration `backend/alembic/versions/0003_phase2_auth_profiles_rbac.py` handling fresh SQLite, existing `pluto.db` (`0002_add_core_indexes` -> `head`) preserving all 14 legacy sessions (`candidate_user_id IS NULL`), and live PostgreSQL.
- Extend `backend/tests/test_migrations.py` (TDD) to assert table/column/index creation, `command.check(cfg)` parity, and zero data loss/auto-claiming on a copy of `pluto.db`.

## Task 2: Auth Security Primitives, Rate Limiting, Audit Service & `/api/auth/*` Router
- Configure runtime secret fallback guard in `backend/app/config.py` (dev/test ephemeral process key when empty; production still fails fast if missing/`<32` chars/placeholder) and security constants (`CSRF_COOKIE_NAME`, `REFRESH_COOKIE_NAME`, reset/verify TTLs).
- Implement `backend/app/services/security_service.py` (Argon2id hashing/rehash, JWT issue/decode, CSPRNG SHA-256 token hashing, sliding-window rate limiter with test reset helper, audit log writer with PII/secret redaction) and `backend/app/services/auth_service.py` (register, email normalization/uniqueness, candidate login + lockout, separate admin login enforcing `admin`/`super_admin`, refresh family rotation + reuse revocation, logout/revoke-all via `token_version`, verify email, forgot/reset password with anti-enumeration generic responses).
- Implement `backend/app/routers/auth.py` and mount under `/api/auth`.
- Write TDD tests (`backend/tests/test_phase2_auth.py`) covering password hashing, duplicate normalized emails, login lockout, admin-vs-candidate portal separation, refresh cookie + CSRF check + reuse revocation, single-use expired reset token, rate limits, and anti-enumeration.

## Task 3: Server-Side RBAC, Cross-Candidate Isolation & Candidate Profile/History API
- Implement `backend/app/services/authorization.py` (`get_current_user`, `get_optional_user`, `require_roles`, `require_session_access`, `require_resume_access`, `get_effective_auth_required`).
- Enforce authentication & ownership/role checks across `/api/resume/*`, `/api/interview/*`, `/api/analysis/*`, `/api/report/*`, and admin-only `/api/settings` whenever `settings.AUTH_ENABLED=True` (keeping `AUTH_ENABLED=False` offline self-practice compatible; blocking `/api/fixtures/save` in production or non-admin auth mode).
- Implement `backend/app/routers/candidate.py` (`GET/PUT /api/candidate/profile`, `GET /api/candidate/history`) persisting personal/education/skills/experience details and DB-backed authenticated interview history.
- Write TDD tests (`backend/tests/test_phase2_rbac_and_profile.py`) verifying `401` unauthenticated, `403` cross-candidate IDOR on sessions/reports/recordings/deletes, mass-assignment role escalation immunity (`PUT /api/candidate/profile` & `/api/auth/register` cannot elevate role), admin access rules, and `AUTH_ENABLED=False` offline backward compatibility.

## Task 4: Admin CLI Bootstrap, Legacy Session Claiming & Management Console API
- Implement `backend/app/services/admin_bootstrap.py` (`python -m backend.app.services.admin_bootstrap`) creating/promoting an initial `admin` / `super_admin` safely via CLI args or env vars (never hardcoded passwords).
- Implement `backend/app/routers/admin.py` (`GET /api/admin/users`, `GET /api/admin/legacy-sessions`, `POST /api/admin/sessions/{sid}/claim`, `GET /api/admin/audit-logs`, `POST /api/admin/users/{uid}/role`) with strict server-side `admin`/`super_admin` checks and immutable audit log entries on every claim/role change.
- Verify strictly that registering/logging in a candidate matching `"Sarthak Bhosale"` never auto-claims the 14 legacy sessions (`candidate_user_id` remains `NULL` until explicitly claimed by an admin).
- Write TDD tests (`backend/tests/test_phase2_admin_claiming.py`).

## Task 5: Secure Multi-Resume Library, Editable Resume Profiles & Universal Job Recommendations
- Seed fresher/entry-level & industry `job_role_templates` data + idempotent loader (`backend/app/services/recommendation_catalog.py`) bridging templates and `jobs`.
- Implement `backend/app/services/resume_profile_service.py`: strict upload validation (extension `.pdf`/`.docx`/`.txt`, MIME check, magic-byte inspection excluding spoofed `.exe`/HTML/zip disguised as PDF, 5 MB limit, PDF page cap `<=15`, random UUID storage key inside private `STORAGE_DIR/resumes`, sanitized filename, SHA-256 hash), reusing `resume_service.parse_resume`, computing honest field provenance/confidence without inventing data, CRUD + confirm edits (`extracted_data_json` vs `edited_data_json`), hard delete removing both DB rows and private file.
- Implement `backend/app/services/job_recommendation_service.py`: universal matching across resume skills (`edited` -> `extracted`), manual profile skills/experience/education, or both; persists/refreshes `job_recommendations` and returns transparent `matched_skills`, `missing_skills`, `score`, `why_recommended`, `interview_ready` regardless of zero completed interviews.
- Mount `backend/app/routers/resumes.py` (`/api/resumes/*`) and `GET /api/jobs/recommendations` in `backend/app/routers/jobs.py` (supporting optional interview start from a recommended job).
- Write TDD tests (`backend/tests/test_phase2_resumes_and_recommendations.py`) covering spoofed uploads, oversized uploads, field editing & confirmation, complete resume deletion, and recommendations for resume-only / profile-only / combined candidates with 0 interviews.

## Task 6: Frontend Auth Flows, Protected Routes, Profile/Resume Review, Recommendations & Admin UI
- Build clean frontend auth client & CSRF-aware fetch helper (`frontend/src/utils/authClient.js` + `AuthContext.jsx`) and History-API SPA routing (without heavy router rewrites) covering `/login`, `/register`, `/forgot-password`, `/reset-password`, `/profile`, `/resumes`, `/recommendations`, `/admin/login`, `/admin`, plus existing `/` self-practice flow.
- When `AUTH_ENABLED=True` (reported via `/api/auth/config` so backend & frontend stay synchronized cleanly!), require sign-in for candidate/admin portals and fetch history from `/api/candidate/history` rather than `localStorage` as truth; when `AUTH_ENABLED=False`, preserve offline self-practice demo flow cleanly while keeping explicit auth routes accessible.
- Build neo-brutalist UI matching PLUTO vProctor design (`LoginPage`, `RegisterPage`, `ResetPasswordPage`, `CandidateProfilePage`, `ResumeLibraryPanel` with editable parsed-field review & confirmation, `RecommendationsPanel`, `AdminLoginPage`, `AdminConsolePage` with legacy session claimer & audit log viewer), update `Navbar.jsx` & `CandidateDashboard.jsx`, run `oxlint`, `npm test`, and `vite build`.

## Task 7: Live DB Backup + Migration, Independent Security Review & Phase 2 Verification Gate
- Back up `backend/app/pluto.db`, run `alembic upgrade head` on live `pluto.db`, verify `14` legacy `Sarthak Bhosale` rows (`candidate_user_id IS NULL`) & `24` storage files unchanged.
- Spawn independent `self` `pro` security code reviewer on all Phase 2 changes; fix all Critical/High findings and evaluate Medium findings.
- Run complete backend `pytest`, live temporary PostgreSQL 16.2 (`pgserver`) migration suite, `oxlint`, `npm test`, `vite build`, and `evaluate_fixtures.py --gate-check`.
- Write `docs/PHASE_2_IMPLEMENTATION_REPORT.md` and stop at the Phase 2 gate for user review before Phase 3.

