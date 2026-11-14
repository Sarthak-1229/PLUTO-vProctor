"""Service managing admin interview question sets, custom templates, and validation."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.db.models import InterviewRoom, Job, Question, QuestionSet, QuestionSetItem, RoomQuestion, User
from backend.app.services.security_service import record_audit_event


def _compute_checksum(items: List[Dict[str, Any]]) -> str:
    serialized = json.dumps(
        [
            {
                "text": (item.get("question_text") or item.get("text") or "").strip(),
                "domain": (item.get("domain") or "General").strip(),
                "skills": sorted(item.get("target_skills") or item.get("target_skills_json") or []),
            }
            for item in items
        ],
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_question_set_payload(data: Dict[str, Any]) -> None:
    """Validate structure and semantic completeness of a question set."""
    name = (data.get("name") or "").strip()
    if not name or len(name) < 3:
        raise AppError(status_code=422, code="invalid_name", message="Question set name must be at least 3 characters.")
    if len(name) > 255:
        raise AppError(status_code=422, code="invalid_name", message="Question set name cannot exceed 255 characters.")

    items = data.get("items") or data.get("questions") or []
    if not isinstance(items, list) or len(items) == 0:
        raise AppError(status_code=422, code="empty_question_set", message="Question set must contain at least 1 question.")
    if len(items) > 200:
        raise AppError(status_code=422, code="too_many_questions", message="Question set cannot exceed 200 questions.")

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise AppError(status_code=422, code="invalid_item", message=f"Question item {idx} must be an object.")
        text = (item.get("question_text") or item.get("text") or item.get("question") or "").strip()
        if not text or len(text) < 5:
            raise AppError(status_code=422, code="invalid_question_text", message=f"Question {idx} text must be at least 5 characters.")
        if len(text) > 2000:
            raise AppError(status_code=422, code="question_text_too_long", message=f"Question {idx} text cannot exceed 2000 characters.")


def create_question_set(
    db: Session,
    *,
    admin_user: User,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a validated question collection owned by an administrator."""
    validate_question_set_payload(data)
    items = data.get("items") or data.get("questions") or []
    checksum = _compute_checksum(items)

    qset_id = f"qset_{uuid.uuid4().hex[:12]}"
    qset = QuestionSet(
        id=qset_id,
        owner_admin_id=admin_user.id,
        name=str(data["name"]).strip(),
        description=(data.get("description") or "").strip() or None,
        source_filename=data.get("source_filename"),
        schema_version="1.0",
        version=1,
        status="active",
        checksum=checksum,
    )
    db.add(qset)

    for idx, item in enumerate(items, start=1):
        item_id = f"qitem_{uuid.uuid4().hex[:12]}"
        target_skills = item.get("target_skills") or item.get("target_skills_json") or item.get("skills") or []
        if isinstance(target_skills, str):
            target_skills = [s.strip() for s in target_skills.split(",") if s.strip()]
        ideal_criteria = item.get("ideal_criteria") or item.get("ideal_criteria_json") or item.get("criteria") or []
        if isinstance(ideal_criteria, str):
            ideal_criteria = [c.strip() for c in ideal_criteria.split(",") if c.strip()]
        q_item = QuestionSetItem(
            id=item_id,
            question_set_id=qset_id,
            source_question_id=item.get("source_question_id") or item.get("question_id"),
            question_text=(item.get("question_text") or item.get("text") or item.get("question") or "").strip(),
            domain=(item.get("domain") or "General").strip(),
            difficulty=(item.get("difficulty") or "Intermediate").strip(),
            target_skills_json=target_skills if isinstance(target_skills, list) else [target_skills],
            ideal_criteria_json=ideal_criteria if isinstance(ideal_criteria, list) else [ideal_criteria],
            ordinal=idx,
            metadata_json=item.get("metadata") or {},
        )
        db.add(q_item)

    record_audit_event(
        db,
        action="question_set.created",
        resource_type="question_set",
        resource_id=qset_id,
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
        details={"name": qset.name, "question_count": len(items), "checksum": checksum},
    )
    db.commit()
    db.refresh(qset)
    return serialize_question_set(qset)


def list_question_sets(
    db: Session,
    *,
    admin_user: User,
) -> List[Dict[str, Any]]:
    """List available question sets for this administrator."""
    query = db.query(QuestionSet).filter(QuestionSet.status == "active")
    if admin_user.role != "super_admin":
        query = query.filter(QuestionSet.owner_admin_id == admin_user.id)
    records = query.order_by(QuestionSet.created_at.desc()).all()
    return [serialize_question_set(r, include_items=False) for r in records]


def get_question_set(
    db: Session,
    qset_id: str,
    *,
    admin_user: User,
) -> Dict[str, Any]:
    """Retrieve full question set details with ordered items."""
    qset = db.query(QuestionSet).filter(QuestionSet.id == qset_id).first()
    if not qset:
        raise AppError(status_code=404, code="question_set_not_found", message="Question set not found.")
    if admin_user.role != "super_admin" and qset.owner_admin_id != admin_user.id:
        raise AppError(status_code=403, code="forbidden_question_set", message="You do not have access to this question set.")
    return serialize_question_set(qset, include_items=True)


def delete_question_set(
    db: Session,
    qset_id: str,
    *,
    admin_user: User,
) -> None:
    """Delete a question set and its child items, safely preserving room references."""
    qset = db.query(QuestionSet).filter(QuestionSet.id == qset_id).first()
    if not qset:
        raise AppError(status_code=404, code="question_set_not_found", message="Question set not found.")
    if admin_user.role != "super_admin" and qset.owner_admin_id != admin_user.id:
        raise AppError(status_code=403, code="forbidden_question_set", message="You do not have permission to delete this question set.")

    # Check for active rooms (LOBBY, LIVE, PAUSED) referencing this set
    active_rooms = (
        db.query(InterviewRoom)
        .filter(InterviewRoom.question_set_id == qset_id, InterviewRoom.status.in_(["LOBBY", "LIVE", "PAUSED"]))
        .count()
    )
    if active_rooms > 0:
        raise AppError(
            status_code=409,
            code="question_set_in_use",
            message=f"Cannot delete question set: it is currently referenced by {active_rooms} active interview room(s). Complete or cancel those rooms before deleting.",
        )

    # For non-active rooms (COMPLETED, CANCELLED, DRAFT), nullify FK reference so historical rooms and RoomQuestion records are preserved
    db.query(InterviewRoom).filter(InterviewRoom.question_set_id == qset_id).update(
        {InterviewRoom.question_set_id: None}, synchronize_session=False
    )

    record_audit_event(
        db,
        action="question_set.deleted",
        resource_type="question_set",
        resource_id=qset_id,
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
        details={"name": qset.name},
    )
    db.delete(qset)
    db.commit()


def update_question_set(
    db: Session,
    qset_id: str,
    *,
    admin_user: User,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing question set and replace its items."""
    qset = db.query(QuestionSet).filter(QuestionSet.id == qset_id).first()
    if not qset:
        raise AppError(status_code=404, code="question_set_not_found", message="Question set not found.")
    if admin_user.role != "super_admin" and qset.owner_admin_id != admin_user.id:
        raise AppError(status_code=403, code="forbidden_question_set", message="You do not have permission to edit this question set.")

    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if len(name) < 3 or len(name) > 255:
            raise AppError(status_code=422, code="invalid_name", message="Question set name must be between 3 and 255 characters.")
        qset.name = name

    if "description" in data:
        desc = (data["description"] or "").strip()
        qset.description = desc or None

    items = data.get("items") or data.get("questions")
    if items is not None:
        if not isinstance(items, list) or len(items) == 0:
            raise AppError(status_code=422, code="empty_question_set", message="Question set must contain at least 1 question.")
        if len(items) > 200:
            raise AppError(status_code=422, code="too_many_questions", message="Question set cannot exceed 200 questions.")

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise AppError(status_code=422, code="invalid_item", message=f"Question item {idx} must be an object.")
            text = (item.get("question_text") or item.get("text") or item.get("question") or "").strip()
            if not text or len(text) < 5:
                raise AppError(status_code=422, code="invalid_question_text", message=f"Question {idx} text must be at least 5 characters.")
            if len(text) > 2000:
                raise AppError(status_code=422, code="question_text_too_long", message=f"Question {idx} text cannot exceed 2000 characters.")

        # Recompute checksum and bump version
        checksum = _compute_checksum(items)
        qset.checksum = checksum
        qset.version = (qset.version or 1) + 1

        # Delete existing items and insert new ones
        db.query(QuestionSetItem).filter(QuestionSetItem.question_set_id == qset_id).delete(synchronize_session=False)

        for idx, item in enumerate(items, start=1):
            item_id = f"qitem_{uuid.uuid4().hex[:12]}"
            target_skills = item.get("target_skills") or item.get("target_skills_json") or item.get("skills") or []
            if isinstance(target_skills, str):
                target_skills = [s.strip() for s in target_skills.split(",") if s.strip()]
            ideal_criteria = item.get("ideal_criteria") or item.get("ideal_criteria_json") or item.get("criteria") or []
            if isinstance(ideal_criteria, str):
                ideal_criteria = [c.strip() for c in ideal_criteria.split(",") if c.strip()]

            q_item = QuestionSetItem(
                id=item_id,
                question_set_id=qset_id,
                source_question_id=item.get("source_question_id") or item.get("question_id"),
                question_text=(item.get("question_text") or item.get("text") or item.get("question") or "").strip(),
                domain=(item.get("domain") or "General").strip(),
                difficulty=(item.get("difficulty") or "Intermediate").strip(),
                target_skills_json=target_skills if isinstance(target_skills, list) else [target_skills],
                ideal_criteria_json=ideal_criteria if isinstance(ideal_criteria, list) else [ideal_criteria],
                ordinal=idx,
                metadata_json=item.get("metadata") or {},
            )
            db.add(q_item)

    record_audit_event(
        db,
        action="question_set.updated",
        resource_type="question_set",
        resource_id=qset_id,
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
        details={"name": qset.name, "item_count": len(items) if items is not None else (len(qset.items) if qset.items else 0), "version": qset.version},
    )
    db.commit()
    db.refresh(qset)
    return serialize_question_set(qset, include_items=True)


def import_question_set(
    db: Session,
    *,
    admin_user: User,
    raw_payload: Any,
    filename: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Import and validate question set from parsed JSON payload with dry_run preview support."""
    if isinstance(raw_payload, list):
        base_name = (filename or "Imported Question Set").rsplit(".", 1)[0].replace("_", " ").title()
        data = {
            "name": base_name,
            "description": f"Imported from {filename or 'JSON file'}",
            "items": raw_payload,
            "source_filename": filename,
        }
    elif isinstance(raw_payload, dict):
        data = dict(raw_payload)
        if "items" not in data and "questions" in data:
            data["items"] = data["questions"]
        if not data.get("name"):
            base_name = (filename or "Imported Question Set").rsplit(".", 1)[0].replace("_", " ").title()
            data["name"] = base_name
        if filename and not data.get("source_filename"):
            data["source_filename"] = filename
    else:
        raise AppError(status_code=422, code="invalid_json_format", message="Imported content must be a JSON object or array of questions.")

    validate_question_set_payload(data)
    items = data.get("items") or []

    if dry_run:
        return {
            "status": "valid",
            "name": data["name"],
            "description": data.get("description"),
            "source_filename": data.get("source_filename"),
            "item_count": len(items),
            "preview_items": [
                {
                    "ordinal": idx,
                    "question_text": (it.get("question_text") or it.get("text") or it.get("question") or "").strip(),
                    "domain": (it.get("domain") or "General").strip(),
                    "difficulty": (it.get("difficulty") or "Intermediate").strip(),
                    "target_skills": it.get("target_skills") or it.get("skills") or [],
                }
                for idx, it in enumerate(items[:5], start=1)
            ],
        }

    created = create_question_set(db, admin_user=admin_user, data=data)
    record_audit_event(
        db,
        action="question_set.imported",
        resource_type="question_set",
        resource_id=created["id"],
        actor_user_id=admin_user.id,
        actor_role=admin_user.role,
        details={"name": created["name"], "source_filename": filename, "item_count": created["item_count"]},
    )
    return created


def populate_room_questions(
    db: Session,
    room_id: str,
    *,
    question_set_id: Optional[str] = None,
    custom_questions: Optional[List[Dict[str, Any]]] = None,
    default_job_id: Optional[str] = None,
    limit: int = 5,
) -> List[RoomQuestion]:
    """Populate initial RoomQuestion rows from a question set, custom list, or default catalog."""
    room_questions: List[RoomQuestion] = []

    if question_set_id:
        qset = db.query(QuestionSet).filter(QuestionSet.id == question_set_id).first()
        if qset and qset.items:
            for item in qset.items:
                rq = RoomQuestion(
                    id=f"rq_{uuid.uuid4().hex[:12]}",
                    room_id=room_id,
                    source_question_id=item.source_question_id,
                    question_text=item.question_text,
                    domain=item.domain,
                    difficulty=item.difficulty,
                    target_skills_json=item.target_skills_json or [],
                    ideal_criteria_json=item.ideal_criteria_json or [],
                    ordinal=item.ordinal,
                    status="pending",
                    time_limit_seconds=180,
                )
                db.add(rq)
                room_questions.append(rq)
            return room_questions

    if custom_questions:
        for idx, cq in enumerate(custom_questions, start=1):
            text = (cq.get("question_text") or cq.get("text") or "").strip()
            if text:
                rq = RoomQuestion(
                    id=f"rq_{uuid.uuid4().hex[:12]}",
                    room_id=room_id,
                    source_question_id=cq.get("source_question_id") or cq.get("question_id"),
                    question_text=text,
                    domain=(cq.get("domain") or "General").strip(),
                    difficulty=(cq.get("difficulty") or "Intermediate").strip(),
                    target_skills_json=cq.get("target_skills") or [],
                    ideal_criteria_json=cq.get("ideal_criteria") or [],
                    ordinal=idx,
                    status="pending",
                    time_limit_seconds=int(cq.get("time_limit_seconds") or 180),
                )
                db.add(rq)
                room_questions.append(rq)
        if room_questions:
            return room_questions

    # Fallback to catalog questions for the job/domain
    query = db.query(Question)
    if default_job_id:
        job = db.query(Job).filter(Job.id == default_job_id).first()
        if job and job.domain:
            query = query.filter(Question.domain.ilike(f"%{job.domain}%"))
    catalog_qs = query.limit(limit).all()
    if not catalog_qs:
        catalog_qs = db.query(Question).limit(limit).all()

    for idx, cq in enumerate(catalog_qs, start=1):
        q_text = getattr(cq, "question", getattr(cq, "question_text", getattr(cq, "text", "")))
        skills = cq.skills if isinstance(cq.skills, list) else ([cq.skills] if cq.skills else [])
        criteria = [cq.ideal_answer_summary] if getattr(cq, "ideal_answer_summary", None) else ([cq.answer] if getattr(cq, "answer", None) else [])
        diff = "Intermediate"
        if getattr(cq, "difficulty", None) is not None:
            if isinstance(cq.difficulty, int):
                diff = {1: "Easy", 2: "Intermediate", 3: "Advanced"}.get(cq.difficulty, str(cq.difficulty))
            else:
                diff = str(cq.difficulty)
        rq = RoomQuestion(
            id=f"rq_{uuid.uuid4().hex[:12]}",
            room_id=room_id,
            source_question_id=cq.id,
            question_text=q_text,
            domain=cq.domain or "General",
            difficulty=diff,
            target_skills_json=skills,
            ideal_criteria_json=criteria,
            ordinal=idx,
            status="pending",
            time_limit_seconds=int(getattr(cq, "est_seconds", 180) or 180),
        )
        db.add(rq)
        room_questions.append(rq)

    return room_questions


def serialize_question_set(qset: QuestionSet, include_items: bool = True) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": qset.id,
        "name": qset.name,
        "description": qset.description,
        "source_filename": qset.source_filename,
        "schema_version": qset.schema_version,
        "version": qset.version,
        "status": qset.status,
        "checksum": qset.checksum,
        "created_at": qset.created_at.isoformat() if qset.created_at else None,
        "item_count": len(qset.items) if qset.items else 0,
    }
    if include_items:
        out["items"] = [
            {
                "id": it.id,
                "source_question_id": it.source_question_id,
                "question_text": it.question_text,
                "domain": it.domain,
                "difficulty": it.difficulty,
                "target_skills": it.target_skills_json,
                "ideal_criteria": it.ideal_criteria_json,
                "ordinal": it.ordinal,
                "metadata": it.metadata_json,
            }
            for it in (qset.items or [])
        ]
    return out
