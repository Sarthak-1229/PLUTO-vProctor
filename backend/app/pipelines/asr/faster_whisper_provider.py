"""Faster-Whisper local ASR provider for PLUTO vProctor.

Runs entirely offline on CPU (or CUDA if available). Forced English,
filler-preserving prompt, silence hallucination suppression.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.io import wavfile

from backend.app.config import settings
from backend.app.pipelines.asr import (
    ASRProvider, Segment, TranscriptionResult, Word, WordSource,
)

# Default filler-rich prompt that biases Whisper to preserve disfluencies
_DEFAULT_FILLER_PROMPT = (
    "Umm, uh, ahh, like, you know, so, basically, I mean... "
    "Hmm, let me think about that. Er, well..."
)


class FasterWhisperASRProvider(ASRProvider):
    """Local offline Faster-Whisper provider with filler preservation."""

    def __init__(self):
        self._model = None

    @property
    def name(self) -> str:
        return "faster_whisper"

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                settings.WHISPER_MODEL_SIZE,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        keywords: Optional[List[str]] = None,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio with forced English and filler-preserving settings."""
        # Load audio
        sr, audio_data = wavfile.read(str(audio_path))
        if audio_data.dtype == np.int16:
            samples = audio_data.astype(np.float32) / 32768.0
        else:
            samples = audio_data.astype(np.float32)
        if len(samples.shape) > 1:
            samples = samples.mean(axis=1)

        duration_sec = len(samples) / float(sr)

        # Build prompt with keywords if available
        prompt = initial_prompt or _DEFAULT_FILLER_PROMPT
        if keywords:
            kw_str = ", ".join(keywords[:20])
            prompt = f"{prompt} Technical terms: {kw_str}."

        model = self._get_model()

        # Transcribe with settings tuned for filler preservation
        raw_segments, info = model.transcribe(
            samples,
            language=language,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=prompt,
            beam_size=settings.WHISPER_BEAM_SIZE,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
        )

        segments: List[Segment] = []
        all_words: List[Word] = []
        full_text_parts: List[str] = []

        # Compute frame-level energy for hallucination suppression
        frame_energies = self._compute_frame_energies(samples, sr)

        for seg in raw_segments:
            # Suppress hallucinated segments on silence
            if seg.no_speech_prob > 0.6:
                seg_start_sample = int(seg.start * sr)
                seg_end_sample = min(int(seg.end * sr), len(samples))
                if seg_end_sample > seg_start_sample:
                    seg_energy = np.sqrt(np.mean(samples[seg_start_sample:seg_end_sample] ** 2))
                    if seg_energy < 0.005:  # ~-46 dBFS, near silence
                        continue

            seg_words: List[Word] = []
            if seg.words:
                for w in seg.words:
                    clean_text = re.sub(r"[^\w']", "", w.word.strip().lower())
                    word = Word(
                        text=clean_text,
                        start=round(w.start, 3),
                        end=round(w.end, 3),
                        confidence=round(w.probability, 3),
                        source=WordSource.ASR,
                    )
                    seg_words.append(word)
                    all_words.append(word)

            segment = Segment(
                text=seg.text.strip(),
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                words=seg_words,
                avg_logprob=round(seg.avg_logprob, 3),
                no_speech_prob=round(seg.no_speech_prob, 3),
                language=language,
            )
            segments.append(segment)
            full_text_parts.append(seg.text.strip())

        return TranscriptionResult(
            segments=segments,
            full_text=" ".join(full_text_parts),
            words=all_words,
            duration_sec=round(duration_sec, 2),
            provider_name=self.name,
            metadata={
                "model_size": settings.WHISPER_MODEL_SIZE,
                "device": settings.WHISPER_DEVICE,
                "compute_type": settings.WHISPER_COMPUTE_TYPE,
            },
        )

    @staticmethod
    def _compute_frame_energies(
        samples: np.ndarray, sr: int, frame_ms: int = 30
    ) -> np.ndarray:
        """Compute RMS energy per frame for silence detection."""
        frame_len = int(sr * frame_ms / 1000)
        n_frames = max(1, len(samples) // frame_len)
        energies = np.zeros(n_frames)
        for i in range(n_frames):
            chunk = samples[i * frame_len : (i + 1) * frame_len]
            energies[i] = np.sqrt(np.mean(chunk ** 2))
        return energies

