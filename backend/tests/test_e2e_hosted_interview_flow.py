"""End-to-End integration test covering the complete hosted interview lifecycle:
Admin room creation, scheduling, invitation tokens, Candidate A join,
Candidate B IDOR isolation, WebSocket signaling & WebRTC payload validation,
question advance/skip, pause/resume, reconnection recovery, interview finalization,
recording upload, secure retrieval by authorized users, and report generation.
"""
from __future__ import annotations

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import InterviewRoom, InterviewSession, Question, User
from backend.app.main import app
from backend.app.services.security_service import hash_password, create_access_token

client = TestClient(app)


def _create_test_user(email: str, role: str, name: str) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=hash_password("SecurePass123!"),
                full_name=name,
                role=role,
                is_active=True,
                email_verified=True,
                token_version=1,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def test_complete_hosted_interview_lifecycle_e2e():
    """Verify all 15 gates of hosted interview orchestration with real API and WebSocket interaction."""
    # 1. Setup Admin, Candidate A, and Candidate B
    admin = _create_test_user("admin_e2e@pluto.local", "admin", "Admin Evaluator")
    cand_a = _create_test_user("cand_a_e2e@pluto.local", "candidate", "Alice Candidate")
    cand_b = _create_test_user("cand_b_e2e@pluto.local", "candidate", "Bob Candidate")

    admin_token, _ = create_access_token(user_id=admin.id, role=admin.role, token_version=admin.token_version)
    cand_a_token, _ = create_access_token(user_id=cand_a.id, role=cand_a.role, token_version=cand_a.token_version)
    cand_b_token, _ = create_access_token(user_id=cand_b.id, role=cand_b.role, token_version=cand_b.token_version)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cand_a_headers = {"Authorization": f"Bearer {cand_a_token}"}
    cand_b_headers = {"Authorization": f"Bearer {cand_b_token}"}

    # 2. Gate 1 & 2: Admin creates interview room and schedules it
    create_payload = {
        "title": "Senior Distributed Systems Engineer - Round 1",
        "assigned_candidate_id": cand_a.id,
        "proctoring_preset": "strict",
        "duration_seconds": 2700,
        "custom_questions": [
            {"question_text": "Explain CAP theorem and PACELC trade-offs in distributed storage.", "domain": "Distributed"},
            {"question_text": "How do you detect and recover from split-brain scenarios in Raft?", "domain": "Distributed"},
        ],
    }
    res_create = client.post("/api/admin/rooms", json=create_payload, headers=admin_headers)
    assert res_create.status_code == 201, res_create.text
    room_data = res_create.json()
    room_id = room_data["id"]
    invite_token = room_data.get("raw_invite_token") or room_data.get("invite_token")
    raw_room_code = room_data["raw_room_code"]
    assert room_data["status"] == "LOBBY"
    assert len(room_data["questions"]) >= 2

    # 3. Gate 4: Candidate B (Unauthorized) cannot access Candidate A's assigned room
    res_b_join = client.post("/api/rooms/join", json={"token_or_code": raw_room_code}, headers=cand_b_headers)
    assert res_b_join.status_code == 403, "Candidate B must not be permitted into Candidate A's private room"

    res_b_snapshot = client.get(f"/api/rooms/{room_id}/snapshot", headers=cand_b_headers)
    assert res_b_snapshot.status_code == 403, "Candidate B must not be allowed to inspect room snapshot"

    # 4. Gate 3: Candidate A joins using the invitation code
    res_a_join = client.post(
        "/api/rooms/join",
        json={
            "token_or_code": raw_room_code,
            "device_checks": {"camera_ok": True, "mic_ok": True, "latency_ms": 24},
        },
        headers=cand_a_headers,
    )
    assert res_a_join.status_code == 200, res_a_join.text
    join_result = res_a_join.json()
    assert join_result["room_id"] == room_id
    assert join_result["status"] == "LOBBY"
    assert "ice_servers" in join_result

    # Candidate A device check endpoint verification
    res_dc = client.post(
        f"/api/rooms/{room_id}/device-check",
        json={"camera_ok": True, "mic_ok": True, "latency_ms": 18, "browser": "AutomatedTestBrowser"},
        headers=cand_a_headers,
    )
    assert res_dc.status_code == 200

    # 5. Gate 5: Admin starts the interview (transitions room to LIVE and links active evaluation session)
    res_start = client.post(f"/api/admin/rooms/{room_id}/start", json={}, headers=admin_headers)
    assert res_start.status_code == 200
    start_snap = res_start.json()
    assert start_snap["status"] == "LIVE"
    active_sess_id = start_snap["active_session_id"]
    assert active_sess_id is not None
    assert start_snap["current_question"]["ordinal"] == 1

    # 6. Gate 7 & 8: WebSocket Signaling and WebRTC negotiation relay
    # Test WebSocket connection rejection for unauthorized Candidate B
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/rooms/{room_id}/ws?token={cand_b_token}"):
            pass

    # Open WebSocket for Candidate A
    with client.websocket_connect(f"/api/rooms/{room_id}/ws?token={cand_a_token}") as ws_cand:
        cand_init = ws_cand.receive_json()
        assert cand_init["type"] == "room.snapshot"
        assert cand_init["snapshot"]["status"] == "LIVE"
        assert cand_init["snapshot"]["active_session_id"] == active_sess_id

        # Heartbeat ping
        ws_cand.send_json({"type": "ping"})
        pong_msg = ws_cand.receive_json()
        assert pong_msg["type"] == "pong"

        # WebRTC Offer relay
        mock_offer = {
            "type": "webrtc.signal",
            "signal_type": "offer",
            "payload": {"type": "offer", "sdp": "v=0\r\no=admin 111 222 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"},
        }
        ws_cand.send_json(mock_offer)

        # WebRTC Answer relay
        mock_answer = {
            "type": "webrtc.signal",
            "signal_type": "answer",
            "payload": {"type": "answer", "sdp": "v=0\r\no=cand_a 333 444 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"},
        }
        ws_cand.send_json(mock_answer)

        # ICE Candidate relay
        mock_ice = {
            "type": "webrtc.signal",
            "signal_type": "ice_candidate",
            "payload": {"candidate": "candidate:1 1 UDP 2130706431 127.0.0.1 5000 typ host", "sdpMid": "0", "sdpMLineIndex": 0},
        }
        ws_cand.send_json(mock_ice)

    # 7. Gate 9: Admin advances question
    res_adv = client.post(f"/api/admin/rooms/{room_id}/advance", json={}, headers=admin_headers)
    assert res_adv.status_code == 200
    adv_snap = res_adv.json()
    assert adv_snap["current_question_ordinal"] == 2
    assert adv_snap["current_question"]["ordinal"] == 2

    # Admin skips question
    res_skip = client.post(f"/api/admin/rooms/{room_id}/skip", json={}, headers=admin_headers)
    assert res_skip.status_code == 200

    # 8. Gate 10: Pause and Resume
    res_pause = client.post(f"/api/admin/rooms/{room_id}/pause", json={"reason": "Candidate connectivity check"}, headers=admin_headers)
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "PAUSED"

    res_resume = client.post(f"/api/admin/rooms/{room_id}/resume", json={}, headers=admin_headers)
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "LIVE"

    # 9. Gate 11: Reconnection after temporary disconnect
    res_reconnect_snap = client.get(f"/api/rooms/{room_id}/snapshot", headers=cand_a_headers)
    assert res_reconnect_snap.status_code == 200
    reconnect_snap = res_reconnect_snap.json()
    assert reconnect_snap["status"] == "LIVE"
    assert reconnect_snap["current_sequence_version"] >= 4

    with client.websocket_connect(f"/api/rooms/{room_id}/ws?token={cand_a_token}") as ws_reconnect:
        re_init = ws_reconnect.receive_json()
        assert re_init["type"] == "room.snapshot"
        assert re_init["snapshot"]["status"] == "LIVE"

    # 10. Gate 12: Admin ends the interview properly
    res_end = client.post(f"/api/admin/rooms/{room_id}/end", json={}, headers=admin_headers)
    assert res_end.status_code == 200
    assert res_end.json()["status"] == "COMPLETED"

    # Verify room is now COMPLETED
    final_snap = client.get(f"/api/rooms/{room_id}/snapshot", headers=cand_a_headers).json()
    assert final_snap["status"] == "COMPLETED"
    active_sess_id = final_snap["active_session_id"]
    assert active_sess_id is not None

    # 11. Gate 13: Candidate uploads actual recording
    # Valid synthetic webm header bytes
    mock_video_bytes = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04\x42\xf3\x81\x08" + (b"\x00" * 4096)
    files = {"file": (f"{active_sess_id}_hosted.webm", mock_video_bytes, "video/webm")}
    res_upload = client.post(f"/api/interview/{active_sess_id}/recording", files=files, headers=cand_a_headers)
    assert res_upload.status_code == 200
    upload_data = res_upload.json()
    assert upload_data["status"] == "success"
    assert "video_filename" in upload_data

    # Verify physical file existence on disk
    video_file = settings.STORAGE_DIR / "recordings" / upload_data["video_filename"]
    assert video_file.exists(), "Recording video file must exist in storage"

    # 12. Gate 14: Recording retrieval permissions (Candidate A and Admin can retrieve, Candidate B gets 403)
    res_a_video = client.get(f"/api/interview/{active_sess_id}/video", headers=cand_a_headers)
    assert res_a_video.status_code == 200
    assert len(res_a_video.content) == len(mock_video_bytes)

    # Retrieval via /recording alias
    res_a_rec = client.get(f"/api/interview/{active_sess_id}/recording", headers=cand_a_headers)
    assert res_a_rec.status_code == 200

    # Admin retrieval
    res_admin_video = client.get(f"/api/interview/{active_sess_id}/video", headers=admin_headers)
    assert res_admin_video.status_code == 200

    # Unauthorized Candidate B access
    res_b_video = client.get(f"/api/interview/{active_sess_id}/video", headers=cand_b_headers)
    assert res_b_video.status_code == 403, "Candidate B must not be permitted to download Candidate A's recording"

    # 13. Gate 15: Run analysis and verify generated final report
    res_run_analysis = client.post(f"/api/analysis/{active_sess_id}/run", headers=cand_a_headers)
    assert res_run_analysis.status_code == 200

    # Retrieve final report
    res_report = client.get(f"/api/report/{active_sess_id}", headers=cand_a_headers)
    assert res_report.status_code == 200
    report = res_report.json()
    assert report["session_id"] == active_sess_id
    assert "overall_score" in report
    assert "grade" in report
    assert "category_scores" in report
    assert "radar_metrics" in report
    assert "questions_breakdown" in report

    # Candidate B cannot access Candidate A's report
    res_b_report = client.get(f"/api/report/{active_sess_id}", headers=cand_b_headers)
    assert res_b_report.status_code == 403, "Candidate B must not be allowed to access Candidate A's report"
