<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 2. HARD CONSTRAINTS (read carefully)

- **Everything runs locally.** No paid cloud APIs. No OpenAI/Anthropic/Google API calls inside the app.
- **Local LLM: `qwen2.5:3b` served by Ollama** (`http://localhost:11434`). The dev machine has **only 6 GB VRAM**, so:
  - Never load more than one GPU model at a time. Use a `GPUScheduler` (a semaphore/lock) so Ollama and Whisper never run on the GPU simultaneously.
  - Whisper: use `faster-whisper` with model `small` (or `base`), `compute_type="int8"`. Make device configurable (`cuda` or `cpu`), default `cpu` while the LLM is loaded, with auto-fallback.
  - Sentence embeddings: `sentence-transformers/all-MiniLM-L6-v2` on **CPU**.
  - MediaPipe runs on CPU.
  - Set Ollama `keep_alive` low (e.g. `30s`) so VRAM frees after use, and `num_ctx` to 4096 max.
- The 3B model is weak. So: keep prompts short and structured, ask for **JSON output** (`format: "json"` in the Ollama API), validate with Pydantic, retry once on invalid JSON, and fall back to deterministic algorithmic logic if the LLM fails. **The LLM must never be the only thing deciding a score.** Core scoring is algorithmic; the LLM assists (explanations, follow-ups, answer-relevance rubric).
- Python 3.10+, FastAPI backend, React (Vite) frontend, SQLite via SQLAlchemy. Windows-friendly (no bash-only assumptions; provide both `.bat` and `.sh` run scripts).
- Browser TTS (`window.speechSynthesis`) is used for the interviewer voice (zero VRAM).
- **Use my real datasets** (section 2B). No synthetic question bank. Synthetic data is allowed only for resume–job pairs (the dataset has none) and must be labelled as synthetic in the docs.
