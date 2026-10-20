# Rule: hardware and local LLM (Always On)

- Target machine: Windows, 6 GB VRAM. Provide `.bat` and `.sh` scripts; never assume bash-only syntax in instructions.
- LLM: Ollama at `http://localhost:11434`, model `qwen2.5:3b`, `num_ctx` <= 4096, `keep_alive` about 30s, `format: "json"` for structured output.
- Whisper: `faster-whisper` small/base, int8, device configurable (`cuda`/`cpu`), default CPU while the LLM is loaded.
- MiniLM embeddings and MediaPipe run on CPU.
- All GPU use goes through one `GPUScheduler` (lock) so the LLM and Whisper never overlap.
- Every LLM call: short prompt, Pydantic-validated JSON, one retry, then deterministic fallback. Log latency and failures.
- Interviewer voice = browser `speechSynthesis` (zero VRAM).
