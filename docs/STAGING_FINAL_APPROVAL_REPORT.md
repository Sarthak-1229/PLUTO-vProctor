# PLUTO vProctor — Staging Readiness & Final Architecture Approval Report

**Document Version:** 1.0  
**Phase Gate:** Phase 1 Staging Pre-Deployment Approval  
**Target Topology:** Option A — Single AWS EC2 Instance (`g4dn.xlarge`) with Docker Compose  
**Intended Production Target:** Option B — Split AWS Architecture (Fargate + RDS + ElastiCache + Dedicated GPU EC2)  
**Platform Version:** 0.1.0 (Release Candidate 1)  
**Date:** November 2026  
**Auditor / DevOps Reviewer:** Autonomous Verification & Cloud Architecture Agent  

---

## 1. Executive Summary & Document Purpose

This document serves as the **definitive pre-deployment gate report** for PLUTO vProctor. It synthesizes all technical audits, configuration inspections, multi-region AWS cost analyses, hardware capacity assessments, and regression tests conducted across the repository.

To ensure transparent decision-making, this report strictly categorizes all findings into:
1. **Verified Facts** (grounded in direct code execution, automated benchmarks, or filesystem inspection).
2. **Assumptions & Projections** (clearly flagged engineering models that require empirical staging measurement).
3. **Unresolved Deployment Blockers** (concrete configuration conflicts preventing immediate deployment).
4. **Decisions Requiring Human Approval** (formal stakeholder sign-offs before any AWS resource creation).

---

## 2. Category 1: Verified Facts

The following statements are proven by direct automated execution, test logs, and source code inspection:

### 2.1 Codebase Integrity & Regression Status
- **Backend Test Suite:** 198 passed, 1 skipped (`test_migrations` requires live PostgreSQL container), 0 failed in 146.57 seconds (`pytest backend/tests`).
- **Frontend Test Suite:** 21 passed, 0 failed in 191.4 ms (`npm run test` in `frontend/`).
- **Frontend Production Build:** Vite v8.3.4 compiled cleanly in 726 ms; 1,961 modules transformed into production assets (`dist/index.html`, `dist/assets/index-BnapYQjg.js`, `dist/assets/vision_bundle-Cm2TTWT3.js`).
- **Linter Status:** `oxlint` executed cleanly across 36 files with 84 non-fatal warnings and **0 errors**.
- **SQLite Database Integrity:** `PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` returned **0 violations**.
- **Dataset & Session Preservation:** All **1,799 technical interview questions**, **14 legacy candidate sessions**, and **3 registered accounts** are verified intact in `backend/app/pluto.db`.
- **Secret Scanning Verification:** Dedicated scanner [scripts/scan_secrets.py](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/scan_secrets.py) scanned 828 files across the repository; confirmed **zero (0) live production credentials, API keys, database passwords, or private keys**.

### 2.2 Tooling & Environment Reality
- **Docker CLI / Engine Absence:** The prior failure of `docker compose config` (exit code 1) was investigated and confirmed: **Docker Desktop / Docker Engine is NOT installed on the local Windows development machine** (`CommandNotFoundException`).
- **Validator Scope:** The Python deployment validator ([scripts/validate_deployment_package.py](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/validate_deployment_package.py)) parses YAML syntax and verifies that all 8 referenced build context paths exist on disk. It now enforces failure (`exit code 1`) whenever deployment blockers are detected.
- **Unverified Tooling Boundaries:** Full Docker Compose runtime semantics (such as network driver creation, port collision detection with host OS, container capability grants, volume permission inheritance, and container runtime execution) cannot be verified without Docker Engine installed on the host. These can only be verified once deployed onto the Linux EC2 staging instance.

### 2.3 Distributed Architecture Boundaries in Existing Code
- **`JobQueue` Implementation:** [backend/app/services/job_queue.py](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/services/job_queue.py) uses Python in-process `asyncio.Queue` and local thread pool locking. Workers are spawned inside the FastAPI event loop in `backend/app/main.py`. It does not connect to Redis.
- **`RoomConnectionManager` Implementation:** [backend/app/services/realtime/connection_manager.py](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/services/realtime/connection_manager.py) manages WebSockets in a process-local memory dictionary (`self._rooms`). It does not publish to Redis Pub/Sub.
- **Worker Container Decoupling:** In `docker-compose.yml`, the separate `worker` service runs in a separate container with its own empty memory queue. It receives zero jobs from `backend`, while consuming ~2.5 GiB of system RAM.
- **Redis Usage:** `Settings.REDIS_URL` is defined, but Redis is currently idle (unutilized by `job_queue` and `connection_manager`).

### 2.4 Hardware Baseline (`g4dn.xlarge`)
- **Hardware Specs:** 4 vCPUs, 16 GiB system RAM, 1x NVIDIA T4 GPU (16 GiB VRAM), 1x 125 GiB ephemeral NVMe instance store, up to 25 Gbps network.
- **Measured ASR Performance:** Faster-Whisper `base.en` running on CPU `int8` has an empirically measured Real-Time Factor (RTF) of **0.25x – 0.35x** on 4 CPU cores (`docs/ASR_BENCHMARK.md`).
- **Measured Client Proctoring:** MediaPipe FaceLandmarker executes client-side in WebAssembly/WebGL at **$\ge$ 15 FPS** (typically 20–30 FPS) with **zero server compute cost** (`docs/GAZE_BENCHMARK.md`).

---

## 3. Category 2: Assumptions & Projections

The following items are engineering models and projections that must be empirically verified during Phase 1 staging load testing:

1. **LLM Generation Throughput on NVIDIA T4:** Projected at **~35–50 tokens/sec** based on published llama.cpp benchmarks for 3B Q4 GGUF models on Turing architecture. Actual inference latency under concurrent prompts must be measured via staging load tests.
2. **WebRTC Media Bitrate:** Projected at **~350–500 kbps** for 720p 15fps WebM video with 64 kbps Opus audio.
3. **Coturn Relay Frequency:** Projected at **15% – 20% of sessions** requiring TURN media relaying due to corporate symmetric NAT firewalls.
4. **Option A Staging Concurrency Limit:** Projected at **1 to 3 concurrent rooms**. While 6.5 GiB of system RAM headroom is available on `g4dn.xlarge`, simultaneous resume parsing, audio transcoding, and multi-stream WebSockets across 5+ rooms may cause memory spikes and CPU thread starvation.
5. **AWS Published Pricing:** Assumes published AWS rates for `us-east-1` and `ap-south-1` as of November 2026.

---

## 4. Category 3: Unresolved Deployment Blockers & Remediation

Before launching Option A staging, the following four (4) technical deployment blockers must be resolved in staging configuration:

| # | Blocker Description | Technical Root Cause | Impact if Unresolved | Staging Remediation |
|---|---|---|---|---|
| **B1** | **`COOKIE_SECURE` Contradiction in Production Mode** | `docker-compose.yml` configures `AUTH_ENABLED=true` alongside `COOKIE_SECURE=false` under `ENVIRONMENT=production`. | `Settings.validate_runtime_safety()` raises fatal `RuntimeError` on boot; backend crashes immediately. | **Fix:** Set `COOKIE_SECURE=True` when deploying with a domain and TLS certificate. If testing on raw HTTP public IP, set `ENVIRONMENT=staging` and `COOKIE_SECURE=False`. |
| **B2** | **Missing Ollama Container in `docker-compose.yml`** | `ollama` is not defined in compose; backend targets `http://localhost:11434`. | Backend inside Docker network cannot reach host Ollama; all question generation and evaluations time out. | **Fix:** Add `ollama` service to `docker-compose.yml` with NVIDIA GPU reservations (`count: all, capabilities: [gpu]`) and point `OLLAMA_BASE_URL=http://ollama:11434`. |
| **B3** | **No Automated Alembic Migration on Container Startup** | No entrypoint or compose hook runs `alembic upgrade head`. | Fresh PostgreSQL database starts with 0 tables; API queries immediately fail. | **Fix:** Mandate running `docker compose run --rm backend alembic upgrade head` as Step 6.4 in the deployment runbook after `postgres` container reaches healthy status. |
| **B4** | **Decoupled Worker Container Process** | `JobQueue` uses in-process `asyncio.Queue` inside `backend`; `worker` container runs a separate isolated process. | Worker container receives 0 jobs; all jobs execute in-process inside `backend`. Wastes ~2.5 GiB of RAM. | **Fix:** Disable the separate `worker` container service in `docker-compose.yml` for staging Option A. Run workers in-process inside `backend` (saves 2.5 GiB RAM). |

---

## 5. Category 4: Multi-Region Cost Comparison (`us-east-1` vs. `ap-south-1`)

A detailed financial comparison was conducted between **`us-east-1` (N. Virginia)** and **`ap-south-1` (Mumbai)**.

### 5.1 Elastic IP vs. Auto-Assigned Public IPv4 Accounting
- **Elastic IP (Required for Staging Domain):** AWS charges $0.005/hr continuously ($3.65/month) whether the instance is running or stopped. This guarantees the public IP never changes, keeping DNS records (`staging.yourdomain.com`) and CORS origins constant across instance stop/start cycles.
- **Auto-Assigned Public IPv4:** Charged only while running ($0.80 for 160h, $0.40 for 80h). However, the IP address changes every time the instance stops, breaking DNS and CORS origins.
- *Accounting Rule:* Elastic IP ($3.65/mo constant) is included in all scenarios below.

### 5.2 Comparative Monthly Staging Cost Table (USD, Including Applicable Taxes)

| Usage Schedule | Cloud Resource Line Item | `us-east-1` (USD) | `ap-south-1` (Mumbai) (USD) |
|---|---|---|---|
| **24/7 Operation**<br>*(730 hours/month)* | EC2 `g4dn.xlarge` On-Demand Compute | $383.98 ($0.526/hr) | $451.14 ($0.618/hr) |
| | Elastic IPv4 Address ($0.005/hr continuous) | $3.65 | $3.65 |
| | 100 GB EBS `gp3` Storage | $8.00 ($0.08/GB-mo) | $9.12 ($0.0912/GB-mo) |
| | 20 GB EBS Snapshots | $1.00 ($0.05/GB-mo) | $1.10 ($0.055/GB-mo) |
| | 50 GB S3 Standard Storage | $1.15 ($0.023/GB-mo) | $1.25 ($0.025/GB-mo) |
| | Route 53 DNS & CloudWatch Logs | $3.50 | $3.50 |
| | Internet Data Transfer Out (50 GB) | $0.00 (Free Tier) | $0.00 (Free Tier) |
| | Coturn WebRTC Relay (Colocated EC2) | $0.00 (Included) | $0.00 (Included) |
| | Subtotal (Before Tax) | **$401.28** | **$469.76** |
| | Applicable Taxes (0% US vs. 18% GST India) | $0.00 | $84.56 |
| | **TOTAL MONTHLY COST (24/7 Staging)** | **$401.28 / mo** | **$554.32 / mo** |
| | *(With 1-Year Compute Savings Plan)* | *~$258.10 / mo* | *~$361.90 / mo* |
|---|---|---|---|
| **8 Hours/Day**<br>*(20 Days = 160 hours/mo)* | EC2 `g4dn.xlarge` Compute (160 hours) | $84.16 | $98.88 |
| | Elastic IPv4 Address (Continuous 730h) | $3.65 | $3.65 |
| | 100 GB EBS `gp3` Storage (Continuous 730h) | $8.00 | $9.12 |
| | 20 GB EBS Snapshots | $1.00 | $1.10 |
| | 50 GB S3 Standard Storage | $1.15 | $1.25 |
| | Route 53 DNS & CloudWatch Logs | $3.00 | $3.00 |
| | Data Transfer & Coturn | $0.00 (Free Tier) | $0.00 (Free Tier) |
| | Subtotal (Before Tax) | **$100.96** | **$117.00** |
| | Applicable Taxes (0% US vs. 18% GST India) | $0.00 | $21.06 |
| | **TOTAL MONTHLY COST (8h/day Staging)** | **$100.96 / mo** | **$138.06 / mo** |
|---|---|---|---|
| **4 Hours/Day**<br>*(20 Days = 80 hours/mo)* | EC2 `g4dn.xlarge` Compute (80 hours) | $42.08 | $49.44 |
| | Elastic IPv4 Address (Continuous 730h) | $3.65 | $3.65 |
| | 100 GB EBS `gp3` Storage (Continuous 730h) | $8.00 | $9.12 |
| | 20 GB EBS Snapshots | $1.00 | $1.10 |
| | 50 GB S3 Standard Storage | $1.15 | $1.25 |
| | Route 53 DNS & CloudWatch Logs | $2.50 | $2.50 |
| | Data Transfer & Coturn | $0.00 (Free Tier) | $0.00 (Free Tier) |
| | Subtotal (Before Tax) | **$58.38** | **$67.06** |
| | Applicable Taxes (0% US vs. 18% GST India) | $0.00 | $12.07 |
| | **TOTAL MONTHLY COST (4h/day Staging)** | **$58.38 / mo** | **$79.13 / mo** |

> [!WARNING]
> **EC2 G-Instance Quota Warning:**  
> In all new AWS accounts, the service quota for **Running On-Demand G and VT instances (`L-DB2E3D59`) is set to 0 vCPUs by default**. You must submit an AWS service quota increase request for at least 4 vCPUs before provisioning in either region.

---

## 6. Storage Persistence & Disaster Recovery Guarantees

PLUTO vProctor interacts with four distinct storage tiers:
- **EBS Persistent Storage (`gp3` 100 GB):** Hosts Docker named volumes `pgdata`, `storage_data`, and `ollamadata`. All database tables, candidate resumes, video recordings, and model weights **persist across container recreation, reboot, and EC2 stop/start cycles**.
- **S3 Object Storage:** Stores offsite daily `pg_dump` database dumps and media archives. Highly durable across total EC2 termination.
- **Local NVMe Instance Store (125 GiB on `g4dn.xlarge`):** Physically attached to host hypervisor. **ALL DATA IS WIPED when the instance is stopped or terminated.** Zero application data relies on this drive. Only used as an optional scratch space for FFmpeg audio slicing.
- **Container Writable Layer (`overlay2`):** Ephemeral filesystem wiped on container recreation. Only transient logs reside here.

---

## 7. Option B Production Readiness Caveat

While Option B (Split AWS Architecture) remains the approved target production architecture:

> [!IMPORTANT]
> **Mandatory Production Engineering Prerequisite:**  
> **Option B CANNOT be claimed production-ready today.** The current codebase utilizes an in-process `JobQueue` (`asyncio.Queue`) and process-local `RoomConnectionManager` (`self._rooms` dictionary). Before Option B can be deployed across multiple ECS Fargate containers, the task queue must be refactored to use a distributed broker (Redis streams/Celery) and WebSocket signaling must be refactored to use Redis Pub/Sub channels to enable cross-instance broadcast. Option A in staging operates safely with one backend process without distributed dependencies.

---

## 8. Decisions Submitted for Formal Stakeholder Approval

The following decisions require explicit stakeholder review and approval before any AWS cloud infrastructure is provisioned:

- [ ] **Decision 1: Blocker Resolutions Approval:** Approve applying the 4 staging configuration fixes:
  1. Setting `COOKIE_SECURE=True` (with domain TLS) or `ENVIRONMENT=staging` (on raw HTTP).
  2. Adding the `ollama` GPU container service to `docker-compose.yml`.
  3. Codifying the `alembic upgrade head` migration execution step in the deployment runbook.
  4. Disabling the redundant `worker` container service in staging compose to reclaim 2.5 GiB RAM.
- [ ] **Decision 2: Target AWS Region Selection:** Approve whether staging launches in **`us-east-1`** ($101/mo for 8h/day; $401/mo for 24/7) or **`ap-south-1`** ($138/mo for 8h/day; $554/mo for 24/7, inclusive of 18% GST).
- [ ] **Decision 3: Operational Schedule & Budget:** Approve whether the staging instance runs on an **8 Hours/Day schedule** (~$101/mo in `us-east-1`) or a **24/7 Continuous schedule** (~$401/mo in `us-east-1`).
- [ ] **Decision 4: Service Quota Verification:** Confirm that the AWS account has an approved quota of $\ge 4$ vCPUs for `Running On-Demand G and VT instances` (`L-DB2E3D59`).
- [ ] **Decision 5: Execution Authorization:** Authorize the creation of the single `g4dn.xlarge` EC2 instance in the approved region following [docs/STAGING_DEPLOYMENT_GUIDE.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/STAGING_DEPLOYMENT_GUIDE.md).

---

*Phase 1 Staging Deployment Preparation is complete. Awaiting human stakeholder approval on Decisions 1–5 before proceeding.*
