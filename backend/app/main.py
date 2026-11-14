"""Main FastAPI application entry point for PLUTO vProctor."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, File, Form, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import settings
from backend.app.core.errors import (
    SECURITY_HEADERS,
    get_current_request_id,
    register_exception_handlers,
    request_id_ctx,
)
from backend.app.services.job_queue import job_queue

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [Req:%(request_id)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Custom log record factory to include request_id default
old_factory = logging.getLogRecordFactory()


def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    if not hasattr(record, "request_id"):
        record.request_id = get_current_request_id()
    return record


logging.setLogRecordFactory(record_factory)
logger = logging.getLogger("pluto.server")

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Manage application startup and shutdown lifecycle cleanly."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode...")
    settings.validate_runtime_safety()
    job_queue.start_workers()
    try:
        yield
    finally:
        job_queue.stop_workers()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready multimodal AI video interview and proctoring engine.",
    lifespan=lifespan,
)
register_exception_handlers(app, cors_origins=settings.CORS_ORIGINS)


# 1. Request-ID Correlation Middleware
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        t0 = time.time()

        # Attach request_id and start_time to request state and logging context
        request.state.request_id = req_id
        request.state.start_time = t0
        token = request_id_ctx.set(req_id)
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.time() - t0) * 1000, 2)

            # Inject X-Request-ID and security headers into response
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Response-Time-MS"] = str(duration_ms)
            response.headers.update(SECURITY_HEADERS)

            # Log completion (avoiding PII in URL params)
            path = request.url.path
            logger.info("%s %s -> %s (%.2fms)", request.method, path, response.status_code, duration_ms)
            return response
        finally:
            request_id_ctx.reset(token)


app.add_middleware(RequestIDMiddleware)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 3. Route Registration
from backend.app.routers.admin import router as admin_router
from backend.app.routers.admin_analytics import router as admin_analytics_router
from backend.app.routers.admin_rooms import router as admin_rooms_router
from backend.app.routers.analysis import router as analysis_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.candidate import router as candidate_router
from backend.app.routers.candidate_roadmap import router as candidate_roadmap_router
from backend.app.routers.interview import router as interview_router
from backend.app.routers.jobs import router as jobs_router
from backend.app.routers.question_sets import router as question_sets_router
from backend.app.routers.report import router as report_router
from backend.app.routers.resume import router as resume_router
from backend.app.routers.resumes import router as resumes_router
from backend.app.routers.rooms import router as rooms_router
from backend.app.routers.settings import router as settings_router

app.include_router(auth_router)
app.include_router(candidate_router)
app.include_router(candidate_roadmap_router)
app.include_router(admin_router)
app.include_router(admin_analytics_router)
app.include_router(admin_rooms_router)
app.include_router(rooms_router)
app.include_router(question_sets_router)
app.include_router(jobs_router)
app.include_router(resume_router)
app.include_router(resumes_router)
app.include_router(interview_router)
app.include_router(analysis_router)
app.include_router(report_router)
app.include_router(settings_router)


@app.post("/api/fixtures/save")
async def save_fixture(
    fixture_id: str = Form(...),
    video_file: UploadFile = File(...),
    labels_json: str = Form(...),
):
    """Save ground-truth fixture recording and annotation labels (dev/test fixture utility)."""
    import re
    if settings.ENVIRONMENT.strip().lower() == "production" or settings.AUTH_ENABLED:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Fixture saving is disabled when AUTH_ENABLED or production mode is active.")
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", fixture_id).strip("_") or "fixture"
    fixture_dir = settings.BASE_DIR / "backend" / "tests" / "fixtures" / "recordings"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    video_bytes = await video_file.read()
    (fixture_dir / f"{safe_id}.webm").write_bytes(video_bytes)
    (fixture_dir / f"{safe_id}.labels.json").write_text(labels_json, encoding="utf-8")
    return {"status": "ok", "fixture_id": safe_id}


@app.get("/health")
@app.get("/api/health")
def health_check():
    """System liveness health probe."""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ollama_endpoint": settings.OLLAMA_BASE_URL,
        "model": settings.LLM_MODEL,
    }


@app.get("/ready")
@app.get("/api/ready")
def readiness_check():
    """System readiness check verifying database and storage availability."""
    db_ok = True
    try:
        from sqlalchemy import text
        from backend.app.db.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_ok = False

    storage_ok = settings.STORAGE_DIR.exists()

    return {
        "status": "ready" if (db_ok and storage_ok) else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "storage": "available" if storage_ok else "missing",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def root():
    """Root redirect / index information."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API. Visit /docs for OpenAPI documentation.",
        "health": "/api/health",
        "ready": "/api/ready",
    }
