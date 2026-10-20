<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 3. Architecture

```
React (Vite) frontend
 ├─ Setup page (job select, resume upload, screening result)
 ├─ Interview page (video, question display + TTS, live alerts, recorder)
 ├─ Processing page (progress polling)
 └─ Report page (scores, summary, deduction timeline, video seek)
        │  REST + WebSocket
FastAPI backend
 ├─ resume_service      (parse + score)
 ├─ question_service    (filter + select + order)
 ├─ interview_service   (session state, follow-ups via LLM)
 ├─ analysis_service    (orchestrates parallel pipelines)
 │    ├─ video_pipeline (MediaPipe: gaze, head pose, body motion)
 │    └─ audio_pipeline (ffmpeg → faster-whisper → pauses/fillers)
 ├─ scoring_engine     (merges all deductions)
 ├─ report_service     (summary via LLM + deterministic fallback)
 └─ llm_client         (Ollama wrapper, JSON mode, retries, GPU lock)
SQLite + local /storage (resumes, recordings, reports)
```

Live checks (gaze/movement alerts) run **in the browser** with MediaPipe Tasks Vision (JS) for low latency and zero backend load. The authoritative scoring is recomputed **server-side after the interview** from the recording using Python MediaPipe, so results are consistent and cannot be spoofed. Both are logged as events with timestamps.
