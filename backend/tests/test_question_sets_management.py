"""End-to-end integration tests for Admin Question-Set Management (Batch 2)."""
from __future__ import annotations

import io
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import AuditLog, InterviewRoom, QuestionSet, QuestionSetItem, RoomQuestion, User
from backend.app.main import app
from backend.app.services.security_service import hash_password, reset_rate_limits


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


def _create_user(role: str = "candidate", prefix: str = "user") -> tuple[dict, str]:
    db = SessionLocal()
    uid = f"usr_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "StrongPassword!123"
    try:
        user = User(
            id=uid,
            email=email,
            password_hash=hash_password(pwd),
            full_name=f"{prefix.title()} FullName",
            role=role,
            is_active=True,
            email_verified=True,
            token_version=0,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as login_client:
        ep = "/api/auth/admin/login" if role in ("admin", "super_admin") else "/api/auth/login"
        resp = login_client.post(ep, json={"email": email, "password": pwd})
        assert resp.status_code == 200, resp.text
        return resp.json()["user"], resp.json()["access_token"]


def test_question_set_response_shape_and_empty_list(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "empty_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Initially, new admin has no question sets -> returns empty list directly
    res = client.get("/api/admin/question-sets", headers=h_admin)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_question_set_create_edit_get_delete_lifecycle(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "crud_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create question set
    create_payload = {
        "name": "Distributed Systems Core",
        "description": "Questions on consensus and partitioning.",
        "items": [
            {
                "question_text": "Explain the Raft leader election algorithm.",
                "domain": "Distributed Systems",
                "difficulty": "Advanced",
                "target_skills": ["Raft", "Consensus"],
                "ideal_criteria": ["Term numbers", "Heartbeats", "Split brain prevention"],
                "time_limit_seconds": 180,
            },
            {
                "question_text": "How does vector clock ordering prevent write divergence?",
                "domain": "Distributed Systems",
                "difficulty": "Intermediate",
                "target_skills": ["Vector Clocks"],
                "ideal_criteria": ["Causal history", "Concurrent branches"],
                "time_limit_seconds": 180,
            },
        ],
    }
    create_resp = client.post("/api/admin/question-sets", headers=h_admin, json=create_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    qset_id = created["id"]
    assert created["name"] == "Distributed Systems Core"
    assert created["item_count"] == 2
    assert created["version"] == 1
    assert created["checksum"] is not None

    # 2. Get specific question set with full items
    get_resp = client.get(f"/api/admin/question-sets/{qset_id}", headers=h_admin)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert len(get_data["items"]) == 2
    assert get_data["items"][0]["ordinal"] == 1
    assert "Raft" in get_data["items"][0]["target_skills"]

    # 3. Edit / Update question set (rename and change items)
    update_payload = {
        "name": "Distributed Systems Specialization v2",
        "description": "Updated questions including Paxos.",
        "items": [
            {
                "question_text": "Explain Multi-Paxos phases and proposer leases.",
                "domain": "Distributed Systems",
                "difficulty": "Advanced",
                "target_skills": ["Paxos", "Consensus"],
                "ideal_criteria": ["Phase 1 Prepare", "Phase 2 Accept"],
                "time_limit_seconds": 240,
            }
        ],
    }
    put_resp = client.put(f"/api/admin/question-sets/{qset_id}", headers=h_admin, json=update_payload)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["name"] == "Distributed Systems Specialization v2"
    assert put_data["version"] == 2
    assert put_data["item_count"] == 1
    assert put_data["items"][0]["question_text"] == "Explain Multi-Paxos phases and proposer leases."

    # 4. Delete question set
    del_resp = client.delete(f"/api/admin/question-sets/{qset_id}", headers=h_admin)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # 5. Confirm deletion (404)
    get_del = client.get(f"/api/admin/question-sets/{qset_id}", headers=h_admin)
    assert get_del.status_code == 404


def test_question_set_json_import_payload_and_dry_run(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "import_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    import_data = {
        "name": "Microservices Architecture",
        "description": "Imported from engineering playbook.",
        "source_filename": "microservices.json",
        "items": [
            {
                "question_text": "What are the trade-offs of the Saga pattern vs 2PC?",
                "domain": "Microservices",
                "difficulty": "Advanced",
                "target_skills": ["Saga", "Transactions"],
            },
            {
                "question_text": "How do you mitigate cascading failures using Circuit Breakers?",
                "domain": "Reliability",
                "difficulty": "Intermediate",
                "target_skills": ["Circuit Breaker", "Resilience"],
            },
        ],
    }

    # Dry-run preview
    preview_resp = client.post("/api/admin/question-sets/import?dry_run=true", headers=h_admin, json=import_data)
    assert preview_resp.status_code == 200
    pdata = preview_resp.json()
    assert pdata["status"] == "valid"
    assert pdata["item_count"] == 2
    assert len(pdata["preview_items"]) == 2

    # Commit import
    commit_resp = client.post("/api/admin/question-sets/import", headers=h_admin, json=import_data)
    assert commit_resp.status_code == 201
    cdata = commit_resp.json()
    assert cdata["name"] == "Microservices Architecture"
    assert cdata["item_count"] == 2


def test_question_set_file_import_multipart(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "file_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    file_content = json.dumps({
        "name": "Frontend Architecture Assessment",
        "description": "Questions on React rendering cycles and Web Workers.",
        "items": [
            {
                "question_text": "How does React 19 reconciliation handle transitions and suspense?",
                "domain": "Frontend",
                "difficulty": "Intermediate",
                "target_skills": ["React", "Performance"],
            }
        ]
    }).encode("utf-8")

    # File upload import
    files = {"file": ("frontend_arch.json", io.BytesIO(file_content), "application/json")}
    resp = client.post("/api/admin/question-sets/import-file", headers=h_admin, files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Frontend Architecture Assessment"
    assert data["item_count"] == 1


def test_question_set_validation_rejections(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "val_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Name too short
    r1 = client.post("/api/admin/question-sets", headers=h_admin, json={"name": "ab", "items": [{"question_text": "Valid text?"}]})
    assert r1.status_code == 422

    # 2. Empty items
    r2 = client.post("/api/admin/question-sets", headers=h_admin, json={"name": "Valid Name", "items": []})
    assert r2.status_code == 422

    # 3. Question text too short
    r3 = client.post("/api/admin/question-sets", headers=h_admin, json={"name": "Valid Name", "items": [{"question_text": "No"}]})
    assert r3.status_code == 422

    # 4. Malformed JSON file upload
    bad_file = {"file": ("bad.json", io.BytesIO(b"{ malformed: json"), "application/json")}
    r4 = client.post("/api/admin/question-sets/import-file", headers=h_admin, files=bad_file)
    assert r4.status_code == 422
    assert "malformed_json" in r4.text

    # 5. Non-json file upload
    bad_ext = {"file": ("doc.txt", io.BytesIO(b"Hello world"), "text/plain")}
    r5 = client.post("/api/admin/question-sets/import-file", headers=h_admin, files=bad_ext)
    assert r5.status_code == 422
    assert "invalid_file_type" in r5.text


def test_candidate_unauthorized_operations(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    cand_user, cand_token = _create_user("candidate", "cand_blocked")
    h_cand = {"Authorization": f"Bearer {cand_token}"}

    # Candidates are blocked from all question-set management endpoints (403 Forbidden)
    assert client.get("/api/admin/question-sets", headers=h_cand).status_code == 403
    assert client.post("/api/admin/question-sets", headers=h_cand, json={"name": "Test", "items": []}).status_code == 403
    assert client.put("/api/admin/question-sets/qset_123", headers=h_cand, json={"name": "Test"}).status_code == 403
    assert client.delete("/api/admin/question-sets/qset_123", headers=h_cand).status_code == 403
    assert client.post("/api/admin/question-sets/import", headers=h_cand, json={}).status_code == 403


def test_admin_idor_isolation(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_a, token_a = _create_user("admin", "admin_alice")
    admin_b, token_b = _create_user("admin", "admin_bob")

    h_a = {"Authorization": f"Bearer {token_a}"}
    h_b = {"Authorization": f"Bearer {token_b}"}

    # Admin A creates a question set
    create_resp = client.post(
        "/api/admin/question-sets",
        headers=h_a,
        json={"name": "Alice Private Set", "items": [{"question_text": "What is thread-safe memory management?"}]},
    )
    assert create_resp.status_code == 201
    qset_id = create_resp.json()["id"]

    # Admin B cannot view Alice's set details directly (403 Forbidden)
    assert client.get(f"/api/admin/question-sets/{qset_id}", headers=h_b).status_code == 403

    # Admin B cannot update Alice's set (403 Forbidden)
    assert client.put(f"/api/admin/question-sets/{qset_id}", headers=h_b, json={"name": "Hacked"}).status_code == 403

    # Admin B cannot delete Alice's set (403 Forbidden)
    assert client.delete(f"/api/admin/question-sets/{qset_id}", headers=h_b).status_code == 403


def test_preserves_historical_rooms_and_blocks_active_rooms(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "room_link_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a question set
    qset_resp = client.post(
        "/api/admin/question-sets",
        headers=h_admin,
        json={"name": "Interview Track Set", "items": [{"question_text": "Explain database normalization forms."}]},
    )
    assert qset_resp.status_code == 201
    qset_id = qset_resp.json()["id"]

    # 2. Create an active room referencing this question set
    room_resp = client.post(
        "/api/admin/rooms",
        headers=h_admin,
        json={
            "title": "Active Room With QSet",
            "question_set_id": qset_id,
            "duration_seconds": 1800,
            "proctoring_preset": "strict",
        },
    )
    assert room_resp.status_code == 201
    room_id = room_resp.json()["id"]

    # 3. Attempting to delete the question set while the room is in LOBBY/LIVE fails with 409 Conflict
    del_conflict = client.delete(f"/api/admin/question-sets/{qset_id}", headers=h_admin)
    assert del_conflict.status_code == 409
    assert "question_set_in_use" in del_conflict.text

    # 4. Mark room as COMPLETED
    db = SessionLocal()
    try:
        room = db.query(InterviewRoom).filter(InterviewRoom.id == room_id).first()
        room.status = "COMPLETED"
        db.commit()
    finally:
        db.close()

    # 5. Now delete should succeed (200 OK)
    del_ok = client.delete(f"/api/admin/question-sets/{qset_id}", headers=h_admin)
    assert del_ok.status_code == 200

    # 6. Verify the historical room and its populated RoomQuestions are NOT deleted
    db = SessionLocal()
    try:
        hist_room = db.query(InterviewRoom).filter(InterviewRoom.id == room_id).first()
        assert hist_room is not None
        assert hist_room.status == "COMPLETED"
        assert hist_room.question_set_id is None  # Safely nullified

        # RoomQuestion copied rows remain intact
        rqs = db.query(RoomQuestion).filter(RoomQuestion.room_id == room_id).all()
        assert len(rqs) == 1
        assert rqs[0].question_text == "Explain database normalization forms."
    finally:
        db.close()

