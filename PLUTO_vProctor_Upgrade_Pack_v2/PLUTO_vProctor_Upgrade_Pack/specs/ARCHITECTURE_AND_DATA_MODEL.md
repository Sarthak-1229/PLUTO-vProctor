# Architecture & Data Model — Target Design

## Architecture principles
- Add features as bounded modules to existing FastAPI/React structure.
- PostgreSQL is the production source of truth; SQLite remains local development mode.
- Use Alembic migrations only. Never edit production schema ad hoc.
- Keep large media files in object storage or private mounted storage, not relational DB blobs.
- Use WebSocket for room state/control events. Use WebRTC through an SFU (e.g. LiveKit) only when live media monitoring is required.
- Background processing stays on worker service with existing GPU lock and queue discipline.

## Suggested backend modules
- `routers/auth.py`, `routers/candidates.py`, `routers/admin.py`, `routers/rooms.py`, `routers/resumes.py` (or extend existing resume router carefully).
- `services/auth_service.py`, `services/authorization.py`, `services/room_service.py`, `services/question_set_service.py`, `services/job_recommendation_service.py`, `services/resume_profile_service.py`.
- `services/realtime/room_events.py` for WebSocket room orchestration.
- Existing `resume_service`, `question_service`, `interview_service`, `analysis_service`, `scoring_engine`, `report_service` remain core and should be refactored only where needed.

## Suggested entities (adapt to actual ORM conventions)
- `users`: id, email_normalized, password_hash, role, is_active, email_verified_at, created_at, updated_at, last_login_at.
- `candidate_profiles`: user_id, display_name, phone_optional, location_optional, headline, profile_json, created_at, updated_at.
- `resumes`: id, candidate_user_id, storage_key, original_filename, content_hash, mime_type, file_size, parser_version, status, created_at, deleted_at.
- `resume_profiles`: resume_id, structured_profile_json, extracted_text_encrypted_or_restricted, confidence_json, confirmed_at, updated_at.
- `job_role_templates`: id, slug, title, level, role_family, required_skills_json, preferred_skills_json, min_experience_months, active, version.
- `job_recommendations`: id, candidate_user_id, nullable resume_id, role_template_id, match_score, explanation_json, input_source (resume/manual_profile/combined/optional_interview_signal), created_at, algorithm_version. Recommendations must work without an interview.
- `question_sets`: id, owner_admin_id, name, source_filename, schema_version, version, status, checksum, created_at.
- `question_set_items`: id, question_set_id, question_id_or_payload, ordinal, metadata_json.
- `interview_rooms`: id, created_by_admin_id, room_code_hash, invite_token_hash, title, status, scheduled_at, expires_at, duration_seconds, mode, proctoring_preset, current_sequence_version, started_at, ended_at.
- `room_participants`: id, room_id, candidate_user_id, status, joined_at, left_at, reconnect_count.
- `room_questions`: id, room_id, source_question_id, ordinal, status, time_limit_seconds, asked_at, completed_at.
- `room_events`: id, room_id, actor_user_id, event_type, payload_json_redacted, sequence_no, created_at.
- `auth_sessions` or `refresh_tokens`: hashed token, user_id, expires_at, revoked_at, rotation_family_id.
- `audit_logs`: actor, action, resource type/id, timestamp, request id, safe metadata.
- Existing `sessions`, `session_questions`, `proctoring_events`, `reports` remain connected to the room/candidate where applicable. Add nullable `candidate_user_id`, `room_id`, `interview_mode` via migration rather than duplicating report data.

## Room state machine
`DRAFT -> SCHEDULED -> LOBBY -> LIVE <-> PAUSED -> PROCESSING -> COMPLETED`
Terminal alternatives: `CANCELLED`, `EXPIRED`, `FAILED`.

Rules:
- Only authorized admin may transition DRAFT/SCHEDULED/LOBBY to LIVE.
- Only server transitions room state; clients request actions.
- Each successful action increments `sequence_no` / `current_sequence_version`.
- Reject stale commands and duplicate commands idempotently.
- Candidate reconnect fetches authoritative snapshot then subscribes to subsequent events.
- Admin can reorder only questions not yet asked; historical order remains immutable and auditable.
- Do not allow room to be started after expiry without explicit authorized extension.

## API outline (final routes must follow existing conventions)
- `POST /api/auth/register`, `/login`, `/logout`, `/refresh`, `/forgot-password`, `/reset-password`, `/verify-email`
- `GET /api/auth/me`
- `GET/PUT /api/candidate/profile`
- `POST /api/resumes`, `GET /api/resumes`, `GET /api/resumes/{id}`, `DELETE /api/resumes/{id}`, `POST /api/resumes/{id}/confirm`
- `GET /api/jobs/recommendations`
- `POST /api/admin/rooms`, `GET /api/admin/rooms`, `GET/PUT/DELETE /api/admin/rooms/{room_id}`
- `POST /api/admin/rooms/{room_id}/invite`, `/start`, `/pause`, `/resume`, `/advance`, `/reorder`, `/end`
- `POST /api/admin/question-sets`, `GET /api/admin/question-sets`, `POST /api/admin/question-sets/{id}/validate`
- `POST /api/rooms/join`, `GET /api/rooms/{room_id}/snapshot`, `WS /api/rooms/{room_id}/events`
- Existing interview, analysis and report endpoints should be reused where possible and protected by ownership/role checks.

## Realtime and media
- WebSocket is for low-volume structured events only: room state, question changes, timers, connection state and admin actions.
- WebRTC media transport is separate. For multi-user production, use an SFU (LiveKit or equivalent) with short-lived scoped tokens and room ACLs.
- Never relay high-bitrate video/audio through FastAPI WebSocket messages.
- If MVP omits admin live media viewing, say so in UI and deployment docs; candidate-side proctoring and recording still run using current approach.
- Media storage uses private buckets/volumes, signed short-lived playback URLs and retention jobs.

## Migrations and compatibility
- Add migrations incrementally, with indexes and constraints.
- Test migration upgrade from a copy of existing SQLite DB and a clean PostgreSQL DB.
- Do not drop or rename current tables/columns until compatibility and rollback are proven.


## Scheduling, analytics and learning roadmap
- Extend `interview_rooms` with timezone, reminder policy and schedule metadata; persist timestamps in UTC.
- Add candidate calendar/upcoming interview endpoints.
- Add admin analytics endpoints with scope checks, aggregate privacy thresholds and filters.
- Add candidate learning-roadmap and progress-update endpoints.
- Recommendation service accepts confirmed resume data OR manual candidate profile; resume/report IDs are nullable. Never require interview history.
