# PLUTO vProctor — Deployment Dependency Inventory

**Document Version:** 1.0  
**Status:** Pre-Deployment Technical Reference  
**Platform Version:** 0.1.0 (RC1)  
**Date:** November 2026  

---

## 1. Executive Overview

This document provides a comprehensive technical inventory of all fourteen (14) runtime components and services required to run PLUTO vProctor in production and pre-production cloud environments.

Each component is cataloged with:
- **Operational Requirement:** Mandatory vs. Optional / Degradable.
- **Compute Sizing:** Minimum and recommended vCPU, RAM, and GPU requirements.
- **Persistent Storage:** Disk space, I/O throughput, and persistence requirements.
- **Networking:** Ingress/egress protocols, internal/external ports, and TLS requirements.
- **Network Boundary:** Public internet-facing vs. private subnet isolation.
- **Failure Impact:** Consequence to user experience if the component experiences downtime.

---

## 2. Master Dependency Matrix

| # | Component | Requirement Level | vCPU | RAM | GPU | Persistent Disk | Protocol & Ports | Network Boundary |
|---|---|---|---|---|---|---|---|---|
| **1** | **Frontend (React SPA / Nginx)** | **Mandatory** | 0.25 - 0.5 | 128 - 256 MB | None | None (Ephemeral) | HTTP 80, HTTPS 443 | **Public** |
| **2** | **FastAPI Backend (Uvicorn)** | **Mandatory** | 1.0 - 2.0 | 2.0 - 4.0 GB | None | Ephemeral / Shared | HTTP/WS 8000 | **Private** (behind Reverse Proxy/ALB) |
| **3** | **PostgreSQL (RDBMS)** | **Mandatory** (Cloud) | 1.0 - 2.0 | 1.0 - 4.0 GB | None | 20 - 100 GB SSD | TCP 5432 | **Strictly Private** (DB Subnet) |
| **4** | **Redis (Cache & Queue)** | **Recommended** (Scale) | 0.5 - 1.0 | 512 MB - 2 GB | None | Optional (RDB/AOF) | TCP 6379 | **Strictly Private** (Internal Subnet) |
| **5** | **Background Worker** | **Mandatory** | 1.0 - 2.0 | 2.0 - 4.0 GB | None | Shared / S3 access | Internal queue | **Strictly Private** |
| **6** | **Ollama Daemon** | **Mandatory** (Local AI) | 4.0 - 8.0 (CPU) or 2.0 (w/ GPU) | 8 - 16 GB (CPU) or 4 - 8 GB (w/ GPU) | NVIDIA >= 6 GB VRAM | 15 - 30 GB SSD | HTTP 11434 | **Strictly Private** (Internal VPC) |
| **7** | **Qwen2.5:3b Model** | **Mandatory** (w/ Ollama) | Integrated | ~2.5 GB RAM/VRAM | Shared with Ollama | 2.0 GB disk image | Internal to Ollama | Internal |
| **8** | **Faster-Whisper (ASR)** | **Mandatory** | 1.0 - 2.0 | 1.0 - 2.0 GB | Optional | 500 MB model cache | Python in-process | Private (Backend/Worker) |
| **9** | **MediaPipe Face Mesh** | **Mandatory** | Client: Device CPU/GPU; Server: 1.0 | Client: Browser; Server: 512 MB | Client WebGL; Server None | None | WASM client-side / Python server | Client-side (Public) / Server (Private) |
| **10** | **FFmpeg / PyAV** | **Mandatory** | 1.0 - 2.0 (Burst) | 512 MB | None | Temp directory | Subprocess / Lib | Private (Backend/Worker) |
| **11** | **Recording Storage** | **Mandatory** | Managed Cloud Object Storage | Managed | None | 100 MB / session (~100 GB/1k interviews) | HTTPS 443 (S3 API) | **Private Bucket** (Presigned URLs) |
| **12** | **Resume Storage** | **Mandatory** | Managed Cloud Object Storage | Managed | None | 2 MB / resume (~10 GB/5k resumes) | HTTPS 443 (S3 API) | **Strictly Private** (Server-only access) |
| **13** | **WebRTC Signaling Hub** | **Mandatory** (Hosted) | Integrated in Backend | Integrated | None | Ephemeral (Memory/Redis) | WSS 443 (proxied to 8000) | **Public** (via WSS proxy) |
| **14** | **STUN / TURN Servers** | **Mandatory** (P2P NAT) | External or 1.0 vCPU | 512 MB | None | None | UDP/TCP 3478, TURNS 5349, UDP 49152-65535 | **Public** (Internet Facing) |

---

## 3. Deep Component Technical Specifications

```mermaid
flowchart TD
    subgraph Public Internet
        Candidate["Candidate Browser (WebRTC + MediaPipe Client)"]
        Admin["Admin Browser (React SPA Console)"]
    end

    subgraph Edge & Security Layer
        ALB["Reverse Proxy / Application Load Balancer (TLS Termination)"]
        STUN_TURN["STUN / TURN Server (NAT Traversal Relay)"]
    end

    subgraph VPC Private Subnets
        subgraph Web & API Tier
            FE["Frontend Container (Nginx Static Host)"]
            BE["FastAPI Backend Containers (Uvicorn ASGI)"]
        end

        subgraph Worker & Asynchronous Tier
            WORKER["Background Task Worker (Job Queue Consumer)"]
        end

        subgraph Persistent & Cache Tier
            PG[("PostgreSQL 16 (Relational DB)")]
            REDIS[("Redis 7 (Job Queue & WS PubSub)")]
        end

        subgraph AI Inference Tier
            OLLAMA["Ollama Host (Qwen2.5:3b LLM)"]
        end
    end

    subgraph Object Storage Tier
        S3_REC[("Recording Store (Video / Audio)")]
        S3_RES[("Resume Store (Encrypted PDF/DOCX)")]
    end

    Candidate -->|HTTPS / WSS| ALB
    Admin -->|HTTPS / WSS| ALB
    Candidate <-->|P2P Media Stream| Admin
    Candidate -.->|Relay Media (Symmetric NAT)| STUN_TURN
    Admin -.->|Relay Media (Symmetric NAT)| STUN_TURN

    ALB -->|Port 80| FE
    ALB -->|Port 8000 HTTP & WSS| BE

    BE <-->|TCP 5432| PG
    BE <-->|TCP 6379| REDIS
    BE -->|HTTP 11434| OLLAMA
    BE -->|Presigned Upload| S3_REC
    BE -->|Encrypted Write| S3_RES

    WORKER <-->|TCP 6379| REDIS
    WORKER <-->|TCP 5432| PG
    WORKER -->|HTTP 11434| OLLAMA
    WORKER -->|Process Audio/Video| S3_REC
    WORKER -->|Parse Resume| S3_RES
```

---

### Component 1: Frontend (React SPA / Nginx)
- **Role:** Delivers the Single Page Application (Candidate UI, Admin Console, Live Interview Room, Question Set Manager, Report View).
- **Technology:** React 18, Vite, React Router 6, TailwindCSS, Lucide Icons. Built into static assets and served via Nginx 1.27 Alpine.
- **Docker Image:** `frontend/Dockerfile` (Multi-stage Node 22 build, Nginx runtime).
- **Compute Sizing:**
  - *Minimum:* 0.25 vCPU, 128 MB RAM.
  - *Production Target:* 0.5 vCPU, 256 MB RAM (handles 2,000 req/sec static asset delivery).
- **Persistent Storage:** Zero (0). Purely stateless container.
- **Networking:**
  - Ingress: Port 80 (HTTP) internally, exposed via ALB/CloudFront on Port 443 (HTTPS).
  - Reverse proxy directives: Proxies `/api/` and `/ws/` to backend service.
- **Public Accessibility:** **Public.**
- **Failure Impact:** Total loss of web UI; API remains functional via programmatic clients.

---

### Component 2: FastAPI Backend (Uvicorn ASGI Gateway)
- **Role:** Core business logic, authentication/RBAC, REST API endpoints, real-time WebSocket signaling, database queries, and proctoring coordination.
- **Technology:** Python 3.12, FastAPI, Uvicorn (uvloop + httptools), SQLAlchemy 2.0, Pydantic v2.
- **Docker Image:** `backend/Dockerfile` (`python:3.12-slim`, non-root user `pluto`, port 8000).
- **Compute Sizing:**
  - *Minimum:* 1.0 vCPU, 2.0 GB RAM.
  - *Production Target:* 2.0 vCPU, 4.0 GB RAM per container instance (scales horizontally).
- **Persistent Storage:** Ephemeral container disk; mounts `/tmp` for audio/video buffering. In SQLite local fallback mode, requires persistent volume.
- **Networking:**
  - Ingress: Port 8000 (HTTP/WebSocket).
  - Egress: Outbound to PostgreSQL (5432), Redis (6379), Ollama (11434), and Cloud Storage (443).
- **Network Boundary:** **Private Subnet** (accessible only via ALB / Reverse Proxy).
- **Failure Impact:** Complete system outage. All API and WebSocket operations halt.

---

### Component 3: PostgreSQL (RDBMS)
- **Role:** Primary persistent data store for accounts, candidate profiles, resumes, question sets, hosted rooms, interview sessions, telemetry metrics, and evaluation reports.
- **Version:** PostgreSQL 15 or 16+.
- **Driver:** Psycopg 3 (`postgresql+psycopg://`) with async pool or Asyncpg (`postgresql+asyncpg://`).
- **Compute Sizing:**
  - *Minimum (Dev/Staging):* 1.0 vCPU, 1.0 GB RAM (AWS RDS `db.t4g.micro`).
  - *Production Target:* 2.0 vCPU, 4.0 GB RAM (AWS RDS `db.t4g.small` or `db.t4g.medium`).
- **Persistent Storage:** 20 GB gp3 SSD (auto-scaling to 100 GB+). IOPS: 3,000 baseline.
- **Networking:** Port 5432 (TCP). Strictly isolated in private database subnets with security group limiting access exclusively to Backend and Worker tasks.
- **Network Boundary:** **Strictly Private.**
- **Failure Impact:** Application becomes read-only or crashes if connection fails. Local development falls back to SQLite if `SQLITE_FALLBACK=true`.

---

### Component 4: Redis (Cache, Task Queue & PubSub Broker)
- **Role:**
  1. Distributed background job queue broker (`backend/app/services/job_queue.py`).
  2. Multi-node WebSocket broadcast pub/sub for horizontal backend scaling.
  3. Distributed IP and account rate limiting.
- **Version:** Redis 7.0+.
- **Compute Sizing:**
  - *Minimum:* 0.25 vCPU, 256 MB RAM (AWS ElastiCache `cache.t4g.micro`).
  - *Production Target:* 0.5 vCPU, 1.0 GB RAM.
- **Persistent Storage:** In-memory with optional append-only file (AOF) or snapshot (RDB) persistence (1 - 5 GB).
- **Networking:** Port 6379 (TCP / TLS enabled `rediss://`).
- **Network Boundary:** **Strictly Private.**
- **Failure Impact:**
  - If Redis is unavailable, background tasks fall back to in-memory threading queue (single instance only). Horizontal WebSocket messaging across multiple backend instances degrades to local-instance broadcasts.

---

### Component 5: Background Worker
- **Role:** Asynchronous processing of heavy compute tasks: PDF resume parsing, Whisper speech-to-text audio processing, video proctoring timeline alignment, and report PDF synthesis.
- **Technology:** Python 3.12 daemon executing `backend.app.services.job_queue:job_queue.run_worker_loop`.
- **Compute Sizing:**
  - *Minimum:* 1.0 vCPU, 2.0 GB RAM.
  - *Production Target:* 2.0 vCPU, 4.0 GB RAM per worker instance.
- **Persistent Storage:** Shared temp volume or S3 bucket access.
- **Networking:** Outbound TCP 6379 (Redis), TCP 5432 (Postgres), HTTP 11434 (Ollama), HTTPS 443 (S3).
- **Network Boundary:** **Strictly Private.**
- **Failure Impact:** API remains responsive, but post-interview evaluations, audio transcriptions, and resume parsing tasks are queued until worker recovers.

---

### Component 6: Ollama LLM Inference Daemon
- **Role:** Hosts the local, offline Large Language Model for interview question generation, response rubric grading, candidate-job skill matching, and feedback generation.
- **Technology:** Ollama inference runtime (Go + llama.cpp).
- **Compute Sizing:**
  - *GPU Mode (Recommended for Cloud):* 2.0 vCPU, 4.0 GB RAM, 1x NVIDIA T4 / A10G GPU (>= 6 GB VRAM). Inference latency: 30 - 60 tokens/sec.
  - *CPU Mode (Acceptable for Low Concurrency):* 4.0 - 8.0 vCPU (AVX2/AVX-512 support), 8 - 16 GB RAM. Inference latency: 5 - 15 tokens/sec.
- **Persistent Storage:** 15 - 30 GB SSD for Ollama binary and cached model weights.
- **Networking:** HTTP port 11434.
- **Network Boundary:** **Strictly Private** (accessible only to backend and worker).
- **Failure Impact:** Automated evaluation and question generation will time out or fall back to rule-based fallback questions and keyword scoring.

---

### Component 7: Qwen2.5:3b LLM Model
- **Role:** The quantized instruct LLM weights loaded by Ollama (`qwen2.5:3b` or `qwen2.5:3b-instruct-q4_K_M`).
- **Model Parameters:** 3.09 Billion parameters, 4-bit quantization (GGUF).
- **Memory Footprint:** ~2.0 GB file on disk; ~2.5 GB active RAM/VRAM during inference.
- **Context Window:** 4,096 tokens configured via `LLM_NUM_CTX=4096`.
- **Network Boundary:** Internal to Ollama host.

---

### Component 8: Faster-Whisper (ASR Engine)
- **Role:** Transcribes candidate spoken audio into timestamped text for technical depth evaluation, communication pace analysis, filler word counting, and silence detection.
- **Technology:** `faster-whisper` (CTranslate2 implementation of OpenAI Whisper).
- **Model:** `base.en` (~140 MB disk, 500 MB RAM) or `small.en` (~460 MB disk, 1 GB RAM).
- **Compute Sizing:** 1.0 - 2.0 vCPU (quantized `int8`). Runs efficiently on CPU.
- **Persistent Storage:** 1.0 GB disk for cached HuggingFace weights.
- **Networking:** Ephemeral outbound to HuggingFace during initial warm-up (or pre-baked into container image). Zero network calls during interview runtime.
- **Network Boundary:** Private (in-process).

---

### Component 9: MediaPipe Face Mesh & Iris Tracking
- **Role:** Tracks 478 3D facial landmarks, iris gaze vector deviations, head pose yaw/pitch/roll, multi-face presence, and candidate absence.
- **Execution Architecture:**
  - **Primary (Client-Side):** Executes in the candidate's browser via WebAssembly (WASM) and WebGL. Extracts gaze and posture coordinates client-side and streams lightweight JSON telemetry (2 Hz) over WebSocket. *Zero server CPU cost.*
  - **Secondary (Server-Side Audit):** Python `mediapipe` library in backend worker for optional post-interview forensic video replay verification.
- **Compute Sizing:**
  - Candidate Browser: Modern dual-core CPU with WebGL hardware acceleration.
  - Server Audit Worker: 1.0 vCPU, 512 MB RAM.

---

### Component 10: FFmpeg & PyAV
- **Role:** Slices, decodes, and transcodes candidate audio chunks (WebM/Opus) into 16 kHz single-channel mono PCM WAV required by Faster-Whisper; extracts video thumbnail keyframes.
- **Technology:** System-level `ffmpeg` binary and Python `av` (PyAV) bindings.
- **Compute Sizing:** 1.0 - 2.0 vCPU (burst compute during audio chunk transcoding; typically completes in < 300 ms).
- **Storage:** Writes to ephemeral system temp directory (`/tmp`).

---

### Component 11: Recording Storage (Video & Audio)
- **Role:** Long-term archival of candidate interview media (video WebM and audio WAV) for recruiter review, compliance audits, and dispute resolution.
- **Storage Engine:**
  - *Local Mode:* Local directory mount (`storage/recordings`).
  - *Production Mode:* AWS S3 (or S3-compatible: MinIO, Cloudflare R2).
- **Capacity Planning:**
  - ~60 - 120 MB per 30-minute interview recording.
  - 1,000 interviews: ~80 - 120 GB.
  - S3 Lifecycle Rule: Transition to Glacier Flexible Retrieval after 90 days; expire/delete after retention window (`RETENTION_DAYS=30` to `365`).
- **Security & Access:**
  - Bucket is **Private** (Block all public access enabled).
  - Candidates and recruiters access recordings strictly via short-lived AWS S3 Presigned URLs (TTL: 15 minutes) generated by FastAPI backend upon verified authorization.

---

### Component 12: Resume Storage (Candidate Documents)
- **Role:** Stores original uploaded resume files (PDF, DOCX, TXT) associated with candidate profiles.
- **Storage Engine:** AWS S3 (or local directory `storage/resumes`).
- **Capacity Planning:**
  - ~500 KB - 2 MB per document.
  - 5,000 resumes: ~5 - 10 GB.
- **Security & Access:**
  - Strictly private bucket with AWS KMS server-side encryption (`aws:kms`).
  - Access is restricted exclusively to the backend service role; files are never directly accessible from the public internet.

---

### Component 13: WebRTC Signaling Hub
- **Role:** Real-time peer discovery, Session Description Protocol (SDP) offer/answer exchange, ICE candidate trickling, chat messaging, and proctoring alert broadcasting.
- **Implementation:** FastAPI WebSocket endpoint (`/api/rooms/{id}/ws` and `/ws/room/{room_id}`).
- **Protocol:** WebSocket Secure (WSS).
- **Scaling:** In single-instance deployment, managed in-process via `ConnectionManager`. In multi-instance deployment, backed by Redis Pub/Sub channels (`room:{room_id}`).
- **Network:** Port 8000 (proxied via ALB Port 443 with sticky sessions / Redis pubsub).

---

### Component 14: STUN / TURN NAT Traversal Infrastructure
- **Role:** Enables direct peer-to-peer WebRTC video and audio transmission between candidate and admin browsers across NAT firewalls.
  - **STUN (Session Traversal Utilities for NAT):** Discovers external IP address and port mapping. Resolves > 80% of consumer NAT environments.
  - **TURN (Traversal Using Relays around NAT):** Media relay server required when either candidate or admin is behind restrictive symmetric enterprise NAT/firewalls.
- **Providers:**
  - *Default Dev STUN:* `stun:stun.l.google.com:19302` (Google Public STUN, free, zero setup).
  - *Production TURN:* Self-hosted Coturn on EC2, or managed cloud TURN (Twilio Network Traversal, Xirsys, Metered.ca).
- **Network Ports:**
  - STUN/TURN: UDP & TCP port 3478.
  - TURNS (TLS): TCP port 5349.
  - Media Relay: UDP dynamic port range 49152 - 65535.
- **Network Boundary:** **Public Internet Facing.**

---

## 4. Minimum vs. Recommended Deployment Profiles

### Profile A: Single-Node Staging / Low-Traffic Production
- **Host Type:** AWS EC2 `t4g.xlarge` (4 vCPU, 16 GB RAM, ARM64) or `c6i.2xlarge` (8 vCPU, 16 GB RAM, x86_64).
- **Topology:** Docker Compose single host running Nginx, Backend, Worker, PostgreSQL, Redis, and Ollama (CPU inference).
- **Storage:** 100 GB EBS gp3 SSD.
- **Target Concurrency:** Up to 5 concurrent active interview rooms; ~20 concurrent candidates browsing.
- **Estimated Cloud Cost:** ~$80 - $140 / month.

### Profile B: Enterprise Multi-Instance Cloud Production (High Concurrency)
- **Frontend:** AWS S3 + CloudFront CDN (Global edge caching, zero server maintenance).
- **Backend Tier:** AWS ECS Fargate (2 - 4 tasks, 2 vCPU, 4 GB RAM each) behind Application Load Balancer.
- **Worker Tier:** AWS ECS Fargate (2 tasks, 2 vCPU, 4 GB RAM each).
- **Database:** AWS RDS PostgreSQL 16 (Multi-AZ, `db.t4g.small` or `db.m6g.large`).
- **Cache/Queue:** AWS ElastiCache Redis 7 (`cache.t4g.small`).
- **AI Inference Tier:** Dedicated AWS EC2 `g4dn.xlarge` (NVIDIA T4 16GB VRAM) running Ollama with Qwen2.5:3b.
- **Media & Document Storage:** AWS S3 with KMS encryption and Glacier lifecycle rules.
- **NAT Traversal:** Managed Twilio TURN or Coturn EC2 cluster.
- **Target Concurrency:** 50+ concurrent active video interviews; 500+ active platform users.
- **Estimated Cloud Cost:** ~$350 - $600 / month.

---

## 5. Deployment Readiness Checklist

- [x] All 14 components cataloged with compute, storage, and networking requirements.
- [x] Failure impacts analyzed and graceful fallback behaviors confirmed.
- [x] Public vs. private network boundary classifications established.
- [x] Storage sizing and S3 retention policies specified.
- [x] Single-node staging vs. enterprise cloud architecture profiles documented.
