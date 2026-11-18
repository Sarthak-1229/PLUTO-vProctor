#!/usr/bin/env python3
"""
PLUTO vProctor — Deployment Smoke & Live E2E Test
=================================================
Hits critical health, readiness, SPA routing, and (with --e2e) full candidate
authentication, resume screening, interview start, and report/PDF flows.

Usage (smoke only):
    PLUTO_BASE_URL=https://your-appsail.catalystappsail.in python scripts/smoke_test.py

Usage (full live E2E):
    PLUTO_BASE_URL=https://your-appsail.catalystappsail.in python scripts/smoke_test.py --e2e

Exit code 0 = all checks passed. Non-zero = at least one check failed.
"""

import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = os.environ.get("PLUTO_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "25"))

PASS = "[PASS]"
FAIL = "[FAIL]"


def check(label: str, url: str, expected_status: int = 200, json_key: str | None = None, expect_html: bool = False) -> bool:
    """Perform a single HTTP GET check and report result."""
    try:
        headers = {"Accept": "text/html" if expect_html else "application/json"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            if status != expected_status:
                print(f"  {FAIL}  {label} — expected HTTP {expected_status}, got {status}")
                return False
            if expect_html and "<div id=\"root\">" not in body:
                print(f"  {FAIL}  {label} — response did not contain SPA root mount")
                return False
            detail = ""
            if json_key:
                try:
                    data = json.loads(body)
                    detail = f" [{json_key}={data.get(json_key, '?')}]"
                    if "jobs_count" in data:
                        detail += f" [jobs={data['jobs_count']}, questions={data.get('questions_count', '?')}]"
                except Exception:
                    pass
            print(f"  {PASS}  {label}{detail}")
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == expected_status:
            print(f"  {PASS}  {label}")
            return True
        print(f"  {FAIL}  {label} — HTTP {exc.code}: {exc.reason}")
        return False
    except Exception as exc:
        print(f"  {FAIL}  {label} — {exc}")
        return False


def _encode_multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----PlutoSmoke{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, val in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(f"{val}\r\n".encode())
    for field_name, (filename, content, content_type) in files.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def run_e2e(base_url: str) -> list[bool]:
    """Run authenticated candidate register -> refresh -> login -> screen -> interview -> report/PDF."""
    results: list[bool] = []
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _req(method: str, path: str, *, json_body=None, raw_body: bytes | None = None, headers: dict | None = None):
        hdrs = dict(headers or {})
        data = raw_body
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(f"{base_url}{path}", data=data, method=method, headers=hdrs)
        try:
            with opener.open(req, timeout=TIMEOUT) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    print("\nEnd-to-End Authenticated Flow:")
    email = f"smoke_{uuid.uuid4().hex[:10]}@pluto.example"
    password = f"PlutoSmoke#{uuid.uuid4().hex[:8]}"

    # 1. Register
    st, body, _ = _req("POST", "/api/auth/register", json_body={"email": email, "password": password, "full_name": "Smoke Tester"})
    ok = st == 201
    print(f"  {PASS if ok else FAIL}  POST /api/auth/register -> HTTP {st}")
    results.append(ok)
    if not ok:
        print("    Response:", body.decode("utf-8", "replace")[:300])
        return results
    reg_data = json.loads(body.decode("utf-8"))
    token = reg_data["access_token"]

    # 2. Refresh cookie + CSRF
    csrf = next((c.value for c in jar if c.name == "pluto_csrf_token"), None)
    st, body, _ = _req("POST", "/api/auth/refresh", headers={"X-CSRF-Token": csrf} if csrf else {})
    ok = st == 200
    print(f"  {PASS if ok else FAIL}  POST /api/auth/refresh (cookie + CSRF) -> HTTP {st}")
    results.append(ok)
    if ok:
        token = json.loads(body.decode("utf-8"))["access_token"]

    # 3. Login
    st, body, _ = _req("POST", "/api/auth/login", json_body={"email": email, "password": password})
    ok = st == 200
    print(f"  {PASS if ok else FAIL}  POST /api/auth/login -> HTTP {st}")
    results.append(ok)
    if ok:
        token = json.loads(body.decode("utf-8"))["access_token"]

    # 4. Fetch jobs from DB
    st, body, _ = _req("GET", "/api/jobs")
    jobs = json.loads(body.decode("utf-8")) if st == 200 else []
    ok = st == 200 and len(jobs) > 0
    print(f"  {PASS if ok else FAIL}  GET /api/jobs -> HTTP {st} ({len(jobs)} jobs)")
    results.append(ok)
    if not ok:
        return results
    job_id = jobs[0]["id"]

    # 5. Resume screening upload
    resume_txt = (
        b"Smoke Tester\n"
        b"Skills: Python, Network Security, Cryptography, Application Security, Linux, Docker, AWS\n"
        b"Experience: 2020 - 2025 Senior Security Analyst\n"
        b"Education: B.Tech Computer Science\n"
    )
    mp_body, mp_ct = _encode_multipart(
        {"job_id": job_id, "candidate_name": "Smoke Tester"},
        {"file": ("smoke_resume.txt", resume_txt, "text/plain")},
    )
    st, body, _ = _req(
        "POST",
        "/api/resume/screen",
        raw_body=mp_body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": mp_ct},
    )
    ok = st == 200
    screen_data = json.loads(body.decode("utf-8")) if ok else {}
    print(f"  {PASS if ok else FAIL}  POST /api/resume/screen -> HTTP {st} (fit={screen_data.get('fit_score')}, sid={screen_data.get('session_id')})")
    results.append(ok)
    if not ok:
        print("    Response:", body.decode("utf-8", "replace")[:300])
        return results
    sid = screen_data["session_id"]

    # 6. Start interview (pull questions from seeded 1,799-question DB)
    st, body, _ = _req(
        "POST",
        f"/api/interview/{sid}/start",
        json_body={"preset_name": "strict"},
        headers={"Authorization": f"Bearer {token}"},
    )
    ok = st == 200
    start_data = json.loads(body.decode("utf-8")) if ok else {}
    print(f"  {PASS if ok else FAIL}  POST /api/interview/{sid}/start -> HTTP {st} (questions={start_data.get('total_questions')})")
    results.append(ok)

    # 7. Submit sample answer + generate report + PDF
    st, body, _ = _req(
        "POST",
        f"/api/interview/{sid}/question/0/answer",
        json_body={"transcript": "I have five years of experience securing distributed cloud networks and web applications."},
        headers={"Authorization": f"Bearer {token}"},
    )
    ok = st == 200
    print(f"  {PASS if ok else FAIL}  POST /api/interview/{sid}/question/0/answer -> HTTP {st}")
    results.append(ok)

    st, body, _ = _req("GET", f"/api/report/{sid}", headers={"Authorization": f"Bearer {token}"})
    ok = st == 200
    rep = json.loads(body.decode("utf-8")) if ok else {}
    print(f"  {PASS if ok else FAIL}  GET /api/report/{sid} -> HTTP {st} (overall_score={rep.get('overall_score')})")
    results.append(ok)

    st, body, _ = _req("GET", f"/api/report/{sid}/pdf", headers={"Authorization": f"Bearer {token}"})
    ok = st == 200 and body.startswith(b"%PDF")
    print(f"  {PASS if ok else FAIL}  GET /api/report/{sid}/pdf -> HTTP {st} ({len(body)} bytes PDF)")
    results.append(ok)

    # 8. Cleanup test session & logout
    _req("DELETE", f"/api/interview/{sid}", headers={"Authorization": f"Bearer {token}"})
    csrf = next((c.value for c in jar if c.name == "pluto_csrf_token"), None)
    st, _, _ = _req("POST", "/api/auth/logout", headers={"Authorization": f"Bearer {token}", **({"X-CSRF-Token": csrf} if csrf else {})})
    ok = st == 200
    print(f"  {PASS if ok else FAIL}  POST /api/auth/logout -> HTTP {st}")
    results.append(ok)

    return results


def main():
    parser = argparse.ArgumentParser(description="PLUTO vProctor deployment smoke & E2E verification")
    parser.add_argument("--url", default=BASE_URL, help="Target base URL")
    parser.add_argument("--e2e", action="store_true", help="Run full authenticated E2E verification flow")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"\n{'='*60}")
    print("  PLUTO vProctor — Deployment Verification")
    print(f"  Target: {base}")
    print(f"{'='*60}\n")

    start = time.monotonic()
    results = []

    print("Core Health & Seeded DB:")
    results.append(check("GET /health", f"{base}/health", json_key="status"))
    results.append(check("GET /ready", f"{base}/ready", json_key="status"))
    results.append(check("GET /api/health", f"{base}/api/health", json_key="status"))

    print("\nSPA Routes (Single-Origin):")
    results.append(check("GET / (SPA root)", f"{base}/", expect_html=True))
    results.append(check("GET /login (SPA route)", f"{base}/login", expect_html=True))
    results.append(check("GET /admin/login (SPA route)", f"{base}/admin/login", expect_html=True))

    print("\nAPI & Auth Guards:")
    results.append(check("GET /api/jobs", f"{base}/api/jobs"))
    results.append(check("GET /api/auth/config", f"{base}/api/auth/config", json_key="auth_enabled"))
    results.append(check("GET /api/auth/me (unauthenticated -> 401)", f"{base}/api/auth/me", expected_status=401))

    if args.e2e:
        results.extend(run_e2e(base))

    elapsed = time.monotonic() - start
    passed = sum(results)
    failed = len(results) - passed

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed  ({elapsed:.2f}s)")
    print(f"{'='*60}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
