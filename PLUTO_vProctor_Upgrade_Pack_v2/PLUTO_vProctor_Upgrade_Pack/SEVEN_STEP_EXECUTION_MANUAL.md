# PLUTO vProctor v2 — Seven-Step Execution Manual

## Step 1 — Prepare and protect the existing repository
1. Open the existing PLUTO repository in Antigravity (folder containing `GEMINI.md`, `KICKOFF.md`, `backend/`, `frontend/`).
2. Ask Antigravity to inspect `git status`, branch and uncommitted changes.
3. Commit or create a full recoverable backup. Do not discard uncommitted work.
4. Extract this ZIP into the repository root. Merge folders carefully; do not overwrite existing project files blindly.
5. Confirm the upgrade pack folder is present.
**Checkpoint:** source, datasets, database and storage are recoverable.

## Step 2 — Let Antigravity install the three tools
1. Ask Antigravity: “Read `PLUTO_vProctor_Upgrade_Pack/ANTIGRAVITY_TOOLS_SETUP.md` and install GSD, Superpowers and Context7 using their official Antigravity-compatible methods. Verify each and record results. Do not change application dependencies.”
2. Approve exact commands when prompted.
3. Complete any official OAuth/browser sign-in yourself. Never paste credentials into chat or project files.
4. Reload Antigravity and verify GSD commands, Superpowers skills and Context7 lookup.
5. Check `docs/ANTIGRAVITY_TOOLING.md`.
**Checkpoint:** all three tools verified, or exact failures documented.

## Step 3 — Start the specification-driven audit
1. Open `PLUTO_vProctor_Upgrade_Pack/prompts/ANTIGRAVITY_MASTER_PROMPT.md`.
2. Paste the entire master prompt into Antigravity.
3. Ensure it reads every file under `specs/` and `antigravity/`, plus existing `GEMINI.md`, `KICKOFF.md` and `.agent/`.
4. Ask it to use GSD to plan the roadmap, but execute Phase 0 only.
5. Require inspection of actual repository files rather than assumptions from the reference document.
**Checkpoint:** repository reality check, architecture map and baseline test report.

## Step 4 — Review database, storage and cleanup
1. Review `docs/UPGRADE_AUDIT.md` and `docs/CLEANUP_PROPOSAL.md`.
2. Check database tables, row counts, indexes, duplicates/orphans, Alembic state and DB file locations.
3. Check storage, resumes, recordings, reports, fixtures, datasets, embeddings and model weights.
4. Verify backup/restore by restoring to a separate temporary location.
5. Approve cleanup items individually. Reject broad “delete unused files” requests.
6. Do not delete source, migrations, datasets, model weights, fixtures or user media without evidence, backup and explicit approval.
**Checkpoint:** exact cleanup actions approved; no destructive action before approval.

## Step 5 — Build authentication, candidate profile and universal recommendations
After approval:
1. Stabilize current application and record baseline.
2. Implement authentication, candidate/admin roles, separate admin login UI and backend RBAC.
3. Implement resume upload, manual profile entry, parser review and confirmation.
4. Expand fresher/entry-level job-role templates.
5. Implement explainable job recommendations available to ALL authenticated candidates before any interview and regardless of AI or admin-hosted mode.
6. Implement candidate learning roadmap and progress tracking.
**Checkpoint:** tests prove ownership/security, parser accuracy and recommendations independent of interview mode.

## Step 6 — Build admin-hosted interviews and additional features
1. Implement interview scheduling with timezone support, invitation links, room codes and optional reminders.
2. Implement admin question dataset upload/validation, selection and ordering.
3. Implement lobby, admin start, pause/resume, advance, reorder upcoming questions and end.
4. Reuse existing preflight, calibration, live gaze, recording, analysis and report pipeline.
5. Implement authenticated WebSocket room state, synchronization and reconnect recovery.
6. Add admin analytics with privacy safeguards.
7. If live admin video/audio viewing is required, implement WebRTC through an SFU such as LiveKit as a separately tested feature. Never send media blobs through REST or WebSocket.
8. Preserve self-practice AI interview mode.
**Checkpoint:** end-to-end tests prove both interview modes work and question order stays synchronized.

## Step 7 — Reliability, deployment and release
1. Run backend tests, frontend tests/build, retrieval benchmarks, fixture evaluation and full evaluation suite.
2. Test low lighting, glasses, camera/mic loss, network loss, browser refresh and admin disconnect.
3. Review consent, privacy, retention, deletion, security and fairness.
4. Deploy staging with PostgreSQL, Redis, private media storage, worker, HTTPS and secrets management.
5. Run migration tests, backup restore, load tests and rollback drill.
6. Pilot with a small group before public release.
7. Keep offline AI interview available if hosted rooms are disabled.
**Checkpoint:** release only when acceptance gates in `specs/QA_AND_ACCEPTANCE_PLAN.md` pass.

## Reusable checkpoint prompt
“Use the PLUTO vProctor Upgrade Pack as the requirements source. Continue only with the next approved phase. Use GSD for milestone tracking, Superpowers for disciplined implementation/testing, and Context7 for current official library docs. Preserve the existing offline AI interview. Run required tests, report exact results and stop at the next approval gate. Do not perform destructive operations without explicit approval.”
