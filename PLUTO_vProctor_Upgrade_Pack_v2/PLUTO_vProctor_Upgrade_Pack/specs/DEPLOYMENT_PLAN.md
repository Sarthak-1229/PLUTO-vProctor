# Deployment Plan

## Recommended target topology
- Frontend: static React build behind CDN/reverse proxy (HTTPS).
- API: FastAPI web service, horizontally scalable where safe.
- Worker: separate background worker for Whisper/video analysis/report generation.
- Database: managed PostgreSQL with automated backups and point-in-time recovery.
- Queue/cache: Redis for production job queue, rate limiting and ephemeral room coordination where appropriate.
- Media: private object storage (S3-compatible) for recordings/resumes/reports, with lifecycle policies and signed URLs.
- Realtime: authenticated WebSocket for room control; LiveKit/SFU for live media observation when that requirement is enabled.
- Observability: structured logs, metrics, tracing, error reporting, uptime/health checks.
- Secrets: cloud secret manager; no secrets in source control or frontend variables.

## Important AI/compute decision
The current local-first stack uses Ollama/Qwen2.5:3b, MiniLM, Faster-Whisper and MediaPipe. These components are not automatically portable to a low-cost serverless host.
Choose explicitly between:
1. **Private GPU/CPU worker deployment:** run the existing models in a dedicated worker VM/container with adequate CPU/RAM/GPU. Best for preserving local model behavior and privacy.
2. **Hybrid deployment:** host app/database/media in cloud while processing sensitive media on a controlled worker. Requires clear data-flow and consent documentation.
3. **Optional hosted providers:** only with explicit opt-in, provider review, regional/data-processing checks and documented fallback.
Do not silently move data to third-party AI APIs.

## Environments
- Local: SQLite, local storage, Ollama, CPU/GPU worker; preserve `run_dev.bat`.
- Staging: PostgreSQL, Redis, private object storage, HTTPS, test email provider, isolated test data.
- Production: managed PostgreSQL, private storage, Redis, worker pool, TLS, backups, monitoring, retention jobs and incident runbook.

## Rollout
1. Keep current local application usable.
2. Deploy auth and candidate/admin web/API in staging.
3. Deploy migrations with backup and rollback.
4. Deploy room orchestration without live video streaming; validate reconnect and controls.
5. Add secure SFU media viewing if required and load-tested.
6. Deploy worker and media pipeline; verify GPU/CPU resource constraints.
7. Enable limited pilot with test candidates and admins.
8. Expand after security, privacy, load and fairness review.

## Operational requirements
- `/health` for liveness and `/ready` for DB/queue/model readiness.
- Graceful shutdown and worker retry/idempotency.
- DB backups plus restore drills; object-storage lifecycle and backup policy.
- Separate staging/prod secrets and data.
- Upload size limits at proxy and API layers; support large video upload with resumable/chunked upload if needed.
- Rate limits, WAF/CDN as appropriate, TLS and secure headers.
- Monitor API latency, queue depth, worker failures, room disconnects, WebSocket connections, storage growth and model resource use.
- Do not store live media in PostgreSQL.
- Load test expected concurrent interviews and recording upload bandwidth before selecting instance sizes.

## Rollback
- Keep previous frontend/API images.
- Use additive DB migrations; document downgrade where safe.
- Never automatically downgrade destructive schema changes.
- Feature flags for auth rollout, room mode, live media and new proctoring thresholds.
- Document how to disable hosted rooms while keeping offline interview mode available.
