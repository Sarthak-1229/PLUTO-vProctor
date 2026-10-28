"""Audio speech-to-text, filler-word detection, pause analysis, and pace evaluation pipeline.

Integrates ASRProvider (FasterWhisper, Deepgram, AssemblyAI), acoustic filled-pause detector,
TTS window exclusion, and DisfluencyEngine.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import av
import numpy as np
from scipy.io import wavfile

# PyAV 14+ compatibility patch for faster-whisper / audio decoding
_orig_av_open = av.open
def _safe_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _orig_av_open(*args, **kwargs)
av.open = _safe_av_open

from backend.app.config import settings
from backend.app.pipelines.acoustic_filler import detect_acoustic_fillers
from backend.app.pipelines.asr import TranscriptionResult, Word, WordSource
from backend.app.pipelines.asr.registry import get_asr_provider
from backend.app.pipelines.disfluency_engine import DisfluencyEngine


class AudioAnalysisPipeline:
    """Audio pipeline extracting 16kHz speech, transcribing via ASR provider,

    detecting acoustic + lexical fillers, pauses, and pacing.
    """

    def __init__(self):
        self.disfluency_engine = DisfluencyEngine()

    @property
    def single_fillers(self) -> Set[str]:
        return self.disfluency_engine.hard_fillers | self.disfluency_engine.soft_fillers

    @property
    def phrase_fillers(self) -> List[str]:
        return self.disfluency_engine.phrase_fillers

    def extract_wav_16k_mono(self, input_path: Path, output_wav_path: Path) -> Path:
        """Demux and resample input media (webm/mp4) to 16 kHz mono PCM WAV using PyAV."""
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
                pcm_chunks.append(rf.to_ndarray())

        container.close()

        if not pcm_chunks:
            data = np.zeros(16000, dtype=np.int16)
        else:
            data = np.concatenate(pcm_chunks, axis=1).squeeze()

        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        wavfile.write(str(output_wav_path), 16000, data)
        return output_wav_path

    @staticmethod
    def filter_tts_windows(
        words: List[Word],
        tts_windows: Optional[List[Tuple[float, float]]] = None,
    ) -> List[Word]:
        """Exclude words that fall within TTS output playback windows (interviewer voice pickup)."""
        if not tts_windows:
            return words

        filtered: List[Word] = []
        for w in words:
            in_tts = False
            for tts_start, tts_end in tts_windows:
                # If word overlaps significantly (>50% of word duration) with TTS window
                inter_s = max(w.start, tts_start)
                inter_e = min(w.end, tts_end)
                if inter_e > inter_s:
                    overlap_dur = inter_e - inter_s
                    w_dur = max(0.001, w.end - w.start)
                    if (overlap_dur / w_dur) > 0.5:
                        in_tts = True
                        break
            if not in_tts:
                filtered.append(w)
        return filtered

    def analyze_audio(
        self,
        media_path: Path,
        *,
        tts_windows: Optional[List[Tuple[float, float]]] = None,
        keywords: Optional[List[str]] = None,
        question_segments: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        """Run complete audio transcription, filler word detection, pause analysis, and pace scoring.

        Args:
            media_path: Path to WebM/MP4 recording or WAV.
            tts_windows: List of (start_sec, end_sec) when AI interviewer was speaking.
            keywords: Technical domain keywords for ASR boosting.
            question_segments: Optional list of {'id': ..., 'start': ..., 'end': ...} question time windows.
            progress_callback: Progress indicator callback.

        Returns:
            Structured dictionary matching scoring engine and report requirements.
        """
        wav_path = media_path.with_suffix(".16k.wav")
        try:
            self.extract_wav_16k_mono(media_path, wav_path)
        except Exception as e:
            print(f"Warning: Audio extraction fallback: {e}")
            wavfile.write(str(wav_path), 16000, np.zeros(16000, dtype=np.int16))

        if progress_callback:
            progress_callback(0.2)

        # 1. Transcribe with active ASR provider
        provider = get_asr_provider()
        asr_result: TranscriptionResult = provider.transcribe(
            wav_path,
            language="en",
            keywords=keywords,
        )

        if progress_callback:
            progress_callback(0.5)

        # 2. Filter out words spoken during interviewer TTS playback
        clean_asr_words = self.filter_tts_windows(asr_result.words, tts_windows)

        # 3. Acoustic filled-pause detection (catches nasal 'um', 'uh' normalized by ASR)
        acoustic_fillers: List[Word] = []
        try:
            acoustic_fillers = detect_acoustic_fillers(wav_path, clean_asr_words)
            # Filter acoustic fillers against TTS windows as well
            acoustic_fillers = self.filter_tts_windows(acoustic_fillers, tts_windows)
        except Exception as e:
            print(f"Warning: Acoustic filler detection failed: {e}")

        if progress_callback:
            progress_callback(0.7)

        # 4. Disfluency & fluency analysis
        disfluency_res = self.disfluency_engine.analyze(
            clean_asr_words,
            acoustic_fillers,
        )

        # Map disfluency events to proctoring / report event format
        events: List[Dict[str, Any]] = []
        for ev in disfluency_res.events:
            sev = "LOW"
            if ev.event_type == "late_start" or ev.sub_type == "long_pause":
                sev = "MEDIUM"
            elif ev.deduction >= 1.5:
                sev = "HIGH"

            # Use standard event types compatible with both scoring engine and fixtures
            if ev.event_type == "filler":
                ev_type = "FILLER_PHRASE" if ev.sub_type == "phrase" else "FILLER_WORD"
            elif ev.event_type == "pause":
                ev_type = "LONG_PAUSE" if ev.sub_type == "long_pause" else "HESITATION"
            elif ev.event_type == "late_start":
                ev_type = "LATE_START"
            elif ev.event_type == "pace":
                ev_type = f"PACE_{ev.sub_type.upper()}"
            else:
                ev_type = f"{ev.event_type.upper()}_{ev.sub_type.upper()}"

            ev_dict = {
                "id": f"evt_{ev.event_type}_{uuid.uuid4().hex[:8]}",
                "t_start": ev.start,
                "t_end": ev.end,
                "category": "Confidence (fluency)",
                "type": ev_type,
                "sub_type": ev.sub_type,
                "severity": sev,
                "points_deducted": ev.deduction,
                "reason": ev.reason,
                "question_id": ev.question_id,
            }
            events.append(ev_dict)

        # Build word dicts for downstream consumers
        word_dicts = [
            {
                "word": w.text,
                "raw_word": w.text,
                "start": w.start,
                "end": w.end,
                "prob": w.confidence,
                "is_filler": w.is_filler,
                "filler_type": w.filler_type,
                "source": w.source.value,
            }
            for w in disfluency_res.words
        ]

        # Reconstruct authoritative transcript from non-acoustic words
        full_transcript = " ".join(
            w.text for w in disfluency_res.words if w.source != WordSource.ACOUSTIC
        ).strip()
        if not full_transcript and asr_result.full_text:
            full_transcript = asr_result.full_text

        # Fluency score (starts at 100, deducted by disfluency_res.total_deduction)
        fluency_score = round(max(0.0, 100.0 - disfluency_res.total_deduction), 1)

        # Clean up temporary WAV file
        if wav_path.exists():
            try:
                wav_path.unlink()
            except Exception:
                pass

        if progress_callback:
            progress_callback(1.0)

        total_duration = asr_result.duration_sec
        if total_duration <= 0.0 and disfluency_res.words:
            total_duration = disfluency_res.words[-1].end

        return {
            "transcript": full_transcript,
            "duration_sec": round(total_duration, 2),
            "word_count": disfluency_res.word_count,
            "provider_name": provider.name,
            "metrics": {
                "filler_count": (
                    disfluency_res.hard_filler_count
                    + disfluency_res.soft_filler_count
                    + disfluency_res.phrase_filler_count
                    + disfluency_res.acoustic_filler_count
                ),
                "hard_filler_count": disfluency_res.hard_filler_count,
                "soft_filler_count": disfluency_res.soft_filler_count,
                "phrase_filler_count": disfluency_res.phrase_filler_count,
                "acoustic_filler_count": disfluency_res.acoustic_filler_count,
                "pause_count": disfluency_res.hesitation_count + disfluency_res.long_pause_count,
                "hesitation_count": disfluency_res.hesitation_count,
                "long_pause_count": disfluency_res.long_pause_count,
                "total_pause_duration": disfluency_res.total_pause_duration,
                "words_per_minute": disfluency_res.pace_wpm,
                "pace_band": disfluency_res.pace_band,
                "fluency_score": fluency_score,
                "fillers_per_minute": disfluency_res.fillers_per_minute,
            },
            "events": events,
            "words": word_dicts,
            "disfluency_summary": disfluency_res.to_dict(),
        }


audio_pipeline = AudioAnalysisPipeline()
