# PLUTO vProctor — Staging Deployment Guide (Option A: Single EC2 Docker Compose)

**Document Version:** 1.1  
**Target Topology:** Option A — Single AWS EC2 Instance with Docker Compose  
**Target Environment:** Staging / Controlled Pre-Production Sandbox  
**Instance Type:** `g4dn.xlarge` (4 vCPU, 16 GiB RAM, 1x NVIDIA T4 16 GiB GPU)  
**Operating System:** Ubuntu 22.04 LTS (x86_64)  
**Date:** November 2026  

---

## 1. Prerequisites & Host Specifications

Before initiating deployment, verify the following prerequisites are met:

### 1.1 AWS Cloud Prerequisites
- **AWS Region:** `us-east-1` (US East, N. Virginia) or `ap-south-1` (Asia Pacific, Mumbai).
- **Service Quota Verification:** Confirm that your AWS account has a service quota of at least 4 vCPUs for `Running On-Demand G and VT instances` (Quota code: `L-DB2E3D59`). New AWS accounts default to 0 vCPUs!
- **Instance Sizing:** `g4dn.xlarge` (On-Demand or Spot instance for staging).
- **Storage:** 100 GB General Purpose SSD (`gp3`), baseline 3,000 IOPS, 125 MB/s throughput.
- **Networking:** Attached Elastic IP (or public IPv4 address) associated with an internet-facing public subnet.
- **Security Group:** Bound to `sg-pluto-staging` (see [docs/STAGING_SECURITY_GROUPS.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/STAGING_SECURITY_GROUPS.md)).

### 1.2 Target Software Stack on Host
- **NVIDIA Driver:** Version 535.x or higher.
- **CUDA Runtime:** Version 12.x compatible.
- **NVIDIA Container Toolkit:** Configured as the default runtime for Docker (`nvidia-ctk runtime configure --runtime=docker`).
- **Docker Engine:** Version 26.0+ with Docker Compose v2.

---

## 2. Distributed Architecture Constraints & Staging Adaptations

An inspection of the codebase establishes the following runtime realities:
1. **In-Process JobQueue:** `backend/app/services/job_queue.py` uses Python's in-process `asyncio.Queue` and local thread pool. Workers are started inside the FastAPI event loop in `backend/app/main.py`.
2. **Process-Local Room State:** `backend/app/services/realtime/connection_manager.py` manages WebSockets in a process-local memory dictionary (`self._rooms`).
3. **Separate Worker Container Redundancy:** Because `JobQueue` is in-memory inside `backend`, a separate `worker` container runs its own isolated memory queue and receives zero jobs from `backend`.
4. **Staging Recommendation:**
   - **Disable the separate `worker` container service in `docker-compose.yml` for staging.**
   - Run the background analysis pipeline in-process inside the single `backend` container.
   - This eliminates process decoupling, guarantees reliable job execution, and **reclaims ~2.5 GiB of system RAM** on the `g4dn.xlarge` instance.
5. **Redis Usage in Staging:** Redis is currently idle (unutilized by `job_queue` and `connection_manager`). It can either be omitted to save another ~0.5 GiB RAM, or left running as a placeholder for future distributed pub/sub integration.

---

## 3. Host Provisioning & System Preparation

Execute the following commands on the freshly provisioned Ubuntu 22.04 LTS instance:

### Step 3.1: Update System Packages & Install Base Utilities
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl wget git jq htop build-essential ca-certificates gnupg lsb-release
```

### Step 3.2: Install NVIDIA GPU Drivers & Container Toolkit
```bash
# 1. Install NVIDIA drivers
sudo apt-get install -y linux-headers-$(uname -r)
sudo apt-get install -y nvidia-driver-535 nvidia-utils-535

# 2. Add NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 3. Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4. Verify GPU visibility
nvidia-smi
```
*Expected Output:* An active NVIDIA T4 GPU table showing 16,160 MiB memory and Driver Version 535+.

### Step 3.3: Install Docker Engine & Docker Compose
```bash
# Add Docker official GPG key & repository
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Grant current user docker execution permissions
sudo usermod -aG docker $USER
newgrp docker
docker compose version
```

---

## 4. Repository Deployment & Configuration

### Step 4.1: Clone Application Repository
```bash
cd /opt
sudo git clone https://github.com/your-org/PLUTO-vProctor.git
sudo chown -R $USER:$USER /opt/PLUTO-vProctor
cd /opt/PLUTO-vProctor
git checkout main
```

### Step 4.2: Generate Secure Staging Configuration (`.env`)
Generate cryptographically strong secrets using Python's CSPRNG and populate `.env`:

```bash
# Generate 64-char hex secret
SECRET_HEX=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

cat <<EOF > .env
# Core Server Environment
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost,http://127.0.0.1,http://YOUR_STAGING_PUBLIC_IP,https://staging.yourdomain.com

# Feature Flags
AUTH_ENABLED=True
HOSTED_ROOMS_ENABLED=True
LIVE_MEDIA_ENABLED=True
MEDIA_TRANSPORT_MODE=p2p
SFU_URL=

# Cryptographic Keys (Generated CSPRNG)
SECRET_KEY=${SECRET_HEX}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
COOKIE_SECURE=True
COOKIE_SAMESITE=lax

# Database Configuration (PostgreSQL 16 via Psycopg 3)
POSTGRES_USER=pluto_user
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_DB=pluto_db
DATABASE_URL=postgresql+psycopg://pluto_user:${DB_PASS}@postgres:5432/pluto_db

# Redis Cache (Optional for Option A)
REDIS_URL=redis://redis:6379/0

# WebRTC STUN & TURN Configuration
STUN_SERVERS=stun:stun.l.google.com:19302
TURN_SERVER_URLS=turns:staging.yourdomain.com:5349?transport=tcp,turn:staging.yourdomain.com:3478
TURN_USERNAME=pluto_staging_user
TURN_CREDENTIAL=REPLACE_WITH_TURN_SECRET

# AI Model Inference (Ollama Container in Docker Network)
OLLAMA_BASE_URL=http://ollama:11434
LLM_MODEL=qwen2.5:3b
LLM_NUM_CTX=4096
LLM_KEEP_ALIVE=30s
LLM_TEMPERATURE=0.2

# ASR Configuration (Faster-Whisper on CPU)
ASR_PROVIDER=auto
WHISPER_MODEL_SIZE=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_BEAM_SIZE=1

# Data Retention Policy (Days)
RETENTION_DAYS=30
EOF

chmod 600 .env
```

> [!IMPORTANT]
> **Resolution of `COOKIE_SECURE`:**  
> If staging with a valid domain and Let's Encrypt TLS certificate, leave `COOKIE_SECURE=True`.  
> If testing temporarily on a raw public IP without TLS (HTTP only), set `ENVIRONMENT=staging` and `COOKIE_SECURE=False` to allow browsers to accept session cookies over HTTP while bypassing the production safety assertion.

---

## 5. Dedicated Staging Compose Specification (`docker-compose.staging.yml`)

For Option A staging, use the dedicated, validated staging configuration file `docker-compose.staging.yml`. This avoids modifying the local development `docker-compose.yml` while resolving all architectural blockers:

1. **One-shot Alembic migration service (`migration`):** Automatically upgrades PostgreSQL schema before backend starts.
2. **Dedicated Ollama GPU container (`ollama`):** Configured with NVIDIA GPU device reservations and healthchecks.
3. **Single Uvicorn worker process (`backend`):** Exactly 1 worker process with in-process `JobQueue` execution.
4. **Decoupled worker container disabled:** Prevents process fragmentation and reclaims ~2.5 GiB RAM.
5. **Hardened Nginx TLS Reverse Proxy (`frontend`):** Mounts `frontend/nginx.staging.conf` and `./certs` for HTTPS (443) and HTTP (80).
6. **Strict loopback isolation:** Internal ports 5432, 6379, 8000, and 11434 are strictly bound to `127.0.0.1`.

```yaml
# Execute with:
docker compose -f docker-compose.staging.yml up -d
```

---

## 6. Deployment Execution Sequence

Execute the following sequential deployment commands on the Ubuntu EC2 instance:

### Step 6.1: Initialize Staging TLS Certificates
Run the SSL initialization helper to prepare certificates in `./certs` (either self-signed bootstrap or Let's Encrypt Certbot):
```bash
bash scripts/setup_staging_ssl.sh
```

### Step 6.2: Validate Deployment Package Statically
Before starting containers, execute the deployment package validator:
```bash
python3 scripts/validate_deployment_package.py
```
*Expected Output:* `✓ VALIDATION PASSED: Deployment package is clean.` (0 errors, 0 blockers).

### Step 6.3: Build Application Images
```bash
docker compose -f docker-compose.staging.yml build
```

### Step 6.4: Start PostgreSQL & Ollama Containers
```bash
docker compose -f docker-compose.staging.yml up -d postgres ollama
```
Wait 15 seconds and verify both services report healthy:
```bash
docker compose -f docker-compose.staging.yml ps
```

### Step 6.5: Pull Qwen2.5:3b Model in Ollama
```bash
docker exec -it pluto-staging-ollama ollama pull qwen2.5:3b
docker exec -it pluto-staging-ollama ollama list
```

### Step 6.6: Execute Database Migrations & Launch Backend and Frontend
Launch the remaining services. The one-shot `migration` service will execute `alembic upgrade head` against PostgreSQL and complete successfully before the `backend` container starts:
```bash
docker compose -f docker-compose.staging.yml up -d migration backend frontend
```
Verify container statuses and migration completion:
```bash
docker compose -f docker-compose.staging.yml ps -a
```
*Expected Status:* `pluto-staging-migration` in state `Exited (0)`, all other containers `Up (healthy)`.

### Step 6.7: Configure Coturn STUN/TURN Media Relay
Copy the validated staging Coturn template to `/etc/turnserver.conf`:
```bash
sudo cp deploy/staging/turnserver.conf /etc/turnserver.conf
# Replace external-ip with actual EC2 public IPv4 address
sudo sed -i "s/# external-ip=YOUR_STAGING_PUBLIC_IP/external-ip=$(curl -s http://checkip.amazonaws.com)/" /etc/turnserver.conf
# Replace secret with staging TURN secret
sudo sed -i "s/REPLACE_WITH_TURN_SECRET/${TURN_CREDENTIAL}/" /etc/turnserver.conf
sudo systemctl restart coturn
sudo systemctl status coturn
```

### Step 6.8: Setup EBS Disk Capacity Monitoring
Add `scripts/monitor_disk_capacity.sh` to the root crontab to alert if EBS volume usage crosses 80%:
```bash
(crontab -l 2>/dev/null; echo "*/15 * * * * /opt/PLUTO-vProctor/scripts/monitor_disk_capacity.sh / 80 >> /var/log/disk_monitor.log 2>&1") | crontab -
```

---

## 7. Post-Deployment Smoke Testing & Validation

```bash
# 1. Check Liveness
curl -f http://localhost:8000/api/health
# Expected: {"status":"healthy","version":"0.1.0"}

# 2. Check Readiness (DB and Redis connectivity)
curl -f http://localhost:8000/api/ready
# Expected: {"status":"ready","database":"connected"}

# 3. Check Web Entrypoint via Nginx
curl -I http://localhost/
# Expected: HTTP/1.1 200 OK with security headers
```

Open browser to `http://YOUR_STAGING_PUBLIC_IP`:
1. Navigate to `/admin/login` and log in with admin credentials.
2. Complete candidate registration and profile setup.
3. Start an interview room, verify WebRTC video self-view renders at 15+ FPS, and verify gaze tracking overlays live attention metrics.

---

## 8. Rollback & Teardown Procedures

### 8.1 Immediate Rollback
```bash
docker compose down
```

### 8.2 Database Migration Rollback
```bash
docker compose run --rm backend alembic downgrade -1
```
