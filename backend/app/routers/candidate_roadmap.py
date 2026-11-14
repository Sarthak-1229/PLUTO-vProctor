"""Candidate learning roadmap, skill growth analytics, and targeted preparation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.authorization import get_current_user
from backend.app.services.roadmap_service import roadmap_service

router = APIRouter(prefix="/api/candidate", tags=["candidate-roadmap"])


@router.get("/analytics")
def get_candidate_analytics_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve historical interview statistics and performance trends for the authenticated candidate."""
    return roadmap_service.get_candidate_analytics(db, current_user.id)


@router.get("/roadmap")
def get_candidate_roadmap_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate structured competency milestones and personalized preparation roadmap."""
    return roadmap_service.generate_learning_roadmap(db, current_user.id)

