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
