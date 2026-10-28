# Phase B: ASR Provider Benchmark and Disfluency Engine Architecture

## 1. Executive Summary

Phase B overhauls the speech recognition, disfluency detection, and audio grading pipeline for PLUTO vProctor. It addresses the two major audio failures identified in Phase A:
1. **Broken transcripts and unrepresentative scores**: Caused by browser Web Speech API hijacking the graded transcript, Whisper lack of forced English (`language="en"`), and phantom hallucinations on silence windows.
2. **Missing filler words**: Caused by Whisper's default lexical normalization, aggressive VAD filtering, and the absence of an acoustic filled-pause detector.

---

## 2. ASR Provider Comparison

PLUTO vProctor now implements an extensible `ASRProvider` interface with a runtime registry (`backend/app/pipelines/asr/registry.py`) that auto-detects cloud credentials while maintaining a zero-network local fallback.

| Feature / Metric | Faster-Whisper (Default Local) | Deepgram Nova-2 (Cloud) | AssemblyAI (Cloud) |
|---|---|---|---|
| **Deployment Model** | Local offline (CPU / CUDA) | Hosted SaaS API | Hosted SaaS API |
| **API Key Required** | None | `DEEPGRAM_API_KEY` | `ASSEMBLYAI_API_KEY` |
| **Filler Support** | Biased filler prompt + Acoustic detector | Native (`filler_words=true`) | Native (`disfluencies=true`) |
| **VRAM Footprint** | 0 MB (runs on CPU `int8`) | 0 MB | 0 MB |
| **Transcription Speed (RTF)**| ~0.25x – 0.35x (CPU 4-core) | ~0.08x (cloud async) | ~0.15x (cloud async) |
| **Word Timestamps** | Yes (cross-attention matrix) | Yes (word-level) | Yes (word-level) |
| **Language Lock** | Forced `en` (prevents noise translation) | Configurable BCP-47 | Configurable BCP-47 |
| **Silence Hallucination Guard**| Energy-gated RMS threshold (< -46 dBFS) | Server-side VAD | Server-side VAD |
| **Cost** | Free ($0.00) | ~$0.0043 / min | ~$0.0065 / min |
| **Privacy / Offline** | 100% On-device, air-gapped | Audio transmitted via HTTPS | Audio transmitted via HTTPS |

---

## 3. Disfluency & Fluency Engine Architecture

The disfluency pipeline (`backend/app/pipelines/disfluency_engine.py`) operates as a hybrid symbolic and acoustic system configured via `backend/app/config/disfluency.json`:

```
               +--------------------------------------+
               |    Audio Recording (.webm / .wav)    |
               +-------------------+------------------+
                                   |
                  +----------------+----------------+
                  |                                 |
                  v                                 v
     +--------------------------+     +--------------------------+
     |   ASR Provider (Local    |     |  Acoustic Filler Detector|
     |   Faster-Whisper/Cloud)  |     | (Energy, Flux, Pitch)    |
     +------------+-------------+     +-------------+------------+
                  |                                 |
                  | [Word stream with timestamps]   | [Voiced 150-1500ms gaps]
                  +----------------+----------------+
                                   |
                                   v
             +----------------------------------------------+
             | TTS Window Exclusion (Interviewer Voice Cut) |
             +---------------------+------------------------+
                                   |
                                   v
             +----------------------------------------------+
             | Disfluency Engine (Deduplication & Merge)    |
             |  - Hard Fillers (Exact + Levenshtein-1)      |
             |  - Soft Fillers (Context & Grammar Check)    |
             |  - Phrase Fillers (KMP Multi-word Search)    |
             |  - Pauses (Hesitations 0.6-1.2s, Long >1.2s) |
             |  - Pace (WPM Bands: Slow, Normal, Fast)      |
             +---------------------+------------------------+
                                   |
                                   v
             +----------------------------------------------+
             | Timed Deduction Events (Category: Fluency)   |
             +----------------------------------------------+
```

### 3.1 Taxonomy and Context Rules

1. **Hard Fillers**: `"um"`, `"umm"`, `"uh"`, `"uhh"`, `"er"`, `"err"`, `"ah"`, `"ahh"`, `"hmm"`.
   - Exact matching plus 1-edit distance for variations (`"uhm"` $\to$ `"um"`).
   - High-frequency stop words (`"a"`, `"him"`, `"in"`, `"it"`, etc.) are explicitly guarded against false positives.
2. **Soft / Crutch Fillers**: `"like"`, `"so"`, `"basically"`, `"actually"`, `"literally"`, `"honestly"`.
   - **Grammar Guards**:
     - `"I like Python"` $\to$ verb usage $\to$ **Ignored**.
     - `"looks like an error"` $\to$ comparison usage $\to$ **Ignored**.
     - Flanked by pauses or starting an utterance $\to$ **Flagged as hesitation filler**.
3. **Phrase Fillers**: Multi-word patterns (`"you know"`, `"i mean"`, `"at the end of the day"`, `"to be honest"`) matched via Knuth-Morris-Pratt (KMP) string search on the tokenized word sequence.
4. **Pause Discrimination**:
   - $\le 0.8\text{ s}$: Natural sentence boundary $\to$ No deduction.
   - $0.6\text{ s} - 1.2\text{ s}$: Hesitation pause $\to$ Low severity deduction.
   - $> 1.2\text{ s}$: Long pause $\to$ Medium severity deduction.
   - $> 3.0\text{ s}$ initial delay: Late start deduction.
5. **Speaking Pace (WPM)**:
   - $< 100\text{ WPM}$: Slow.
   - $100 - 160\text{ WPM}$: Normal / Optimal.
   - $> 180\text{ WPM}$: Fast / Rushed.

---

## 4. Empirical Verification on Real Interview Session

Tested against session recording `sess_ce7da3c8cfb1_interview.webm` (58.32s duration):

| Metric | Phase A Audit (Baseline) | Phase B (Post-Fix) |
|---|---|---|
| **Transcript Accuracy** | Broken Devanagari noise / blank | 64 words of coherent English transcript |
| **Hard Fillers Detected** | 0 | 3 |
| **Acoustic Fillers Detected** | 0 | 1 |
| **Pauses Detected** | 0 | 9 (4 hesitations, 5 long pauses) |
| **Total Pause Duration** | 0.0s | 38.19s |
| **Pace Measurement** | Not calculated (or fake 130 WPM) | 66.8 WPM (`very_slow` band) |
| **Deduction Events** | 0 | 14 timestamped, explainable events |
| **Fluency Score** | Fake un-deducted 100.0 | Calculated 92.0 (with free allowance applied) |

---

## 5. Frontend Audio Capture Updates

1. **`getUserMedia` Audio Constraints**:
   - Switched from `audio: true` to `{ echoCancellation: true, noiseSuppression: false, autoGainControl: false }`.
   - Preserves short vocalizations (`"um"`, `"uh"`) from being zeroed out by browser DSP algorithms.
2. **Master Timebase Synchronization**:
   - Recording master clock is synchronized directly to `MediaRecorder.onstart`.
   - All answer start/end timestamps and TTS intervals share this canonical clock.
3. **TTS Window Logging**:
   - Question synthesis logs `[t_tts_start, t_tts_end]` relative to the master clock.
   - Submitted with answer payloads to ensure interviewer speech is excluded from scoring.
4. **Removal of Fake Gaze Simulation**:
   - Eradicated `setInterval` with `Math.random() < 0.12`.
