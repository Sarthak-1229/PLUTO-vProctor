# PLUTO vProctor — Comprehensive System Architecture Specification

**Document Version:** 2.0  
**Product Version:** 0.1.0  
**Architectural Baseline:** Multimodal AI Video Interview & Proctoring Platform  
**Last Updated:** November 2026  

---

## Table of Contents
1. [Executive System Overview](#1-executive-system-overview)
2. [High-Level Architecture & Subsystem Boundaries](#2-high-level-architecture--subsystem-boundaries)
3. [Frontend Client Architecture](#3-frontend-client-architecture)
4. [Backend API Gateway & Service Architecture](#4-backend-api-gateway--service-architecture)
5. [Authentication, Token Rotation & RBAC Flow](#5-authentication-token-rotation--rbac-flow)
6. [Candidate Workflow & Dual-Mode Lifecycles](#6-candidate-workflow--dual-mode-lifecycles)
   - 6.1 [Self-Practice Interview Lifecycle (7-Step Wizard)](#61-self-practice-interview-lifecycle-7-step-wizard)
   - 6.2 [Hosted Recruiter Interview Lifecycle (Authoritative FSM)](#62-hosted-recruiter-interview-lifecycle-authoritative-fsm)
7. [WebRTC Peer-to-Peer Signaling & Media Architecture](#7-webrtc-peer-to-peer-signaling--media-architecture)
8. [Session Recording & Media Storage Architecture](#8-session-recording--media-storage-architecture)
9. [AI & Computer Vision Multimodal Processing Pipeline](#9-ai--computer-vision-multimodal-processing-pipeline)
   - 9.1 [MediaPipe Iris & Gaze Divergence Engine](#91-mediapipe-iris--gaze-divergence-engine)
   - 9.2 [Faster-Whisper & Acoustic Disfluency Engine](#92-faster-whisper--acoustic-disfluency-engine)
10. [Question Retrieval, Knapsack MMR & Selection Engine](#10-question-retrieval-knapsack-mmr--selection-engine)
11. [Explainable Monotonic Evaluation & Scoring Pipeline](#11-explainable-monotonic-evaluation--scoring-pipeline)
12. [Resume Parsing & Universal Recommendation Pipeline](#12-resume-parsing--universal-recommendation-pipeline)
13. [Candidate Skill-Development Roadmap Generator](#13-candidate-skill-development-roadmap-generator)
14. [Database & Local Storage Architecture](#14-database--local-storage-architecture)
15. [Asynchronous Background Tasks & Job Queue](#15-asynchronous-background-tasks--job-queue)
16. [Local SQLite Mode vs PostgreSQL Deployment Compatibility](#16-local-sqlite-mode-vs-postgresql-deployment-compatibility)
17. [Component Requirements Matrix (Required vs Optional)](#17-component-requirements-matrix-required-vs-optional)

---

## 1. Executive System Overview

**PLUTO vProctor** (*Personalized Learning & Unified Test Operations — Virtual Proctor*) is an enterprise-grade multimodal artificial intelligence platform providing automated self-practice interview simulations and recruiter-hosted live interview rooms.

The platform is designed around three architectural tenets:
1. **Local-First Privacy & Zero-Cloud Leakage:** All biometric facial landmark tracking, iris gaze angle estimation, acoustic disfluency analysis, speech transcription, and generative scoring execute on the local host machine. No candidate audio, video, or biometric landmarks are transmitted to third-party public clouds.
2. **Explainable Monotonic Deductions:** Instead of "black-box" generative grades, interview scores are deterministically reconstructed through an itemized deduction ledger where every penalty links to an exact millisecond timestamp, rule code, and video offset.
3. **Dual-Mode Operational Parity:** The system gracefully supports single-user offline practice without authentication (`AUTH_ENABLED=False`) as well as multi-user recruiter rooms with strict Argon2id authentication, rotating JWT token families, and real-time WebRTC media streaming.

---

## 2. High-Level Architecture & Subsystem Boundaries

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Client (React 18 + Vite 8)"]
        UI_Practice["Self-Practice Wizard"]
        UI_Hosted["Live Hosted Room (WebRTC)"]
        UI_Admin["Admin Console & Room Manager"]
        UI_Candidate["Profile, Resumes, Recommendations & Roadmap"]
        WASM_Vision["MediaPipe WASM (Gaze & 478 Face Landmarks)"]
    end

    subgraph APILayer["FastAPI API Gateway (:8000)"]
        ReqMiddleware["Request-ID Correlation & Security Headers"]
        AuthRBAC["Auth & RBAC Service (Argon2id + JWT + CSRF)"]
        RoomWS["Realtime WebSocket Signaling Hub"]
        JobQueue["Async Multi-Worker Background Queue"]
    end

    subgraph InferenceLayer["Local Multimodal AI Telemetry"]
        WhisperASR["Faster-Whisper (CPU int8 Speech-to-Text)"]
        DisfluencyEng["Acoustic Disfluency & Pace Engine"]
        GazeEng["Video Pipeline (One-Euro Filter & Gaze Vector)"]
        ScoringEng["Monotonic 4-Bucket Scoring Engine"]
        OllamaLLM["Local Ollama Daemon (qwen2.5:3b / Deterministic Fallback)"]
    end

    subgraph DataLayer["Persistence & Storage Layer"]
        SQLiteDB[("SQLite Database (pluto.db)")]
        FileStore["Local Storage (storage/recordings, resumes, audio)"]
        CatalogData["Curated Dataset (1,799 Verified Questions)"]
    end

    ClientLayer <-->|REST API + HTTP/1.1| APILayer
    ClientLayer <-->|WebSocket Signaling| RoomWS
    ClientLayer <-.->|WebRTC P2P Media Stream| ClientLayer
    APILayer --> AuthRBAC
    APILayer --> JobQueue
    JobQueue --> WhisperASR
    JobQueue --> DisfluencyEng
    JobQueue --> GazeEng
    WhisperASR --> ScoringEng
    DisfluencyEng --> ScoringEng
    GazeEng --> ScoringEng
    OllamaLLM -.-> ScoringEng
    APILayer --> SQLiteDB
    APILayer --> FileStore
    JobQueue --> SQLiteDB
    JobQueue --> FileStore
    CatalogData --> APILayer
```

---

## 3. Frontend Client Architecture

The frontend is a single-page application (SPA) built using **React 18**, **Vite 8**, and **Tailwind CSS 4** with a custom Neo-brutalist design theme.

### Primary Subsystems:
- **`App.jsx` (Central Coordinator):** Coordinates global application state, active media streams, route resolution, and session state recovery.
- **`utils/authClient.js`:** Pure SPA route guards (`resolveRouteAccess`), in-memory access token storage, cookie parsers, and silent token refresh queue.
- **`utils/interviewFSM.js`:** Finite State Machine managing self-practice transitions (`IDLE -> ROLE_SELECTED -> SCREENING -> PRECHECK -> CALIBRATING -> ASKING -> LISTENING -> EVALUATING -> FINISHED`).
- **`utils/questionSetUtils.js`:** Array normalization, schema validation, and JSON import preview utilities.
- **`components/LiveInterviewRoom.jsx`:** Dual-stream WebRTC room containing candidate and interviewer video feeds, real-time proctoring telemetry HUD, synchronized question cards, and host controls.
- **`components/ReportView.jsx`:** Interactive evaluation report featuring total scores, readiness stamps, 5-axis competency radar charts, per-question transcripts, and a synchronized video player scrubber.

---

## 4. Backend API Gateway & Service Architecture

The backend is built on **FastAPI** (Python 3.12) running under **Uvicorn**:

### 14 Modular Routers (`backend/app/routers/`):
1. `auth.py`: Registration, login, silent refresh, password reset, and portal isolation.
2. `candidate.py`: Candidate profiles, resume management, and career goals.
3. `candidate_roadmap.py`: Candidate analytics and milestone roadmaps.
4. `admin.py`: User governance, role modifications, and global interview browser.
5. `admin_analytics.py`: Macro-level platform throughput and proctoring distributions.
6. `admin_rooms.py`: Room scheduling and host orchestration controls.
7. `rooms.py`: Candidate join endpoints, lobby state snapshots, and WebRTC WebSocket signaling.
8. `question_sets.py`: Custom question set management, versioning, conflict-safe deletion, and JSON imports.
9. `jobs.py`: 12 verified engineering job specifications and Trie prefix search.
10. `resume.py`: Initial screening and resume fit calculation.
11. `resumes.py`: Candidate multi-resume library uploads with binary magic-byte validation.
12. `interview.py`: Mock session initialization, answer submissions, and video streaming.
13. `analysis.py`: Background telemetry processing and pipeline status polling.
14. `report.py`: Evaluation report generation, IDOR-protected retrieval, and PDF export.

---

## 5. Authentication, Token Rotation & RBAC Flow

```mermaid
sequenceDiagram
    autonumber
    actor Candidate as Candidate Browser
    participant API as FastAPI Gateway
    participant DB as SQLite (pluto.db)

    Candidate->>API: POST /api/auth/login {email, password}
    API->>DB: Query User by email
    API->>API: Verify password via Argon2id
    API->>DB: Insert new refresh_token & rotation_family_id
    API-->>Candidate: 200 OK + in-memory access_token + Set-Cookie pluto_refresh_token (HTTP-Only)
    
    Note over Candidate,API: 15 Minutes Elapse (Access Token Expires)

    Candidate->>API: GET /api/candidate/profile (401 Unauthorized)
    Candidate->>API: POST /api/auth/refresh (Cookie: pluto_refresh_token + X-CSRF-Token)
    API->>DB: Validate token hash in rotation family
    API->>DB: Mark old token revoked, insert new rotated token
    API-->>Candidate: 200 OK + new access_token + rotated pluto_refresh_token cookie
    Candidate->>API: Retry GET /api/candidate/profile (200 OK)
```

---

## 6. Candidate Workflow & Dual-Mode Lifecycles

### 6.1 Self-Practice Interview Lifecycle (7-Step Wizard)
Autonomous simulation designed for candidate self-preparation:
1. **Role & Resume Selection (`select`):** Candidate selects target job and provides resume or profile skills.
2. **Screening Fit & Consent (`screening`):** Algorithmic keyword and vector fit check. Candidate signs proctoring consent.
3. **Pre-Flight Hardware Check (`precheck`):** Verifies camera clarity and live microphone volume level.
4. **Neutral Gaze Calibration (`calibration`):** 5-second center gaze capture capturing iris coordinates and head pitch/yaw to establish an individualized baseline.
5. **Live Mock Interview (`interview`):** AI audio prompter reads questions via TTS; speech timer enforces response windows; live proctoring HUD monitors gaze in real time.
6. **Multimodal Telemetry Processing (`processing`):** WebM recording uploaded; parallel video and audio analysis workers process telemetry.
7. **Evaluation Dossier (`report`):** Interactive report displayed with overall score, letter grade, deduction timeline, and PDF download.

### 6.2 Hosted Recruiter Interview Lifecycle (Authoritative FSM)
Server-side state machine governing live rooms (`backend/app/services/room_service.py`):

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> SCHEDULED : Schedule Room & Questions
    SCHEDULED --> LOBBY : Candidate Joins
    LOBBY --> LIVE : Host Admits Candidate
    LIVE --> PAUSED : Host Pauses (Technical Issue)
    PAUSED --> LIVE : Host Resumes
    LIVE --> PROCESSING : Host Concludes Interview
    PROCESSING --> COMPLETED : Pipelines Finalize Scoring
    COMPLETED --> [*]
```

---

## 7. WebRTC Peer-to-Peer Signaling & Media Architecture

In hosted interview rooms, live media is streamed directly between the interviewer and candidate using WebRTC:

```mermaid
sequenceDiagram
    autonumber
    actor Candidate as Candidate Browser
    participant WS as FastAPI WebSocket Hub (:8000)
    actor Host as Recruiter / Host Browser

    Candidate->>WS: Connect /api/rooms/{id}/ws?token=JWT
    Host->>WS: Connect /api/rooms/{id}/ws?token=JWT
    WS-->>Candidate: room.snapshot + occupants
    WS-->>Host: room.snapshot + occupants

    Host->>WS: webrtc.signal (offer, target: candidate)
    WS->>Candidate: webrtc.signal (offer, from: host)
    Candidate->>Candidate: setRemoteDescription(offer) & createAnswer()
    Candidate->>WS: webrtc.signal (answer, target: host)
    WS->>Host: webrtc.signal (answer, from: candidate)
    Host->>Host: setRemoteDescription(answer)

    Candidate->>WS: webrtc.signal (ice_candidate)
    WS->>Host: webrtc.signal (ice_candidate)
    Host->>WS: webrtc.signal (ice_candidate)
    WS->>Candidate: webrtc.signal (ice_candidate)

    Note over Candidate,Host: WebRTC P2P Direct Media Stream Established (Audio / Video)
```

---

## 8. Session Recording & Media Storage Architecture

- **Client-Side Capture:** Media streams are captured via the standard browser `MediaRecorder` API using `video/webm;codecs=vp9,opus` (with fallback to `vp8,opus`).
- **Binary Upload:** Finalized recordings are uploaded via multipart form POST to `/api/interview/{id}/recording`.
- **Storage Layout:**
  - Videos: `storage/recordings/{session_id}_hosted.webm`
  - Resumes: `storage/resumes/{user_id}_{hash}.pdf`
  - Extracted Audio: `storage/audio/{session_id}.wav`
- **Streaming & Seek Support:** `GET /api/interview/{id}/video` implements HTTP `206 Partial Content` with byte-range headers (`Range: bytes=start-end`), enabling instant seeking in long interview recordings.

---

## 9. AI & Computer Vision Multimodal Processing Pipeline

```mermaid
flowchart LR
    VideoFile["Session Video (.webm)"] --> PyAV["Audio/Video Demuxer (PyAV)"]
    PyAV --> Frames["Video Frame Stream (15 FPS)"]
    PyAV --> AudioWAV["Audio WAV Stream (16 kHz Mono)"]

    subgraph VideoPipeline["Video Processing Pipeline"]
        Frames --> FaceMesh["MediaPipe FaceMesh (478 Landmarks)"]
        FaceMesh --> IrisTracking["Iris Vectors (468/473)"]
        FaceMesh --> HeadPose["3D Euler Head Pose (Pitch, Yaw, Roll)"]
        IrisTracking --> OneEuro["One-Euro Adaptive Filter"]
        HeadPose --> OneEuro
        OneEuro --> BaselineSubtract["Subtract User Calibration Baseline"]
        BaselineSubtract --> GazeViolations["Flag Gaze & Posture Deductions"]
    end

    subgraph AudioPipeline["Audio Processing Pipeline"]
        AudioWAV --> Whisper["Faster-Whisper (CPU int8)"]
        Whisper --> Transcript["Question Transcripts"]
        AudioWAV --> Disfluency["Disfluency Detection"]
        Disfluency --> Fillers["Flag Filler Words ('um', 'uh')"]
        Disfluency --> Pauses["Flag Unusually Long Pauses (>3.5s)"]
        Disfluency --> WPM["Compute Speech Pace (WPM)"]
    end

    GazeViolations --> ScoringEngine["Scoring Engine"]
    Transcript --> ScoringEngine
    Fillers --> ScoringEngine
    Pauses --> ScoringEngine
    WPM --> ScoringEngine
```

---

## 10. Question Retrieval, Knapsack MMR & Selection Engine

When dynamic question selection is used, PLUTO vProctor budgets questions from the 1,799 verified catalog using two algorithms:

1. **0/1 Knapsack Duration Budgeting:** Selects questions whose estimated answer durations fit exactly within the configured interview duration limit (e.g. 45 minutes).
2. **Maximal Marginal Relevance (MMR) Diversification:** Selects questions that maximize relevance to the target job while minimizing redundancy across question domains:
   $$\text{MMR} = \arg\max_{Q_i \in R \setminus S} \left[ \lambda \cdot \text{Sim}(Q_i, \text{Job}) - (1 - \lambda) \max_{Q_j \in S} \text{Sim}(Q_i, Q_j) \right]$$

---

## 11. Explainable Monotonic Evaluation & Scoring Pipeline

PLUTO vProctor evaluates interviews using four weighted scoring buckets:

| Scoring Bucket | Weight | Evaluation Method & Telemetry Inputs |
|---|---|---|
| **Technical Depth** | **35%** | Answer correctness against ground-truth rubrics using BM25 keyword matching (60%) and LLM evaluation (40%). |
| **Communication** | **25%** | Speech pace ($90 - 180\text{ WPM}$), phrase fluency, pause frequency, and filler word penalty deductions. |
| **Proctoring Integrity** | **25%** | Starts at 100 points; deducts points for sustained gaze diversion ($>2.5\text{s}$), extreme head rotation, and face absence. |
| **Resume Relevance** | **15%** | Alignment between claimed resume skills and concepts demonstrated during answers. |

---

## 12. Resume Parsing & Universal Recommendation Pipeline

- **Multi-Format Extraction:** PDF (via `pdfplumber`), DOCX (via `python-docx`), and plain text.
- **Magic-Byte Binary Validation:** Verifies genuine file signatures (`%PDF-`, `PK\x03\x04`) to prevent disguised malicious file uploads.
- **Competency Matching:** Cross-references extracted tokens against catalog skills using SentenceTransformers semantic similarity and Jaccard intersection.

---

## 13. Candidate Skill-Development Roadmap Generator

- **Analytics Synthesis:** Gathers performance across all historical sessions for the candidate.
- **Readiness Grade:** Computes cumulative grade (A, B, C, D) using weighted historical growth curves.
- **Milestone Drills:** Automatically synthesizes targeted study tasks focusing on lowest-scoring competency domains.

---

## 14. Database & Local Storage Architecture

- **Engine:** SQLite 3 configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and a 30-second busy timeout.
- **Location:** `backend/app/pluto.db`.
- **Entity Count:** 22 relational tables managing identity, resumes, jobs, question sets, rooms, sessions, telemetry events, and reports.

---

## 15. Asynchronous Background Tasks & Job Queue

- **In-Process Worker Queue:** Manages background execution of heavy multimodal video and audio analysis pipelines.
- **Concurrency Control:** Limits simultaneous video pipelines on CPU to prevent system freezing.
- **Polling Interface:** Clients poll progress via `/api/analysis/{sessionId}/status` every 1.5 seconds.

---

## 16. Local SQLite Mode vs PostgreSQL Deployment Compatibility

PLUTO vProctor is architected for zero-code-change migration between local development and cloud deployments:

| Architectural Property | Local Development Mode (Current) | Cloud Deployment Mode (Future) |
|---|---|---|
| **Database** | SQLite 3 (`backend/app/pluto.db`) | PostgreSQL 16+ via `psycopg` (v3) |
| **Connection String** | `sqlite:///./backend/app/pluto.db` | `postgresql+psycopg://user:pass@host/db` |
| **File Storage** | Local Disk (`storage/`) | S3 / Blob Storage with Signed URLs |
| **Realtime Signaling** | In-Process WebSocket Manager | Redis Pub/Sub Cluster Hub |

---

## 17. Component Requirements Matrix (Required vs Optional)

| Component / Subsystem | Self-Practice Mode | Recruiter Hosted Mode | Fallback if Missing |
|---|---|---|---|
| **FastAPI Backend (:8000)** | **Required** | **Required** | System unavailable |
| **React Frontend (:5173)** | **Required** | **Required** | System unavailable |
| **SQLite Database (`pluto.db`)** | **Required** | **Required** | System unavailable |
| **Webcam & Microphone** | **Required** | **Required** | Blocks at pre-flight check |
| **Local Faster-Whisper** | **Required** | **Required** | Downloads on first run |
| **MediaPipe FaceMesh WASM** | **Required** | **Required** | Served locally via Vite |
| **Local Ollama Daemon (:11434)** | Optional | Optional | Falls back to deterministic rubric scoring |
| **WebRTC STUN Server** | Not Needed | **Required** | Falls back to loopback candidates |
| **Authentication (`AUTH_ENABLED`)** | Optional | **Required** | Offline practice allows guest runs |
