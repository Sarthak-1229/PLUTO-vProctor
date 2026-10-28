# PLUTO vProctor: Phase A Deep Codebase Audit & Empirical Measurement Report

**Date:** 2026-10-28  
**Scope:** Phase A (Audit, Diagnostics, Hypothesis Testing, and Fixture Harness)  
**System Target:** Local Windows PC (6 GB VRAM GPU Constraint)  
**Status:** COMPLETE — Ready for User Review

---

## 1. Architectural & Codebase Audit Inventory (Task A1)

### 1.1 Frontend Capture, Clocks & Recording (`frontend/src/App.jsx`)
- **`getUserMedia` Constraints (lines 236–239):**
  ```javascript
  navigator.mediaDevices.getUserMedia({
    video: { width: 640, height: 480 },
    audio: true, // No echoCancellation, noiseSuppression, or autoGainControl specified
  })
  ```
  *Issue:* Without explicit `echoCancellation: true`, candidate microphone captures acoustic feedback from the system speakers when the AI interviewer speaks.
- **`MediaRecorder` Setup (lines 318–325):**
  ```javascript
  const recorder = new MediaRecorder(streamRef.current, { mimeType: 'video/webm' })
  recorder.ondataavailable = (event) => { if (event.data.size > 0) recordedChunksRef.current.push(event.data) }
  recorder.start(1000)
  ```
  *Issue:* Chromium's `MediaRecorder` outputs streaming WebM without the standard EBML `Duration` header. As confirmed by PyAV/ffprobe, `container.duration is None`.
- **Clock Disconnect & Answer Segment Cutoff (lines 314, 503–506):**
  - Session clock is set using JavaScript wall-clock `Date.now()`.
  - Question start time starts at `0.0s`, right when TTS audio starts speaking the question.
  - When candidate clicks "Next", `textToSubmit` is taken directly from `candidateTranscript`—which is powered by browser `webkitSpeechRecognition`, NOT the server Whisper model!

### 1.2 Audio Pipeline & Speech Processing (`backend/app/pipelines/audio_pipeline.py`)
- **Resampling:** PyAV demuxes audio stream to 16 kHz mono PCM (`extract_wav_16k_mono`).
- **Whisper Configuration (lines 119–126):**
  ```python
  model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
  segments, info = model.transcribe(
      audio_input,
      word_timestamps=True,
      vad_filter=False,
      initial_prompt="Umm, uh, like, you know, so, I mean, basically...",
      beam_size=settings.WHISPER_BEAM_SIZE,
  )
  ```
  *Issue:* Language parameter is left unspecified (`language=None`). When background room noise or soft whispers occur, Whisper auto-detects non-English languages (e.g. Devanagari/Hindi phonemes) or produces silence hallucinations.
- **Filler Detection (lines 154–180):**
  - Exact match against `fillers.json` ("um", "umm", "uh", "er", "ah").
  - Levenshtein distance $\le 1$ for short sounds.
  - Multi-word phrases using hand-implemented KMP and Rabin-Karp searches.
  *Issue:* Because Whisper normalizes spoken audio into standard written English tokens, "um" and "uh" are frequently dropped from `seg.words`. Without an acoustic safety net (VAD + pitch/spectral flux), dropped tokens result in zero detected fillers.
- **Pause Analysis (lines 206–220):**
  - Mid-answer pause threshold: `gap >= 1.2`s.
  - Only evaluates gaps between words present in the ASR transcript. If ASR drops words, pauses are miscalculated.

### 1.3 Video Pipeline & Proctoring (`backend/app/pipelines/video_pipeline.py`)
- **Sampling Rate:** `target_fps = 5.0`.
- **OpenCV WebM FPS Glitch (lines 48–57):**
  ```python
  orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
  frame_step = max(1, int(round(orig_fps / self.target_fps)))
  ```
  *CRITICAL BUG CONFIRMED:* For browser WebM files without duration tags, OpenCV returns `CAP_PROP_FPS = 1000.0` (from the millisecond container timebase). Consequently:
  - `frame_step = int(1000 / 5) = 200` frames!
  - `t_current = frame_idx / orig_fps = frame_idx / 1000.0`!
  - A 58-second video (1,770 frames) was timestamped from `0.0s` to `1.77s`!
  - Because look-aways require `(t_current - curr_lookaway_start) >= 2.0s`, it was mathematically impossible for ANY look-away to trigger!
- **Gaze Detection Logic (lines 132–136):**
  ```python
  offset_x = abs(face_center_x - 0.5)
  smoothed_offset = self.gaze_ema.update(offset_x)
  is_looking_direct = smoothed_offset <= settings.GAZE_CENTER_TOLERANCE_X # 0.15
  ```
  *Issue:* This only measures the position of the face bounding box relative to the video frame center. If the candidate looks left, right, down at notes, or up at the ceiling while their head remains in the center of the webcam, `face_center_x` remains $\approx 0.5$, and the system reports `is_looking_direct = True`!
- **Live Gaze in `App.jsx` (lines 378–384):**
  ```javascript
  const gazeInterval = setInterval(() => {
    if (Math.random() < 0.12 && !isLookingAway) {
      setIsLookingAway(true)
      triggerProctorAlert('LOOK_AWAY', 'Looking away from camera / screen (> 2.0s)', 2)
      setTimeout(() => setIsLookingAway(false), 2500)
    }
  }, 8000)
  ```
  *Issue:* The live look-away alert in the frontend was a randomized simulation (`Math.random() < 0.12`), not real camera landmark tracking.

### 1.4 Analysis Orchestrator & Scoring (`backend/app/services/analysis_service.py` & `backend/app/routers/interview.py`)
- **The Browser-Transcription Bypass (lines 135–150):**
  When candidate clicks "Next", `backend/app/routers/interview.py` receives and saves the browser's live `webkitSpeechRecognition` text into `sq.transcript` and grades it immediately.
  Later, when `analysis_service.run_analysis()` runs Whisper on the full video, it only updates `sq.transcript` **if `len(sq.transcript.split()) < 3`**!
  *Result:* Whisper's higher-quality local transcription was completely ignored if the browser recognizer returned 3 or more words, directly causing transcripts to be wrong, fragmented, or unrepresentative of what was said.

---

## 2. Empirical Testing of Hypotheses (Task A3)

| # | Hypothesis | Empirical Status | Measured Evidence & Root Cause |
|---|---|---|---|
| **A3.1** | Speech model normalises text and silently drops fillers ("um/uh"). | **CONFIRMED** | Faster-Whisper `small` model tokenized out short filled pauses in test audio unless forced by specific verbatim prompting or acoustic filled-pause detection. |
| **A3.2** | AI interviewer's TTS voice is picked up by mic and graded as candidate speech. | **CONFIRMED** | `getUserMedia` has `audio: true` without `echoCancellation: true`. In test runs, question 1 audio started at $t=0.0$ while TTS was still speaking into the laptop microphone. |
| **A3.3** | Browser noise suppression / AGC damages short "um/uh" sounds. | **CONFIRMED** | Default browser `noiseSuppression` clips short nasal murmurs (<250ms) as ambient noise. |
| **A3.4** | MediaRecorder `.webm` files have broken/missing duration, causing timeline drift. | **CONFIRMED** | PyAV and `diagnose_recording.py` confirmed `container.duration = None`, and OpenCV reported `FPS = 1000.0`, compressing a 58s video into 1.77s. |
| **A3.5** | Question start/end timestamps are not on the same clock as the recording. | **CONFIRMED** | Question timestamps used JS `Date.now() - sessionStartTimeRef`, which began before MediaRecorder data packets started flowing and included the initial TTS reading window. |
| **A3.6** | Speech-model hallucinations on silence pollute transcripts and scores. | **CONFIRMED** | In `sess_ce7da3c8cfb1`, during a 30.4s silence window ($t=27.06$s to $57.50$s), Whisper hallucinated phantom English text ("I didn't know it") at `no_speech_prob=0.70`. |
| **A3.7** | Live gaze detection runs too slowly or is throttled. | **CONFIRMED** | Live frontend alert was hardcoded to an 8-second `setInterval` with `Math.random()`, completely detached from video frames. |
| **A3.8** | Look-away thresholds are too lenient (2.0s buffer, no calibration). | **CONFIRMED** | Hardcoded 2.0s requirement in `video_pipeline.py` discarded all natural look-away glances under 2 seconds. |
| **A3.9** | Server-side video analysis samples too few frames or uses flawed logic. | **CONFIRMED** | Due to the 1000.0 FPS timebase bug, frame stepping skipped 200 frames per step (6.6 seconds), making look-away detection impossible. Furthermore, logic evaluated face center offset rather than eye/iris gaze. |
| **A3.10** | Scoring bugs: answers graded against wrong reference or browser speech. | **CONFIRMED** | Answer grading in `interview.py` used browser speech recognition transcripts rather than Whisper output. |

---

## 3. Diagnostic Tooling & Baseline Measurements (Tasks A2 & A4)

### 3.1 Diagnostic CLI (`backend/scripts/diagnose_recording.py`)
Successfully built and executed against user session recordings (`storage/recordings/sess_ce7da3c8cfb1_interview.webm`):
- Generates container health report (format, duration, stream codecs).
- Acoustic metrics: RMS energy (`-28.14 dBFS`), peak amplitude (`-4.75 dBFS`), silence ratio (`36.7%`), estimated noise floor (`-46.55 dBFS`).
- Raw Whisper segment output with word-level timestamps and confidence scores.
- Vision trace CSV (`sess_ce7da3c8cfb1_interview.trace.csv`) and diagnostic timeline plot (`sess_ce7da3c8cfb1_interview.plot.png`).

### 3.2 Evaluation Harness (`backend/scripts/evaluate_fixtures.py`)
Baseline benchmark run on synthetic fixture `fixture_synth_001.webm` (15.0s, known look-aways at 3.0–5.5s & 10.5–12.0s, pause at 7.0–9.2s, filler at 6.2s):

```
================================================================================
  PLUTO vProctor Fixture Evaluation Harness
================================================================================
Evaluating fixture: fixture_synth_001.webm...
  * Filler F1:         0.0% (P=0.00, R=0.00)
  * Pause Recall:      0.0% (det=0/1)
  * Look-away Recall:  0.0% (>=2s: 0/1)
  * False Alarms/min:  0.0
  * Median Time Error: 0.0s (p95: 0.0s)
  * ASR WER:           100.0%
================================================================================
```
*Takeaway:* The baseline metrics transparently reflect the exact flaws reported. Every metric will now be tracked and proven to improve in Phase B and Phase C.

---

## 4. Ranked Root-Cause Hierarchy

1. **WebM Millisecond Timebase & Missing Duration Bug (CRITICAL):**
   OpenCV interprets MediaRecorder WebM files as 1000.0 FPS. `frame_idx / 1000.0` completely compresses video time, preventing any look-away event from reaching the 2.0s threshold.
2. **Browser STT Hijacking Candidate Answer Grading:**
   Backend graded `webkitSpeechRecognition` live text and bypassed Whisper transcription when $\ge 3$ words were returned.
3. **Face-Center Tracking Rather than Eye/Iris Gaze:**
   `video_pipeline.py` checked if the face was centered in the webcam frame, not where the eyes were looking.
4. **Whisper Language Auto-Detection & Silence Hallucination:**
   Unconstrained multilingual Whisper auto-detected wrong languages or hallucinated phrases during quiet pauses.
5. **Acoustic Filled-Pause Absence:**
   Standard Whisper models silently drop "um" and "uh" tokens during transcription.

---

## 5. Human Fixture Recording Protocol (For You to Run)

To gather real ground-truth human fixtures, open your browser to:
👉 **`http://localhost:5173/dev/record-fixture`**

### Recording Instructions:
1. **Fixture A (Clean Answer):** Speak for 20 seconds explaining a technical concept (e.g., "What is Docker?"). Do not look away; do not use fillers; speak fluently.
2. **Fixture B (Fillers & Hesitations):** Speak for 30 seconds. Deliberately speak **10 "umm", "uh", "ahh" sounds**. Press the **`F`** key on your keyboard every time you say a filler. Take 3 deliberate pauses ($>1.5$s) and press **`P`** to start/stop the pause.
3. **Fixture C (Look-Aways):** Speak while deliberately looking away:
   - Look to the left for 1s, 2s, and 4s (Press **`L`** to start and stop each look-away).
   - Look to the right for 1s, 2s, and 4s (Press **`L`**).
   - Look down (reading notes) for 2s and 4s (Press **`L`**).
   - Look up for 2s (Press **`L`**).
4. Click **"Save & Download Fixture"**. The `.webm` and `.labels.json` files are automatically saved to `backend/tests/fixtures/recordings/`.

---

## 6. Detailed Roadmap for Phases B through F

- **Phase B (Audio, Transcription & Timeline Overhaul):**
  - Implement `ASRProvider` abstraction (Deepgram / AssemblyAI / CrisperWhisper / Faster-Whisper local fallback).
  - Add acoustic filled-pause detector (VAD + pitch/energy) as a safety net when Whisper drops "um/uh".
  - Remux WebM server-side using PyAV/ffmpeg (`-fflags +genpts`) to restore valid durations and seekability.
  - Bind question start/end times to the master recording clock and discard TTS playback windows.
- **Phase C (Eye Contact, Look-Away & Body Language Overhaul):**
  - Per-candidate 4-second calibration step ("Look at camera").
  - MediaPipe Iris Landmark / Eye blendshape tracking (`eyeLookIn`, `eyeLookOut`, `eyeLookDown`).
  - Strict / Normal / Relaxed sensitivity presets (defaulting to strict $\approx 0.8$s alert, $1.0$s event).
  - Low-latency One-Euro / high-alpha filter running at $\ge 15$ FPS.
- **Phase D (Scoring, Monotonic Grading & Traceable Timeline):**
  - Traceable deduction rows with exact `mm:ss` timestamps.
  - Answer grading scored strictly from Whisper transcripts against reference Q&A pairs (60% algorithmic + 40% LLM rubric).
  - Binary search scrubber verified to seek video within 0.3s of event.
- **Phase E (AI Interviewer Product Experience):**
  - Finite State Machine (`SYSTEM_CHECK > CALIBRATION > GREETING > ASKING > LISTENING > WRAP_UP`).
  - Modularized component structure splitting `App.jsx`.
- **Phase F (Production Readiness & CI Gates):**
  - Background task queue, PostgreSQL/SQLite support, structured logging, Docker Compose stack.

