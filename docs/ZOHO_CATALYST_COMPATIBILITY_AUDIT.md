# PLUTO vProctor — Zoho Catalyst Architecture Compatibility Audit

**Document Version:** 1.0  
**Target Platform:** Zoho Catalyst (Cloud Platform Evaluation)  
**Date Checked:** November 16, 2026  
**Status:** ARCHITECTURAL ASSESSMENT & COMPATIBILITY AUDIT (Zero Cloud Resources Provisioned)  
**Operating Schedule:** 8 hours/day  
**Monthly Budget Target:** Approximately $80/month  
**Account Credits:** $250 Catalyst introductory credits (pending user balance verification in console)  

---

## 1. Executive Summary & Strategic Shift

Following the static verification of the AWS staging configuration package, deployment planning is redirected to a **Zoho-First Architecture** utilizing **Zoho Catalyst** as the primary application hosting and orchestration platform.

This audit evaluates the feasibility of deploying PLUTO vProctor on Zoho Catalyst, reviews the reusability of existing AWS staging artifacts, and assesses Catalyst's native primitives—including **AppSail**, **Serverless Functions**, **Web Client Hosting**, **Data Store**, **Stratus Object Storage**, **Cache**, **Signals**, and **QuickML**.

### Key Audit Findings:
1. **Frontend SPA (React + Vite):** **100% Native Compatibility.** Deploys directly to **Catalyst Web Client Hosting** with global CDN distribution and automated SSL.
2. **FastAPI ASGI Backend:** **Supported via AppSail.** AppSail container runtimes support Python/FastAPI, but request timeouts (30s) and ephemeral disk state require decoupling long-running audio transcription and media processing.
3. **Relational Database (SQLAlchemy + PostgreSQL):** **Incompatible with Native Data Store.** Catalyst Data Store is a proprietary serverless database accessed via ZCQL/SDK; it lacks PostgreSQL wire protocol and SQLAlchemy dialect. **An external managed PostgreSQL service is strictly required** to preserve all 22 tables, Alembic migrations, and existing authentication/RBAC logic.
4. **AI Large Language Model:** **Feasible via QuickML Adapter.** Catalyst QuickML provides Foundation Model endpoints (including Qwen and Pixtral) with pay-as-you-go token pricing ($0.20/1M input, $0.40/1M output), eliminating the need for expensive dedicated GPU instances on AWS.
5. **Real-time WebSockets & Media Relay (WebRTC):** **Constrained.** Catalyst Functions do not support persistent WebSockets. AppSail supports WebSockets on single instances, but Catalyst cannot host Coturn (UDP relay port range `49160–49200`). A minimal external TURN relay (e.g. AWS `ap-south-1`) is required for symmetric NAT traversal.
6. **Object Storage (Resumes, Recordings, Reports):** **Native Compatibility via Stratus.** Catalyst Stratus provides S3-compatible bucket storage with **Zero Egress Fees**, drastically reducing media streaming costs.

---

## 2. Review of Existing AWS Staging Artifacts

The deployment artifacts created during the AWS staging phase were reviewed to determine which components can be directly reused, adapted, or discarded:

| Artifact | Location | Disposition | Adaptation / Replacement Strategy for Zoho Catalyst |
|---|---|---|---|
| **React Frontend SPA** | `frontend/src/` | **REUSE (100%)** | Compile via `npm run build` and deploy static assets directly to **Catalyst Web Client Hosting**. |
| **FastAPI Backend Application** | `backend/app/` | **REUSE (95%)** | Retain all 14 routers, Pydantic schemas, and security services. Adapt `STORAGE_DIR` to use S3-compatible Stratus URLs and add a QuickML client adapter alongside Ollama. |
| **Database Models & Alembic Migrations** | `backend/app/db/models.py`, `backend/alembic/` | **REUSE (100%)** | Retain all 22 SQLAlchemy models and migrations. Target an external managed PostgreSQL instance (e.g. Supabase, Neon, or AWS RDS `ap-south-1`). |
| **Nginx Reverse Proxy Config** | `frontend/nginx.staging.conf` | **DISCARD** | Nginx is not used on Catalyst. Reverse proxying, TLS termination, and path-based routing are natively managed by Catalyst API Gateway and Web Client Hosting. |
| **Docker Compose Staging File** | `docker-compose.staging.yml` | **DISCARD / ARCHIVE** | Catalyst does not run Docker Compose multi-container networks. Services are deployed individually via Catalyst CLI (`catalyst deploy`). Retain file for AWS fallback. |
| **Coturn Configuration Template** | `deploy/staging/turnserver.conf` | **ADAPT / MOVE TO EXTERNAL** | Cannot run on Catalyst. Reused if deploying an external minimal Coturn instance on AWS EC2 in `ap-south-1`. |
| **SSL Setup Script** | `scripts/setup_staging_ssl.sh` | **DISCARD** | Catalyst Web Client Hosting and AppSail provide automated, free SSL certificates for custom domains. Manual certificate generation is unnecessary. |
| **Disk Capacity Monitor** | `scripts/monitor_disk_capacity.sh` | **DISCARD** | Serverless storage in Catalyst (Stratus and Data Store) scales elastically; local EBS monitoring does not apply to serverless runtimes. |
| **Deployment Package Validator** | `scripts/validate_deployment_package.py` | **ADAPT** | Expand to support validating Catalyst deployment package manifests (`catalyst.json`, `app-config.json`). |

---

## 3. Comprehensive Subsystem Compatibility Matrix

Evaluating all 14 architectural components of PLUTO vProctor against Zoho Catalyst capabilities:

| # | Subsystem / Component | Repository Implementation | Native Catalyst Equivalent | Compatibility Rating | Technical Roadblocks & Mandatory Architecture Decisions |
|---|---|---|---|---|---|
| **1** | **Candidate Frontend SPA** | React 19, Vite 8, Tailwind CSS, MediaPipe client bundle | Catalyst Web Client Hosting | **NATIVE** | Zero code changes. Compiled static files in `frontend/dist` deploy to Catalyst global CDN. Free custom domain SSL included. |
| **2** | **FastAPI ASGI REST API** | FastAPI 0.115, Starlette, Uvicorn, 60+ endpoints | Catalyst AppSail | **COMPATIBLE WITH CONSTRAINTS** | Runs as a containerized Python service. Must respect AppSail's **30-second request timeout**. Long-running analysis must be decoupled. |
| **3** | **Relational Persistence Layer** | PostgreSQL 16 via SQLAlchemy 2.0 & Psycopg 3 | Catalyst Data Store | **INCOMPATIBLE** | Catalyst Data Store lacks PostgreSQL wire protocol and SQLAlchemy dialect. **Requires external managed PostgreSQL** (e.g., Supabase / Neon in `ap-south-1`). |
| **4** | **Database Migrations** | Alembic 1.14 (4 revision chains) | N/A (Catalyst has no DDL runner) | **EXTERNAL EXECUTION** | Run migrations via CI/CD or local CLI against the external PostgreSQL instance before deploying AppSail. |
| **5** | **Realtime WebSocket Signaling** | `RoomConnectionManager` (in-process `asyncio` hub) | Catalyst AppSail / Data Streams | **CONSTRAINED** | Serverless Functions lack WebSockets. AppSail supports WebSockets on a single container instance, but multi-instance scaling requires sticky sessions or Catalyst Data Streams. |
| **6** | **WebRTC P2P Media Plane** | Browser-to-browser WebRTC (VP8 video, Opus audio) | Client-to-Client | **NATIVE** | Direct peer-to-peer media flows between candidate and interviewer browsers without traversing the server (80–85% of connections). |
| **7** | **STUN/TURN Media Relay** | Coturn STUN/TURN daemon | N/A | **INCOMPATIBLE WITH CATALYST** | Catalyst does not provide raw UDP port allocation (`49160–49200`). Requires an external lightweight Coturn relay (e.g. AWS `t4g.nano` in `ap-south-1`). |
| **8** | **AI Large Language Model** | Ollama local daemon (`qwen2.5:3b`) | Catalyst QuickML / Foundation Models | **COMPATIBLE VIA ADAPTER** | Catalyst cannot run local GPU daemons. QuickML provides managed Qwen/Pixtral endpoints via API. Implement pluggable `QuickMLClient` in backend. |
| **9** | **Speech-to-Text (ASR)** | Faster-Whisper (CPU int8 CTranslate2 + FFmpeg) | Catalyst Functions / External Worker | **CONSTRAINED** | ASR execution for 15-minute audio takes 30–60s, exceeding AppSail's 30s timeout. Must run in an asynchronous worker container or external cloud STT API. |
| **10**| **Computer Vision Proctoring** | MediaPipe Tasks Vision (FaceLandmarker 478 pts) | Client Browser WebAssembly | **NATIVE** | Executes 100% in the candidate's browser at 15+ FPS. Zero server compute cost or cloud dependency. |
| **11**| **Resume Document Storage** | Local filesystem (`/app/storage/resumes`) | Catalyst Stratus Object Storage | **NATIVE** | Stratus provides S3-compatible API with zero egress fees. Replaces ephemeral container disk. |
| **12**| **Recording & Report Storage** | Local filesystem (`/app/storage/recordings`) | Catalyst Stratus Object Storage | **NATIVE** | High-volume video recordings and PDF dossiers stored in S3-compatible Stratus buckets. Zero egress cost on video playback. |
| **13**| **Algorithmic Search & Scoring** | Trie prefix search, Knapsack MMR, BM25, MinHash | In-Memory Python on AppSail | **NATIVE** | Precomputed embeddings (`embeddings.npy`) and algorithm libraries execute in Python memory in < 15 ms. |
| **14**| **Cache & Task Queue** | `asyncio.Queue` / Redis placeholder | Catalyst Cache / Signals | **OPTIONAL / COMPATIBLE** | PLUTO currently runs in-process job scheduling. Catalyst Signals can be adopted for asynchronous post-interview processing. |

---

## 4. In-Depth Evaluation of Zoho Catalyst Primitives

### 4.1 Catalyst AppSail (PaaS Container Hosting)
- **Architecture:** Managed container execution platform supporting custom Dockerfiles and multi-language runtimes (Python 3.10/3.11, Node.js, Java).
- **Compute Profiles:**
  - Memory tiers: 256 MB, 512 MB, 1 GB, 2 GB (and custom configurations).
  - vCPU: Automatically allocated proportionally to configured memory.
- **Documented Technical Limits:**
  - **Request Timeout:** Standard HTTP requests enforce a **30-second timeout**. Long synchronous tasks fail with 504 Gateway Timeout.
  - **Scale-to-Zero Inactivity:** Instances scale to zero after **5 minutes of inactivity** unless configured with minimum active instances.
  - **Instance Concurrency:** 100 concurrent requests per instance before horizontal scaling triggers.
  - **GPU Availability:** **None.** AppSail provides CPU-only compute. No NVIDIA GPUs or CUDA runtime environments exist.
  - **Filesystem Ephemerality:** Container filesystems are temporary. Any data written to local disk is lost upon container shutdown or restart.

### 4.2 Catalyst Serverless Functions (Basic & Advanced I/O)
- **Architecture:** Event-driven micro-functions triggered by HTTP requests, cron schedules, or Catalyst Signals.
- **Documented Technical Limits:**
  - Memory: 128 MB to 1,024 MB.
  - Execution Timeouts: 15 seconds (Basic I/O) to 300 seconds (Advanced I/O / Event Functions).
  - **WebSocket Incompatibility:** Serverless functions cannot maintain persistent TCP/WebSocket connections. They operate strictly on a request-response model.
- **Verdict for PLUTO:** Serverless Functions cannot host the core FastAPI application or the real-time WebSocket room manager. They are suited exclusively for event listeners (e.g. triggering email notifications upon report generation).

### 4.3 Catalyst Web Client Hosting
- **Architecture:** High-performance static web hosting integrated with Zoho's global Content Delivery Network (CDN).
- **Features:**
  - Direct hosting of React SPA build files (`dist/index.html`, assets, JS/CSS bundles).
  - Native Single Page Application (SPA) routing fallback (`index.html` rewrites).
  - Custom domain binding with automated SSL certificate provisioning.
- **Verdict for PLUTO:** **Perfect fit.** Replaces the Nginx container entirely for candidate and admin web UI delivery.

### 4.4 Catalyst Data Store
- **Architecture:** Proprietary managed relational cloud database.
- **Access Method:** Accessed exclusively via Catalyst SDKs (JavaScript, Java, Python) or Zoho Catalyst Query Language (ZCQL).
- **Documented Incompatibilities:**
  - **No PostgreSQL Wire Protocol:** Port 5432 is not exposed.
  - **No SQLAlchemy Dialect:** SQLAlchemy 2.0 ORM and `psycopg` drivers cannot communicate with Data Store.
  - **Migration Incompatibility:** Alembic cannot execute DDL operations against Data Store.
- **Verdict for PLUTO:** **Incompatible.** Migrating to Data Store would require rewriting all database models, relationship cascades, and queries across 15+ backend services. An external PostgreSQL database is mandatory.

### 4.5 Catalyst Stratus (CloudScale Object Storage)
- **Architecture:** S3-compatible cloud object storage built on buckets and objects.
- **Documented Pricing & Capabilities:**
  - Storage: $0.02 / GB / month (5 GB free tier monthly).
  - **Zero Egress Fees:** $0.00 / GB bandwidth charge for downloading or streaming media out of Stratus.
  - S3 API Compatibility: Supports standard S3 client libraries (`boto3`) and presigned URLs.
- **Verdict for PLUTO:** **Ideal.** Perfect replacement for local EBS `/app/storage` volumes, allowing candidates to stream large interview recordings without bandwidth penalties.

### 4.6 Catalyst Cache & Signals
- **Catalyst Cache:** Abstracted managed Redis cluster. Provides segment-based key-value caching via Catalyst SDK. It does not expose raw Redis RESP sockets, but PLUTO does not currently depend on Redis.
- **Catalyst Signals:** Serverless event bus for event-driven architectures. Can be used to dispatch post-interview events (`interview.completed` -> trigger ASR transcription and grading).

### 4.7 Catalyst QuickML
- **Architecture:** Managed ML pipeline and Foundation Large Language Model serving infrastructure.
- **Model Support:** Hosts foundational open-weight models including **Qwen** and **Pixtral**, accessible via authenticated REST endpoints.
- **Documented Pricing:**
  - Free Tier: 1,000,000 input tokens and 500,000 output tokens free per month.
  - Pay-As-You-Go: **$0.20 per million input tokens**, **$0.40 per million output tokens**.
- **Verdict for PLUTO:** **High Value.** Enables running Qwen-based rubric evaluation, follow-up generation, and report summarization without paying $100–$400/month for dedicated GPU compute.

---

## 5. Architectural Boundary & Risk Register

| Risk / Constraint | Severity | Impact on PLUTO vProctor | Mitigation Strategy |
|---|---|---|---|
| **AppSail 30s Request Timeout** | **HIGH** | Faster-Whisper audio transcription (30–60s) will time out if executed synchronously within an HTTP API request. | Process audio transcription asynchronously in a background worker or integrate a cloud STT API. |
| **No Native Coturn / UDP Relay** | **HIGH** | Remote candidates behind strict corporate symmetric NATs will experience ICE connection failures. | Deploy a minimal external Coturn instance (e.g. AWS `t4g.nano` in `ap-south-1`) to serve as the WebRTC TURN relay. |
| **AppSail Scale-to-Zero Cold Starts** | **MEDIUM** | If traffic is inactive for > 5 minutes, AppSail scales down. Next candidate request incurs 3–5s cold start. | Configure AppSail `min-instances=1` during the 8-hour operational window, or configure a scheduled ping via Catalyst Cron. |
| **No PostgreSQL Wire Protocol in Data Store** | **HIGH** | Cannot connect SQLAlchemy or Alembic to Catalyst Data Store. | Use an external managed PostgreSQL instance in AWS `ap-south-1` (Mumbai) or Supabase. |
| **WebSocket Memory Fragmentation** | **MEDIUM** | If AppSail auto-scales to multiple instances, process-local `RoomConnectionManager` memory is isolated. | Restrict AppSail to 1 instance for staging, or adopt Catalyst Data Streams for distributed signaling. |

---

## 6. Audit Conclusion

Zoho Catalyst provides an exceptional application delivery environment for PLUTO vProctor's **Frontend SPA (Web Client Hosting)**, **REST API (AppSail)**, **Object Storage (Stratus)**, and **AI Inference (QuickML)**, while offering substantial cost savings through its generous free tier, $250 credits, and zero egress fees.

However, a **pure "Catalyst-Only" architecture is technically impossible** without rewriting the application's database layer and abandoning WebRTC TURN relay functionality. The recommended staging architecture is a **Zoho-First Hybrid Model**, deploying the core web application, API, storage, and AI inference on Catalyst while connecting to an external managed PostgreSQL database and a minimal external Coturn relay in AWS `ap-south-1`.
