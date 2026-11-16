# PLUTO vProctor — Staging Environment Configuration Reference

**Document Version:** 1.0  
**Target Topology:** Option A — Single EC2 Docker Compose  
**Environment Identifier:** Staging  
**Platform Version:** 0.1.0 (Release Candidate 1)  
**Date:** November 2026  

---

## 1. Overview & Scope

This document specifies the exact configuration variables, defaults, and security boundaries required to operate PLUTO vProctor in the **Option A Staging Sandbox** (`g4dn.xlarge` instance).

All values are injected via the root `.env` file or Docker Compose environment blocks, overriding defaults in [backend/app/config.py](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/config.py).

---

## 2. Staging Configuration Matrix

| Variable Name | Staging Requirement | Recommended Staging Value | Description & Operational Impact |
|---|---|---|---|
| `ENVIRONMENT` | **Mandatory** | `"production"` | Activates production security assertions, strict route guards, and Argon2id authentication. Normalizes `prod` -> `production`. |
| `DEBUG` | **Mandatory** | `False` | Disables verbose exception tracebacks in HTTP error responses. |
| `LOG_LEVEL` | **Optional** | `"INFO"` | Logging verbosity: `"INFO"` captures request IDs, WebSocket events, and pipeline progress without filling disk logs. |
| `API_HOST` | **Mandatory** | `"0.0.0.0"` | Binds Uvicorn to all container network interfaces to receive reverse-proxied traffic from Nginx. |
| `API_PORT` | **Mandatory** | `8000` | Internal container port for FastAPI ASGI application. |
| `CORS_ORIGINS` | **Mandatory** | `"http://localhost,http://YOUR_STAGING_IP,https://staging.yourdomain.com"` | Comma-separated list of permitted browser origins. Wildcards (`*`) are prohibited. |
| `AUTH_ENABLED` | **Mandatory** | `True` | Activates JWT issuing, Argon2id password verification, and RBAC route enforcement. |
| `HOSTED_ROOMS_ENABLED` | **Mandatory** | `True` | Activates real-time interview rooms, admin room controls, and candidate invitations. |
| `LIVE_MEDIA_ENABLED` | **Mandatory** | `True` | Activates WebRTC audio/video streaming in interview rooms. |
| `MEDIA_TRANSPORT_MODE` | **Mandatory** | `"p2p"` | Sets media mode to Peer-to-Peer mesh with WebSocket signaling. |
| `SECRET_KEY` | **Mandatory** | Generated 64-char hex string | High-entropy signing key for JWT tokens. Must be generated using CSPRNG. Never use placeholder strings. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | **Optional** | `15` | Lifespan of JWT access tokens. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | **Optional** | `7` | Lifespan of HTTP-only refresh tokens. |
| `COOKIE_SECURE` | **Mandatory** | `True` (or `False` if plain HTTP IP) | **Critical:** `validate_runtime_safety()` requires `True` when `ENVIRONMENT=production` and `AUTH_ENABLED=True`. If testing on raw IP without TLS, set `ENVIRONMENT=staging`. |
| `COOKIE_SAMESITE` | **Optional** | `"lax"` | Cross-site cookie attribute for CSRF defense. |
| `POSTGRES_USER` | **Mandatory** | `"pluto_user"` | Database user account created in PostgreSQL container. |
| `POSTGRES_PASSWORD` | **Mandatory** | Generated secret string | Password for PostgreSQL user. Injected into compose. |
| `POSTGRES_DB` | **Mandatory** | `"pluto_db"` | Primary application database name. |
| `DATABASE_URL` | **Mandatory** | `"postgresql+psycopg://pluto_user:${DB_PASS}@postgres:5432/pluto_db"` | SQLAlchemy connection URI using Psycopg 3 driver pointing to PostgreSQL container. |
| `REDIS_PASSWORD` | **Optional** | Generated secret string | Optional authentication password for Redis task queue. |
| `REDIS_URL` | **Mandatory** | `"redis://:${REDIS_PASS}@redis:6379/0"` | Connection URI pointing to Redis container service. |
| `OLLAMA_BASE_URL` | **Mandatory** | `"http://ollama:11434"` | Resolves to the colocated `ollama` container on the internal Docker bridge network. |
| `LLM_MODEL` | **Optional** | `"qwen2.5:3b"` | Quantized instruct model tag loaded in Ollama. |
| `LLM_NUM_CTX` | **Optional** | `4096` | Context window size in tokens for prompt evaluation. |
| `LLM_KEEP_ALIVE` | **Optional** | `"30s"` | Duration model remains resident in GPU memory between calls. |
| `LLM_TEMPERATURE` | **Optional** | `0.2` | Sampling temperature for reproducible evaluation scoring. |
| `ASR_PROVIDER` | **Optional** | `"auto"` | Automatically detects local Faster-Whisper. |
| `WHISPER_MODEL_SIZE` | **Optional** | `"base.en"` | CPU-optimized Whisper model size (~140 MB). |
| `WHISPER_DEVICE` | **Mandatory** | `"cpu"` | Pinned to CPU to protect GPU VRAM for the LLM. |
| `WHISPER_COMPUTE_TYPE` | **Optional** | `"int8"` | 8-bit quantization for rapid CPU audio transcription. |
| `STUN_SERVERS` | **Optional** | `"stun:stun.l.google.com:19302"` | Public STUN server for NAT IP discovery. |
| `TURN_SERVER_URLS` | **Optional** | `""` | Comma-separated list of TURN relays. Optional in staging if peers connect on public network. |
| `RETENTION_DAYS` | **Optional** | `30` | Number of days before candidate recordings and transient audit logs are purged. |

---

## 3. Resolving the Staging `COOKIE_SECURE` Contradiction

A critical runtime safety guard exists in `Settings.validate_runtime_safety()`:

```python
if self.ENVIRONMENT.strip().lower() == "production" and self.AUTH_ENABLED:
    if not self.COOKIE_SECURE:
        raise RuntimeError("Unsafe production config: COOKIE_SECURE must be True in production when AUTH_ENABLED=True.")
```

### Staging Deployment Rules:
1. **With Domain & SSL Certificate (Recommended):**
   - Configure a domain (e.g. `staging.plutovproctor.com`) with a Let's Encrypt TLS certificate.
   - Set `COOKIE_SECURE=True` and `ENVIRONMENT=production`.
   - Browser receives cookies over HTTPS with the `Secure` flag enabled.
2. **Without Domain (Testing on Raw Public IP via HTTP):**
   - Web browsers strictly reject cookies marked `Secure` when transmitted over unencrypted HTTP.
   - If deploying without TLS, set `ENVIRONMENT=staging` and `COOKIE_SECURE=False`. This bypasses the production `COOKIE_SECURE` assertion while preserving full authentication and RBAC behavior.

---

## 4. Sanitized Staging `.env` Template

```bash
# ==============================================================================
# PLUTO vProctor — Staging Environment Template (.env)
# ==============================================================================

# Server & Runtime Environment
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

# Cryptographic Keys (Replace with CSPRNG generated hex)
SECRET_KEY=REPLACE_WITH_GENERATED_64_CHAR_HEX_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
COOKIE_SECURE=True
COOKIE_SAMESITE=lax

# PostgreSQL Database Configuration
POSTGRES_USER=pluto_user
POSTGRES_PASSWORD=REPLACE_WITH_STRONG_DB_PASSWORD
POSTGRES_DB=pluto_db
DATABASE_URL=postgresql+psycopg://pluto_user:REPLACE_WITH_STRONG_DB_PASSWORD@postgres:5432/pluto_db

# Redis Cache & Task Queue
REDIS_PASSWORD=REPLACE_WITH_REDIS_PASSWORD
REDIS_URL=redis://:REPLACE_WITH_REDIS_PASSWORD@redis:6379/0

# WebRTC NAT Traversal (STUN & TURN)
STUN_SERVERS=stun:stun.l.google.com:19302
TURN_SERVER_URLS=
TURN_USERNAME=
TURN_CREDENTIAL=

# Ollama AI Inference (Internal Docker Container)
OLLAMA_BASE_URL=http://ollama:11434
LLM_MODEL=qwen2.5:3b
LLM_NUM_CTX=4096
LLM_KEEP_ALIVE=30s
LLM_TEMPERATURE=0.2

# ASR & Disfluency Models (Faster-Whisper on CPU)
ASR_PROVIDER=auto
WHISPER_MODEL_SIZE=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_BEAM_SIZE=1

# Data Retention Policy (Days)
RETENTION_DAYS=30
```
