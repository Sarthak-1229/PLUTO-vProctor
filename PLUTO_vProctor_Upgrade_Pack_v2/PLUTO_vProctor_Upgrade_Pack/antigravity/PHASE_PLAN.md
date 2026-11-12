# Implementation Phases & Stop Gates

## Phase 0 — Repository, database and storage audit (STOP FOR APPROVAL)
- Verify repo and git state; map current architecture.
- Inventory DB schema, row counts, indexes, duplicates/orphans and migration status.
- Inventory storage, datasets, models, generated artifacts and duplicated docs.
- Propose safe cleanup with evidence; backup/restore plan.
- Deliver `UPGRADE_AUDIT.md`, `CLEANUP_PROPOSAL.md`, `UPGRADE_BASELINE.md`.
- Stop. Obtain explicit approval before deleting anything.

## Phase 1 — Stabilize foundation
- Add architecture decision records, environment validation, feature flags and API error conventions.
- Capture regression baselines.
- Fix only proven reliability defects with tests.
- No new user-facing features yet.

## Phase 2 — Authentication, accounts and RBAC
- User model, secure auth, sessions/tokens, candidate/admin roles.
- Separate candidate and admin login UI shells.
- Backend route protection and ownership checks.
- Migration, auth tests, audit logging.

## Phase 3 — Resume profile and universal recommendations
- Resume library, parser review/edit step, manual profile form.
- Field provenance/confidence and no-fabrication behavior.
- Versioned role templates and expanded fresher roles.
- Explainable job recommendations for every candidate, available before interviews and independent of interview mode.
- Candidate skill-development roadmap with progress tracking.
- Tests proving AI-only, hosted-only and never-interviewed candidates all receive recommendations.

## Phase 4 — Admin scheduling, analytics, question bank and room management
- Interview scheduling, timezone handling, calendar/timeline and reminder outbox.
- Admin aggregate analytics with privacy thresholds and filters.
- Admin question bank and room management
- Question set upload/validation/versioning.
- Admin dashboard, room creation, invite token/room code, lobby.
- Room state machine, audit log, WebSocket control events.
- Admin start/advance/reorder/end; candidate receives authoritative order.

## Phase 5 — Hosted interview candidate experience
- Reuse preflight, calibration, live gaze detector, recording and analysis.
- Connect interview session to room and candidate.
- Reconnect, refresh, disconnect and expiry behavior.
- Keep offline mode regression green.

## Phase 6 — Live human media monitoring (decision gate)
- If required, implement SFU/WebRTC with scoped ephemeral tokens.
- Build admin monitor UI, candidate consent and connection quality.
- Load/security test; do not use REST/WebSocket for media payloads.
- If deferred, document MVP limitation and leave safe integration boundary.

## Phase 7 — Reliability, retrieval and fairness
- Retrieval benchmarks and tuning.
- Proctoring false-positive/false-negative review and confidence.
- Job role coverage and parser taxonomy evaluation.
- Improve diagnostics, report evidence and system-health separation.

## Phase 8 — Deployment and operations
- Staging PostgreSQL/Redis/private media storage/worker.
- CI, migration workflow, secrets, TLS, monitoring, backups.
- Load tests, restore test, rollback drill.
- Limited pilot and release checklist.

At every phase gate, provide changed files, tests run, exact results, known issues, migration/rollback notes and ask before moving on.
