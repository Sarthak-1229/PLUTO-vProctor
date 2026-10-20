<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 5. Feature specifications (part B: interview and analysis)

### 5.4 Interview experience (frontend + WebSocket)
- Pre-check screen: camera + mic permission, face-in-frame guide, **distance check** (face bounding-box width as a % of frame: too close >55%, too far <18%), lighting check (mean brightness), "Start interview" enabled only when OK.
- Interviewer panel shows question text + animated avatar/waveform, TTS speaks the question. Candidate's mic is only evaluated after TTS finishes.
- Controls: "Next question" (or auto-advance after 3 s of detected silence following speech), progress bar, countdown timer per question.
- **Live proctoring in the browser** (MediaPipe Face Landmarker with iris landmarks + Pose Landmarker):
  - Gaze/eye-contact estimate from iris position relative to eye corners + head yaw/pitch from face transformation matrix.
  - If looking away > 2.0 s (sliding window + EMA smoothing), show a red on-screen alert and log an event `{type:"LOOK_AWAY", t_start, t_end, severity}`.
  - Movement: shoulder/nose landmark displacement variance over a 1 s window; excessive movement logs `EXCESSIVE_MOTION`; leaning/slouching logs `POSTURE`; no face → `FACE_MISSING`; multiple faces → `MULTIPLE_FACES`.
  - Live score gauge decreasing as deductions occur.
- Record with `MediaRecorder` (video+audio, webm). Upload in chunks at the end (or stream chunks) to `/api/interview/{id}/recording`. Also send per-question start/end timestamps so each answer can be mapped to the recording.
- Handle tab-switching (`visibilitychange`) as `TAB_SWITCH` event.

### 5.5 Post-interview analysis (parallel)
Use `concurrent.futures.ProcessPoolExecutor` / `asyncio` so these run **simultaneously**:

**Video pipeline (`video_pipeline.py`)**
- Sample frames at ~5 fps with OpenCV; MediaPipe Face Mesh (iris) + Pose.
- Compute per-frame: gaze direction, head yaw/pitch/roll, eye-contact boolean, shoulder/nose displacement, posture angle, face count.
- Smooth with EMA/Kalman; detect continuous violation segments with a **sliding window** and merge adjacent segments with **interval merging**.
- Output: list of events with `t_start, t_end, type, severity` and aggregate stats (eye-contact %, motion index, posture score).

**Audio pipeline (`audio_pipeline.py`)**
- `ffmpeg` extract 16 kHz mono wav.
- `faster-whisper` with `word_timestamps=True`, `vad_filter=False` (VAD removes fillers), and an `initial_prompt` such as "Umm, uh, like, you know, so, I mean..." to encourage keeping fillers in the transcript.
- **Filler detection:** exact match with a hash set, plus multi-word fillers via **KMP** (implement) and compare with **Rabin–Karp**; fuzzy variants ("ummm", "uhhh", "ahm") through Levenshtein distance ≤ 1 against the filler list.
- **Pauses:** gaps between consecutive word timestamps > 1.2 s (mid-answer pause), and response latency > 3 s after the question ends (late start).
- **Pace:** words per minute per answer; flag < 100 or > 180 wpm.
- Optionally compute pitch/energy variability using `librosa` for a "monotone" indicator (low weight).
- Output: transcript with timestamps, events (`FILLER_WORD`, `LONG_PAUSE`, `LATE_START`, `PACE_FAST`, `PACE_SLOW`), and per-answer stats.
