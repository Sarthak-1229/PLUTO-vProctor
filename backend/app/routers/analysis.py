"""API endpoints for triggering parallel video/audio analysis and polling status via JobQueue."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.db.models import InterviewSession, User
from backend.app.services.analysis_service import analysis_service
from backend.app.services.authorization import (
    ADMIN_ROLES,
    enforce_session_access,
    get_user_when_auth_enabled,
)
from backend.app.services.job_queue import job_queue

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


@router.post("/{sid}/run", response_model=Dict[str, Any])
async def run_session_analysis(
    sid: str,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Trigger parallel video and audio analysis pipelines via managed JobQueue."""
    enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )
    try:
        job = job_queue.enqueue(session_id=sid, job_type="FULL_ANALYSIS")
        # Ensure workers are active
        job_queue.start_workers()

        return {
            "status": job.status.value,
            "job_id": job.job_id,
            "session_id": sid,
            "stage": job.stage,
            "message": "Analysis scheduled in background queue.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sid}/status", response_model=Dict[str, Any])
def get_analysis_status(
    sid: str,
    current_user: Optional[User] = Depends(get_user_when_auth_enabled),
    db: Session = Depends(get_db),
):
    """Poll per-pipeline progress for video and audio analysis."""
    enforce_session_access(
        db.query(InterviewSession).filter(InterviewSession.id == sid).first(),
        current_user,
    )
    job = job_queue.get_job_by_session(sid)
    legacy = analysis_service.get_status(sid)

    if job:
        video_pct = int(round(job.progress.get("video", legacy.get("video_progress", 0.0)) * 100))
        audio_pct = int(round(job.progress.get("audio", legacy.get("audio_progress", 0.0)) * 100))
        return {
            "session_id": sid,
            "job_id": job.job_id,
            "status": job.status.value,
            "stage": job.stage,
            "video_pct": max(video_pct, int(legacy.get("video_progress", 0) * 100)),
            "audio_pct": max(audio_pct, int(legacy.get("audio_progress", 0) * 100)),
            "video_progress": job.progress.get("video", legacy.get("video_progress", 0.0)),
            "audio_progress": job.progress.get("audio", legacy.get("audio_progress", 0.0)),
            "video": legacy.get("video", {"status": "PROCESSING", "progress": 0.5}),
            "audio": legacy.get("audio", {"status": "PROCESSING", "progress": 0.5}),
            "error": job.error or legacy.get("error"),
        }

    return legacy


@router.get("/jobs/stats", response_model=Dict[str, Any])
def get_queue_stats(current_user: Optional[User] = Depends(get_user_when_auth_enabled)):
    """Retrieve queue depth, running jobs, and failure metrics for observability."""
    if settings.AUTH_ENABLED and (current_user is None or current_user.role not in ADMIN_ROLES):
        raise AppError(status_code=403, code="forbidden_role", message="Administrator privileges required.")
    return job_queue.get_metrics()
