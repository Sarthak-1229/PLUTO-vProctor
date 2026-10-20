# PLUTO vProctor: project identity (always loaded, keep this file short)

PLUTO vProctor is a **local, offline AI mock-interview + proctoring web app** (AIML academic project).
Candidate picks a job, uploads a resume, gets screened, is interviewed by an AI that asks and speaks questions
(filtered from MY real Q&A dataset), is monitored for eye contact / movement, and gets a score with a mm:ss deduction timeline.

**Stack:** Python 3.10+, FastAPI, SQLAlchemy + SQLite, React (Vite) + Tailwind, MediaPipe, faster-whisper, scikit-learn,
sentence-transformers (MiniLM, CPU), local LLM **qwen2.5:3b via Ollama** (6 GB VRAM machine, Windows).

**Source of truth lives in `docs/spec/`.** Read only the spec file(s) the current phase workflow names. Do not load them all.

**Non-negotiables**
1. Everything runs locally. No cloud LLM/API calls inside the app.
2. My datasets in `datasets/data/` and `datasets/data1/` (train/val/test, question+answer pairs) are the ONLY source of interview questions. Never invent a question bank.
3. Never fit or tune on `test`. Test is used once, by `evaluate_*.py` scripts.
4. The 3B LLM is weak: JSON-only prompts, Pydantic validation, one retry, then a deterministic fallback. The LLM never alone decides a score.
5. Never keep two GPU models loaded at once (GPUScheduler lock).
6. Search/sort/ML algorithms listed in `docs/spec/06-algorithms.md` must be hand-implemented, tested and documented.
7. All thresholds and weights live in `backend/app/config.py`.

**Workflow:** work one phase at a time using the `/phase-N-...` workflows in `.agent/workflows/`.
