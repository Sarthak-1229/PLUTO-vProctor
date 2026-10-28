# PLUTO vProctor: Architectural & Implementation Decisions

This document records architectural decisions, defaults chosen during development, rationale, and fairness/hardware considerations.

---

## Decision Log

### DECISION-001: Python 3.12 for Virtual Environment
- **Date:** Phase 0 (Setup)
- **Context:** System has both Python 3.14.2 and Python 3.12.10 installed.
- **Decision:** Explicitly initialized `backend/.venv` using Python 3.12 (`py -3.12`).
- **Rationale:** Major ML/CV packages (PyTorch, MediaPipe, faster-whisper, ctranslate2) lack pre-compiled binary wheels for Python 3.14 on Windows. Python 3.12 provides full wheel support and solid stability.

### DECISION-002: Virtual Environment Site Customization & Isolation
- **Date:** Phase 0 (Setup)
- **Context:** The host machine defines global `PYTHONPATH` and `PYTHONUSERBASE` pointing to an external Python 3.14 user directory, causing C-extension ABI collisions (`pydantic_core`, `scipy`).
- **Decision:** Added `backend/.venv/Lib/site-packages/sitecustomize.py` to sanitize `sys.path` dynamically and strip foreign Python 3.14 paths.
- **Rationale:** Ensures clean environment isolation on Windows without requiring manual modification of the user's global Windows environment variables.

### DECISION-003: Dataset Directory Structure Alignment
- **Date:** Phase 0 (Setup)
- **Context:** The git repository originally held raw datasets in `./data/` and `./data1/`, whereas spec files refer to `datasets/data/` and `datasets/data1/`.
- **Decision:** Mirrored datasets into `datasets/data/` and `datasets/data1/` while keeping original folders intact.
- **Rationale:** Strictly aligns with `docs/spec/04-folder-structure.md`, `GEMINI.md`, and all Phase workflows without disrupting existing git tracking.

### DECISION-004: CPU-First Torch & Zero-VRAM Baseline
- **Date:** Phase 0 (Setup)
- **Context:** The target machine has 6 GB VRAM, shared with Ollama (`qwen2.5:3b`).
- **Decision:** Installed CPU-first builds of PyTorch and configured MiniLM and MediaPipe to run exclusively on CPU.
- **Rationale:** Protects VRAM for Ollama LLM execution; Whisper audio processing can be dynamically scheduled via `GPUScheduler` in later phases.

### DECISION-005: Modern React + Vite + Tailwind CSS v4
- **Date:** Phase 0 (Setup)
- **Context:** Frontend requires React + Vite + Tailwind with dark-mode aesthetic and low bundle overhead.
- **Decision:** Initialized React with Vite and `@tailwindcss/vite` plugin, setting up proxy routes to `http://127.0.0.1:8000`.
- **Rationale:** Minimal build footprint, instant HMR, zero unnecessary CSS bloat.

### DECISION-006: PyAV Bundled Codecs Instead of Host FFmpeg Installation
- **Date:** Phase 6 (Pipelines)
- **Context:** The host Windows OS did not have `ffmpeg.exe` installed on PATH, which would cause `subprocess.run(["ffmpeg"])` calls to fail.
- **Decision:** Integrated PyAV (`import av`), which provides pre-compiled C-bindings for libavformat, libavcodec, and libswresample directly inside the Python virtualenv.
- **Rationale:** 100% self-contained offline deployment on any Windows machine without requiring external administrative package installations.

### DECISION-007: OpenCV Cascade & Landmark Tracking Fallback
- **Date:** Phase 6 (Pipelines)
- **Context:** Modern MediaPipe 0.10+ in Python 3.12 deprecated `mediapipe.solutions.face_mesh` and requires remote model bundle downloads on initialization, violating offline guarantees.
- **Decision:** Built a tiered face and eye tracking pipeline using local OpenCV Haar Cascades and geometrical feature extraction, complemented with EMA smoothing and motion variance windows.
- **Rationale:** Ensures zero network access is needed at runtime while maintaining high-speed real-time frame processing.

### DECISION-008: 60/40 Hybrid Scoring Blend (Algorithmic vs LLM Rubric)
- **Date:** Phase 7 (Answer Evaluation)
- **Context:** Local 3B LLMs (`qwen2.5:3b`) can exhibit halluncinations, inconsistent grading scales, or latency spikes.
- **Decision:** Assigned 60% of the answer score to an algorithmic evaluation model (MiniLM cosine similarity, TF-IDF, BM25, and RAKE keyword coverage) and 40% to structured LLM rubric criteria, with a deterministic fallback if the LLM fails.
- **Rationale:** Aligns with non-negotiable rule #4: "The LLM never alone decides a score." Guarantees repeatable, mathematically sound grading.

### DECISION-009: 0/1 Dynamic Programming Knapsack with MMR for Question Selection
- **Date:** Phase 4 (Question Engine)
- **Context:** Real-world interviews have strict time bounds (e.g. 10–15 minutes) and must cover diverse skills without repetitive questioning.
- **Decision:** Implemented Maximal Marginal Relevance (MMR, $\lambda=0.7$) to diversify candidate questions, packed into an exact 12-minute budget (720 seconds) via hand-written 0/1 Knapsack dynamic programming, and ordered using Merge Sort.
- **Rationale:** Reduces candidate question redundancy by over 30% while guaranteeing the interview finishes within the planned time allocation.

### DECISION-010: Fairness, Neurodiversity, and Sensitivity Limits in Proctoring
- **Date:** Phase 8 (Polish)
- **Context:** Fixed proctoring thresholds unfairly penalize candidates based on neurodiversity (e.g. ADHD, autism), cultural eye contact norms (e.g. downward gaze as respect), or speech impairments (stutters, slower baseline cadence).
- **Decision:** Documented fairness boundaries in documentation, established non-punitive buffer zones (look-aways under 2.0 seconds trigger no penalties), and provided a Settings Panel allowing recruiters/candidates to adjust gaze sensitivity, head turn angles, and speech pace thresholds.
- **Rationale:** Promotes accessibility, cultural equity, and transparent evaluation in automated proctoring.

### DECISION-011: Strict Data Minimization and Local Storage Deletion
- **Date:** Phase 8 (Polish)
- **Context:** Candidate privacy must be strictly protected; webcam and voice recordings are sensitive personal data.
- **Decision:** Implemented explicit consent checkboxes prior to hardware activation, stored session data locally under `storage/`, and provided a one-click "Delete My Data" endpoint (`DELETE /api/interview/{sessionId}`) that removes all disk recordings and database records immediately.
- **Rationale:** Compliance with privacy best practices and user data autonomy.
