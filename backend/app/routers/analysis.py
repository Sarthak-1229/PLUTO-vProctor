"""API endpoints for triggering parallel video/audio analysis and polling status."""
from __future__ import annotations

import asyncio
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.app.services.analysis_service import analysis_service

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


@router.post("/{sid}/run", response_model=Dict[str, Any])
async def run_session_analysis(sid: str, background_tasks: BackgroundTasks):
    """Trigger parallel video and audio analysis pipelines in background."""
    try:
        # Schedule analysis in background
        background_tasks.add_task(analysis_service.run_analysis, sid)
        return {
            "status": "PROCESSING",
            "session_id": sid,
            "message": "Analysis started in background.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sid}/status", response_model=Dict[str, Any])
def get_analysis_status(sid: str):
    """Poll per-pipeline progress for video and audio analysis."""
    return analysis_service.get_status(sid)
