# PLUTO vProctor — Staging Deployment Execution Checklist

**Document Version:** 1.1  
**Target Topology:** Option A — Single EC2 Docker Compose  
**Platform Version:** 0.1.0 (Release Candidate 1)  
**Date:** November 2026  

---

## 1. Overview & Verification Protocol

This checklist governs the step-by-step execution of **Option A Staging Deployment**. Every step must be executed in sequence, verified, and checked off by the deploying engineer.

---

## 2. Phase 1: Pre-Deployment Cloud Preparation

- [ ] **1.1 AWS Service Quota Verified:** Confirm that your AWS account has a quota of at least 4 vCPUs for `Running On-Demand G and VT instances` (`L-DB2E3D59`) in the target region (`us-east-1` or `ap-south-1`). If 0, submit an AWS quota increase request before proceeding.
- [ ] **1.2 AWS Budget Alert Configured:** Configure an AWS CloudWatch billing alarm alerting at $150 (for 8h/day schedule) or $450 (for 24/7 schedule).
- [ ] **1.3 Elastic IP Allocated:** Allocate 1 Elastic IP. Note: AWS charges $0.005/hr continuously for Elastic IPs ($3.65/month), even when the attached instance is stopped.
- [ ] **1.4 Security Group Configured:** Verify `sg-pluto-staging` rules allow TCP 80, TCP 443, TCP 22 (strictly from admin IP `/32`), and optional Coturn ports (UDP/TCP 3478, TCP 5349, UDP 49160–49200). Confirm internal ports 5432, 6379, 8000, and 11434 are blocked from public ingress.
- [ ] **1.5 S3 Backup Bucket Provisioned:** Create `s3://pluto-staging-backups-[region]` with default KMS encryption and Block Public Access enabled.

---

## 3. Phase 2: Host Provisioning & Hardware Setup

- [ ] **2.1 EC2 Instance Launched:** Launch `g4dn.xlarge` instance using official Ubuntu 22.04 LTS AMI with 100 GB `gp3` root volume. Ensure `DeleteOnTermination=false` for persistent data safety.
- [ ] **2.2 Elastic IP Attached:** Associate allocated Elastic IP with the running instance.
- [ ] **2.3 Host System Updated:** Execute `sudo apt-get update && sudo apt-get upgrade -y`.
- [ ] **2.4 NVIDIA Driver 535+ Installed:** Install `nvidia-driver-535` and verify output of `nvidia-smi` displays active T4 GPU with 16 GiB VRAM.
- [ ] **2.5 Docker Engine 26+ Installed:** Install Docker CE and verify `docker --version`.
- [ ] **2.6 NVIDIA Container Toolkit Installed:** Install `nvidia-container-toolkit`, execute `nvidia-ctk runtime configure --runtime=docker`, and restart Docker daemon.
- [ ] **2.7 GPU Container Visibility Verified:** Run `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi` to confirm containers can access GPU acceleration.
- [ ] **2.8 Ephemeral NVMe Safety Verified:** Confirm that the 125 GiB NVMe instance store is NOT mounted to `/var/lib/docker` or any persistent data directories.

---

## 4. Phase 3: Configuration & Secret Injection

- [ ] **3.1 Repository Cloned:** Clone code into `/opt/PLUTO-vProctor` and checkout `main` (RC1 release tag).
- [ ] **3.2 CSPRNG Secret Keys Generated:** Run `python3 -c "import secrets; print(secrets.token_hex(32))"` to generate a 64-character `SECRET_KEY`.
- [ ] **3.3 Strong Database Passwords Generated:** Generate random 24-character passwords for `POSTGRES_PASSWORD`.
- [ ] **3.4 `.env` File Created:** Populate `.env` from [docs/STAGING_ENVIRONMENT_REFERENCE.md](file:///D:/_TY/MDM/PLUTO-vProctor/docs/STAGING_ENVIRONMENT_REFERENCE.md).
- [ ] **3.5 Cookie Security Parameter Aligned:**
  - If deploying on domain with TLS: Confirm `COOKIE_SECURE=True` and `ENVIRONMENT=production`.
  - If testing on raw HTTP public IP: Set `COOKIE_SECURE=False` and `ENVIRONMENT=staging` to prevent browser cookie drops and fail-fast assertions.
- [ ] **3.6 File Permissions Hardened:** Execute `chmod 600 .env` to prevent unauthorized local read access.

---

## 5. Phase 4: Container Build, Migration & Launch

- [ ] **4.1 Staging SSL Initialized:** Run `bash scripts/setup_staging_ssl.sh` to populate `./certs` with TLS certificates (self-signed bootstrap or Let's Encrypt).
- [ ] **4.2 Static Package Validation Passed:** Run `python3 scripts/validate_deployment_package.py` and confirm 0 errors and 0 blockers.
- [ ] **4.3 Docker Images Built:** Execute `docker compose -f docker-compose.staging.yml build`. Verify zero build errors for frontend and backend.
- [ ] **4.4 Base Infrastructure Started:** Execute `docker compose -f docker-compose.staging.yml up -d postgres ollama`. Confirm separate `worker` container is disabled to reclaim 2.5 GiB RAM.
- [ ] **4.5 Container Health Confirmed:** Execute `docker compose -f docker-compose.staging.yml ps` and confirm `postgres` and `ollama` reach `healthy` state.
- [ ] **4.6 Qwen2.5:3b Model Pulled:** Run `docker exec -it pluto-staging-ollama ollama pull qwen2.5:3b`. Confirm model tag `qwen2.5:3b` is present via `ollama list`.
- [ ] **4.7 Ollama Inference Smoke Test:** Run `bash scripts/verify_ollama_readiness.sh` to confirm model readiness and forward tensor inference execution.
- [ ] **4.8 Automated Migration & App Stack Launched:** Execute `docker compose -f docker-compose.staging.yml up -d migration backend frontend`. Confirm `pluto-staging-migration` exits with code 0 (`alembic upgrade head`) and `backend` starts with exactly 1 Uvicorn worker process.
- [ ] **4.9 Coturn Relay Configured:** Copy `deploy/staging/turnserver.conf` to `/etc/turnserver.conf`, configure external IP via IMDSv2, set TURN secret, and restart Coturn service.
- [ ] **4.10 Disk Monitoring Crontab Added:** Register `scripts/monitor_disk_capacity.sh` in crontab at 15-minute intervals with 80% warning threshold.

---

## 6. Phase 5: Post-Deployment Smoke Testing & Validation

- [ ] **6.1 Liveness Probe Verified:** `curl -f http://localhost:8000/api/health` returns `200 OK` with status `healthy`.
- [ ] **6.2 Readiness Probe Verified:** `curl -f http://localhost:8000/api/ready` returns `200 OK` with database `connected`.
- [ ] **6.3 Nginx Web Proxy Verified:** `curl -I http://localhost/` returns `200 OK` with security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`).
- [ ] **6.4 Secure Context & Browser Media Verified:** Confirm browser opens `https://staging.yourdomain.com` without certificate errors and `window.isSecureContext === true`, allowing camera/mic permission prompts.
- [ ] **6.5 Admin Console Login:** Open browser, navigate to `/admin/login`, log in with administrator credentials, and confirm console loads.
- [ ] **6.6 Candidate Onboarding:** Register a new candidate account, complete profile, and verify universal recommendations render.
- [ ] **6.7 Room Creation & Lifecycle:** Create an interview room in Admin Room Manager, invite candidate, start room, and verify state advances from `LOBBY` to `LIVE`.
- [ ] **6.8 WebRTC Media & Gaze Tracking:** Enter interview room, verify webcam stream displays at 15+ FPS, and verify gaze tracking HUD overlays live attention score.
- [ ] **6.9 Recording & AI Evaluation:** Complete interview session, upload recording, trigger evaluation, and confirm final scoring dossier PDF is generated.
- [ ] **6.10 Persistence Drill Executed:** Stop containers (`docker compose down`), stop EC2 instance, restart instance, relaunch containers, and verify candidate session records and reports persist intact.

---

## 7. Phase 6: Rollback Protocol (If Validation Fails)

- [ ] **7.1 Containers Stopped:** Execute `docker compose down`.
- [ ] **7.2 Database Reverted (If Migration Failed):** Run `docker compose run --rm backend alembic downgrade -1`.
- [ ] **7.3 Diagnostics Captured:** Capture container logs via `docker compose logs > /opt/staging_failure_logs.txt`.
- [ ] **7.4 Persistent Volumes Preserved:** Confirm named volumes (`pgdata`, `storage_data`) are preserved on disk.
- [ ] **7.5 Stakeholder Notification:** Report issue to engineering lead with captured logs and error trace.
