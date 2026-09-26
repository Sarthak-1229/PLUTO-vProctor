<div align="center">

# 🛰️ PLUTO vProctor

**A fully local interview-practice tool.** Upload a résumé, get an adaptive mock
interview that adjusts difficulty to how well you answer, and receive a
descriptive practice report — all on a 6 GB laptop GPU, nothing leaves the
machine.

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-qwen2.5%3A7b-black?logo=ollama&logoColor=white)
![License](https://img.shields.io/badge/License-Personal-lightgrey)

</div>

---

## What it is

PLUTO vProctor is a **practice diagnostic**, not an evaluation. It runs a mock
interview built from a bank of 100+ scored questions across behavioral, HR,
situational, aptitude, and technical tracks (CS fundamentals, backend, frontend,
data/ML, system design, PM), tiered 1–5.

Two axes are kept strictly separate, by design:

- **Competence** — a content-correctness score `S ∈ [0,1]` for each answer. This
  is the **only** signal that drives question difficulty (an Elo + confidence
  state machine picks what to ask next).
- **Delivery** — speech and on-camera signals (words/min, filler rate, pauses,
  face-present / centered / head-motion ratios). These are **descriptive only**:
  raw numbers shown in the report, **never scored**, never fed back into
  difficulty.

**It makes no judgment** of emotion, nervousness, confidence, honesty, or
interview-readiness, and produces no pass/fail result or 0–100 score.

## ✨ Features

- **📄 Résumé-aware** — drop a PDF / DOCX / TXT (or paste text); role, seniority,
  and skills are inferred locally to select relevant questions.
- **🎚️ Adaptive difficulty** — answer well and it escalates; struggle and it
  rebuilds or switches topics. Content score is the sole driver.
- **🧮 Two-tier grading** — a fast lexical Tier-1 score drives live adaptation;
  a local-LLM Tier-2 pass (qwen2.5:7b via Ollama) refines the score for the
  report without re-folding the live Elo.
- **🎙️ Speak or type** — in-browser Web Speech API for dictation, with a CPU
  faster-whisper fallback. Everything degrades gracefully with no mic/camera.
- **📷 Descriptive delivery signals** — optional in-browser MediaPipe face
  metrics; consent-gated and never scored.
- **🔒 Answer key never leaves the server** — ideal points, keywords, rubric,
  red flags, and IRT params are whitelisted out of every client response.
- **📊 Practice report** — competence trajectory, per-question content
  breakdown, descriptive delivery aggregates, and content-only recommendations,
  exportable to PDF. Explicit no-hireability / no-emotion disclaimer throughout.
- **🗑️ Consent & delete** — audio / camera / transcript-storage are opt-in;
  one click permanently deletes all stored session data.

## 🏗️ Architecture

```
Browser UI (ui/interview.html + interview.js)
   │  JSON + base64 (résumé bytes, optional audio)
   ▼
FastAPI server (127.0.0.1:8080)
   ├─ /interview/resume   parse-only preview
   ├─ /interview/start    build a question pool for the profile
   ├─ /interview/next     serve the next question (answer key stripped)
   ├─ /interview/answer   Tier-1 score ─► live Elo/FSM; Tier-2 refine (background)
   ├─ /interview/report(.pdf)   competence + descriptive delivery + recs
   ├─ /interview/history · /interview/questions
   ├─ DELETE /interview/session/{id}   consent revocation / hard delete
   └─ /speak   optional edge-tts question replay (degrades to silence)
   │
   ├─ Tier-2 grading ─► Ollama (127.0.0.1:11434) ─► qwen2.5:7b   [GPU]
   └─ STT fallback  ─► faster-whisper (small, int8)              [CPU]
```

`core/interview/` holds the engine: `question_bank`, `session_store`,
`resume_parser`, `eval_tier1`, `adaptive`, `judge_llm`, `stt_service`,
`delivery`, `report`, and the `router`. Its only cross-module dependency is
`core/config.py`.

## 🚀 Quick start

**Prerequisites:** Python 3.11+ and [Ollama](https://ollama.com).

```bash
# 1. (recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. pull the grading model (one-time, ~4.5 GB)
ollama pull qwen2.5:7b

# 4. start the server
python -m uvicorn app:app --host 127.0.0.1 --port 8080
```

Then open **http://127.0.0.1:8080** (redirects to the interview UI).

> Ollama down? The interview still runs — answers keep their fast Tier-1 score
> and the Tier-2 refinement is simply skipped.

## ⚙️ Configuration

Settings live in [`core/config.py`](core/config.py):

| Setting | Default | Description |
|---|---|---|
| `LLM_MODEL_NAME` | `qwen2.5:7b` | Tier-2 grading model (~4.5 GB VRAM at Q4) |
| `STT_MODEL_SIZE` | `small` | faster-whisper size for the CPU STT fallback |
| `FORCE_STT_CPU` | `True` | Keep STT off the GPU to protect the VRAM budget |
| `VRAM_BUDGET_MB` | `6000` | Target GPU memory ceiling |
| `REPORTS_DIR` | `reports` | Where exported PDF reports are written |

## 🧪 Testing

All suites are plain scripts (no pytest); each exits `0` on pass. Tier-2 is
stubbed in the router/report suites, so they're hermetic and need no network.

```bash
python tests/validate_bank.py         # question-bank schema + coverage
python tests/test_resume_parser.py    # résumé parsing / role & seniority inference
python tests/test_adaptive.py         # Elo math, confidence FSM, Tier-1, full loop
python tests/test_router.py           # JSON API end-to-end + answer-key leak checks
python tests/test_report_delivery.py  # delivery aggregates + report builder
```

## 🎯 Design notes

- **Competence and delivery never mix.** Only content correctness changes
  difficulty; delivery is descriptive and negated in every disclaimer.
- **The candidate never sees the answer key.** Presentation fields are
  whitelisted; the rest is dropped server-side before serialization.
- **VRAM first.** The 6 GB budget is binding — the LLM owns the GPU, STT is
  pinned to CPU, and TTS is optional/off-GPU.

## 📝 License

Private project — built for personal use.
