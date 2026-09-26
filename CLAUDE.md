# PLUTO v2 - Phase 1 Behavioral Contract

## Architecture & Constraints

* **Current Phase:** Phase 1 (Voice Interaction & Autonomous Research).
* **Hardware Constraint:** The user is running a local laptop with only 6GB of VRAM (RTX 4050).
* **VRAM Budgeting:** NEVER suggest heavy local models. Use `faster-whisper` (base/small models) for STT. Use `edge-tts` (CPU-bound) for TTS to save VRAM. Use local lightweight Ollama (`llama3.2:3b`) or cloud APIs for core LLM reasoning.

## Development Rules for Claude Code

1. **Python Environment:** Always assume we are operating inside the local `.venv`.
2. **Modular Code:** Do not write one massive `main.py`. Split functionalities into:
   - `core/audio_stt.py` (Listening/Whisper)
   - `core/audio_tts.py` (Speaking/Edge-TTS)
   - `core/researcher.py` (Web scraping using `duckduckgo_search` & `bs4`)
   - `core/brain.py` (LLM prompt routing)
3. **Keyword Routing:** The system must listen for verbal intent keywords.
   - If the user says "Give me a quick answer about X", route to a short conversational LLM prompt.
   - If the user says "Create a report on X", route to `core/researcher.py` to scrape the web, synthesize a markdown document, and save it to the `/reports` directory.
4. **Tool Usage:** You (Claude Code) have native tools like `bash` for shell execution and `text_editor` for file operations. Use them to write test scripts, run them, and verify the audio hardware is picking up the microphone correctly.

## Commands

* Run the main agent loop: `python main.py`

## Git Discipline

- NEVER run `git commit` or `git push` without explicit confirmation from
  the user in that same session. Always summarize what changed and ask
  "commit now?" first, even if a previous session auto-committed.
