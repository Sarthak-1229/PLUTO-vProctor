# PLUTO vProctor — Troubleshooting & Diagnostic Guide

**Document Version:** 1.0  
**Product Version:** 0.1.0  
**Target Audience:** System Administrators, Local Operators, Developers, Technical Support  
**Last Updated:** November 2026  

---

## Table of Contents
1. [Overview & Diagnostic Strategy](#1-overview--diagnostic-strategy)
2. [Installation and Startup Issues](#2-installation-and-startup-issues)
   - 2.1 [Python Virtual Environment Issues](#21-python-virtual-environment-issues)
   - 2.2 [Node.js & npm Dependency Issues](#22-nodejs--npm-dependency-issues)
   - 2.3 [Backend Server Startup Failures](#23-backend-server-startup-failures)
   - 2.4 [Frontend Vite Dev Server Startup Failures](#24-frontend-vite-dev-server-startup-failures)
   - 2.5 [Configuration & Environment Variable Errors](#25-configuration--environment-variable-errors)
   - 2.6 [Database Connection & SQLite Lock Errors](#26-database-connection--sqlite-lock-errors)
3. [Authentication & Authorization Issues](#3-authentication--authorization-issues)
   - 3.1 [Login Credential Verification Failures](#31-login-credential-verification-failures)
   - 3.2 [Expired Access Tokens & Silent Refresh Failures](#32-expired-access-tokens--silent-refresh-failures)
   - 3.3 [CSRF Token Mismatch & 403 Forbidden](#33-csrf-token-mismatch--403-forbidden)
   - 3.4 [Role Permission Denials (403 Forbidden)](#34-role-permission-denials-403-forbidden)
4. [Resume Parsing & Job Recommendations](#4-resume-parsing--job-recommendations)
   - 4.1 [Unsupported Resume File Type or Magic Byte Failure](#41-unsupported-resume-file-type-or-magic-byte-failure)
   - 4.2 [Resume Text Extraction Failure](#42-resume-text-extraction-failure)
   - 4.3 [Empty Job Recommendations](#43-empty-job-recommendations)
5. [Interview Session & Telemetry Pipeline](#5-interview-session--telemetry-pipeline)
   - 5.1 [Camera & Microphone Permission Denials](#51-camera--microphone-permission-denials)
   - 5.2 [Pre-Flight Device Check Fails](#52-pre-flight-device-check-fails)
   - 5.3 [WebSocket Signaling Disconnections](#53-websocket-signaling-disconnections)
   - 5.4 [WebRTC Peer Connection Failures (ICE / NAT)](#54-webrtc-peer-connection-failures-ice--nat)
   - 5.5 [Candidate Mid-Interview Disconnection](#55-candidate-mid-interview-disconnection)
   - 5.6 [Reconnection & FSM Sequence State Recovery](#56-reconnection--fsm-sequence-state-recovery)
   - 5.7 [Session Recording Unavailable](#57-session-recording-unavailable)
   - 5.8 [Evaluation Pipeline Processing Delays](#58-evaluation-pipeline-processing-delays)
6. [AI Inference & Local Model Telemetry](#6-ai-inference--local-model-telemetry)
   - 6.1 [Ollama Service Unavailable](#61-ollama-service-unavailable)
   - 6.2 [LLM Model Not Found or Out of Memory](#62-llm-model-not-found-or-out-of-memory)
   - 6.3 [Faster-Whisper Transcription Errors](#63-faster-whisper-transcription-errors)
   - 6.4 [High Inference Latency on CPU](#64-high-inference-latency-on-cpu)
7. [Reports, Question Sets & Administrative Actions](#7-reports-question-sets--administrative-actions)
   - 7.1 [Missing Report or Report In Processing](#71-missing-report-or-report-in-processing)
   - 7.2 [Report Access Denied (IDOR Block)](#72-report-access-denied-idor-block)
   - 7.3 [Question-Set File Import Syntax Errors](#73-question-set-file-import-syntax-errors)
   - 7.4 [Active Room Prevents Question Set Deletion (409 Conflict)](#74-active-room-prevents-question-set-deletion-409-conflict)

---

## 1. Overview & Diagnostic Strategy

When diagnosing issues in PLUTO vProctor:
1. **Identify the Layer:** Determine whether the failure occurs in the Browser (Client/MediaRecorder/WebRTC), the FastAPI Gateway, the SQLite Database, or the Local AI Engine (Ollama/Faster-Whisper/MediaPipe).
2. **Consult Request IDs:** Every HTTP response from the backend contains an `X-Request-ID` header. Search backend logs for `[Req:<request_id>]` to trace exact error call stacks.
3. **Check System Health:** Run `curl http://127.0.0.1:8000/api/health` and `curl http://127.0.0.1:8000/api/ready` to verify component readiness.

---

## 2. Installation and Startup Issues

### 2.1 Python Virtual Environment Issues
- **Symptoms:** `ModuleNotFoundError: No module named 'fastapi'` or Python command fails with missing package errors.
- **Likely Causes:** Activated virtual environment is pointing to wrong Python binary, or dependencies were not installed in `backend/.venv`.
- **Diagnostic Steps:**
  ```powershell
  backend\.venv\Scripts\python.exe --version
  backend\.venv\Scripts\python.exe -m pip list
  ```
- **Safe Resolution:**
  1. Ensure Python 3.11 or 3.12 64-bit is installed.
  2. Reinstall dependencies into the local environment:
     ```powershell
     backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
     ```
- **File Paths:** `backend/requirements.txt`, `backend/.venv/`.

### 2.2 Node.js & npm Dependency Issues
- **Symptoms:** `npm run dev` fails with `vite: command not found` or module resolution errors in `node_modules`.
- **Likely Causes:** Corrupt `node_modules` or out-of-date Node version.
- **Diagnostic Steps:**
  ```powershell
  node --version   # Must be >= 18.0.0
  npm --version
  ```
- **Safe Resolution:**
  ```powershell
  cd frontend
  npm install
  npm test         # Verify standard node test suite passes
  ```
- **File Paths:** `frontend/package.json`, `frontend/node_modules/`.

### 2.3 Backend Server Startup Failures
- **Symptoms:** Server terminates immediately upon execution with `OSError: [WinError 10048] Only one usage of each socket address is normally permitted`.
- **Likely Causes:** Port 8000 is already occupied by a previously running uvicorn instance or another local service.
- **Diagnostic Steps:**
  ```powershell
  netstat -ano | findstr :8000
  ```
- **Safe Resolution:**
  1. Identify the Process ID (PID) from the `netstat` command output.
  2. Terminate the orphaned process:
     ```powershell
     taskkill /PID <PID> /F
     ```
  3. Restart the backend via `run_dev.bat` or:
     ```powershell
     backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
     ```
- **File Paths:** `backend/app/main.py`.

### 2.4 Frontend Vite Dev Server Startup Failures
- **Symptoms:** Vite starts on port 5174 instead of 5173, or fails to connect to backend API with network errors.
- **Likely Causes:** Port 5173 is occupied, or Vite's local dev cache is corrupted.
- **Diagnostic Steps:**
  ```powershell
  netstat -ano | findstr :5173
  ```
- **Safe Resolution:**
  1. Terminate any orphaned node processes listening on 5173:
     ```powershell
     taskkill /IM node.exe /F
     ```
  2. Clear Vite cache if necessary:
     ```powershell
     Remove-Item -Recurse -Force frontend\node_modules\.vite
     cd frontend && npm run dev
     ```
- **File Paths:** `frontend/vite.config.js`.

### 2.5 Configuration & Environment Variable Errors
- **Symptoms:** `RuntimeError: Unsafe production config: SECRET_KEY must be configured` on startup.
- **Likely Causes:** `ENVIRONMENT=production` is set in `.env` without providing a cryptographically secure 32+ character `SECRET_KEY`.
- **Diagnostic Steps:** Inspect `.env` file settings.
- **Safe Resolution:**
  - For local development, set `ENVIRONMENT=development` in `.env`.
  - In development mode, PLUTO vProctor automatically generates an ephemeral in-memory secret if none is specified.
- **File Paths:** `.env`, `backend/app/config.py`.

### 2.6 Database Connection & SQLite Lock Errors
- **Symptoms:** `sqlite3.OperationalError: database is locked`.
- **Likely Causes:** Multiple processes attempting concurrent write operations on SQLite with long open transactions.
- **Diagnostic Steps:** Check for concurrent pytest sessions running against `pluto.db` while the backend dev server is active.
- **Safe Resolution:**
  1. Terminate test runs before launching the interactive server.
  2. PLUTO vProctor uses SQLite WAL (Write-Ahead Logging) mode and a 30-second busy timeout to mitigate contention.
  3. If database file is corrupted:
     > [!WARNING]
     > Never delete `pluto.db` without first taking a backup. Make a copy:
     > `Copy-Item backend\app\pluto.db backend\app\pluto.db.bak`
- **File Paths:** `backend/app/pluto.db`, `backend/app/db/database.py`.

---

## 3. Authentication & Authorization Issues

### 3.1 Login Credential Verification Failures
- **Symptoms:** `POST /api/auth/login` returns `HTTP 401 Unauthorized: Invalid email or password`.
- **Likely Causes:** Incorrect password, email mismatch, or account marked inactive (`is_active = False`).
- **Diagnostic Steps:**
  - Check user table in database:
    ```powershell
    backend\.venv\Scripts\python.exe -c "from backend.app.db.database import SessionLocal; from backend.app.db.models import User; db=SessionLocal(); u=db.query(User).filter_by(email='user@example.com').first(); print(u.id, u.role, u.is_active if u else 'Not found'); db.close()"
    ```
- **Safe Resolution:**
  - Ensure the user registered successfully.
  - Reset the candidate password using the forgot-password flow (`/forgot-password`).
- **File Paths:** `backend/app/routers/auth.py`, `backend/app/services/auth_service.py`.

### 3.2 Expired Access Tokens & Silent Refresh Failures
- **Symptoms:** API calls return `HTTP 401 Unauthorized` after 15 minutes of inactivity.
- **Likely Causes:** The 15-minute in-memory JWT access token expired, and the silent refresh call failed because the HTTP-only refresh cookie (`pluto_refresh_token`) was missing or expired.
- **Diagnostic Steps:** Inspect browser DevTools $\to$ Application $\to$ Cookies $\to$ `http://localhost:5173`. Check if `pluto_refresh_token` exists.
- **Safe Resolution:**
  - In `authClient.js`, `authFetch` automatically attempts silent refresh via `POST /api/auth/refresh`.
  - If the 7-day refresh token has expired, re-authenticate via the login screen.
- **File Paths:** `frontend/src/utils/authClient.js`, `backend/app/routers/auth.py`.

### 3.3 CSRF Token Mismatch & 403 Forbidden
- **Symptoms:** State-changing requests (`POST`, `PUT`, `DELETE`) return `HTTP 403 Forbidden: CSRF token missing or invalid`.
- **Likely Causes:** Request did not provide `X-CSRF-Token` header matching the `pluto_csrf_token` cookie.
- **Diagnostic Steps:** Inspect outgoing request headers in Network tab. Verify `X-CSRF-Token` header is present.
- **Safe Resolution:**
  - Always use `authFetch()` in frontend code, which automatically extracts `pluto_csrf_token` and attaches the `X-CSRF-Token` header.
- **File Paths:** `frontend/src/utils/authClient.js`, `backend/app/routers/auth.py`.

### 3.4 Role Permission Denials (403 Forbidden)
- **Symptoms:** Candidate navigating to `/admin` is redirected, or API returns `HTTP 403 Forbidden: Insufficient permissions`.
- **Likely Causes:** The logged-in user has role `candidate` and is attempting to access admin-only endpoints.
- **Diagnostic Steps:** Check `user.role` from `GET /api/auth/me`.
- **Safe Resolution:**
  - Candidates are prohibited from admin resources by design.
  - To grant administrative rights, a Super Administrator must elevate the account via the Accounts tab (`POST /api/admin/users/{uid}/role`).
- **File Paths:** `backend/app/services/authorization.py`, `backend/app/routers/admin.py`.

---

## 4. Resume Parsing & Job Recommendations

### 4.1 Unsupported Resume File Type or Magic Byte Failure
- **Symptoms:** `POST /api/resumes` returns `HTTP 400 Bad Request: Unsupported file format or corrupt file signature`.
- **Likely Causes:** File extension was renamed (e.g. an image renamed to `.pdf`), or file magic bytes do not match `%PDF-` or PK zip signature.
- **Diagnostic Steps:** Check the first 8 bytes of the uploaded file.
- **Safe Resolution:**
  - Save the resume as a genuine PDF, DOCX, or UTF-8 plain text file from Microsoft Word, Google Docs, or LibreOffice.
  - Ensure file size is under 5 MB.
- **File Paths:** `backend/app/services/resume_service.py`, `backend/app/routers/resumes.py`.

### 4.2 Resume Text Extraction Failure
- **Symptoms:** Resume uploads successfully, but extracted text is empty or garbled.
- **Likely Causes:** The PDF is an image-only scan without an embedded digital text layer.
- **Diagnostic Steps:** Open the PDF in Acrobat or browser and attempt to highlight and copy text. If text cannot be selected, it is a raster scan.
- **Safe Resolution:**
  - Export a clean PDF directly from text authoring software rather than scanning printed paper.
  - Alternatively, use the Candidate Profile page (`/profile`) to enter skills and career history manually.
- **File Paths:** `backend/app/services/resume_service.py`.

### 4.3 Empty Job Recommendations
- **Symptoms:** Recommendations page displays "No matching jobs found".
- **Likely Causes:** Candidate profile has 0 skills listed, no active resume is uploaded, or the job catalog is empty.
- **Diagnostic Steps:**
  ```powershell
  backend\.venv\Scripts\python.exe -c "from backend.app.db.database import SessionLocal; from backend.app.db.models import Job; db=SessionLocal(); print('Jobs count:', db.query(Job).count()); db.close()"
  ```
- **Safe Resolution:**
  - Add at least 3 relevant skills to your Candidate Profile (`/profile`).
  - If job count is 0, initialize database jobs by running the database migration or seed script.
- **File Paths:** `backend/app/routers/candidate.py`, `backend/app/services/recommendation_service.py`.

---

## 5. Interview Session & Telemetry Pipeline

### 5.1 Camera & Microphone Permission Denials
- **Symptoms:** Browser alerts *"Permission denied"* or *"NotFoundError: Requested device not found"*.
- **Likely Causes:** Browser blocked media access, or another application holds exclusive hardware lock on the webcam.
- **Diagnostic Steps:** Check Chrome permissions (`chrome://settings/content/camera`).
- **Safe Resolution:**
  1. Close Zoom, MS Teams, Skype, or OBS.
  2. Click the lock icon in the browser URL bar and set Camera and Microphone to **"Allow"**.
  3. Reload the application page.
- **File Paths:** `frontend/src/components/SystemCheckStep.jsx`.

### 5.2 Pre-Flight Device Check Fails
- **Symptoms:** Audio meter in system check does not move when speaking.
- **Likely Causes:** Wrong microphone input selected, or OS microphone privacy settings disabled.
- **Diagnostic Steps:** Test microphone in Windows Sound Settings (`mmsys.cpl`).
- **Safe Resolution:** Select the correct default input device in Windows settings and browser settings.
- **File Paths:** `frontend/src/components/SystemCheckStep.jsx`.

### 5.3 WebSocket Signaling Disconnections
- **Symptoms:** Console displays `WebSocket connection to 'ws://localhost:8000/ws/rooms/...' failed`.
- **Likely Causes:** Backend server is stopped, or proxy does not support HTTP/1.1 WebSocket upgrades.
- **Diagnostic Steps:** Check backend server terminal for WebSocket connection logs.
- **Safe Resolution:** Ensure FastAPI backend is running on `127.0.0.1:8000`. In reverse proxies (e.g. Nginx), verify `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`.
- **File Paths:** `backend/app/routers/rooms.py`, `frontend/src/components/LiveInterviewRoom.jsx`.

### 5.4 WebRTC Peer Connection Failures (ICE / NAT)
- **Symptoms:** Candidate and host connect to lobby, but video stream displays black screen with `ICE connection state: failed`.
- **Likely Causes:** Direct peer-to-peer UDP traffic blocked by symmetric NAT or corporate firewall.
- **Diagnostic Steps:** Open Chrome WebRTC diagnostics at `chrome://webrtc-internals`. Inspect ICE candidate pairs.
- **Safe Resolution:**
  - For local development on the same machine, WebRTC connects over host loopback candidates.
  - Across restrictive enterprise subnets, configure a TURN server in `.env` (`TURN_SERVER_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL`).
- **File Paths:** `backend/app/config.py`, `frontend/src/components/LiveInterviewRoom.jsx`.

### 5.5 Candidate Mid-Interview Disconnection
- **Symptoms:** Host UI indicates *"Candidate disconnected"*; question timer freezes.
- **Likely Causes:** Candidate network glitch, accidental tab close, or laptop sleep.
- **Diagnostic Steps:** Inspect Room FSM state in `AdminRoomManager.jsx`.
- **Safe Resolution:** The host can click **"Pause Interview"**. The candidate can reopen the room link (`/rooms/:roomId`), re-enter the room, and resume without losing session history.
- **File Paths:** `backend/app/services/room_service.py`.

### 5.6 Reconnection & FSM Sequence State Recovery
- **Symptoms:** Client reconnects but displays out-of-order question.
- **Likely Causes:** WebSocket message dropped during temporary network drop.
- **Diagnostic Steps:** Check room snapshot via `GET /api/rooms/{id}/snapshot`.
- **Safe Resolution:** PLUTO vProctor includes authoritative FSM sequence versioning. On reconnect, the client automatically synchronizes with the server's authoritative snapshot state.
- **File Paths:** `backend/app/services/room_service.py`, `backend/app/routers/rooms.py`.

### 5.7 Session Recording Unavailable
- **Symptoms:** Completed room card displays *"Recording unavailable"* and video player cannot open.
- **Likely Causes:** Candidate disconnected before `MediaRecorder` finalized, or upload to `/api/interview/{id}/recording` timed out.
- **Diagnostic Steps:** Check if the recording file exists on the server file system:
  ```powershell
  Get-ChildItem storage\recordings\
  ```
- **Safe Resolution:**
  - If the `.webm` file is present in `storage/recordings/` but missing from the database record, update `InterviewSession.video_filename` to match the file.
- **File Paths:** `storage/recordings/`, `backend/app/routers/interview.py`.

### 5.8 Evaluation Pipeline Processing Delays
- **Symptoms:** Session status stays in `PROCESSING` for several minutes.
- **Likely Causes:** Video analysis pipeline running on high-resolution video using CPU, or Faster-Whisper model downloading on first run.
- **Diagnostic Steps:** Check backend console output. Verify whether Faster-Whisper is downloading weights (`base.en`).
- **Safe Resolution:**
  - On initial run, Faster-Whisper downloads $\approx 140\text{ MB}$ from HuggingFace. Allow the download to complete.
  - Video processing runs $\approx 0.3 \times$ real-time on CPU. A 10-minute interview requires $\approx 3$ minutes of processing.
- **File Paths:** `backend/app/services/video_analysis.py`, `backend/app/services/audio_analysis.py`.

---

## 6. AI Inference & Local Model Telemetry

### 6.1 Ollama Service Unavailable
- **Symptoms:** Backend logs: `httpx.ConnectError: [Errno 10061] Connect call failed ('127.0.0.1', 11434)`.
- **Likely Causes:** Ollama daemon is not running locally.
- **Diagnostic Steps:**
  ```powershell
  curl http://localhost:11434/api/tags
  ```
- **Safe Resolution:**
  1. Start the Ollama service:
     ```powershell
     ollama serve
     ```
  2. In offline/mock mode, PLUTO vProctor gracefully falls back to deterministic algorithmic rubric scoring if Ollama is unreachable.
- **File Paths:** `backend/app/services/llm_client.py`, `backend/app/config.py`.

### 6.2 LLM Model Not Found or Out of Memory
- **Symptoms:** Ollama returns `model 'qwen2.5:3b' not found, try pulling it first`.
- **Likely Causes:** Configured model was not pulled into local Ollama library.
- **Diagnostic Steps:** Run `ollama list`.
- **Safe Resolution:**
  ```powershell
  ollama pull qwen2.5:3b
  ```
- **File Paths:** `backend/app/config.py`.

### 6.3 Faster-Whisper Transcription Errors
- **Symptoms:** `RuntimeError: Library cublas64_12.dll not found` or crash during audio analysis.
- **Likely Causes:** `WHISPER_DEVICE=cuda` configured on a machine without matching CUDA/cuDNN DLLs.
- **Diagnostic Steps:** Inspect `backend/app/config.py` $\to$ `WHISPER_DEVICE`.
- **Safe Resolution:** Set `WHISPER_DEVICE=cpu` and `WHISPER_COMPUTE_TYPE=int8` in `.env` to run robustly on standard CPU hardware without GPU driver dependencies.
- **File Paths:** `backend/app/config.py`, `backend/app/services/audio_analysis.py`.

### 6.4 High Inference Latency on CPU
- **Symptoms:** Live TTS prompt generation or transcription takes over 30 seconds.
- **Likely Causes:** Large model size configured for CPU inference.
- **Diagnostic Steps:** Check `WHISPER_MODEL_SIZE` in `.env`.
- **Safe Resolution:** Keep `WHISPER_MODEL_SIZE=base.en` (default), which provides high accuracy at $\approx 5\times$ real-time on multi-core CPUs.
- **File Paths:** `backend/app/config.py`.

---

## 7. Reports, Question Sets & Administrative Actions

### 7.1 Missing Report or Report In Processing
- **Symptoms:** Candidate opens `/report/:sessionId` and sees a loading spinner or *"Evaluation processing in progress"*.
- **Likely Causes:** Background analysis pipeline is actively processing telemetry.
- **Diagnostic Steps:** Query `GET /api/analysis/{sessionId}/status` to check `video_pct` and `audio_pct`.
- **Safe Resolution:** Wait for background workers to finalize scoring. The UI polls every 1.5 seconds and refreshes automatically when status reaches `COMPLETED`.
- **File Paths:** `backend/app/routers/analysis.py`, `frontend/src/App.jsx`.

### 7.2 Report Access Denied (IDOR Block)
- **Symptoms:** Navigating to `/report/:sessionId` returns `HTTP 403 Forbidden: Access denied to this evaluation report`.
- **Likely Causes:** Candidate A is attempting to access Candidate B's private evaluation report.
- **Diagnostic Steps:** Check session ownership in database: `candidate_user_id == current_user.id`.
- **Safe Resolution:**
  - Candidates can only view their own evaluation reports.
  - Administrators and Super Administrators can view reports across all candidates. Log in with administrative credentials if auditing as a recruiter.
- **File Paths:** `backend/app/services/authorization.py`, `backend/app/routers/report.py`.

### 7.3 Question-Set File Import Syntax Errors
- **Symptoms:** Import modal displays *"Invalid JSON structure"* or *"Questions array missing"*.
- **Likely Causes:** Uploaded file has trailing commas, single quotes instead of double quotes, or question objects lack `question_text`.
- **Diagnostic Steps:** Open the `.json` file in a text editor or linter.
- **Safe Resolution:** Ensure question items include `question_text` (minimum 5 characters) and valid JSON syntax. Review `docs/ADMIN_USER_MANUAL.md` for example format.
- **File Paths:** `frontend/src/utils/questionSetUtils.js`, `backend/app/routers/question_sets.py`.

### 7.4 Active Room Prevents Question Set Deletion (409 Conflict)
- **Symptoms:** Clicking delete on a question set returns `HTTP 409 Conflict: Cannot delete question set actively assigned to ongoing rooms`.
- **Likely Causes:** An interview room in `LOBBY`, `LIVE`, or `PAUSED` status is referencing this question set.
- **Diagnostic Steps:** Query `GET /api/admin/rooms` to check active room statuses.
- **Safe Resolution:** In the Admin Room Manager, locate the active room and click **"End Interview"** or conclude the session. Once the room reaches `COMPLETED`, the question set can be safely deleted.
- **File Paths:** `backend/app/services/question_set_service.py`, `backend/app/routers/question_sets.py`.
