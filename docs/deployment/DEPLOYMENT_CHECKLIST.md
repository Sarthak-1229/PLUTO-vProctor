# PLUTO vProctor — Deployment Checklist

> Updated: 2026-11-17  
> Legend: 🤖 Agent-completed | 👤 Owner action required | ✅ Done | ⬜ Pending

---

## A — Agent Pre-Flight (Completed by Engineering Agent)

| # | Task | Status |
|---|---|---|
| A1 | Backend startup optimized — port binding in 3.53s (AppSail 10s limit) | ✅ |
| A2 | Failing test `test_legacy_sessions_preservation_invariant` fixed | ✅ |
| A3 | All 215 backend tests passing, 0 failing, 1 skipped (intentional) | ✅ |
| A4 | All 21 frontend tests passing, 0 failing | ✅ |
| A5 | Frontend build produces clean `frontend/dist/` (901ms) | ✅ |
| A6 | `catalyst.json` Python stack updated to `python_3_12` | ✅ |
| A7 | `.gitignore` updated: `.env`, `*.joblib`, `*.npy`, `*.task` excluded | ✅ |
| A8 | `backend/.env.example` created (safe template, no secrets) | ✅ |
| A9 | `backend/.env.hosted.example` created (Catalyst AppSail template) | ✅ |
| A10 | `frontend/.env.production.example` created | ✅ |
| A11 | `scripts/smoke_test.py` created (health + API + auth guard checks) | ✅ |
| A12 | 6 handover documents created in `docs/deployment/` | ✅ |
| A13 | Database integrity verified: `PRAGMA integrity_check` = ok, 0 FK errors | ✅ |
| A14 | Database preservation: 16 sessions intact (14 original + 2 benchmark) | ✅ |
| A15 | Question bank: 1,799 questions loaded at startup | ✅ |
| A16 | No hardcoded secrets in source code | ✅ |
| A17 | No hardcoded `localhost:8000` in frontend source | ✅ |
| A18 | All changes committed to Git (`main` branch) | ✅ |

---

## B — Owner Pre-Deployment (Required Before Running Catalyst CLI)

| # | Task | Status |
|---|---|---|
| B1 | Verify Catalyst account plan: **must be Sandbox** (not Pay-As-You-Go) | ⬜ |
| B2 | Verify Zoho wallet credit type — confirm it applies to Catalyst billing, or treat as zero | ⬜ |
| B3 | Authenticate Catalyst CLI: `catalyst login` | ⬜ |
| B4 | Link project: `catalyst project switch` → select project 73453000000046001 | ⬜ |
| B5 | Generate a real SECRET_KEY: `python -c "import secrets; print(secrets.token_urlsafe(48))"` | ⬜ |
| B6 | Set SECRET_KEY in AppSail console → Environment Variables | ⬜ |
| B7 | Verify Python 3.12 stack is available in your Catalyst tier (if not, change `catalyst.json` → `python_3_10`) | ⬜ |
| B8 | Build frontend: `cd frontend && npm install && npm run build` | ⬜ |

---

## C — Deployment Steps (Owner Executes)

| # | Task | Status |
|---|---|---|
| C1 | Deploy backend: `catalyst appsail deploy` | ⬜ |
| C2 | Note the AppSail service URL from the CLI output | ⬜ |
| C3 | Update `frontend/.env.production` with the real AppSail URL | ⬜ |
| C4 | Rebuild frontend: `npm run build` | ⬜ |
| C5 | Deploy frontend: `catalyst webclient deploy` | ⬜ |
| C6 | Set `CORS_ORIGINS` env var in AppSail console to match the frontend URL | ⬜ |

---

## D — Post-Deployment Verification (Owner Runs)

| # | Task | Status |
|---|---|---|
| D1 | `GET /health` → 200, `{"status": "ok"}` | ⬜ |
| D2 | `GET /ready` → 200 | ⬜ |
| D3 | Run smoke test: `python scripts/smoke_test.py` with `PLUTO_BASE_URL` set | ⬜ |
| D4 | Open frontend in browser — landing page loads | ⬜ |
| D5 | Login with admin credentials — succeeds | ⬜ |
| D6 | Create a practice interview session — session ID returned | ⬜ |
| D7 | Browse question bank — questions load | ⬜ |
| D8 | Upload a resume PDF — parsing succeeds (even without ML model) | ⬜ |

---

## E — Cost Control (Owner Configures)

| # | Task | Status |
|---|---|---|
| E1 | Set budget alert at 70% of free tier (630 GB-min) in Catalyst Billing | ⬜ |
| E2 | Set budget alert at 90% of free tier (810 GB-min) | ⬜ |
| E3 | Confirm AppSail min-instances=0 (auto scale to zero) | ⬜ |
| E4 | Confirm no payment method attached to account | ⬜ |

---

## Blocked Items (Requires Owner Action to Unblock)

| Item | Blocker | Resolution |
|---|---|---|
| Actual Zoho credit eligibility | Account-level verification needed | Owner logs into Catalyst Console → Billing |
| Python 3.12 stack availability | Depends on Catalyst project tier | Owner checks AppSail stack options in Console |
| AppSail service URL | Only available after deployment | Owner runs `catalyst appsail deploy` |
| Docker/Linux container test | No Docker/WSL on development workstation | Optional — Dockerfile is correct per static analysis |
