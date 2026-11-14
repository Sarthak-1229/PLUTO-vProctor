# PLUTO vProctor — Production Deployment & Operations Guide

This guide details the topology, configuration, containerization, and operations for deploying PLUTO vProctor v2 in local, staging, and production environments.

---

## 1. Architecture & Deployment Topologies

PLUTO vProctor supports three primary deployment configurations:

```
+-----------------------------------------------------------------------------------+
| 1. Local Offline Development                                                      |
|    Browser <--> Vite Dev Server (5173) <--> FastAPI (8000) <--> SQLite (pluto.db) |
|                                                                                   |
| 2. Lightweight Docker (SQLite + In-Memory Queue)                                  |
|    Browser <--> Nginx Reverse Proxy (80) <--> FastAPI (8000) <--> SQLite Volume   |
|                                                                                   |
| 3. Production High-Availability (PostgreSQL + Redis + Dedicated Worker Pool)     |
|    Browser <== HTTPS/WSS ==> Nginx / CDN                                          |
|                                 |                                                 |
|             +-------------------+-------------------+                             |
|             |                                       |                             |
|             v                                       v                             |
|    FastAPI API Server (8000)             Background Worker                        |
|             |                                       |                             |
|             +---------> PostgreSQL 16 <-------------+                             |
|             |                                       |                             |
|             +------------> Redis 7 <----------------+                             |
+-----------------------------------------------------------------------------------+
```

### Topology Comparison

| Feature | Local Dev (`run_dev.bat`) | Docker Standalone (`docker-compose.sqlite.yml`) | Full Production (`docker-compose.yml`) |
|---|---|---|---|
| **Database** | SQLite (`backend/app/pluto.db`) | SQLite (`/app/storage/pluto.db`) | PostgreSQL 16 (Managed or Container) |
| **Task Queue** | In-Process Memory Queue | In-Process Memory Queue | Redis 7 + Dedicated Worker Process |
| **Web Server** | Uvicorn `--reload` + Vite | Nginx Alpine + Uvicorn | Multi-worker Uvicorn behind Nginx/ALB |
| **WebRTC Media** | Direct P2P (localhost) | P2P + Google Public STUN | P2P / SFU + Authenticated TURN Servers |
| **Authentication** | Optional (`AUTH_ENABLED=0`) | Enabled (`AUTH_ENABLED=1`) | Enabled (`AUTH_ENABLED=1`, `COOKIE_SECURE=1`) |

---

## 2. Configuration & Environment Variables

All settings are configured via environment variables or a `.env` file loaded by Pydantic Settings.

### Core Settings

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Deployment tier: `development`, `test`, `staging`, `production`. |
| `DATABASE_URL` | `sqlite:///backend/app/pluto.db` | Connection string (`sqlite:///...` or `postgresql+psycopg://...`). |
| `REDIS_URL` | `""` | Redis connection URL (`redis://redis:6379/0`). |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `AUTH_ENABLED` | `false` | Enable JWT authentication, registration, and RBAC guards. |
| `HOSTED_ROOMS_ENABLED` | `false` | Enable Admin-hosted interview rooms and WebSocket signaling. |
| `LIVE_MEDIA_ENABLED` | `false` | Enable live video and audio observation during interviews. |
| `MEDIA_TRANSPORT_MODE` | `p2p` | Transport mode: `none`, `p2p`, or `sfu`. |
| `SFU_URL` | `""` | WebSocket URL for external SFU (required if `MEDIA_TRANSPORT_MODE=sfu`). |
| `SECRET_KEY` | `""` | Minimum 32-character secret key for JWT and signing (required in production). |
| `COOKIE_SECURE` | `false` | Set to `true` in production to enforce `Secure` flag on HTTPS cookies. |
| `CORS_ORIGINS` | `["http://localhost:5173", ...]` | Allowed HTTP origins for CORS cross-origin requests. |

### WebRTC & NAT Traversal Settings

| Variable | Default | Description |
|---|---|---|
| `STUN_SERVERS` | `["stun:stun.l.google.com:19302"]` | Comma-separated list or JSON array of STUN server URIs. |
| `TURN_SERVER_URLS` | `[]` | TURN relay server URIs for NAT traversal across restrictive corporate firewalls. |
| `TURN_USERNAME` | `""` | TURN authentication username. |
| `TURN_CREDENTIAL` | `""` | TURN authentication credential / password. |

### Production Fail-Fast Validation

When `ENVIRONMENT=production`, the application executes `settings.validate_runtime_safety()` on startup:
1. `SECRET_KEY` must be at least 32 characters and cannot contain placeholders (`"change-me"`, `"placeholder"`, etc.).
2. `COOKIE_SECURE` must be `true` when `AUTH_ENABLED=true`.
3. `SFU_URL` must be non-empty when `MEDIA_TRANSPORT_MODE="sfu"`.

---

## 3. Deployment Methods

### Option A: Local-First Standalone (Zero Container Overhead)

Ideal for quick development, testing, and offline practice:

```cmd
:: 1. Launch development servers using the bundled batch script
run_dev.bat
```

Or manually:
```bash
# Terminal 1: Backend
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Option B: Docker Compose — Full Production (PostgreSQL + Redis)

Ideal for staging and production deployments:

```bash
# 1. Generate a strong secret key
export SECRET_KEY=$(openssl rand -hex 32)

# 2. Start all services in detached mode
docker compose up -d --build

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Check cluster status
docker compose ps
```

Services exposed:
- `http://localhost:80` (or configured domain): Frontend SPA and API via Nginx
- `http://localhost:8000/docs`: Backend OpenAPI Swagger documentation
- `http://localhost:8000/api/health`: Health probe
- `http://localhost:8000/api/ready`: Readiness probe

### Option C: Docker Compose — Standalone SQLite

Ideal for lightweight single-server deployments without PostgreSQL/Redis overhead:

```bash
export SECRET_KEY=$(openssl rand -hex 32)
docker compose -f docker-compose.sqlite.yml up -d --build
```

---

## 4. Reverse Proxy & Realtime WebSocket Configuration

When deploying behind external reverse proxies (Nginx, Traefik, AWS ALB, Cloudflare), WebSocket upgrading **must** be explicitly enabled for `/api/rooms/{room_id}/ws`.

### Nginx Example (`frontend/nginx.conf`):
```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    client_max_body_size 250M;

    # Realtime WebSocket Room Signaling
    location ~* ^/api/rooms/.*/ws$ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # REST API
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
    }

    # Single Page Application fallback
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 5. Database Migrations & Safety

All schema migrations are strictly version-controlled with Alembic and are safe for both SQLite and PostgreSQL.

### Applying Migrations
```bash
# Upgrade database to latest revision
alembic upgrade head

# Verify current revision
alembic current

# Check for schema drift
alembic check
```

### Safe Rollback Procedure
```bash
# Downgrade by one revision
alembic downgrade -1

# Downgrade to a specific milestone (e.g. Phase 2)
alembic downgrade 0003_phase2_auth_profiles_rbac
```

> [!IMPORTANT]
> Always take a snapshot backup of `pluto.db` or PostgreSQL before running migrations in production:
> ```bash
> # SQLite backup
> cp backend/app/pluto.db "backups/pluto_pre_migration_$(date +%Y%m%d_%H%M%S).db"
> 
> # PostgreSQL backup
> pg_dump -U pluto_user -d pluto_db -Fc > "backups/pg_dump_$(date +%Y%m%d_%H%M%S).dump"
> ```

---

## 6. Observability, Health Checks & Monitoring

### Liveness Probe
`GET /api/health`
Returns HTTP 200 with runtime environment, version, and timestamp.
```json
{
  "status": "ok",
  "app_name": "PLUTO vProctor",
  "version": "0.1.0",
  "environment": "production",
  "timestamp": "2026-11-14T02:00:00Z"
}
```

### Readiness Probe
`GET /api/ready`
Verifies live database connectivity and storage directory availability.
```json
{
  "status": "ready",
  "database": "connected",
  "storage": "available",
  "timestamp": "2026-11-14T02:00:00Z"
}
```

### Correlation & Structured Logs
Every request is assigned a unique `X-Request-ID` header. Structured logs automatically format requests with correlation context:
```
2026-11-14 02:00:00 [INFO] [Req:a1b2c3d4] pluto.server: GET /api/admin/rooms -> 200 (12.45ms)
```

---

## 7. Disaster Recovery & Fallback

If hosted rooms or WebRTC signaling encounter external network or infrastructure outages:
1. **Preserve Offline Practice:** Set `HOSTED_ROOMS_ENABLED=false` and `AUTH_ENABLED=false` in `.env` to immediately revert the application to local self-practice interview mode with zero downtime.
2. **Database Rollback:** Restore the pre-migration database snapshot directly into `backend/app/pluto.db` or PostgreSQL. Legacy candidate data remains preserved.

