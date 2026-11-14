# PLUTO vProctor — Known Limitations & Operational Considerations

This document records technical limitations, environmental constraints, and architectural boundaries identified during the Final Release Audit.

---

## 1. Host Environment Docker & PostgreSQL Absence

### Limitation:
The development host operating system (Windows 11) does not have the Docker Engine daemon or native PostgreSQL CLI tools installed (`The term 'docker' is not recognized`).

### Effect:
- While multi-stage container definitions ([backend/Dockerfile](file:///D:/_TY/MDM/PLUTO-vProctor/backend/Dockerfile), [frontend/Dockerfile](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/Dockerfile), [frontend/nginx.conf](file:///D:/_TY/MDM/PLUTO-vProctor/frontend/nginx.conf)) and orchestration manifests ([docker-compose.yml](file:///D:/_TY/MDM/PLUTO-vProctor/docker-compose.yml), [docker-compose.sqlite.yml](file:///D:/_TY/MDM/PLUTO-vProctor/docker-compose.sqlite.yml)) have been authored and verified, executing live multi-container orchestration on this specific host is blocked.
- PostgreSQL DDL compilation has been verified (`test_alembic_postgresql_ddl_compilation_clean`), but live cluster verification was marked as skipped locally when `TEST_POSTGRES_URL` was unset.

### Operational Remediation:
To launch the full enterprise stack on any machine with Docker installed:
```bash
# Generate secure production secret
export SECRET_KEY=$(openssl rand -hex 32)

# Build and start all services
docker compose up -d --build

# Run Alembic migrations against PostgreSQL
docker compose exec backend alembic upgrade head
```
For local execution on the current machine, PLUTO vProctor is 100% operational via the native Python/Vite servers using `run_dev.bat`.

---

## 2. WebRTC NAT Traversal (STUN vs TURN)

### Limitation:
Browser-to-browser WebRTC Peer-to-Peer media utilizes Google's public STUN server (`stun:stun.l.google.com:19302`) by default for ICE candidate gathering.

### Effect:
- P2P direct media works across normal residential broadband, mobile networks, and standard routers.
- Direct P2P UDP packet traversal may fail if both peers are behind restrictive corporate symmetric NATs or enterprise firewalls that block non-standard UDP ports.

### Operational Remediation:
For production enterprise environments, configure TURN relay server credentials in `.env`:
```env
TURN_SERVER_URLS=turn:turn.example.com:3478
TURN_USERNAME=pluto_turn_user
TURN_CREDENTIAL=pluto_turn_secret_password
```
Alternatively, switch the media transport layer to an SFU (such as LiveKit) by setting `MEDIA_TRANSPORT_MODE=sfu` and configuring `SFU_URL`.

---

## 3. Local Ollama LLM Offline Fallback

### Limitation:
PLUTO vProctor uses a local 3B parameter model (`qwen2.5:3b`) via Ollama (`http://localhost:11434`) for qualitative evaluation feedback.

### Effect:
If the local Ollama process is not running, LLM API calls time out after 45 seconds or fail connection.

### Design Mitigation:
The evaluation engine never relies exclusively on the LLM (adhering to core architectural rule #4: *"The LLM never alone decides a score"*). When Ollama is offline:
- The system automatically falls back to deterministic algorithmic evaluation: MiniLM cosine similarity, TF-IDF vector similarity, BM25 ranking, and RAKE keyword matching.
- Scoring, rubric breakdowns, radar metrics, and report generation complete successfully without crashing.

---

## 4. Ground-Truth Fixture Audio Metric

### Limitation:
The ground-truth fixture test asset `fixture_synth_001.webm` uses synthetic audio tones and synthetic video to test pipeline stability.

### Effect:
- ASR word error rate (WER) on this specific synthetic asset is 100% because no natural spoken English words exist in the audio track.
- Look-away recall (100.0%) and timestamp median error (2.07s) are fully evaluated and comfortably satisfy the CI benchmark gate threshold ($\le 4.0\text{s}$).

