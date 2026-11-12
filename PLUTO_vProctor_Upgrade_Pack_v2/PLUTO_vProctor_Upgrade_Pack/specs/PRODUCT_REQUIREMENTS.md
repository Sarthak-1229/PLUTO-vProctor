# Product Requirements — PLUTO vProctor v2

## Product direction
A multi-user interview platform with two interview modes:
- **Self-practice / offline-first AI interview:** preserve current seven-step candidate workflow.
- **Admin-hosted online interview:** admin controls room lifecycle and question order; candidate uses the same preflight, calibration, proctoring, recording and post-interview analysis methods.

## Roles and permissions
| Capability | Visitor | Candidate | Admin | Super Admin |
|---|---:|---:|---:|---:|
| View public landing page | Yes | Yes | Yes | Yes |
| Candidate registration/login | Yes | Yes | Optional | Optional |
| Upload/edit own resume | No | Yes | No by default | Audited support only |
| View own recommendations/reports | No | Yes | No by default | Audited support only |
| Create/manage rooms | No | No | Yes | Yes |
| Upload/manage question sets | No | No | Yes | Yes |
| Start/advance/reorder room questions | No | No | Yes | Yes |
| Manage admins/system config | No | No | No | Yes |

## Candidate account
- Every authenticated candidate receives job recommendations regardless of interview mode: AI-only, admin-hosted-only, both, or no interview yet. Recommendations must not depend on a completed interview/report.
- Recommendations work from an uploaded/confirmed resume, manually entered profile/skills, or both. Interview performance may be an optional transparent extra signal, never a prerequisite.

- Registration, login, logout, email verification, password reset.
- Profile with manually entered details and editable parsed resume.
- Resume upload: PDF, DOCX, TXT; validate extension, MIME, magic bytes, size, page count and parser failure.
- Parse into structured fields and show confidence/provenance. Never infer missing facts.
- Candidate can save multiple resume versions and choose one for recommendations/interview.
- Recommended jobs show match score, matched skills, missing skills, experience alignment and “why recommended”.
- Candidate dashboard lists upcoming invitations, active rooms, past interviews and reports.
- Candidate can revoke/delete resume and request account data deletion subject to retention/legal constraints documented by deployment.

## Admin application
- Dedicated `/admin/login`, `/admin/*` layout and visual design.
- Admin dashboard includes room status, scheduled interviews, candidate invitations and recent completed interviews.
- Create room: title, candidate(s), scheduled time, duration, proctoring preset, interview mode, question set, question order, optional per-question time.
- Question bank upload: accept documented CSV/JSONL schema; validate each row; preview, reject malformed records with row-level errors; store dataset version and provenance.
- Select existing curated question dataset and filter by role/domain/skills/difficulty.
- Reorder question slate with drag/drop and keyboard-accessible controls. Persist only upcoming order during active interview.
- Start, pause/resume, skip/advance, reorder upcoming questions, end, cancel and extend room (permission-gated).
- Admin can monitor connection, camera/mic readiness and system health. If live media monitoring is enabled, it uses secure WebRTC/SFU, not REST.
- Audit every room action.

## Room joining
- Signed, expiring invitation URL plus room code.
- Candidate must authenticate or complete an explicitly configured guest verification flow.
- Lobby before admin starts; display clear device/consent checklist.
- Prevent unauthorized, duplicate or expired joins; handle reconnect and browser refresh.
- Do not expose internal session IDs as access credentials.

## Interview execution
- Reuse current hardware check, 4-second calibration, MediaRecorder, LiveGazeDetector, event recording, Whisper, video pipeline, audio pipeline, scoring and report.
- In hosted mode, server owns authoritative question sequence and room state.
- Admin question changes sync to candidate over authenticated WebSocket.
- Persist sequence version and event log to recover state after reconnect.
- Candidate can see current question, time remaining, connection state and allowed controls.
- Candidate cannot skip/reorder unless room policy explicitly permits it.
- On completion, run existing asynchronous analysis and generate report.

## Job catalogue expansion
- Add entry-level and fresher roles such as Junior Python Developer, Junior Java Developer, Frontend Developer Intern, React Developer Intern, Backend Developer Intern, Full-Stack Developer Trainee, QA / Test Engineer Trainee, Manual Tester, Automation Tester Intern, Data Analyst Intern, Junior Data Engineer, ML Intern, AI/Prompt Engineering Intern (with realistic skill requirements), Cloud Support Associate, DevOps Intern, Cybersecurity Analyst Trainee, IT Support Associate, SQL Developer Trainee, Android Developer Intern, UI Developer Intern, Technical Support Engineer and Graduate Engineer Trainee.
- These are candidate role suggestions, not a claim of actual vacancies. Separate job-role templates from live job listings.
- Maintain a canonical skills taxonomy with aliases and role-to-skill mappings.
- Do not create fake employers or imply roles are currently hiring. Label sample role templates as illustrative.

## Reports and history
- Existing report remains accessible to candidate and authorized admin only.
- Preserve score breakdown, Q&A evidence, video timeline, timestamps and PDF export.
- Add interview mode, room metadata, question set version, admin actions and system-health notes.
- Distinguish automated analysis indicators from human observations.
- Add candidate-facing explanation and appeal/review request workflow.


## Additional required features

### Interview scheduling and calendar
- Admin schedules rooms with date/time, timezone, duration, candidate(s), reminders and expiry.
- Candidate dashboard shows upcoming AI practice and admin-hosted interviews in one timeline/calendar.
- Optional email reminders use a configurable provider; local development works without email. External Google/Outlook calendar integration is optional; built-in scheduling must work independently.
- Store timestamps in UTC and render in the user's timezone.

### Admin analytics dashboard
- Aggregate completion, attendance, score distributions, skill-wise performance, role/domain distribution, question difficulty and question usage.
- Filters: date range, role, interview mode and status.
- Separate AI practice and human-hosted cohorts; show sample sizes and missing-data warnings.
- Restrict candidate-level details to authorized admins; prefer aggregate views.

### Candidate development roadmap
- Generate an actionable improvement plan from evidenced resume skill gaps and interview answer weaknesses.
- Recommend skills, approved-dataset practice questions, project ideas and learning topics.
- Explain why each item is recommended and link to evidence.
- Candidate can mark items planned, in progress or completed. Recommendations are advisory and never guarantee employment.

### Unified job recommendations
- Dedicated jobs/recommendations page and candidate dashboard widget for every authenticated candidate.
- Never gate recommendations on AI or admin-hosted interview participation.
- Explain match reasons, missing skills, level/experience alignment and limitations.
