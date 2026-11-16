# PLUTO vProctor — Zoho Catalyst Deployment Guide

**Target Environment:** Zoho Catalyst (AppSail + Web Client Hosting + QuickML + Stratus)  
**Operating Budget:** ~$80/month (8 hours/day operational window, 160–176 hrs/month)  
**Region:** `ap-south-1` (India / South Asia)  

---

## 1. Architecture Overview

```
                      +---------------------------------------+
                      |       Candidate & Admin Browsers      |
                      +-------------------+-------------------+
                                          |
                        HTTPS (SPA)       |    WSS Signaling / REST
                                          |
                      +-------------------+-------------------+
                      |   Zoho Catalyst Web Client Hosting    |
                      |          (React Vite SPA)             |
                      +-------------------+-------------------+
                                          |
                                          | REST API / WebSocket
                                          v
                      +---------------------------------------+
                      |       Zoho Catalyst AppSail           |
                      |   (FastAPI Backend / 1 Uvicorn Worker)|
                      +-----+-------------------+-------+-----+
                            |                   |       |
            S3 REST (0$ egress)                 |       | HTTPS JSON
                            |                   |       |
                            v                   |       v
               +-----------------------+        |  +-----------------------+
               | Zoho Catalyst Stratus |        |  | Zoho Catalyst QuickML |
               | (Recordings & Resumes)|        |  |  (Qwen 2.5:3b LLM)    |
               +-----------------------+        |  +-----------------------+
                                                |
               +--------------------------------+
               |
               v External VPC Peering / Internet
      +-----------------------------+        +-----------------------------+
      |  External PostgreSQL 15     |        |   External Coturn Relay     |
      |  (AWS ap-south-1 / RDS)     |        |   (AWS t4g.small / EC2)     |
      |  Full SQLAlchemy Migrations |        |   Symmetric NAT Traversal   |
      +-----------------------------+        +-----------------------------+
```

---

## 2. Prerequisites

1. **Zoho Catalyst CLI (`catalyst-cli`):**
   ```bash
   npm install -g zcatalyst-cli
   catalyst login
   ```
2. **PostgreSQL Database:** External PostgreSQL instance reachable from Catalyst (AWS RDS in `ap-south-1` or Supabase).
3. **STUN/TURN Relay:** External Coturn instance running with UDP/TCP port 3478 and configured relay ports (`49160–49200`).

---

## 3. Step-by-Step Deployment Workflow

### Step 1: Initialize Catalyst Project
```bash
catalyst init
# Select your Catalyst project name when prompted
```

### Step 2: Build the Frontend SPA
```bash
npm --prefix frontend install
npm --prefix frontend run build
# Generates production distribution in frontend/dist/
```

### Step 3: Run Database Migrations Against External PostgreSQL
```bash
export DATABASE_URL="postgresql+psycopg2://pluto_user:PASSWORD@YOUR_POSTGRES_HOST:5432/pluto_db"
backend/.venv/Scripts/python.exe -m alembic upgrade head
```

### Step 4: Configure AppSail Environment Variables
```bash
catalyst appsail:var:set --name pluto-backend --key ENVIRONMENT --value staging
catalyst appsail:var:set --name pluto-backend --key AUTH_ENABLED --value true
catalyst appsail:var:set --name pluto-backend --key HOSTED_ROOMS_ENABLED --value true
catalyst appsail:var:set --name pluto-backend --key LIVE_MEDIA_ENABLED --value true
catalyst appsail:var:set --name pluto-backend --key MEDIA_TRANSPORT_MODE --value p2p
catalyst appsail:var:set --name pluto-backend --key SECRET_KEY --value "YOUR_MIN_32_CHAR_SECRET_KEY"
catalyst appsail:var:set --name pluto-backend --key DATABASE_URL --value "postgresql+psycopg2://..."
catalyst appsail:var:set --name pluto-backend --key QUICKML_ENDPOINT --value "https://api.catalyst.zoho.com/quickml/v1/predict"
catalyst appsail:var:set --name pluto-backend --key QUICKML_API_KEY --value "YOUR_QUICKML_KEY"
catalyst appsail:var:set --name pluto-backend --key STRATUS_ENDPOINT --value "https://stratus.catalyst.zoho.com"
catalyst appsail:var:set --name pluto-backend --key STRATUS_BUCKET --value "pluto-staging-media"
catalyst appsail:var:set --name pluto-backend --key STRATUS_ACCESS_KEY --value "YOUR_STRATUS_KEY"
catalyst appsail:var:set --name pluto-backend --key STRATUS_SECRET_KEY --value "YOUR_STRATUS_SECRET"
```

### Step 5: Deploy AppSail & Client Hosting
```bash
catalyst deploy --only appsail,client
```

---

## 4. Verification & Smoke Testing

Once deployment completes:
1. Open the hosted web client URL (e.g., `https://pluto-staging.catalystserverless.in`).
2. Verify `/health` endpoint on the AppSail domain returns HTTP 200 `{"status": "ok"}`.
3. Perform candidate registration and login flow.
4. Launch self-practice interview and confirm audio/video prompts.
5. Create an admin room, join from candidate tab, and confirm WebRTC dual-stream media transmission.
