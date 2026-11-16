# PLUTO vProctor — Deployment Architecture Review & Validation Report

**Document Version:** 1.0  
**Status:** Architecture Review Decision Gate  
**Platform Version:** 0.1.0 (Release Candidate 1)  
**Date:** November 2026  
**Auditor / Reviewer:** Autonomous Architecture & DevOps Verification Agent  

---

## 1. Executive Summary & Objective

Following the graduation of PLUTO vProctor to **Release Candidate 1 (RC1)**, a comprehensive **Deployment Architecture Review & Validation Pass** was conducted to critically examine, refine, and stress-test the proposed cloud hosting and infrastructure strategy.

This validation pass establishes strict hardware placement boundaries, clarifies GPU resource limits, evaluates three end-to-end deployment topologies, provides empirical workload capacity modeling across 1 to 20 concurrent interview rooms, formalizes operational security standards, and audits the limitations of automated secret scanners.

### Key Conclusions & Decisions at a Glance:
1. **Compute Placement Law:** AWS ECS Fargate provides CPU-only serverless containers and **CANNOT** host GPU workloads. The Ollama LLM inference daemon (`qwen2.5:3b`) must run on dedicated EC2 GPU instances equipped with NVIDIA hardware.
2. **GPU Sizing Constraint (`g4dn.xlarge`):** The AWS `g4dn.xlarge` instance (4 vCPU, 16 GiB RAM, 1x NVIDIA T4 16 GiB VRAM) provides adequate static capacity for the 2.5 GiB model. However, due to single-stream serialization, memory bandwidth limits, and colocated RAM pressure, **it cannot be declared suitable for 5, 10, or 20 concurrent sessions without empirical load testing**.
3. **Staging Recommendation:** Deploy **Option A (Single-Host EC2 Docker Compose)** on a `g4dn.xlarge` instance as a temporary, low-cost ($150–$220/mo) sandbox to measure live RAM/VRAM footprints and validate public WebRTC NAT traversal.
4. **Production Recommendation:** Deploy **Option B (Split AWS Architecture)** with ECS Fargate for stateless API/worker containers, AWS RDS PostgreSQL 16 (Multi-AZ), AWS ElastiCache Redis 7, AWS S3 with Glacier archival, and a dedicated EC2 GPU instance for Ollama.
5. **Operational Verification:** Zero application code, database records, or configuration dependencies were modified during this review.

---

## 2. Compute Placement Validation

A rigorous analysis of PLUTO vProctor's runtime subsystems established a strict boundary between CPU-only and GPU-dependent workloads:

```text
[ PLUTO vProctor Subsystem Compute Placement ]
├── CPU-Only Workloads (ECS Fargate Compatible)
│   ├── Frontend Nginx Web Server (Stateless static SPA assets)
│   ├── FastAPI ASGI Backend (Uvicorn event loop, REST routes, WebSocket signaling hub)
│   ├── Background Task Worker (Redis queue consumer, report compilation)
│   ├── Faster-Whisper ASR (CTranslate2 int8 CPU execution, ~0.25x–0.35x RTF)
│   ├── FFmpeg / PyAV (Audio slicing and transcoding into 16kHz mono WAV)
│   └── MediaPipe Facial Analysis (Client-side WebGL/WASM; server-side audit in Python)
│
└── GPU-Dependent Workloads (Requires Dedicated EC2 GPU Capacity)
    └── Ollama Inference Daemon + Qwen2.5:3b Instruct LLM (GGUF 4-bit)
```

### 2.1 Why Ollama Cannot Run on ECS Fargate
AWS Fargate does **not** provide NVIDIA GPU devices or CUDA runtime drivers. While Fargate is ideal for stateless web and worker containers, running `qwen2.5:3b` in CPU emulation on Fargate would result in prohibitive inference latencies (5 to 15 seconds per token generation chunk), severely degrading the candidate experience and causing WebSocket timeouts.

### 2.2 Comparison of Compute Orchestration Models

| Dimension | Model 1: ECS Fargate (API/Worker) + Dedicated EC2 GPU (AI) | Model 2: ECS on EC2 (Consolidated Cluster) | Model 3: Single EC2 Docker Compose (Staging) |
|---|---|---|---|
| **Architecture** | Serverless API/Worker + Managed GPU Host. | Single ECS cluster with heterogeneous EC2 nodes. | Colocated multi-container stack on 1 GPU host. |
| **Operational Overhead** | **Low:** No OS or patching for API/workers; 1 EC2 node. | **High:** OS, AMI, Docker, and ECS agent patching. | **Minimal:** Standard Docker Compose operations. |
| **Fault Isolation** | **Complete:** Web spikes cannot starve the AI GPU node. | **Partial:** Shared cluster control plane. | **None:** Single OOM crash halts all services. |
| **Horizontal Elasticity**| **Instant:** Auto-scale Fargate tasks in seconds. | **Moderate:** Scale EC2 Auto Scaling Groups. | **None:** Strictly vertical scaling on one machine. |
| **Production Fit** | **Recommended Production Architecture.** | Viable for large enterprise platform teams. | **Strictly Staging / Non-Production.** |

---

## 3. GPU Sizing Validation (`g4dn.xlarge`)

### 3.1 Hardware Specifications
- **Compute:** 4 vCPUs (Intel Cascade Lake, up to 3.1 GHz).
- **System RAM:** 16 GiB.
- **GPU Accelerator:** 1x NVIDIA T4 (2,560 CUDA cores, 320 Tensor cores).
- **GPU VRAM:** 16 GiB GDDR6 (320 GB/s bandwidth).
- **Temporary Storage:** 125 GiB NVMe SSD instance store.

### 3.2 Colocated Resource Allocation & Contention Risks
When evaluated for Option A (single-host colocated staging), the 16 GiB of system RAM and 4 vCPUs must be shared across the entire stack:
- **System RAM Budget:**
  - Ubuntu OS & Docker Runtime: ~1.5 GiB
  - PostgreSQL 16 Buffer Pool: ~2.0 – 3.0 GiB
  - Redis 7 In-Memory Store: ~0.5 GiB
  - FastAPI / Uvicorn Processes: ~1.5 GiB
  - Worker + Faster-Whisper ASR: ~2.0 – 3.0 GiB
  - Ollama Daemon System Memory: ~1.5 GiB
  - **Remaining Headroom:** < 3.0 GiB (Vulnerable to OOM spikes during concurrent resume uploads or long audio transcodings).
- **CPU Thread Contention:** 4 vCPUs must simultaneously service the Uvicorn ASGI event loop, real-time WebSocket heartbeats, database query execution, and Faster-Whisper CTranslate2 CPU threads.
- **T4 Memory Bandwidth:** The NVIDIA T4 memory bandwidth (320 GB/s) is sufficient for sequential token generation (~35–50 tokens/sec), but degrades when concurrent prompts share context slots.

> [!CAUTION]
> **Empirical Validation Principle:**  
> The `g4dn.xlarge` instance is architecturally adequate for baseline testing (1–3 concurrent sessions). **It cannot be declared suitable for 5, 10, or 20 concurrent interviews without empirical workload measurements.** For enterprise concurrency, larger instances (`g4dn.2xlarge` with 8 vCPUs and 32 GiB RAM, or `g5.xlarge` with NVIDIA A10G 24 GiB VRAM) must be evaluated.

---

## 4. Deployment Topology Overview

The three formal deployment topology options are fully specified in [docs/DEPLOYMENT_ARCHITECTURE_OPTIONS.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_ARCHITECTURE_OPTIONS.md):

```mermaid
flowchart TD
    subgraph Option A: Single EC2 Staging
        EC2_STG["Single EC2 g4dn.xlarge (All Containers Colocated)"]
    end

    subgraph Option B: Split AWS Production (Recommended)
        ALB["Application Load Balancer"]
        FARGATE["ECS Fargate (FastAPI + Worker Tasks)"]
        RDS_PROD[("RDS PostgreSQL 16 (Multi-AZ)")]
        REDIS_PROD[("ElastiCache Redis 7")]
        EC2_AI["Dedicated EC2 g4dn.xlarge (Ollama GPU)"]
        S3_PROD[("S3 + Glacier Storage")]
    end

    subgraph Option C: Enterprise Auto-Scaling
        AURORA[("Amazon Aurora Serverless v2")]
        ASG_GPU["EC2 Auto-Scaling GPU Pool (g5.xlarge)"]
        SFU["LiveKit / Mediasoup SFU Cluster"]
    end

    ALB --> FARGATE
    FARGATE <--> RDS_PROD
    FARGATE <--> REDIS_PROD
    FARGATE --> EC2_AI
    FARGATE --> S3_PROD
```

### 4.1 Topology Summary
- **Option A (Controlled Staging):** Single `g4dn.xlarge` instance running Docker Compose. All services colocated on local bridge network. Ideal for initial cloud verification; single point of failure (SPOF); not production-ready.
- **Option B (Recommended Production):** Decoupled architecture separating stateless Fargate tasks from managed persistence (RDS Multi-AZ, ElastiCache) and isolating Ollama on a dedicated EC2 GPU instance. Eliminates SPOFs, provides RTO < 5 min and RPO < 5 min.
- **Option C (Future Scalable Architecture):** High-concurrency enterprise topology with an Auto-Scaling GPU cluster behind an internal NLB, Aurora Serverless v2, and an enterprise SFU media bridge cluster for 100+ concurrent interview sessions.

---

## 5. Workload & Capacity Assessment Summary

The capacity modeling documented in [docs/DEPLOYMENT_CAPACITY_ASSESSMENT.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_CAPACITY_ASSESSMENT.md) separates measured empirical data from projections:

### 5.1 Measured Baselines
- **Faster-Whisper ASR:** Real-Time Factor (RTF) of **0.25x – 0.35x** on 4 CPU cores (`base.en`, quantized `int8`). 10 seconds of audio transcribes in 2.5s–3.5s.
- **Faster-Whisper VRAM:** **0 MB** (runs entirely on CPU).
- **MediaPipe Client Tracking:** Executes at **$\ge$ 15 FPS** (typ. 20–30 FPS) client-side in WebAssembly/WebGL with zero server compute overhead.
- **MediaPipe Server Replay:** Evaluated at **10.0 FPS** (590 frames / 58.32s).

### 5.2 Concurrency Sizing Matrix (1, 5, 10, 20 Concurrent Rooms)

| Metric | 1 Session (Baseline) | 5 Sessions (Small Cohort) | 10 Sessions (Peak Hiring) | 20 Sessions (Enterprise Day) |
|---|---|---|---|---|
| **API / Worker vCPU** | 1.0 – 1.5 vCPU | 3.0 – 4.0 vCPU | 6.0 – 8.0 vCPU | 12.0 – 16.0 vCPU |
| **System RAM** | ~4 GB | ~12 GB | ~24 GB | ~48 GB |
| **GPU VRAM** | ~2.5 GiB | ~4.5 GiB | ~7.5 GiB | ~14.0 GiB |
| **TURN Bandwidth** | 0 – 1 Mbps | 1 – 2 Mbps | 2 – 3 Mbps | 4 – 6 Mbps |
| **Hourly Storage** | ~264 MB / hr | ~1.3 GB / hr | ~2.6 GB / hr | ~5.3 GB / hr |
| **Architecture Fit**| **Option A** | **Option A (Borderline) / Option B** | **Option B (`g4dn.2xlarge`)** | **Option B (Enhanced) / Option C** |

### 5.3 Pre-Deployment Load Testing Plan
The report establishes a 4-phase testing plan to be executed in staging before live candidate onboarding:
1. *API & WebSocket Signaling Saturation* (Locust/Artillery up to 100 concurrent clients).
2. *ASR Worker Saturation* (Synthetic audio feeder into Redis queue).
3. *Ollama Concurrency & Context Slot Benchmark* (`OLLAMA_NUM_PARALLEL=1, 2, 4` latency measurement).
4. *End-to-End Multimodal Concurrency* (Simulated complete interview lifecycle across 1, 5, 10, and 20 rooms).

---

## 6. Operational & Security Governance Review

A comprehensive operational review was conducted across seven critical domains:

### 6.1 Secret Management & Rotation
- **Zero `.env` in Images:** Docker images must never package `.env` files (`.dockerignore` and `.gitignore` verified).
- **CSPRNG Generation:** Production `SECRET_KEY` must be generated with `python -c "import secrets; print(secrets.token_hex(32))"`.
- **Cloud Secret Injection:** Secrets injected at container launch via AWS Secrets Manager or SSM Parameter Store using IAM execution roles.
- **Rotation:** `SECRET_KEY` rotation invalidates active sessions; scheduled rotation should occur during maintenance windows.

### 6.2 S3 Media Access, Encryption & Retention
- **Private Buckets:** S3 Block Public Access enabled on all buckets.
- **KMS Encryption:** Server-side encryption enforced via `aws:kms`.
- **Presigned URLs:** Candidate video/audio recordings and resume files accessed strictly via short-lived presigned URLs (TTL: 15 minutes) generated upon verified authorization.
- **Glacier Lifecycle:** Automated lifecycle rules transition raw media to Glacier Flexible Retrieval after 90 days.

### 6.3 Database Backups, PITR & Restoration
- **Automated Snapshots:** AWS RDS daily snapshots with 35-day retention.
- **Point-In-Time Recovery (PITR):** Transaction logs continuously archived to S3, enabling recovery to any second within the retention window.
- **Restoration Drills:** Quarterly automated restore tests into an isolated test subnet to verify snapshot integrity.

### 6.4 Redis Persistence & Recovery
- **Dual Semantics:** Redis serves both as transient cache / pubsub broker and as background task queue.
- **Persistence:** RDB snapshots enabled every 15 minutes; append-only file (AOF) enabled for task queue durability.
- **Graceful Fallback:** If Redis fails, background tasks fall back to an in-memory worker thread pool, and uncompleted jobs reconcile against database records.

### 6.5 HTTPS/WSS, WebRTC & TURN Credentials
- **TLS Termination:** ALB handles TLS 1.3 termination using ACM certificates.
- **WebSocket Routing:** ALB configured with stickiness and WebSocket upgrade headers.
- **Ephemeral TURN Credentials:** STUN discovers public IPs; TURN relay credentials generated dynamically via HMAC-SHA1 with expiring timestamps to prevent unauthorized media relay abuse.

### 6.6 Monitoring, Alerts & Incident Recovery
- **Health Checks:** Periodic probes to `/api/health` (liveness) and `/api/ready` (readiness verifying database and Redis connectivity).
- **Container Insights:** CloudWatch alarms trigger when ECS CPU/Memory > 80% for 3 consecutive periods.
- **GPU Metrics:** CloudWatch agent monitoring NVIDIA GPU temperature, VRAM allocation, and core utilization.

### 6.7 Database Migration & Rollback Strategy
- **Alembic Migrations:** All schema changes managed via forward-compatible Alembic revisions.
- **Pre-Migration Snapshot:** Mandate an automated RDS snapshot before applying migrations in production.
- **Rollback Runbook:** Every migration script must include a verified `downgrade()` implementation; column additions must be nullable or include non-locking defaults.

---

## 7. Secret Scanner Verification & Limitation Analysis

The investigation into the prior automated scanner failure was finalized in [docs/SECRET_SCAN_REPORT.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SECRET_SCAN_REPORT.md):
- **Root Cause Confirmed:** PowerShell syntax error (`Missing expression after ','`). Python never launched.
- **Scan Coverage:** 828 files scanned across the working tree via [scripts/scan_secrets.py](file:///D:/_TY/MDM/PLUTO-vProctor/scripts/scan_secrets.py).
- **Zero Production Secrets:** The two detected matches in `backend/tests/test_phase6_deployment_and_hardening.py` (lines 76 and 97) were verified as synthetic unit test mocks testing `Settings.validate_runtime_safety()`.
- **Documented Limitations:** The report clearly specifies that the working-tree scanner does not inspect historical Git commit objects, base64-encoded strings, or binary SQLite files. CI/CD pipelines should incorporate `gitleaks` for deep historical commit auditing.

---

## 8. Final Recommendations & Stakeholder Decision Register

### 8.1 Summary of Architectural Recommendations
1. **Staging Recommendation:** Deploy **Option A** (`g4dn.xlarge` single-host Docker Compose) in an isolated AWS staging account to execute the 4-phase pre-deployment load test plan and measure actual RAM/VRAM footprints under real network conditions.
2. **Production Recommendation:** Graduate to **Option B** (Split AWS Architecture) for live candidate interviews. Deploy ECS Fargate for API and worker workloads, AWS RDS PostgreSQL 16 (Multi-AZ), AWS ElastiCache Redis 7, AWS S3 for recordings, and isolate Ollama on a dedicated EC2 GPU instance.

### 8.2 Estimated Cost Drivers

| Topology | Estimated Monthly Cost | Primary Cost Drivers |
|---|---|---|
| **Staging (Option A)** | ~$150 – $220 / month | 1x EC2 `g4dn.xlarge` ($0.526/hr on-demand) + 100 GB EBS gp3 volume. |
| **Production (Option B)** | ~$450 – $750 / month | Dedicated GPU EC2 node ($240–$384/mo), RDS Multi-AZ ($50–$80/mo), Fargate tasks ($45–$90/mo), NAT Gateway ($32/mo), ALB ($25/mo), S3 storage. |

### 8.3 Decisions Submitted for Stakeholder Approval
The following decisions require human sign-off before proceeding with cloud infrastructure provisioning:

- [ ] **Decision 1: Staging Architecture Approval:** Approve deployment of Option A (`g4dn.xlarge` single-host Docker Compose) for controlled staging and load testing.
- [ ] **Decision 2: Production Architecture Approval:** Approve Option B (Split AWS Architecture) as the target production topology.
- [ ] **Decision 3: TURN Provider Selection:** Approve selection between self-hosted Coturn on EC2 vs. managed Twilio Network Traversal Service.
- [ ] **Decision 4: Database Initial Sizing:** Approve starting production with Single-AZ `db.t4g.micro` vs. enterprise Multi-AZ `db.t4g.small`.
- [ ] **Decision 5: Load Testing Execution:** Authorize execution of the 4-phase load testing plan in staging prior to production candidate onboarding.

---

## 9. Deliverables & Documentation Index

| Document | File Path | Scope |
|---|---|---|
| **Architecture Review Report** | [docs/DEPLOYMENT_ARCHITECTURE_REVIEW_REPORT.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_ARCHITECTURE_REVIEW_REPORT.md) | This master decision document. |
| **Deployment Topology Options** | [docs/DEPLOYMENT_ARCHITECTURE_OPTIONS.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_ARCHITECTURE_OPTIONS.md) | Detailed topology specification for Options A, B, and C with Mermaid diagrams. |
| **Capacity Assessment** | [docs/DEPLOYMENT_CAPACITY_ASSESSMENT.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_CAPACITY_ASSESSMENT.md) | Measured vs. assumed resource models, concurrency tiers (1–20), and load testing plan. |
| **Pre-Deployment Readiness** | [docs/PRE_DEPLOYMENT_READINESS_REPORT.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/PRE_DEPLOYMENT_READINESS_REPORT.md) | AWS vs. Zoho Catalyst vs. Hybrid assessment and staging vs. production recommendations. |
| **Configuration Reference** | [docs/DEPLOYMENT_CONFIGURATION_REFERENCE.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_CONFIGURATION_REFERENCE.md) | Exhaustive environment variable specification and production `.env` template. |
| **Dependency Inventory** | [docs/DEPLOYMENT_DEPENDENCY_INVENTORY.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/DEPLOYMENT_DEPENDENCY_INVENTORY.md) | Technical catalog of all 14 runtime components. |
| **Secret Scan Report** | [docs/SECRET_SCAN_REPORT.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/SECRET_SCAN_REPORT.md) | Root cause investigation, scanner limitations, and test fixture proof. |
| **Master Documentation Index** | [docs/INDEX.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/INDEX.md) | Complete documentation index and knowledge map. |
