---
description: PLUTO Phase 0: project skeleton, environment and dependency checks
---

# Phase 0: Setup

Read: `docs/spec/04-folder-structure.md`, `docs/spec/02-constraints.md`.

1. Create the folder structure from the spec (empty modules with docstrings are fine).
2. Backend: venv at `backend/.venv`, `requirements.txt` (fastapi, uvicorn, sqlalchemy, pydantic, scikit-learn, sentence-transformers, faster-whisper, mediapipe, opencv-python, pdfplumber, python-docx, rapidfuzz, numpy, pandas, joblib, reportlab, pytest). Do not install the CUDA build of torch without asking me.
3. Frontend: Vite + React + Tailwind in `frontend/`.
4. `backend/app/config.py` with all constants, a `/health` endpoint, and `run_dev.bat` / `run_dev.sh`.
5. `scripts/check_env.py`: verifies Ollama is reachable and `qwen2.5:3b` responds (print the `ollama pull qwen2.5:3b` instruction if not), ffmpeg exists, and `datasets/data` + `datasets/data1` exist (list every file found with size).
6. README skeleton.

Acceptance: `/health` returns OK, `check_env.py` prints a clear report, frontend dev server starts.
