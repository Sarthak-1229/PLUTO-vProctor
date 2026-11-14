# PLUTO vProctor — Deployment Configuration Reference

**Document Version:** 1.0  
**Status:** Pre-Deployment Technical Reference  
**Platform Version:** 0.1.0 (RC1)  
**Date:** November 2026  

---

## 1. Overview & Configuration Precedence

PLUTO vProctor utilizes a unified, type-safe configuration system implemented in [backend/app/config.py](file:///D:/_TY/MDM/PLUTO-vProctor/backend/app/config.py) via Pydantic v2 `BaseSettings` (`Settings`).

### 1.1 Precedence Hierarchy
Configuration variables are resolved in the following priority order (highest to lowest):
1. **OS Environment Variables** (injected by host shell, Docker, ECS task definition, or Kubernetes Pod manifest).
2. **Environment File (`.env`)** in the application root directory.
3. **Application Default Values** hardcoded in `backend/app/config.py`.

### 1.2 Fail-Fast Safety Guard (`validate_runtime_safety()`)
When `ENVIRONMENT=production`, the application executes strict startup assertions:
- `SECRET_KEY` must be configured, must exceed 32 characters, and must not match development placeholder strings (`dev-secret`, `changeme`, `placeholder`, etc.).
- `COOKIE_SECURE` must be explicitly set to `True` when `AUTH_ENABLED=True`.
- If `MEDIA_TRANSPORT_MODE="sfu"`, `SFU_URL` must be non-empty.

Any violation immediately halts process startup with a fatal `RuntimeError`, preventing insecure deployments.

---

## 2. Master Variable Classification

Variables are classified into four operational categories:
- 🔴 **Mandatory (Production):** Required for production operation; system will fail or be critically insecure without them.
- 🟡 **Feature Flags & Rollout:** Controls subsystem activation (auth, live rooms, media mode).
- 🟢 **Optional / Tuning:** Has production-ready defaults; tune for performance or scaling needs.
- ⚪ **Development Only:** Used exclusively for local offline testing; must be disabled in production.

---

## 3. Configuration Reference by Subsystem

### 3.1 Server & Core Runtime Settings

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `ENVIRONMENT` | 🔴 Mandatory | String | `"development"` | Set to `"production"`. Valid options: `development`, `test`, `staging`, `production`. Normalizes aliases (`prod` -> `production`). |
| `DEBUG` | ⚪ Dev Only | Boolean | `True` | **Must be `False` in production.** Suppresses verbose exception stack traces in HTTP responses. |
| `LOG_LEVEL` | 🟢 Optional | String | `"INFO"` | Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Use `INFO` for production; `WARNING` in high-throughput environments. |
| `API_HOST` | 🔴 Mandatory | String | `"127.0.0.1"` | Set to `"0.0.0.0"` inside Docker containers; bound to reverse proxy/ALB. |
| `API_PORT` | 🔴 Mandatory | Integer | `8000` | Port for Uvicorn ASGI server (1 - 65535). |
| `CORS_ORIGINS` | 🔴 Mandatory | List[str] | `["http://localhost:5173", ...]` | Comma-separated list of allowed frontend origins (e.g. `https://proctor.example.com`). **Wildcards (`*`) are prohibited in production.** |

---

### 3.2 Feature Flags & Subsystem Boundaries

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `AUTH_ENABLED` | 🟡 Flag | Boolean | `False` | Enables Argon2id password authentication, JWT issuing, RBAC, and candidate login. Set to `True` in production. |
| `HOSTED_ROOMS_ENABLED` | 🟡 Flag | Boolean | `False` | Enables admin-managed hosted interview rooms, candidate invitations, and real-time lobby state machines. Set to `True` in production. |
| `LIVE_MEDIA_ENABLED` | 🟡 Flag | Boolean | `False` | Activates real-time audio/video streaming in interview rooms. |
| `MEDIA_TRANSPORT_MODE` | 🟡 Flag | String | `"p2p"` | Options: `"none"`, `"p2p"`, `"sfu"`. Use `"p2p"` for direct browser-to-browser media mesh; `"sfu"` for selective forwarding unit. |
| `SFU_URL` | 🟢 Optional | String | `""` | WebSocket/HTTP endpoint of external SFU cluster (e.g. LiveKit/Mediasoup). Required only if `MEDIA_TRANSPORT_MODE="sfu"`. |

---

### 3.3 Authentication, Token & Security Settings

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `SECRET_KEY` | 🔴 Mandatory | String | `""` (ephemeral) | **Critical cryptographic secret.** Must be >= 32 random characters (generated via CSPRNG). Used to sign JWTs and CSRF tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 🟢 Optional | Integer | `15` | JWT access token lifespan (1 - 1440 minutes). Recommended: `15`. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 🟢 Optional | Integer | `7` | Refresh token lifespan (1 - 90 days). Recommended: `7`. Stored in HTTP-only cookie. |
| `COOKIE_SECURE` | 🔴 Mandatory | Boolean | `False` | **Must be `True` in production.** Enforces `Secure` flag on cookies, ensuring transmission strictly over HTTPS. |
| `COOKIE_SAMESITE` | 🟢 Optional | String | `"lax"` | Cookie cross-site policy: `"lax"`, `"strict"`, or `"none"`. Recommended: `"lax"`. |
| `REFRESH_COOKIE_NAME` | 🟢 Optional | String | `"pluto_refresh_token"` | Name of the HTTP-only refresh token cookie. |
| `CSRF_COOKIE_NAME` | 🟢 Optional | String | `"pluto_csrf_token"` | Name of the double-submit CSRF protection cookie. |
| `PASSWORD_RESET_EXPIRE_MINUTES` | 🟢 Optional | Integer | `30` | Lifespan of password recovery reset tokens. |
| `EMAIL_VERIFY_EXPIRE_HOURS` | 🟢 Optional | Integer | `24` | Lifespan of email verification activation tokens. |
| `MAX_FAILED_LOGIN_ATTEMPTS` | 🟢 Optional | Integer | `5` | Failed attempts before account lockout (3 - 20). |
| `LOCKOUT_MINUTES` | 🟢 Optional | Integer | `15` | Duration of temporary account lockout following excessive failures. |

---

### 3.4 WebRTC NAT Traversal (STUN & TURN)

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `STUN_SERVERS` | 🟢 Optional | List[str] | `["stun:stun.l.google.com:19302"]` | Comma-separated list or JSON array of STUN server URLs for public IP discovery. |
| `TURN_SERVER_URLS` | 🔴 Mandatory | List[str] | `[]` | Comma-separated list of TURN/TURNS relay servers (e.g. `turns:turn.example.com:5349?transport=tcp`). Essential for enterprise firewalls. |
| `TURN_USERNAME` | 🔴 Mandatory | String | `""` | Username or ephemeral credentials identifier for TURN authentication. |
| `TURN_CREDENTIAL` | 🔴 Mandatory | String | `""` | Password or HMAC auth token for TURN relay server. **Never commit to git.** |

---

### 3.5 Database & Task Queue Settings

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `DATABASE_URL` | 🔴 Mandatory | String | `sqlite:///...` | Connection URI. For cloud PostgreSQL, use Psycopg 3: `postgresql+psycopg://user:password@host:5432/dbname`. |
| `REDIS_URL` | 🔴 Mandatory (Scale) | String | `""` | Redis connection URI: `redis://user:password@host:6379/0` (or `rediss://` for TLS). Required for multi-instance horizontal scaling and distributed job queue. |
| `RETENTION_DAYS` | 🟢 Optional | Integer | `30` | Data retention policy for raw media and transient audit logs before GDPR auto-pruning. |

---

### 3.6 Large Language Model (LLM) Inference Settings

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `OLLAMA_BASE_URL` | 🔴 Mandatory | String | `"http://localhost:11434"` | HTTP endpoint for Ollama daemon. In cloud, points to private internal VPC IP or DNS name. |
| `LLM_MODEL` | 🟢 Optional | String | `"qwen2.5:3b"` | Model tag to load. Options: `qwen2.5:3b`, `qwen2.5:3b-instruct-q4_K_M`. |
| `LLM_NUM_CTX` | 🟢 Optional | Integer | `4096` | Context window size in tokens. 4096 accommodates complete interview transcripts and resumes. |
| `LLM_KEEP_ALIVE` | 🟢 Optional | String | `"30s"` | Duration to keep model in VRAM/RAM between calls (`30s`, `5m`, `-1` for indefinitely loaded). |
| `LLM_TEMPERATURE` | 🟢 Optional | Float | `0.2` | Sampling temperature. Low temperature (0.1 - 0.3) ensures reproducible, objective rubric evaluation. |
| `LLM_TIMEOUT_SECONDS` | 🟢 Optional | Float | `45.0` | Maximum time allowed for LLM inference before triggering fallback scoring. |
| `LLM_MAX_RETRIES` | 🟢 Optional | Integer | `1` | Retry attempts on transient inference failure. |

---

### 3.7 Speech-to-Text (ASR) & Embeddings Settings

| Variable Name | Category | Type | Default | Production Value / Description |
|---|---|---|---|---|
| `ASR_PROVIDER` | 🟢 Optional | String | `"auto"` | Options: `"auto"`, `"faster_whisper"`, `"deepgram"`, `"assemblyai"`. Auto selects Faster-Whisper if local; falls back cleanly. |
| `WHISPER_MODEL_SIZE` | 🟢 Optional | String | `"base.en"` | Size of local Whisper model: `tiny.en`, `base.en`, `small.en`. `base.en` provides optimal accuracy/speed on CPU. |
| `WHISPER_DEVICE` | 🟢 Optional | String | `"cpu"` | `"cpu"` or `"cuda"`. Keep `"cpu"` in production to reserve GPU VRAM entirely for the LLM. |
| `WHISPER_COMPUTE_TYPE` | 🟢 Optional | String | `"int8"` | Quantization mode. `"int8"` minimizes CPU RAM footprint and maximizes transcription speed. |
| `WHISPER_BEAM_SIZE` | 🟢 Optional | Integer | `1` | Beam search width. `1` uses greedy search for lowest latency; `3` provides marginally higher accuracy. |
| `DEEPGRAM_API_KEY` | 🟢 Optional | String | `""` | Optional hosted ASR API key. When omitted, zero network calls are made. |
| `ASSEMBLYAI_API_KEY` | 🟢 Optional | String | `""` | Optional hosted ASR API key. |
| `EMBEDDING_MODEL_NAME` | 🟢 Optional | String | `"sentence-transformers/all-MiniLM-L6-v2"` | Sentence transformer model for resume and question vector embeddings. |
| `EMBEDDING_DEVICE` | 🟢 Optional | String | `"cpu"` | Keep `"cpu"` to prevent VRAM contention with Ollama. |

---

### 3.8 Proctoring Thresholds & Scoring Weights

These constants define the behavioral heuristics for gaze, posture, pace, and scoring. They have pre-validated production defaults and should generally remain unchanged unless specific institutional calibration is required:

```python
# Video & Head Pose Thresholds
MIN_FACE_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5
GAZE_CENTER_TOLERANCE_X = 0.15      # Horizontal iris deviation limit
GAZE_CENTER_TOLERANCE_Y = 0.12      # Vertical iris deviation limit
HEAD_YAW_THRESHOLD_DEG = 25.0       # Left/right head turn limit
HEAD_PITCH_THRESHOLD_DEG = 20.0     # Up/down head tilt limit
HEAD_ROLL_THRESHOLD_DEG = 20.0      # Sideways head roll limit
MULTIPLE_FACES_PENALTY_PER_SEC = 2.0
NO_FACE_PENALTY_PER_SEC = 1.0

# Speech Pace & Fluency Thresholds
SPEECH_PACE_MIN_WPM = 90            # Words per minute floor
SPEECH_PACE_MAX_WPM = 180           # Words per minute ceiling
SPEECH_PAUSE_THRESHOLD_SEC = 3.5    # Unusually long pause threshold
FILLER_WORD_PENALTY = 0.5           # Deduction per excessive filler word

# Monotonic Scoring Category Weights (Must sum to 1.0)
SCORING_WEIGHTS = {
    "technical_depth": 0.35,        # Correctness & depth vs ground truth
    "communication": 0.25,          # Fluency, vocabulary, structure, pace
    "proctoring_integrity": 0.25,   # Eye contact, posture, integrity
    "resume_relevance": 0.15,       # Alignment with candidate background
}
```

---

## 4. Production Secret Protection & Best Practices

### 4.1 Cryptographic Key Generation
Generate `SECRET_KEY` using an OS-level CSPRNG. Never use human-readable phrases or passwords:
```bash
# Generate 64-character hex string (256-bit entropy):
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4.2 Cloud Secret Injection Patterns
- **AWS ECS / Fargate:**
  Reference secrets directly from AWS Secrets Manager or SSM Parameter Store in the container task definition:
  ```json
  {
    "name": "SECRET_KEY",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:pluto/SECRET_KEY"
  },
  {
    "name": "DATABASE_URL",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:pluto/DATABASE_URL"
  }
  ```
- **Never Mount `.env` in Production Images:**
  Ensure `.env` is listed in `.dockerignore` and `.gitignore`. Docker images must be built without environment files baked in.

### 4.3 Safe Logging & Redaction
FastAPI and Uvicorn log filters automatically sanitize connection strings and authorization headers:
- URLs with embedded passwords (`postgresql://user:pass@host/db`) are automatically redacted to `postgresql://user:***@host/db` before printing to logs.
- Authorization Bearer tokens are redacted in HTTP access logs.

---

## 5. Production Environment Template (`.env.production`)

Below is a sanitized template ready for production staging configuration:

```bash
# ==============================================================================
# PLUTO vProctor — Production Environment Configuration Template
# ==============================================================================

# Server & Runtime Environment
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=https://proctor.yourdomain.com,https://admin.yourdomain.com

# Feature Flags
AUTH_ENABLED=True
HOSTED_ROOMS_ENABLED=True
LIVE_MEDIA_ENABLED=True
MEDIA_TRANSPORT_MODE=p2p
SFU_URL=

# Cryptographic & Session Security (Replace with generated 64-char hex)
SECRET_KEY=REPLACE_WITH_GENERATED_64_CHAR_HEX_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
COOKIE_SECURE=True
COOKIE_SAMESITE=lax
REFRESH_COOKIE_NAME=pluto_refresh_token
CSRF_COOKIE_NAME=pluto_csrf_token

# PostgreSQL Relational Database (Psycopg 3 driver)
DATABASE_URL=postgresql+psycopg://pluto_admin:REPLACE_WITH_DB_PASSWORD@postgres.internal.vpc:5432/pluto_prod

# Redis Cache & Task Queue (TLS enabled)
REDIS_URL=rediss://:REPLACE_WITH_REDIS_PASSWORD@redis.internal.vpc:6379/0

# WebRTC NAT Traversal (STUN & TURN)
STUN_SERVERS=stun:stun.l.google.com:19302
TURN_SERVER_URLS=turns:turn.yourdomain.com:5349?transport=tcp
TURN_USERNAME=pluto_webrtc_user
TURN_CREDENTIAL=REPLACE_WITH_SECURE_TURN_PASSWORD

# Ollama AI Inference (Internal VPC Host)
OLLAMA_BASE_URL=http://ollama.internal.vpc:11434
LLM_MODEL=qwen2.5:3b
LLM_NUM_CTX=4096
LLM_KEEP_ALIVE=30s
LLM_TEMPERATURE=0.2

# ASR & Embedding Models
ASR_PROVIDER=auto
WHISPER_MODEL_SIZE=base.en
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_BEAM_SIZE=1
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

# Data Retention Policy (days)
RETENTION_DAYS=30
```
