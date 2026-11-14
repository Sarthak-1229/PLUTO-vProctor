"""Comprehensive automated test suite for Phase 3: Hosted Rooms, WebRTC P2P Signaling, and Live Media."""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import InterviewRoom, InterviewSession, QuestionSet, RoomEvent, RoomParticipant, RoomQuestion, User
from backend.app.main import app
from backend.app.services.realtime.transport_adapter import P2PMediaTransportAdapter, SFUMediaTransportAdapter
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

    # Login to get valid JWT
    with TestClient(app) as login_client:
        ep = "/api/auth/admin/login" if role in ("admin", "super_admin") else "/api/auth/login"
        resp = login_client.post(ep, json={"email": email, "password": pwd})
        assert resp.status_code == 200, resp.text
        return resp.json()["user"], resp.json()["access_token"]


def test_question_set_crud_validation_and_rbac(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "qset_admin")
    cand_user, cand_token = _create_user("candidate", "qset_cand")

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_cand = {"Authorization": f"Bearer {cand_token}"}

    # Candidate blocked from managing question sets
    bad_create = client.post(
        "/api/admin/question-sets",
        headers=h_cand,
        json={"name": "Candidate Set", "items": [{"question_text": "How does DNS work?"}]},
    )
    assert bad_create.status_code == 403

    # Admin validation failure on empty items
    empty_items = client.post(
        "/api/admin/question-sets",
        headers=h_admin,
        json={"name": "Empty Set", "items": []},
    )
    assert empty_items.status_code == 422

    # Admin successfully creates question set
    create_resp = client.post(
        "/api/admin/question-sets",
        headers=h_admin,
        json={
            "name": "Backend Engineering Core",
            "description": "Distributed systems, Python, and DB indexing",
            "items": [
                {
                    "question_text": "Explain the difference between optimistic and pessimistic locking in databases.",
                    "domain": "Databases",
                    "difficulty": "Intermediate",
                    "target_skills": ["SQL", "Databases", "Concurrency"],
                    "ideal_criteria": ["Mentions isolation levels", "Explains performance tradeoffs"],
                    "time_limit_seconds": 180,
                },
                {
                    "question_text": "How do you design a thread-safe sliding window rate limiter in memory?",
                    "domain": "System Design",
                    "difficulty": "Hard",
                    "target_skills": ["Algorithms", "Concurrency"],
                    "ideal_criteria": ["Mentions locks/semaphores", "Explains queue eviction"],
                    "time_limit_seconds": 240,
                },
            ],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    qset_data = create_resp.json()
    qset_id = qset_data["id"]
    assert qset_data["name"] == "Backend Engineering Core"
    assert qset_data["item_count"] == 2
    assert qset_data["checksum"] is not None

    # List question sets
    list_resp = client.get("/api/admin/question-sets", headers=h_admin)
    assert list_resp.status_code == 200
    assert any(s["id"] == qset_id for s in list_resp.json())

    # Get specific question set
    get_resp = client.get(f"/api/admin/question-sets/{qset_id}", headers=h_admin)
    assert get_resp.status_code == 200
    assert len(get_resp.json()["items"]) == 2
    assert get_resp.json()["items"][0]["ordinal"] == 1


def test_admin_room_creation_and_candidate_idor_access(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "room_admin")
    cand_alice, token_alice = _create_user("candidate", "alice")
    cand_bob, token_bob = _create_user("candidate", "bob")

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_alice = {"Authorization": f"Bearer {token_alice}"}
    h_bob = {"Authorization": f"Bearer {token_bob}"}

    # 1. Admin creates a room specifically assigned to Alice
    create_room_resp = client.post(
        "/api/admin/rooms",
        headers=h_admin,
        json={
            "title": "Alice Technical Assessment",
            "assigned_candidate_id": cand_alice["id"],
            "duration_seconds": 1800,
            "proctoring_preset": "strict",
            "custom_questions": [
                {"question_text": "What is the CAP theorem?", "domain": "Distributed Systems"},
                {"question_text": "Explain how hash maps handle collisions.", "domain": "Data Structures"},
            ],
        },
    )
    assert create_room_resp.status_code == 201, create_room_resp.text
    room_data = create_room_resp.json()
    room_id = room_data["id"]
    room_code = room_data["raw_room_code"]
    invite_token = room_data["raw_invite_token"]

    assert room_data["status"] == "LOBBY"
    assert len(room_data["questions"]) == 2
    assert room_code.startswith("PLUTO-")

    # 2. Candidate Bob tries to join Alice's designated room via room code -> 403 Forbidden
    bob_join = client.post(
        "/api/rooms/join",
        headers=h_bob,
        json={"token_or_code": room_code},
    )
    assert bob_join.status_code == 403
    assert "another registered candidate" in bob_join.text

    # 3. Candidate Alice joins with room code -> 200 OK and admitted to waiting room
    alice_join = client.post(
        "/api/rooms/join",
        headers=h_alice,
        json={
            "token_or_code": room_code,
            "device_checks": {"camera_ok": True, "mic_ok": True, "latency_ms": 32.5},
        },
    )
    assert alice_join.status_code == 200, alice_join.text
    alice_snap = alice_join.json()
    assert alice_snap["room_id"] == room_id
    assert alice_snap["participant_status"] in ("waiting_room", "admitted")
    assert "ice_servers" in alice_snap
    assert len(alice_snap["ice_servers"]) >= 1

    # Candidate Alice snapshot: pending questions do NOT leak question text
    snap_resp = client.get(f"/api/rooms/{room_id}/snapshot", headers=h_alice)
    assert snap_resp.status_code == 200
    for q in snap_resp.json()["questions"]:
        if q["status"] == "pending":
            assert "question_text" not in q

    # Candidate Bob cannot fetch snapshot of Alice's room -> 403
    assert client.get(f"/api/rooms/{room_id}/snapshot", headers=h_bob).status_code == 403


def test_room_state_machine_and_question_progression(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "fsm_admin")
    cand_user, cand_token = _create_user("candidate", "fsm_cand")

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_cand = {"Authorization": f"Bearer {cand_token}"}

    # 1. Create room with 3 questions
    c_resp = client.post(
        "/api/admin/rooms",
        headers=h_admin,
        json={
            "title": "State Machine Interview",
            "assigned_candidate_id": cand_user["id"],
            "custom_questions": [
                {"question_text": "Question 1: Explain ACID properties.", "domain": "DB"},
                {"question_text": "Question 2: Explain Raft consensus.", "domain": "Distributed"},
                {"question_text": "Question 3: How does TLS 1.3 handshake work?", "domain": "Security"},
            ],
        },
    )
    assert c_resp.status_code == 201
    room_id = c_resp.json()["id"]

    # Candidate joins waiting room
    client.post("/api/rooms/join", headers=h_cand, json={"token_or_code": c_resp.json()["raw_room_code"]})

    # 2. Reorder pending questions 2 and 3 before starting
    initial_qs = c_resp.json()["questions"]
    q1_id, q2_id, q3_id = initial_qs[0]["id"], initial_qs[1]["id"], initial_qs[2]["id"]

    reorder_resp = client.post(
        f"/api/admin/rooms/{room_id}/reorder",
        headers=h_admin,
        json={"ordered_question_ids": [q1_id, q3_id, q2_id]},
    )
    assert reorder_resp.status_code == 200

    # 3. Admin starts room (LOBBY -> LIVE)
    start_resp = client.post(f"/api/admin/rooms/{room_id}/start", headers=h_admin)
    assert start_resp.status_code == 200
    snap = start_resp.json()
    assert snap["status"] == "LIVE"
    assert snap["current_question"]["ordinal"] == 1
    assert "ACID" in snap["current_question"]["text"]

    # Attempting to reorder while Q1 is active and already ordered raises 400
    bad_reorder = client.post(
        f"/api/admin/rooms/{room_id}/reorder",
        headers=h_admin,
        json={"ordered_question_ids": [q1_id, q2_id, q3_id]},
    )
    assert bad_reorder.status_code == 400

    # 4. Pause and Resume
    pause_resp = client.post(f"/api/admin/rooms/{room_id}/pause", headers=h_admin, json={"reason": "Technical pause"})
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"

    resume_resp = client.post(f"/api/admin/rooms/{room_id}/resume", headers=h_admin)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "LIVE"

    # 5. Advance to next question (Q1 answered -> Q3 becomes active due to reorder)
    adv_resp = client.post(f"/api/admin/rooms/{room_id}/advance", headers=h_admin)
    assert adv_resp.status_code == 200
    assert adv_resp.json()["current_question"]["ordinal"] == 2
    assert "TLS 1.3" in adv_resp.json()["current_question"]["text"]

    # 6. Skip current question (Q3 skipped -> Q2 becomes active)
    skip_resp = client.post(f"/api/admin/rooms/{room_id}/skip", headers=h_admin)
    assert skip_resp.status_code == 200
    assert skip_resp.json()["current_question"]["ordinal"] == 3
    assert "Raft" in skip_resp.json()["current_question"]["text"]

    # 7. End interview (LIVE -> COMPLETED)
    end_resp = client.post(f"/api/admin/rooms/{room_id}/end", headers=h_admin)
    assert end_resp.status_code == 200
    assert end_resp.json()["status"] == "COMPLETED"

    # Verifying linked InterviewSession was created and transitioned to RECORDED
    db = SessionLocal()
    try:
        room_db = db.query(InterviewRoom).filter(InterviewRoom.id == room_id).first()
        assert room_db.active_session_id is not None
        sess = db.query(InterviewSession).filter(InterviewSession.id == room_db.active_session_id).first()
        assert sess is not None
        assert sess.interview_mode == "hosted"
        assert sess.interview_status == "RECORDED"

        # Verify audit log and events recorded sequence numbers
        events = db.query(RoomEvent).filter(RoomEvent.room_id == room_id).order_by(RoomEvent.sequence_no.asc()).all()
        assert len(events) >= 5
        event_types = [e.event_type for e in events]
        assert "room.created" in event_types
        assert "room.state_changed" in event_types
        assert "question.active" in event_types
        assert "question.skipped" in event_types
        assert "room.ended" in event_types
    finally:
        db.close()


def test_webrtc_signaling_and_media_transport_adapters(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "webrtc_admin")
    cand_user, cand_token = _create_user("candidate", "webrtc_cand")

    # 1. Test transport adapters
    p2p_adapter = P2PMediaTransportAdapter()
    assert p2p_adapter.get_transport_type() == "p2p"
    ice_servers = p2p_adapter.get_ice_servers()
    assert len(ice_servers) >= 1
    assert "urls" in ice_servers[0]

    sfu_adapter = SFUMediaTransportAdapter("https://sfu.example.com")
    assert sfu_adapter.get_transport_type() == "sfu"
    sfu_creds = sfu_adapter.generate_join_credentials(
        room_id="room_123", user_id="usr_123", user_name="Test", role="candidate"
    )
    assert sfu_creds["transport"] == "sfu"
    assert sfu_creds["sfu_url"] == "https://sfu.example.com"

    # 2. Test WebSocket connection authentication
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    create_room_resp = client.post(
        "/api/admin/rooms",
        headers=h_admin,
        json={"title": "WebSocket Signaling Room", "assigned_candidate_id": cand_user["id"]},
    )
    room_id = create_room_resp.json()["id"]

    # Missing token on WS handshake rejected
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/rooms/{room_id}/ws") as ws:
            pass

    # Invalid token rejected
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/rooms/{room_id}/ws?token=invalid.jwt.token") as ws:
            pass

    # Valid authenticated candidate connects and receives initial snapshot
    with client.websocket_connect(f"/api/rooms/{room_id}/ws?token={cand_token}") as ws_cand:
        initial_msg = ws_cand.receive_json()
        assert initial_msg["type"] == "room.snapshot"
        assert initial_msg["snapshot"]["room_id"] == room_id

        # Ping-pong heartbeat
        ws_cand.send_json({"type": "ping"})
        pong_msg = ws_cand.receive_json()
        assert pong_msg["type"] == "pong"

        # WebRTC signaling packet relay
        ws_cand.send_json({
            "type": "webrtc.signal",
            "signal_type": "offer",
            "payload": {"type": "offer", "sdp": "v=0\r\no=- 12345 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"},
        })

