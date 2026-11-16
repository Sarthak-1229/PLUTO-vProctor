# PLUTO vProctor — Zoho-First Staging Architecture Recommendation

**Document Version:** 1.0  
**Target Platform:** Zoho Catalyst (Primary) + AWS ap-south-1 (Minimal Supporting Infrastructure)  
**Date Checked:** November 16, 2026  
**Status:** DEFINITIVE STAGING RECOMMENDATION & ROADMAP (Zero Cloud Resources Provisioned)  
**Operating Schedule:** 8 hours/day  
**Monthly Budget Ceiling:** $80 / month  
**Projected Staging Cost:** **$14.28 / month** (out-of-pocket with $250 credits); **$36.83 / month** (ongoing cash burn)  

---

## 1. Executive Summary & Strategic Architecture

Following a thorough technical audit of the PLUTO vProctor codebase and official Zoho Catalyst specifications, deployment planning is definitively transitioned from an AWS-only EC2 GPU deployment to a **Zoho-First Hybrid Architecture (Topology 2)**.

This strategy establishes **Zoho Catalyst** as the core platform for the user-facing Single Page Application (Web Client Hosting), REST API & real-time signaling (AppSail), zero-egress media storage (Stratus), and AI model evaluation (QuickML), while coupling it with minimal external infrastructure in **AWS ap-south-1 (Mumbai)** to provide full PostgreSQL 16 compatibility and WebRTC symmetric NAT traversal.

```mermaid
flowchart TD
    subgraph Candidate & Recruiter Browsers
        C_User["Candidate Browser (React SPA + MediaPipe)"]
        R_User["Recruiter Browser (Admin Console + Video)"]
    end

    subgraph Primary Cloud: Zoho Catalyst [Covered by $250 Credits]
        FE["Catalyst Web Client Hosting<br>(React Vite SPA + Global CDN + Free SSL)"]
        API["Catalyst AppSail (FastAPI Backend & WSS Hub)<br>1 GB RAM Instance | min=1, max=1<br>In-Memory Embeddings & Algorithms"]
        AI["Catalyst QuickML<br>(Qwen 2.5 Foundation LLM Endpoint)"]
        Storage["Catalyst Stratus Object Storage<br>(S3-Compatible Buckets | ZERO Egress Fees)<br>Resumes, Recordings, Reports"]
    end

    subgraph Minimal Supporting Cloud: AWS ap-south-1 [~$14.28 / month]
        DB[("Managed PostgreSQL 16<br>(AWS RDS db.t4g.micro or Supabase)<br>22 Relational Tables + Alembic Migrations")]
        Coturn["Minimal Coturn Media Relay<br>(AWS EC2 t4g.nano in ap-south-1)<br>UDP 3478, TCP 5349, UDP 49160-49200"]
    end

    C_User -->|Fetch Web Client (HTTPS)| FE
    R_User -->|Fetch Admin Console (HTTPS)| FE

    C_User <==>|Signaling & Telemetry (WSS 443)| API
    R_User <==>|Signaling & Telemetry (WSS 443)| API

    API -->|LLM Prompts & Rubrics| AI
    API -->|Presigned Uploads & Downloads| Storage
    API <-->|SQLAlchemy ORM (TCP 5432)| DB

    C_User <-.->|Direct P2P Media (80-85% of Sessions)| R_User
    C_User -.->|Symmetric NAT Relay Fallback| Coturn
    Coturn -.->|Relayed SRTP Stream| R_User
```

---

## 2. Component Mapping & Hosting Decisions

| Subsystem | Target Cloud Service | Hosting Details | Justification & Architectural Benefit |
|---|---|---|---|
| **Frontend Web SPA** | **Catalyst Web Client Hosting** | Precompiled static build (`frontend/dist`) distributed via Zoho global CDN. | Zero server compute cost, automated free SSL certificates, native SPA client-side routing. |
| **FastAPI REST API** | **Catalyst AppSail** | Single container instance (1 GB RAM tier), running Uvicorn ASGI server with `min-instances=1, max-instances=1`. | Preserves all 60+ REST endpoints, Pydantic validation schemas, Argon2id auth, and in-process WebSocket room management. |
| **Relational Database** | **External Managed PostgreSQL** (`ap-south-1`) | AWS RDS `db.t4g.micro` or Supabase Free Tier in Mumbai. | **Catalyst Data Store lacks PostgreSQL wire protocol and SQLAlchemy dialect.** External database preserves all 22 models, Alembic migrations, and relational integrity. |
| **AI LLM Inference** | **Catalyst QuickML** | Serverless Qwen 2.5 Foundation Model endpoint via REST API. | Eliminates $100–$400/mo AWS GPU instance. Monthly token cost is **$0.00** within Catalyst free tier (1M input / 500k output tokens free). |
| **Media & Object Storage**| **Catalyst Stratus** | S3-compatible cloud object storage (`pluto-resumes`, `pluto-recordings`, `pluto-reports`). | Replaces ephemeral container disk. **Zero egress fees** eliminate video playback bandwidth charges. |
| **WebRTC Media Relay** | **External Coturn VM** (`ap-south-1`) | AWS EC2 `t4g.nano` (ARM64) running Coturn with restricted relay ports (`49160–49200`). | Catalyst cannot expose arbitrary UDP port ranges. External relay ensures 100% connectivity for candidates behind enterprise firewalls. |
| **Speech-to-Text (ASR)** | **Cloud ASR API** (Deepgram / AssemblyAI) | Remote speech-to-text API integrated via existing provider registry (`backend/app/pipelines/asr/`). | Bypasses AppSail's 30-second HTTP request timeout while providing rapid 5–10s audio transcription at ~$0.06 per interview. |
| **Computer Vision Proctoring**| **Client Web Browser** | MediaPipe Tasks Vision WebAssembly running on candidate GPU/CPU. | 100% client-side execution; delivers 15+ FPS gaze tracking with zero server load. |

---

## 3. Financial Summary & Budget Adherence

### 3.1 Operating Schedule: 8 Hours / Day (240 Hours / Month)
- **Zoho Catalyst Monthly Gross Spend:** **$22.55 / month**  
  *(1 GB AppSail compute: $17.55 + Project maintenance fee: $5.00. Web Client Hosting, Stratus storage, and QuickML LLM are 100% covered by monthly free tiers).*
- **Catalyst Promotional Credits Applied:** **-$22.55 / month**  
  *(The $250 credit pool fully absorbs all Catalyst platform fees for ~11 months).*
- **Net Zoho Out-of-Pocket Spend:** **$0.00 / month** during credit period.
- **External AWS & Cloud ASR Spend (Cash):** **$14.28 / month**  
  *(AWS RDS PostgreSQL 16: $6.67 + AWS EC2 Coturn: $1.94 + Elastic IP: $2.45 + Deepgram ASR: $3.22).*
- **Total Net Out-of-Pocket Monthly Cash:** **$14.28 / month**  
  $$\mathbf{\$14.28 \ll \$80.00 \text{ (82\% below budget ceiling)}}$$

### 3.2 Ongoing Normal Spend (After $250 Credits Exhaust)
- Total Monthly Gross Spend: **$36.83 / month**  
  *(Zoho Catalyst: $22.55 + AWS/ASR: $14.28).*  
  $$\mathbf{\$36.83 \ll \$80.00 \text{ (54\% below budget ceiling)}}$$

---

## 4. Key Compatibility Gaps & Technical Workarounds

| Subsystem Gap | Technical Reality | Workaround / Architecture Resolution |
|---|---|---|
| **Catalyst Data Store Incompatibility** | Data Store lacks PostgreSQL port 5432, SQLAlchemy dialect, and Alembic support. Rewriting 22 tables is infeasible. | Deploy external managed PostgreSQL 16 in AWS `ap-south-1` (Mumbai). Configure AppSail with standard `DATABASE_URL`. |
| **AppSail 30s Request Timeout** | AppSail terminates HTTP requests running > 30 seconds. Faster-Whisper CPU transcription takes 3–5 minutes for full interviews. | Use existing cloud ASR adapter (`DeepgramProvider`) which transcribes in 5–10 seconds, or process ASR asynchronously via background worker. |
| **No Coturn / UDP Relay on Catalyst** | Catalyst does not expose raw UDP port ranges (`49160–49200`) required for WebRTC symmetric NAT media relay. | Deploy a minimal AWS `t4g.nano` instance in `ap-south-1` running Coturn with restricted ports. Point AppSail `TURN_SERVER_URLS` to this instance. |
| **AppSail Ephemeral Local Disk** | Files written to `/app/storage` are destroyed when container instances scale down after 5 minutes of inactivity. | Migrate file operations to Catalyst Stratus (S3-compatible) buckets using `boto3`. |
| **WebSocket Memory Fragmentation** | Process-local `RoomConnectionManager` holds room state in memory. Multi-instance auto-scaling splits participant connections. | Pin AppSail to a single persistent instance (`min-instances=1, max-instances=1`) for staging. |

---

## 5. Required Future Code Changes (Pre-Deployment Phase)

The following four targeted code adaptations will prepare the repository for Zoho Catalyst deployment:

1. **QuickML Provider Adapter (`backend/app/services/llm_client.py`):**
   - Implement `QuickMLProvider` alongside existing `OllamaProvider`.
   - Toggle via environment variable: `LLM_PROVIDER=quickml` (for cloud) vs `LLM_PROVIDER=ollama` (for local offline development).
   - Retain existing deterministic algorithmic fallbacks (`fallback_factory`).
2. **Stratus S3 Storage Adapter (`backend/app/services/storage_service.py`):**
   - Introduce an S3 object storage abstraction for resumes, video recordings, and reports using `boto3`.
   - Read `STRATUS_ENDPOINT`, `STRATUS_ACCESS_KEY`, and `STRATUS_SECRET_KEY` from configuration.
   - Maintain local directory storage when running locally.
3. **Cloud ASR Configuration:**
   - Configure `ASR_PROVIDER=deepgram` in staging `.env` to leverage existing `DeepgramProvider`, bypassing AppSail's 30-second timeout.
4. **Catalyst Deployment Manifests:**
   - Author `catalyst.json` and `app-config.json` defining AppSail container build parameters, Web Client Hosting directories (`frontend/dist`), and environment variable bindings.

---

## 6. Phased Implementation Roadmap

```mermaid
flowchart TD
    subgraph Step 1: Verification & Pre-Requisites
        A1["Verify $250 Catalyst Credit Balance & Expiry in Console"]
        A2["Install Catalyst CLI (npm install -g zcatalyst-cli)"]
    end

    subgraph Step 2: Codebase Adapters (Zero Regressions)
        B1["Implement QuickML Provider in llm_client.py"]
        B2["Implement Stratus S3 Adapter in storage_service.py"]
        B3["Run Pytest & Vitest Suites (Ensure 198+21 Tests Pass)"]
    end

    subgraph Step 3: Supporting Infrastructure (AWS ap-south-1)
        C1["Provision AWS RDS db.t4g.micro (PostgreSQL 16) in Mumbai"]
        C2["Run Alembic Migrations & Seed Questions (1,799 questions)"]
        C3["Provision AWS EC2 t4g.nano (Coturn Relay) with IMDSv2"]
    end

    subgraph Step 4: Zoho Catalyst Deployment
        D1["Create Stratus Buckets (pluto-resumes, pluto-recordings, pluto-reports)"]
        D2["Deploy React SPA to Catalyst Web Client Hosting"]
        D3["Deploy FastAPI Container to Catalyst AppSail (min=1, max=1)"]
    end

    subgraph Step 5: End-to-End Validation
        E1["Verify Liveness & Readiness Probes via Catalyst Gateway"]
        E2["Execute Real Browser WebRTC Interview with Gaze Tracking"]
        E3["Verify Video Assembly & Stratus Zero-Egress Playback"]
    end

    A1 --> A2 --> B1 --> B2 --> B3 --> C1 --> C2 --> C3 --> D1 --> D2 --> D3 --> E1 --> E2 --> E3
```

---

## 7. Operational Compliance Statement

In strict adherence to project directives:
- **Zero AWS or Zoho cloud resources were provisioned.**
- **Zero application code files were modified.**
- **Zero database tables or records were migrated.**
- **The SQLite database (`backend/app/pluto.db`) remains 100% intact with all 1,799 questions and 14 legacy sessions preserved.**
- **No credentials or secrets were exposed.**
- **All existing AWS staging documentation and compose files are preserved unmodified for fallback.**

**Awaiting user review and authorization to proceed with implementation.**
