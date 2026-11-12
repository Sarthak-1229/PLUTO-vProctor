# QA & Acceptance Plan

## Regression baseline
Before changes, run and record:
- backend pytest suite
- frontend FSM tests
- frontend production build
- fixture evaluation gate
- retrieval evaluation suite
- full existing evaluation suite where practical

Record exact baseline metrics and failures in `docs/UPGRADE_BASELINE.md`.

## Authentication and authorization
- Register/login/logout/refresh/password reset/email verification.
- Password hashes are non-reversible.
- Candidate A cannot access Candidate B's resume, report, session, recording or room.
- Candidate cannot invoke admin endpoints.
- Admin cannot access unassigned rooms.
- Expired/revoked token/session/invite/room code is rejected.
- Rate limiting and CSRF/CORS tests.

## Resume
- PDF, DOCX and TXT valid files; malformed and spoofed files; oversize; empty document; scanned PDF/OCR unavailable behavior.
- Extraction confidence and missing fields; user edit/confirm; manual entry.
- Parser must never fabricate a value.
- Recommendation explanations must list evidence and gaps.
- Verify resume deletion covers file and derived data.

## Rooms
- Create, invite, join, wait in lobby, start, pause/resume, advance, reorder upcoming questions, end, expire, cancel.
- Concurrent admin actions; stale sequence version; duplicate request; reconnect; browser refresh; admin disconnect.
- Unauthorized join, brute-force room code and expired token.
- Candidate receives same authoritative question sequence after reconnect.
- Audit log records actor, action and time.

## Proctoring and analysis
- Preserve existing fixture metrics and regression gates.
- Test lighting, glasses, camera angle, face occlusion, multiple faces, low FPS, camera loss, mic loss, background noise, browser tab switch and network interruption.
- Measure false-positive rate and timestamp accuracy.
- Distinguish system faults from behavior events.
- Verify calibration quality and confidence.
- Ensure TTS windows do not count as candidate speech.
- Verify video/audio timeline alignment and report consistency.

## Retrieval and jobs
- Measure Recall@1/5, MRR, nDCG where labels permit, duplicate rate, latency and role/domain coverage.
- Test exact skill, alias, typo, multi-skill, fresher and no-experience profiles.
- Verify question source IDs and dataset provenance.
- Ensure test split is not used for tuning.

## Performance and deployment
- API load, concurrent rooms, WebSocket fan-out, upload bandwidth, worker queue depth and memory/VRAM.
- Migration on copied existing DB and clean PostgreSQL.
- Backup restore drill.
- Staging smoke test and rollback rehearsal.

## Release gate
Do not release if:
- a critical authorization test fails;
- existing offline interview flow regresses;
- destructive migration lacks backup/rollback;
- user data or secrets leak into logs;
- fixture/proctoring reliability falls below agreed baseline without documented approval;
- live room question ordering diverges between admin and candidate;
- privacy/consent UI is missing.
