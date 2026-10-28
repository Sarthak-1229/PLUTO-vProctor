"""API router for dynamically querying and tuning application thresholds and weights."""
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.config import settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsUpdateSchema(BaseModel):
    gaze_tolerance_x: float | None = None
    gaze_tolerance_y: float | None = None
    head_yaw_deg: float | None = None
    head_pitch_deg: float | None = None
    speech_pause_sec: float | None = None
    filler_penalty: float | None = None
    speech_min_wpm: int | None = None
    speech_max_wpm: int | None = None
    technical_weight: float | None = None
    communication_weight: float | None = None
    proctoring_weight: float | None = None
    resume_weight: float | None = None


@router.get("", response_model=Dict[str, Any])
def get_current_settings():
    """Retrieve active thresholds, fairness limits, and scoring weights."""
    return {
        "gaze_tolerance_x": settings.GAZE_CENTER_TOLERANCE_X,
        "gaze_tolerance_y": settings.GAZE_CENTER_TOLERANCE_Y,
        "head_yaw_deg": settings.HEAD_YAW_THRESHOLD_DEG,
        "head_pitch_deg": settings.HEAD_PITCH_THRESHOLD_DEG,
        "speech_pause_sec": settings.SPEECH_PAUSE_THRESHOLD_SEC,
        "filler_penalty": settings.FILLER_WORD_PENALTY,
        "speech_min_wpm": settings.SPEECH_PACE_MIN_WPM,
        "speech_max_wpm": settings.SPEECH_PACE_MAX_WPM,
        "weights": settings.SCORING_WEIGHTS,
        "llm_model": settings.LLM_MODEL,
        "keep_alive": settings.LLM_KEEP_ALIVE,
    }


@router.put("", response_model=Dict[str, Any])
def update_settings(payload: SettingsUpdateSchema):
    """Adjust thresholds and fairness parameters for the interview runtime."""
    if payload.gaze_tolerance_x is not None:
        settings.GAZE_CENTER_TOLERANCE_X = payload.gaze_tolerance_x
    if payload.gaze_tolerance_y is not None:
        settings.GAZE_CENTER_TOLERANCE_Y = payload.gaze_tolerance_y
    if payload.head_yaw_deg is not None:
        settings.HEAD_YAW_THRESHOLD_DEG = payload.head_yaw_deg
    if payload.head_pitch_deg is not None:
        settings.HEAD_PITCH_THRESHOLD_DEG = payload.head_pitch_deg
    if payload.speech_pause_sec is not None:
        settings.SPEECH_PAUSE_THRESHOLD_SEC = payload.speech_pause_sec
    if payload.filler_penalty is not None:
        settings.FILLER_WORD_PENALTY = payload.filler_penalty
    if payload.speech_min_wpm is not None:
        settings.SPEECH_PACE_MIN_WPM = payload.speech_min_wpm
    if payload.speech_max_wpm is not None:
        settings.SPEECH_PACE_MAX_WPM = payload.speech_max_wpm

    # Update weights if specified
    weights = dict(settings.SCORING_WEIGHTS)
    if payload.technical_weight is not None:
        weights["technical_depth"] = payload.technical_weight
    if payload.communication_weight is not None:
        weights["communication"] = payload.communication_weight
    if payload.proctoring_weight is not None:
        weights["proctoring_integrity"] = payload.proctoring_weight
    if payload.resume_weight is not None:
        weights["resume_relevance"] = payload.resume_weight

    total = sum(weights.values())
    if abs(total - 1.0) < 0.05:
        settings.SCORING_WEIGHTS = weights

    return {
        "status": "updated",
        "settings": get_current_settings(),
    }
