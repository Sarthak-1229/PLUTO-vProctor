---
description: PLUTO Phase 6: parallel video and audio analysis pipelines
---

# Phase 6: Analysis pipelines (hardest phase, go slowly)

Read: `docs/spec/5b-interview-analysis.md` (section 5.5) and `.agent/rules/00-hardware-and-llm.md`.

1. `video_pipeline.py`: OpenCV frame sampling about 5 fps, MediaPipe face mesh + pose, gaze, head pose, motion, posture, face count, EMA/Kalman smoothing, sliding-window violation detection, interval merging.
2. `audio_pipeline.py`: ffmpeg to 16 kHz wav, faster-whisper with word timestamps and a filler-preserving `initial_prompt`, filler detection (hash set + KMP + Rabin-Karp + Levenshtein variants), pauses, late starts, pace.
3. `analysis_service.py`: run both pipelines **simultaneously** (process pool / asyncio), status endpoint with per-pipeline progress, GPUScheduler.
4. Test with a short sample clip (generate a synthetic one if none exists). Log peak VRAM.

Acceptance: both pipelines produce timestamped events in parallel on a sample recording without exceeding 6 GB VRAM.
