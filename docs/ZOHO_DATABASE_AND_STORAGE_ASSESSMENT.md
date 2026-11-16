# PLUTO vProctor — Zoho Database & Storage Architecture Assessment

**Document Version:** 1.0  
**Target Platform:** Zoho Catalyst (Data Store, Stratus) + External Managed PostgreSQL  
**Date Checked:** November 16, 2026  
**Status:** TECHNICAL ASSESSMENT & PERSISTENCE ARCHITECTURE SPECIFICATION (Zero Data Migrated)  
**Database Preserved:** SQLite `backend/app/pluto.db` intact (1,799 questions, 14 sessions)  

---

## 1. Executive Summary

PLUTO vProctor’s data tier consists of two fundamental pillars:
1. **Relational Transactional Data:** 22 relational tables managing user credentials (Argon2id hashes), RBAC roles, candidate profiles, multi-resume metadata, job templates, question catalog (1,799 questions), interview room states, real-time participants, and evaluation scores.
2. **Unstructured Media Storage:** PDF resumes, recorded WebM video chunks, extracted WAV audio, and generated PDF evaluation dossiers.

This assessment evaluates **Catalyst Data Store** against PLUTO's **SQLAlchemy 2.0 / PostgreSQL 16** persistence layer, establishes why an external managed PostgreSQL database is strictly required, evaluates candidate PostgreSQL hosting providers in **AWS ap-south-1 (Mumbai)**, and details the integration of **Catalyst Stratus** for zero-egress object storage.

---

## 2. In-Depth Audit: Catalyst Data Store vs. PostgreSQL & SQLAlchemy

### 2.1 The Wire Protocol & Driver Disconnect

```mermaid
flowchart TD
    subgraph PLUTO Application Tier: FastAPI on Catalyst AppSail
        ORM["SQLAlchemy 2.0 ORM<br>(backend/app/db/models.py)"]
        Driver["psycopg3 Driver<br>(PostgreSQL Wire Protocol)"]
        Alembic["Alembic Migration Engine<br>(alembic upgrade head)"]
    end

    subgraph Native Catalyst Cloud
        DS["Catalyst Data Store<br>(Proprietary Serverless Database)"]
        ZCQL["ZCQL / Catalyst Python SDK<br>(HTTP REST Endpoint)"]
    end

    subgraph External Managed Database
        RDS["External Managed PostgreSQL 16<br>(AWS RDS ap-south-1 / Supabase)<br>Listening on Port 5432"]
    end

    ORM --> Driver
    Driver -.->|❌ BLOCKED: No TCP 5432 Wire Protocol| DS
    Alembic -.->|❌ BLOCKED: No DDL Syntax Support| DS
    ORM -.->|❌ INCOMPATIBLE: No SQLAlchemy Dialect| ZCQL

    Driver ==>|✓ Standard TCP 5432 Connection String| RDS
    Alembic ==>|✓ Standard PostgreSQL DDL Migrations| RDS
```

#### Technical Breakdown:
1. **Absence of TCP Port 5432:** Catalyst Data Store does not expose a native TCP socket or listener. It cannot be targeted via a standard database connection string (`postgresql+psycopg://user:password@host:5432/dbname`).
2. **Absence of SQLAlchemy Dialect:** SQLAlchemy translates Python class models (`User`, `InterviewSession`, `Question`) into SQL dialect statements. There is no SQLAlchemy dialect for Catalyst Data Store.
3. **Absence of Alembic DDL Support:** Alembic manages schema versioning via standard DDL (`ALTER TABLE`, `CREATE INDEX`, `ADD CONSTRAINT`). Catalyst Data Store does not support PostgreSQL DDL; table schemas are configured via the Catalyst Console GUI or proprietary metadata APIs.
4. **Refactoring Impact:** Replacing SQLAlchemy with Catalyst Data Store would require:
   - Discarding all 22 models in `backend/app/db/models.py`.
   - Discarding all 4 Alembic migrations in `backend/alembic/versions/`.
   - Manually rewriting queries across `auth_service.py`, `resume_service.py`, `room_service.py`, `question_service.py`, `scoring_engine.py`, and 10+ routers to use the proprietary `catalyst_sdk` Python package.
   - **Verdict:** Refactoring is prohibited by operational safety guidelines. **An external managed PostgreSQL instance is strictly required.**

---

## 3. External Managed PostgreSQL Evaluation (Target: ap-south-1 / India)

To minimize network latency between Zoho Catalyst compute runtimes and the database, candidate PostgreSQL services must reside in or near **AWS ap-south-1 (Mumbai)**:

| Provider | Hosting Region | Pricing (8h/day Schedule) | Connection Pooling | SQLAlchemy 2.0 & Alembic Support | Staging Suitability |
|---|---|---|---|---|---|
| **AWS RDS PostgreSQL 16 (`db.t4g.micro`)** | AWS `ap-south-1` (Mumbai) | **~$4.38 / month** (at 8h/day; ~$13.14/mo for 24/7) | Configurable via RDS Proxy or SQLAlchemy `QueuePool` | **100% Native** | **RECOMMENDED (AWS Fallback Alignment)** |
| **Supabase Managed Postgres** | AWS `ap-south-1` (Mumbai) | **$0.00** (Free Tier: 500 MB DB) | Built-in Supavisor connection pooler | **100% Native** | **HIGH (Cost-Optimal Free Tier)** |
| **Neon Serverless Postgres** | AWS `ap-south-1` (Mumbai) | **$0.00** (Free Tier: 0.5 GiB) | Built-in PgBouncer pooling | **100% Native** | **HIGH (Auto-suspend on idle)** |
| **Aiven for PostgreSQL** | AWS Mumbai | Free Trial / $19/mo | Managed PgBouncer | **100% Native** | **MEDIUM** |

### 3.1 Recommended Database Strategy: AWS RDS or Supabase in ap-south-1
1. **For Maximum Cost Efficiency (Zero Database Cost):**
   - Utilize a **Supabase or Neon Free Tier PostgreSQL instance** located in `ap-south-1` (Mumbai).
   - Monthly cost: **$0.00**.
   - Storage capacity: 500 MB (sufficient for ~5,000 interview sessions and all 1,799 questions).
2. **For Production Consistency & AWS Alignment:**
   - Utilize an **AWS RDS `db.t4g.micro` instance** in `ap-south-1`.
   - Running on an **8-hour/day schedule** (using AWS Instance Scheduler or automated Lambda stop/start):
     $$\text{Cost} = 240 \text{ hours} \times \$0.0182/\text{hr} = \$4.37/\text{month}$$
   - Includes automated daily snapshots, KMS encryption, and direct VPC/public access with IP restriction.

### 3.2 SQLAlchemy Connection Pool Optimization for AppSail
Because Catalyst AppSail container instances scale up or down based on traffic, database connections must be managed safely to avoid exhausting database connection limits:

```python
# Recommended configuration in backend/app/db/database.py for AppSail:
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,             # Maintain 5 active connections per AppSail container
    max_overflow=10,         # Allow up to 10 burst connections during spikes
    pool_timeout=30,         # Match AppSail request timeout
    pool_recycle=1800,       # Recycle connections every 30 minutes to prevent stale TCP sockets
    pool_pre_ping=True,      # Verify connection liveness before checkout (prevents broken pipe errors)
)
```

---

## 4. Unstructured Object Storage Architecture: Catalyst Stratus

### 4.1 Transition from Ephemeral Disk to Stratus
In the local development and single-EC2 architecture, files were written to the local filesystem under `/app/storage/`:
- `/app/storage/resumes` (Candidate PDF resumes)
- `/app/storage/recordings` (WebM video chunks and final interview recordings)
- `/app/storage/reports` (Generated candidate assessment PDF dossiers)

On **Catalyst AppSail**, container filesystems are strictly **ephemeral**. Any file written to `/app/storage` is permanently destroyed when the container instance scales down to zero after 5 minutes of inactivity.

### 4.2 Stratus S3-Compatible Integration Architecture

Zoho Catalyst **Stratus** provides S3-compatible cloud object storage. It replaces the local directory paths with persistent cloud buckets:

```mermaid
flowchart LR
    AppSail["FastAPI on AppSail"]

    subgraph Catalyst Stratus Object Storage [S3 API Compatible | Zero Egress]
        B1[("Bucket: pluto-resumes<br>(Candidate PDF Documents)")]
        B2[("Bucket: pluto-recordings<br>(WebM Interview Videos)")]
        B3[("Bucket: pluto-reports<br>(PDF Evaluation Dossiers)")]
    end

    AppSail -->|PutObject / GetObject via boto3| B1
    AppSail -->|PutObject / GetObject via boto3| B2
    AppSail -->|PutObject / GetObject via boto3| B3

    Admin["Admin Console Browser"] -->|Presigned GET URL (Zero Egress Cost)| B2
    Candidate["Candidate Dashboard"] -->|Presigned GET URL (Zero Egress Cost)| B3
```

### 4.3 Stratus Pricing & Zero Egress Advantage
- **Storage Rate:** **$0.02 per GB / month** (with 5 GB included free every month).
- **Data Transfer Out (Egress):** **$0.00 / GB (ZERO EGRESS FEES)**.
  - On AWS S3, streaming 100 GB of recorded interview videos to recruiters incurs **$9.00/month** in egress bandwidth ($0.09/GB).
  - On Catalyst Stratus, streaming 100 GB of interview videos incurs **$0.00**.
- **API Request Rates:**
  - File Uploads: $0.000005 per request (1,000 free/mo).
  - File Downloads: $0.0000004 per request (10,000 free/mo).

### 4.4 Staging Storage Cost Projection (50 Interviews / Month)

| Asset Type | Estimated Volume | Monthly Storage Size | Monthly Stratus Cost | Monthly Egress Cost |
|---|---|---|---|---|
| **Resumes (PDF)** | 50 candidates $\times$ 1 MB | 50 MB | $0.00 (Within 5 GB free) | $0.00 (Free) |
| **Recordings (WebM)** | 50 sessions $\times$ 15 min $\times$ 50 MB | 2.5 GB | $0.00 (Within 5 GB free) | $0.00 (Free) |
| **Reports (PDF)** | 50 dossiers $\times$ 500 KB | 25 MB | $0.00 (Within 5 GB free) | $0.00 (Free) |
| **Total Media Storage** | — | **~2.6 GB** | **$0.00 / month** | **$0.00 / month** |

---

## 5. Implementation Roadmap for Data & Storage

1. **Phase 1: External Database Initialization:**
   - Provision managed PostgreSQL 16 instance in AWS `ap-south-1` or Supabase.
   - Run Alembic migrations against target database: `alembic upgrade head`.
   - Seed core question catalog (1,799 questions) and job templates via `scripts/seed_db.py`.
2. **Phase 2: Stratus Bucket Creation:**
   - Create buckets `pluto-resumes`, `pluto-recordings`, and `pluto-reports` via Catalyst Console.
   - Configure S3 access credentials in AppSail environment variables (`STRATUS_ENDPOINT`, `STRATUS_ACCESS_KEY`, `STRATUS_SECRET_KEY`).
3. **Phase 3: Storage Service Adapter:**
   - Author a lightweight S3 storage client (`backend/app/services/storage_service.py`) using `boto3` to route uploads/downloads to Stratus when `STORAGE_BACKEND=stratus`, while maintaining local filesystem fallback when `STORAGE_BACKEND=local`.
