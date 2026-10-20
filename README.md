# PLUTO vProctor 🛡️

> **Local, Offline AI Mock-Interview + Proctoring Web Application**  
> AIML Academic Project — Built for strict 6 GB VRAM Windows offline execution.

---

## Overview

PLUTO vProctor is a comprehensive mock-interview platform that runs completely offline on consumer hardware:
1. **Candidate Screening**: Resume parsing and matching against curated job profiles.
2. **Dynamic Interview**: Generates grounded questions sourced exclusively from real interview Q&A datasets.
3. **Multimodal Proctoring**: Real-time eye contact tracking, gaze deviation monitoring, and speech fluency analysis.
4. **Scoring & Report Engine**: Generates a detailed breakdown with a minute-by-minute (`mm:ss`) deduction timeline and exportable PDF report.

---

## Core Stack & Hardware Constraints

- **Hardware Target**: Windows PC with 6 GB VRAM.
- **Local LLM**: `qwen2.5:3b` via Ollama (`http://localhost:11434`, `format: "json"`).
- **Vision Proctoring**: MediaPipe Face Mesh & Pose (CPU-only).
- **Speech Recognition**: `faster-whisper` (int8, configurable CPU/CUDA fallback).
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (CPU-only).
- **Backend**: FastAPI + SQLAlchemy + SQLite.
- **Frontend**: React (Vite) + Tailwind CSS.
- **Algorithms**: 15 hand-implemented algorithms (Trie, BM25, Knapsack, MinHash, MMR, etc.).

---

## Quickstart

### 1. Prerequisites
- **Python**: 3.10+ (Python 3.12 recommended)
- **Node.js**: 18+
- **Ollama**: [Download & install](https://ollama.com/), then run:
  ```bash
  ollama pull qwen2.5:3b
  ```
- **ffmpeg**: Required for audio/video stream processing (`winget install Gyan.FFmpeg`).

### 2. Verify Environment & Datasets
Run the diagnostic check script:
```bash
backend\.venv\Scripts\python.exe scripts\check_env.py
```

### 3. Start Development Servers
Run the Windows startup batch file:
```cmd
run_dev.bat
```
Or on Linux/macOS:
```bash
./run_dev.sh
```

- **Frontend UI**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## Testing
Run backend test suite:
```bash
backend\.venv\Scripts\python.exe -m pytest backend\tests
```

---

## Project Structure
```
pluto-vproctor/
├── datasets/                      # Real Q&A datasets (train, val, test)
│   ├── data/
│   └── data1/
├── backend/                       # FastAPI application
│   ├── app/
│   │   ├── config.py              # Central thresholds and parameters
│   │   ├── main.py                # App entrypoint and routes
│   │   ├── algorithms/            # Hand-implemented algorithms
│   │   ├── pipelines/             # Audio and video proctoring pipelines
│   │   ├── routers/               # API endpoints
│   │   └── services/              # Domain logic
│   └── tests/                     # Pytest suite
├── frontend/                      # React + Vite + Tailwind UI
├── scripts/                       # Diagnostics and ingestion scripts
└── docs/                          # Architecture, spec, and decisions
```
