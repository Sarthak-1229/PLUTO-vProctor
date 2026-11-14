"""API endpoints for admin interview question collections and custom sets."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.authorization import require_roles
from backend.app.services.question_set_service import (
    create_question_set,
    delete_question_set,
    get_question_set,
    list_question_sets,
    validate_question_set_payload,
)

router = APIRouter(prefix="/api/admin/question-sets", tags=["Admin Question Sets"])


class QuestionItemSchema(BaseModel):
    source_question_id: Optional[str] = None
    question_text: str = Field(..., min_length=5)
    domain: Optional[str] = "General"
    difficulty: Optional[str] = "Intermediate"
    target_skills: Optional[List[str]] = Field(default_factory=list)
    ideal_criteria: Optional[List[str]] = Field(default_factory=list)
    time_limit_seconds: Optional[int] = 180


class CreateQuestionSetSchema(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    source_filename: Optional[str] = None
    items: List[QuestionItemSchema] = Field(..., min_length=1)


@router.post("", response_model=Dict[str, Any], status_code=201)
def create_set_endpoint(
    payload: CreateQuestionSetSchema,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Create a validated question collection owned by an administrator."""
    return create_question_set(db, admin_user=admin_user, data=payload.model_dump())


@router.get("", response_model=List[Dict[str, Any]])
def list_sets_endpoint(
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """List question sets available to this administrator."""
    return list_question_sets(db, admin_user=admin_user)


@router.get("/{qset_id}", response_model=Dict[str, Any])
def get_set_endpoint(
    qset_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Get full question set details with ordered items."""
    return get_question_set(db, qset_id, admin_user=admin_user)


@router.delete("/{qset_id}")
def delete_set_endpoint(
    qset_id: str,
    admin_user: User = Depends(require_roles(["admin", "super_admin"])),
    db: Session = Depends(get_db),
):
    """Delete a custom question set."""
    delete_question_set(db, qset_id, admin_user=admin_user)
    return {"status": "deleted", "id": qset_id}


@router.post("/validate")
def validate_set_endpoint(
    payload: CreateQuestionSetSchema,
    _admin: User = Depends(require_roles(["admin", "super_admin"])),
):
    """Validate question set payload structure and completeness."""
    validate_question_set_payload(payload.model_dump())
    return {"status": "valid", "item_count": len(payload.items)}

