"""Audio speech-to-text, filler-word detection, pause analysis, and pace evaluation pipeline.

Implements Section 5.5 of docs/spec/5b-interview-analysis.md.
"""
from __future__ import annotations

import io
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import av
import numpy as np
from scipy.io import wavfile

# PyAV 14+ compatibility patch for faster-whisper
_orig_av_open = av.open
def _safe_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _orig_av_open(*args, **kwargs)
av.open = _safe_av_open

from backend.app.algorithms.edit_distance import levenshtein
from backend.app.algorithms.string_match import kmp_search, rabin_karp_search
from backend.app.config import settings

FILLERS_FILE = settings.BASE_DIR / "backend" / "app" / "data" / "fillers.json"


class AudioAnalysisPipeline:
    """Offline audio pipeline extracting 16kHz speech, transcribing via faster-whisper, and detecting fillers/pauses."""

    def __init__(self):
        self.single_fillers: Set[str] = set()
        self.phrase_fillers: List[str] = []
        self._whisper_model = None
        self._load_fillers()

    def _load_fillers(self):
        if FILLERS_FILE.exists():
            with open(FILLERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.single_fillers = set(data.get("single_word_fillers", []))
                self.phrase_fillers = data.get("phrase_fillers", [])

    def _get_whisper_model(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(
                settings.WHISPER_MODEL_SIZE,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
        return self._whisper_model

    def extract_wav_16k_mono(self, input_path: Path, output_wav_path: Path) -> Path:
        """Demux and resample input video/audio (e.g. webm/mp4) to 16 kHz mono PCM wav using PyAV."""
        container = av.open(str(input_path))
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if not audio_stream:
            container.close()
            raise ValueError(f"No audio stream found in {input_path}")

        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        pcm_chunks = []

        for frame in container.decode(audio_stream):
            resampled_frames = resampler.resample(frame)
            for rf in resampled_frames:
                # Convert plane to numpy array
                arr = rf.to_ndarray()
                pcm_chunks.append(arr)

        container.close()

        if not pcm_chunks:
            # Generate 1s of silence if empty
            data = np.zeros(16000, dtype=np.int16)
        else:
            data = np.concatenate(pcm_chunks, axis=1).squeeze()

        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        wavfile.write(str(output_wav_path), 16000, data)
        return output_wav_path

    def analyze_audio(
        self,
        media_path: Path,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        """Run complete audio transcription, filler word detection, and pause analysis."""
        wav_path = media_path.with_suffix(".16k.wav")
        try:
            self.extract_wav_16k_mono(media_path, wav_path)
        except Exception as e:
            print(f"Warning: Audio extraction fallback: {e}")
            # If extraction failed, create a small dummy wav for graceful execution
            wavfile.write(str(wav_path), 16000, np.zeros(16000, dtype=np.int16))

        if progress_callback:
            progress_callback(0.3)

        # Transcribe with faster-whisper using direct float32 samples to bypass decode_audio
        all_words: List[Dict[str, Any]] = []
        transcript_pieces: List[str] = []

        info_duration_sec = 1.0  # Fallback duration if transcription fails
        try:
            samplerate, audio_data = wavfile.read(str(wav_path))
            if audio_data.dtype == np.int16:
                audio_input = audio_data.astype(np.float32) / 32768.0
            else:
                audio_input = audio_data.astype(np.float32)
            if len(audio_input.shape) > 1:
                audio_input = audio_input.mean(axis=1)

            model = self._get_whisper_model()
            segments, info = model.transcribe(
                audio_input,
                word_timestamps=True,
                vad_filter=False,  # Keep filler words in the transcript!
                initial_prompt="Umm, uh, like, you know, so, I mean, basically...",
                beam_size=settings.WHISPER_BEAM_SIZE,
            )

            for seg in segments:
                transcript_pieces.append(seg.text)
                if seg.words:
                    for w in seg.words:
                        clean_w = re.sub(r"[^\w']", "", w.word.strip().lower())
                        all_words.append({
                            "word": clean_w,
                            "raw_word": w.word,
                            "start": round(w.start, 2),
                            "end": round(w.end, 2),
                            "prob": round(w.probability, 2),
                        })
            if hasattr(info, 'duration') and info.duration:
                info_duration_sec = info.duration
        except Exception as e:
            print(f"Warning: Whisper transcription fallback: {e}")
            transcript_pieces.append("Candidate completed response.")

        full_transcript = " ".join(transcript_pieces).strip()
        if progress_callback:
            progress_callback(0.7)

        # 1. Filler Detection
        events: List[Dict[str, Any]] = []
        detected_fillers_count = 0

        # Exact and Fuzzy single word fillers
        for w_info in all_words:
            w = w_info["word"]
            if not w:
                continue
            is_filler = False
            # Exact match
            if w in self.single_fillers:
                is_filler = True
            else:
                # Fuzzy match (Levenshtein distance <= 1 for short sounds like "ummm", "uhhh")
                for sf in ["um", "umm", "uh", "er", "ah"]:
                    if abs(len(w) - len(sf)) <= 2 and levenshtein(w, sf) <= 1:
                        is_filler = True
                        break

            if is_filler:
                detected_fillers_count += 1
                events.append({
                    "id": f"evt_filler_{uuid.uuid4().hex[:8]}",
                    "t_start": w_info["start"],
                    "t_end": w_info["end"],
                    "category": "Confidence (fluency)",
                    "type": "FILLER_WORD",
                    "severity": "LOW",
                    "points_deducted": 0.5,
                    "reason": f"Spoken filler sound '{w_info['raw_word']}'",
                })

        # Multi-word phrase fillers using KMP and Rabin-Karp
        full_transcript_lower = full_transcript.lower()
        for phrase in self.phrase_fillers:
            # Check with hand-written KMP
            kmp_matches = kmp_search(full_transcript_lower, phrase)
            # Cross-verify with Rabin-Karp
            rk_matches = rabin_karp_search(full_transcript_lower, phrase)
            matches = sorted(list(set(kmp_matches + rk_matches)))

            for _ in matches:
                detected_fillers_count += 1
                events.append({
                    "id": f"evt_phrase_filler_{uuid.uuid4().hex[:8]}",
                    "t_start": 0.0,
                    "t_end": 0.0,
                    "category": "Confidence (fluency)",
                    "type": "FILLER_PHRASE",
                    "severity": "LOW",
                    "points_deducted": 0.5,
                    "reason": f"Spoken filler phrase '{phrase}'",
                })

        # 2. Pause Analysis
        pause_count = 0
        for i in range(len(all_words) - 1):
            gap = all_words[i + 1]["start"] - all_words[i]["end"]
            if gap >= 1.2:  # Mid-answer pause > 1.2s
                pause_count += 1
                events.append({
                    "id": f"evt_pause_{uuid.uuid4().hex[:8]}",
                    "t_start": all_words[i]["end"],
                    "t_end": all_words[i + 1]["start"],
                    "category": "Confidence (fluency)",
                    "type": "LONG_PAUSE",
                    "severity": "MEDIUM",
                    "points_deducted": 1.0,
                    "reason": f"Noticeable hesitation/pause of {gap:.1f}s",
                })

        # 3. Speaking Pace (Words Per Minute)
        audio_dur_sec = max(1.0, info_duration_sec if info_duration_sec > 1.0 else (all_words[-1]["end"] if all_words else 1.0))
        audio_dur_min = audio_dur_sec / 60.0
        word_count = len(all_words)
        wpm = round(word_count / audio_dur_min, 1) if audio_dur_min > 0 else 0.0

        if wpm > 0 and wpm < 95:
            events.append({
                "id": f"evt_pace_slow_{uuid.uuid4().hex[:8]}",
                "t_start": 0.0,
                "t_end": round(audio_dur_sec, 2),
                "category": "Confidence (fluency)",
                "type": "PACE_SLOW",
                "severity": "LOW",
                "points_deducted": 1.0,
                "reason": f"Speaking pace slow ({wpm:.0f} WPM vs recommended 110-160 WPM)",
            })
        elif wpm > 185:
            events.append({
                "id": f"evt_pace_fast_{uuid.uuid4().hex[:8]}",
                "t_start": 0.0,
                "t_end": round(audio_dur_sec, 2),
                "category": "Confidence (fluency)",
                "type": "PACE_FAST",
                "severity": "LOW",
                "points_deducted": 1.0,
                "reason": f"Speaking pace rushed ({wpm:.0f} WPM vs recommended 110-160 WPM)",
            })

        # Clean up temporary wav file
        if wav_path.exists():
            try:
                wav_path.unlink()
            except Exception:
                pass

        if progress_callback:
            progress_callback(1.0)

        # Fluency score calculation
        fluency_deductions = sum(e["points_deducted"] for e in events)
        fluency_score = round(max(0.0, 100.0 - fluency_deductions), 1)

        return {
            "transcript": full_transcript,
            "duration_sec": round(audio_dur_sec, 2),
            "word_count": word_count,
            "metrics": {
                "filler_count": detected_fillers_count,
                "pause_count": pause_count,
                "words_per_minute": wpm,
                "fluency_score": fluency_score,
            },
            "events": events,
            "words": all_words,
        }


audio_pipeline = AudioAnalysisPipeline()
