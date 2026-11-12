# MASTER PROMPT — PLUTO vProctor v2 Upgrade

You are the senior engineer and technical lead upgrading the EXISTING PLUTO vProctor repository. Read this entire prompt and all files in `PLUTO_vProctor_Upgrade_Pack/` before changing code.

## 0. Install developer tools first
The owner explicitly asks you to download/configure these tools yourself. Read `ANTIGRAVITY_TOOLS_SETUP.md` and follow its current official instructions:
1. GSD (`gsd-build/get-shit-done`) for planning.
2. Superpowers (`obra/superpowers`) for engineering workflow and TDD.
3. Context7 (`context7.com`) for current docs through supported Antigravity MCP/skills integration.
Use project-local scope where supported. Verify installations and record versions/results in `docs/ANTIGRAVITY_TOOLING.md`. These are developer tools only, never app runtime dependencies. Do not bypass permission prompts. If OAuth is needed, ask the owner to complete official browser sign-in without sharing credentials in chat. Report failures accurately.

## 0. Mission
Upgrade PLUTO vProctor from a local-first AI mock-interview application into a secure, multi-user interview and proctoring platform with:
1. Candidate registration, login, profile and interview history.
2. A separate administrator login experience and role-protected admin console.
3. Resume upload OR manual profile entry, editable parsing, skill extraction, job-role matching and fresher-friendly job recommendations. Every candidate gets recommendations regardless of AI interview mode, admin-hosted mode, both or no interview yet; never gate recommendations on interview participation.
4. Admin-created live interview rooms with invitation link and room code, question dataset upload/selection, question ordering and live interview controls.
5. A human-proctored online interview mode that reuses the existing offline interview/proctoring method and analysis pipeline as much as possible.
6. Reliability improvements to live proctoring, question retrieval, transcript handling, job coverage and reports.
7. Production deployment, observability, backups and privacy controls.
8. Interview scheduling/calendar, admin analytics dashboard and candidate skill-development roadmap.

Do not rebuild from scratch. Preserve and improve the existing React 19/Vite, FastAPI, SQLAlchemy/Alembic, MediaPipe, Whisper, Ollama, retrieval, scoring and report components.

## 1. Mandatory first action: audit and safe cleanup proposal
Before implementation:
- Inspect the actual repository, git status/branch, current docs, all existing Antigravity rules/workflows, frontend routes, backend routers/services/models, Alembic history, tests, scripts, datasets, model assets, database files and storage directories.
- Verify the repository against the supplied `PLUTO-vProctor.md` reference; treat the actual checked-out code as truth if it differs.
- Identify duplicate, generated, stale, unused or oversized files. For every candidate, show path, size, last use/reference evidence, import/reference search results, whether tracked by git, and risk.
- Inspect database tables, row counts, indexes, constraints, duplicate/orphan records, migration state and database file size. Inspect storage file inventory separately.
- Produce `docs/UPGRADE_AUDIT.md` and `docs/CLEANUP_PROPOSAL.md`, plus a backup/restore procedure.
- Make a timestamped backup of SQLite DB and relevant storage before any approved database/storage cleanup. Never delete the only copy.
- Do NOT delete data, migrations, datasets, embeddings, model weights, evaluation fixtures, recordings, reports, user uploads, or source code merely because it appears unused. Do not drop tables or run destructive SQL.
- Stop after the audit and cleanup proposal. Ask the repository owner to approve the exact destructive actions. Safe, reversible cleanup (e.g. ignored cache directories) may be proposed but must still be reported.

## 2. Preserve existing design constraints
- Maintain local-first processing for the existing AI interview pipeline by default.
- No cloud upload of resume, audio, video, transcripts, face landmarks or biometric/proctoring data unless the user/admin has been clearly informed, consent is collected, and the deployment explicitly configures the relevant storage/processing.
- Retain the existing dataset-ground-truth policy: use curated question datasets for technical question selection. Do not silently replace them with synthetic LLM-generated technical questions.
- Keep GPU resource locks and the 6 GB VRAM constraint. Do not load multiple heavy models concurrently.
- Preserve deterministic scoring guardrails, Pydantic validation, retries/fallbacks, timestamped events and report traceability.
- Do not change current scoring weights or penalties without documenting the reason, impact, tests and migration.
- Maintain compatibility with current offline flow. The human-hosted room mode is additive.
- Keep API contracts backward compatible where practical; version breaking changes.

## 3. Required user experiences
### Candidate
- Every authenticated candidate gets job recommendations from their resume or manually entered profile, independent of interview mode or interview completion. Candidates who only use AI interviews, only join admin-hosted interviews, use both, or have never interviewed must all have this feature.
- Recommendations must not require a report. Interview performance may be an optional, explainable signal only.
- Candidate dashboard includes upcoming interviews/calendar, recommended jobs and a personalized skill-development roadmap.
- Public landing page with clear Candidate Login / Sign Up and Admin Login entry points.
- Candidate authentication, logout, password reset flow, profile, resume library, editable parsed profile, recommended jobs, upcoming/past interviews and reports.
- Resume upload accepts supported PDF/DOCX/TXT with strict validation and size limits. Extracted fields must be shown in a review/edit step before saving. Manual entry must be equally supported.
- Candidate can accept an interview invitation through a secure token link or enter a room code. Do not expose room participant lists or private data.
- Candidate preflight, consent, camera/mic check, calibration and interview flow should reuse existing components and behavior.

### Admin
- Admin dashboard includes interview scheduling/calendar, aggregate analytics and candidate progress insights.
- Separate `/admin/login` UI and admin layout; separate from candidate login visually and in route structure.
- Admin role must be enforced on the backend, not just hidden in the frontend.
- Admin dashboard: create/edit/cancel rooms, schedule or start now, set duration, configure proctoring preset, select/upload question dataset, preview questions, reorder questions, set question timing, invite candidates, monitor room status, end interview and access authorized reports.
- Admin must be able to start, pause/resume where appropriate, skip/advance, reorder upcoming questions and end the interview. Every control must be audited.
- Room codes must be high entropy, rate-limited, expiry-bound and revocable. Invitation URLs use unguessable signed tokens; never use sequential IDs as access credentials.

## 4. Resume intelligence and job matching
- Extend current parser and skills taxonomy; do not discard current deterministic matching.
- Support parsed sections: contact details, summary, education, skills, projects, internships/experience, certifications and links when present.
- Return field-level confidence and source snippets/locations where feasible. Unknown values remain blank; never invent experience, degrees or skills.
- Show extracted values for candidate confirmation/editing.
- Build job recommendations from required/preferred skills, experience level, role family and candidate evidence. Explain match reasons and missing skills.
- Include fresher / internship / trainee / entry-level roles. Keep role data in a maintainable versioned JSON or database source, not duplicated frontend constants.
- Add taxonomy coverage tests and role data validation. Recommendations are advisory, not hiring decisions.

## 5. Human-proctored online interview mode
The online human-proctored mode must use the same candidate preparation, calibration, live gaze/posture detection, audio/video capture, event schema, transcription, analysis and report pipeline as the current offline mode wherever technically possible.

Additional room orchestration:
- Admin creates room and receives a candidate invitation link and short room code.
- Candidate joins and waits in a lobby until admin starts.
- Admin chooses question set and ordering before start; admin may reorder remaining questions during the interview.
- Admin start event begins the candidate interview. Question changes are authoritative server events and are synchronized to candidate UI.
- Candidate cannot choose or modify the question order in a controlled human-hosted room.
- Handle disconnect/reconnect, duplicate joins, stale room state, browser refresh, admin disconnect and room expiry safely.
- Record who performed each action and when.
- Separate “human proctor controls the interview” from “AI analysis evaluates recorded signals”; make this explicit in the data model and UI.
- If admin needs to watch live candidate video/audio, use a secure WebRTC design (prefer a managed/self-hostable SFU such as LiveKit for multi-participant reliability). Do not stream video through ordinary REST polling or put media blobs in the database. If live video is not in the first release, clearly label MVP as room orchestration + candidate-side proctoring + recording, and keep the SFU integration as a later phase.
- Do not silently switch to hosted media/AI providers. Require explicit configuration, consent, region/data-processing review and documented fallback behavior.

## 6. Question retrieval and proctoring reliability
- Benchmark current retrieval before tuning. Add evaluation for Recall@K, MRR, nDCG where labels allow, duplicate rate, domain coverage, latency and fallback behavior.
- Add query normalization, role/skill filters, difficulty controls, deduplication and clear source IDs for each question.
- Keep dataset split boundaries intact. Do not train or tune against test split.
- Improve proctoring using confidence thresholds, temporal smoothing/hysteresis, calibration quality checks, lighting/face visibility diagnostics, event debouncing and false-positive evaluation.
- Treat gaze-away as a weak signal, not proof of misconduct. Provide event confidence, duration, evidence timestamp and human review status.
- Distinguish camera unavailable, face not detected, model error, tab blur and suspected behavior. Do not collapse these into one penalty.
- Do not penalize a candidate for system/network faults. Record system-health events separately.
- Add browser compatibility tests and real-world fixture tests. Preserve the existing fixture evaluation harness.

## 7. Security and data architecture
Implement the security controls in `specs/SECURITY_PRIVACY_AND_FAIRNESS.md`:
- Password hashing using Argon2id or bcrypt with appropriate parameters; never store plaintext passwords.
- Short-lived access tokens and secure refresh/session rotation; HttpOnly, Secure, SameSite cookies where cookie auth is used; CSRF protection for cookie-based state changes.
- Email verification and password reset tokens with expiry and one-time use; avoid requiring email provider for local dev.
- RBAC: candidate, admin, optionally super_admin. Backend authorization on every protected endpoint and object-level ownership checks.
- Login throttling, room-code throttling, upload validation, MIME/magic-byte validation, malware scanning strategy for production, secure headers, strict CORS, secret management and audit logs.
- Prevent IDOR across session, report, resume, room and recording resources.
- Encrypt transport; define encryption-at-rest approach for production storage and database backups.
- Data retention and deletion workflows for resumes, recordings, reports and account data.
- Consent version, timestamp, purpose and policy version stored for proctoring/recording.
- Do not log passwords, tokens, resume text, transcripts, raw video or sensitive biometric data.

## 8. Additional required features
- Scheduling: date/time/timezone, duration, invites, expiry and optional reminders. Store UTC, render local time.
- Analytics: completion, attendance, score distributions, skill gaps, roles/domains and question usage; filter by date, role and mode. Show sample sizes and protect candidate privacy.
- Learning roadmap: evidence-based skill gaps, approved-dataset practice questions, project ideas and learning topics, with progress tracking.
- Universal recommendations: resume/manual-profile based and available before any interview. Never require AI or human-hosted interview history.

## 9. Engineering execution
Work phase-by-phase according to `antigravity/PHASE_PLAN.md`.
For each phase:
1. State files inspected and intended changes.
2. Write/adjust tests first for critical behavior.
3. Implement the smallest coherent increment.
4. Run relevant backend tests, frontend tests, lint/build, retrieval/proctoring evals.
5. Report exact commands, pass/fail counts and known failures.
6. Update docs, API examples and migration notes.
7. Stop at phase gate and ask before proceeding to the next major phase.

Do not perform a massive one-shot refactor. Do not replace libraries/frameworks without a compatibility and cost analysis. Do not add a dependency until its need is justified.

## 10. Definition of done
A phase is not done merely because code was generated. It is done when:
- migrations apply on a clean DB and an existing DB backup;
- backend authorization tests cover allowed and denied roles/ownership;
- frontend build and tests pass;
- API integration tests pass;
- core offline interview regression tests pass;
- human-hosted room state and question ordering tests pass;
- resume parser tests cover PDF/DOCX/TXT, malformed files and manual entry;
- retrieval and proctoring benchmarks show measured outcomes;
- docs and deployment configuration are updated;
- secrets and personal data are absent from tracked files and logs.

## 11. First response required from you
Do not implement features yet. First return:
A. Repository reality check vs supplied reference.
B. Database and storage inventory.
C. Proposed safe cleanup list with evidence and risk.
D. Backup and restore plan.
E. Architecture gaps and recommended implementation order.
F. Questions that truly block the plan (ask one concise grouped set).
Then stop and wait for explicit approval of the cleanup proposal.
