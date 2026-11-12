# Security, Privacy & Fairness Requirements

## Authentication
- Use a maintained password hashing library with Argon2id preferred; never reversible encryption or plaintext.
- Normalize email and enforce unique constraint.
- Use short-lived access tokens and rotating refresh sessions; store only refresh token hashes.
- For browser cookies: HttpOnly, Secure in production, SameSite appropriate to deployment, CSRF protection on mutations.
- Password reset and email verification tokens are random, hashed at rest, one-time, short expiry.
- Add login and reset rate limits, generic error messages and suspicious-login audit events.

## Authorization
- Roles: candidate, admin, super_admin (if needed).
- Enforce role and object ownership on every backend route/service. Frontend route guards are UX only.
- Candidate may access only their own resumes, rooms, recordings and reports.
- Admin may access only rooms they own or are explicitly assigned to.
- Prevent IDOR and mass assignment. Use Pydantic allowlists for request fields.
- Audit privilege changes, room actions, report access, exports and deletion.

## Upload safety
- Extension + MIME + magic-byte validation; strict maximum file size and parser limits.
- Random storage keys; never trust user-supplied paths or filenames.
- Protect against path traversal, archive bombs, malformed PDFs and parser timeouts.
- Production malware scanning/quarantine strategy; never execute uploaded content.
- Keep uploads outside public web root. Use private object storage and short-lived signed URLs.

## Proctoring consent and fairness
- Explain camera, microphone, recording, live monitoring, AI analysis, retention and purpose before consent.
- Store consent policy version, purpose, timestamp and user action.
- Provide a non-proctored alternative or accommodation process where feasible.
- Face/gaze/posture indicators are imperfect and affected by lighting, disability, camera placement, hardware and network conditions.
- Never state that a gaze event proves cheating. Label it as a signal requiring context/human review.
- Do not penalize device/network/model failure as candidate misconduct.
- Show event type, confidence, duration, timestamp and system-health context.
- Allow admin review, candidate explanation/appeal, and correction of false positives.
- Avoid emotion, personality, protected-trait or mental-state inference.

## Data handling
- Minimize stored resume text and biometric-derived data.
- Define separate retention periods for resumes, raw video/audio, transcripts, reports and audit logs.
- Deletion must cover DB rows, object storage, derived artifacts, caches and backups according to documented backup expiry.
- Encrypt transport (TLS); encrypt disks/object storage and backups at rest in production.
- Keep secrets in deployment secret manager/environment, never committed `.env`.
- Logs must redact credentials, invite tokens, room codes, resume text, transcripts and media URLs.
- Provide data export/deletion process and incident response runbook.

## Security test requirements
- Candidate cannot read another candidate's report/resume/session.
- Candidate cannot call admin room controls.
- Admin cannot access rooms outside their scope.
- Expired/revoked invitation and room codes fail.
- Rate limits apply to login, reset and room join.
- Upload validation rejects spoofed MIME, oversized and malformed files.
- CSRF/CORS/cookie configuration tested in production-like setup.
