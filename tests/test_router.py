"""
Router-level tests for PLUTO vProctor interview mode (Part 4 + Part 5 wiring).

Drives the JSON API end-to-end with Starlette's TestClient over a minimal app
that mounts ONLY the interview router (so we don't pull in the heavy assistant
brain). Verifies: session lifecycle, the answer-key never leaks to the client,
Tier-1 drives adaptation, the report + PDF endpoints, and consent-revoking delete.

Tier-2 refine (which would call Ollama) is stubbed to a no-op so the suite is
hermetic and fast. CPU-only, no network. Exit 0 = pass, 1 = fail.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from starlette.testclient import TestClient

import core.interview.router as router_mod

# Stub Tier-2 so no background task ever reaches Ollama during tests.
router_mod._tier2_refine = lambda *a, **k: None

app = FastAPI()
app.include_router(router_mod.router)
client = TestClient(app)

# Fields that would reveal the answer key — must NEVER appear in any question
# object sent to the client.
ANSWER_KEY_FIELDS = ("ideal_answer_points", "keywords", "scoring_rubric",
                     "red_flags", "irt", "expected_star")

_fail = [0]


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        _fail[0] += 1
    print(f"  [{tag}] {name}" + (f" - {extra}" if extra else ""))
    return cond


def _assert_no_key(q):
    return not any(f in q for f in ANSWER_KEY_FIELDS)

def test_full_flow():
    print("\n[router] start -> next -> answer x3 -> report -> pdf -> delete")

    # questions listing must not leak the answer key
    r = client.get("/interview/questions", params={"limit": 5})
    check("GET /questions 200", r.status_code == 200, str(r.status_code))
    qs = r.json().get("questions", [])
    check("questions listed", len(qs) > 0)
    check("no answer-key in /questions", all(_assert_no_key(q) for q in qs))

    # start a session with explicit profile fields
    r = client.post("/interview/start", json={
        "skills": ["python", "sql"], "target_role": "backend",
        "seniority": "mid", "limit": 6,
        "consent": {"audio": True, "store_transcript": True},
    })
    check("POST /start 200", r.status_code == 200, r.text[:120])
    sid = r.json().get("session_id")
    check("session_id returned", bool(sid))
    check("pool built", r.json().get("pool_size", 0) > 0)

    answered = 0
    texts = ["Use a covering index and cache hot reads; shard if write-heavy.",
             "um, I don't know", "I paired with the reviewer and added regression tests."]
    for i in range(3):
        r = client.get("/interview/next", params={"session_id": sid})
        check(f"GET /next 200 (#{i+1})", r.status_code == 200, r.text[:120])
        body = r.json()
        if body.get("done"):
            break
        q = body["question"]
        check(f"served question has no answer-key (#{i+1})", _assert_no_key(q))
        r = client.post("/interview/answer", json={
            "session_id": sid, "question_id": q["id"],
            "transcript": texts[i % len(texts)],
            "delivery": {"face_present_ratio": 0.9, "centered_ratio": 0.8, "mean_motion": 0.02},
        })
        check(f"POST /answer 200 (#{i+1})", r.status_code == 200, r.text[:160])
        j = r.json()
        check(f"answer has tier1 content_score (#{i+1})", "content_score" in j.get("tier1", {}))
        check(f"answer has adaptation trace (#{i+1})", "adaptation" in j)
        answered += 1
    check("answered at least 3", answered >= 3, str(answered))

    # history
    r = client.get("/interview/history", params={"session_id": sid})
    check("GET /history 200", r.status_code == 200)
    check("history lists answers", len(r.json().get("answers", [])) == answered)

    # JSON report
    r = client.get("/interview/report", params={"session_id": sid})
    check("GET /report 200", r.status_code == 200, r.text[:120])
    rep = r.json()
    for k in ("competence", "content_breakdown", "delivery_observations",
              "recommendations", "disclaimer"):
        check(f"report has {k}", k in rep)
    check("report competence has Elo", "overall_ability_elo" in rep["competence"])

    # PDF report
    r = client.get("/interview/report.pdf", params={"session_id": sid})
    check("GET /report.pdf 200", r.status_code == 200, str(r.status_code))
    check("report.pdf is application/pdf", r.headers.get("content-type", "").startswith("application/pdf"),
          r.headers.get("content-type"))
    check("report.pdf has PDF header", r.content[:5] == b"%PDF-")

    # delete (consent revocation)
    r = client.delete(f"/interview/session/{sid}")
    check("DELETE /session 200", r.status_code == 200)
    check("delete confirmed", r.json().get("deleted") is True)
    r = client.get("/interview/report", params={"session_id": sid})
    check("report after delete is 404", r.status_code == 404, str(r.status_code))


def test_unknown_session():
    print("\n[router] unknown session handling")
    r = client.get("/interview/next", params={"session_id": "does-not-exist"})
    check("unknown session -> 404", r.status_code == 404, str(r.status_code))


def main():
    test_full_flow()
    test_unknown_session()
    if _fail[0]:
        print(f"\n{_fail[0]} FAILURE(S).")
        return 1
    print("\nOK - interview router valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
