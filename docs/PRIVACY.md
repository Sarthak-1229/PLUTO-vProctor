# PLUTO vProctor: Data Retention & Candidate Privacy Policy

PLUTO vProctor is built around principles of data minimization, transparent candidate consent, and enforceable right-to-be-forgotten controls compliant with GDPR and CCPA guidelines.

---

## 1. Candidate Consent & Disclosure
- **Mandatory Consent Check:** Candidates must explicitly opt-in to automated video, audio, and attention monitoring on the Screening screen before media hardware is engaged.
- **On-Screen Telemetry Indicators:** Candidates are provided with clear on-screen badges indicating when their camera is recording (`REC`), when audio is being transcribed, and when gaze telemetry is active.

---

## 2. Retention Policy
- **Default TTL:** Video recordings, audio extracts, and evaluation artifacts are stored for a maximum configurable period of **30 days** (`RETENTION_DAYS=30`).
- **Automated Lifecycle Expiration:** Ephemeral session caches in `sessionStorage` expire automatically after 3 hours.

---

## 3. "Delete My Data" Implementation

Candidates or administrators can permanently purge all stored session data on-demand via the UI or API:

### API Endpoint:
```http
DELETE /api/interview/{sessionId}
DELETE /api/interview/{sessionId}/delete-data
```

### Physical Purge Actions Executed:
1. **Video Recordings:** Deleted from `storage/recordings/{sessionId}_interview.webm`.
2. **Audio Extracts:** Extracted 16kHz WAV tracks deleted from `storage/audio/{sessionId}_*.wav`.
3. **Resumes & Transcripts:** Resume uploads and generated PDFs deleted from `storage/resumes/` and `storage/reports/`.
4. **Database Cascade:** Explicit deletion of all associated `ProctoringEvent`, `SessionQuestion`, and `InterviewSession` records.
5. **Memory State:** Session cache is wiped from client `sessionStorage` and `localStorage`.

---

## 4. PII Protection in Logs
- Application structured logs record only operational request traces (`X-Request-ID`, endpoint, latency, status code).
- Candidate transcripts, resume text, and biometric landmarks are **never** logged to server stdout or plain-text application log files.
