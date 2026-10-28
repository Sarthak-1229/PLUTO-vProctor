"""Main FastAPI application entry point for PLUTO vProctor."""

from datetime import datetime, timezone
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local offline AI mock-interview and proctoring web application.",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.routers.analysis import router as analysis_router
from backend.app.routers.interview import router as interview_router
from backend.app.routers.jobs import router as jobs_router
from backend.app.routers.report import router as report_router
from backend.app.routers.resume import router as resume_router
from backend.app.routers.settings import router as settings_router

app.include_router(jobs_router)
app.include_router(resume_router)
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
    """Save ground-truth fixture recording and annotation labels."""
    fixture_dir = settings.BASE_DIR / "backend" / "tests" / "fixtures" / "recordings"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    video_bytes = await video_file.read()
    (fixture_dir / f"{fixture_id}.webm").write_bytes(video_bytes)
    (fixture_dir / f"{fixture_id}.labels.json").write_text(labels_json, encoding="utf-8")
    return {"status": "ok", "fixture_id": fixture_id}


@app.get("/health")
def health_check():
    """System health check endpoint."""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ollama_endpoint": settings.OLLAMA_BASE_URL,
        "model": settings.LLM_MODEL,
    }


@app.get("/")
def root():
    """Root redirect / index information."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API. Visit /docs for OpenAPI documentation.",
        "health": "/health",
    }
