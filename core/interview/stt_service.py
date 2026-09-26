"""
STT service for PLUTO vProctor (resident faster-whisper, CPU-only).

Differs from core/audio_stt.py in two ways that the interview mode needs:
  1. The model is loaded ONCE and kept resident (a full interview is many
     answers; reloading "small" per answer wastes seconds each time).
  2. It returns word-level timings + DESCRIPTIVE delivery signals (speaking
     rate, filler rate, long-pause count) alongside the transcript.

CONTENT vs DELIVERY invariant (from the plan): the metrics returned here are
DESCRIPTIVE only. They populate the final practice report; they are NEVER fed
into the difficulty/FSM engine, which reads the CONTENT score S alone.

Stays on CPU (config.FORCE_STT_CPU) so the resident qwen2.5:7b keeps the GPU.
"""
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from faster_whisper import WhisperModel

from core import config

logger = logging.getLogger(__name__)

# Nudge Whisper to keep disfluencies verbatim instead of silently cleaning them
# up — we need "um"/"uh" for the filler-rate delivery signal.
FILLER_INITIAL_PROMPT = "Um, uh, you know, like, I mean, so, basically, actually, er."

# Surface forms counted as fillers (word-boundary matched, case-insensitive).
FILLER_WORDS = {"um", "uh", "er", "erm", "hmm", "like", "basically", "actually",
                "literally", "so", "well"}
FILLER_PHRASES = ["you know", "i mean", "kind of", "sort of"]

# A gap between words longer than this (seconds) counts as a "long pause".
LONG_PAUSE_SEC = 1.5


@dataclass
class DeliverySignals:
    """DESCRIPTIVE speech-delivery metrics. Never used to adapt difficulty."""
    duration_sec: float = 0.0
    word_count: int = 0
    words_per_minute: float = 0.0
    filler_count: int = 0
    filler_rate_per_min: float = 0.0
    long_pause_count: int = 0
    mean_gap_sec: float = 0.0


@dataclass
class Transcription:
    text: str = ""
    language: Optional[str] = None
    delivery: DeliverySignals = field(default_factory=DeliverySignals)
    words: List[dict] = field(default_factory=list)  # [{word, start, end}, ...]


class STTService:
    """Resident CPU faster-whisper wrapper with word timings + delivery signals."""

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or config.STT_MODEL_SIZE
        self._model: Optional[WhisperModel] = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            # int8 on CPU keeps RAM low and leaves all 6GB VRAM for the LLM.
            logger.info("Loading resident Whisper '%s' on CPU (int8)", self.model_size)
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: str) -> Transcription:
        """Transcribe an answer clip and derive descriptive delivery signals."""
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._ensure_model()
        segments, info = model.transcribe(
            audio_path,
            word_timestamps=True,
            initial_prompt=FILLER_INITIAL_PROMPT,
        )

        words: List[dict] = []
        text_parts: List[str] = []
        for seg in segments:
            text_parts.append(seg.text)
            for w in (seg.words or []):
                words.append({"word": w.word, "start": w.start, "end": w.end})

        text = " ".join(t.strip() for t in text_parts).strip()
        text = re.sub(r"\s+", " ", text)
        delivery = self._delivery_signals(text, words)
        return Transcription(text=text, language=getattr(info, "language", None),
                             delivery=delivery, words=words)

    @staticmethod
    def _delivery_signals(text: str, words: List[dict]) -> DeliverySignals:
        sig = DeliverySignals()
        tokens = [w["word"].strip().lower().strip(".,!?;:") for w in words]
        tokens = [t for t in tokens if t]
        sig.word_count = len(tokens)

        # Duration from word timings when available, else 0.
        if words:
            start = words[0].get("start") or 0.0
            end = words[-1].get("end") or 0.0
            sig.duration_sec = max(0.0, end - start)

        if sig.duration_sec > 0:
            sig.words_per_minute = round(sig.word_count / sig.duration_sec * 60.0, 1)

        # Filler words + phrases.
        filler = sum(1 for t in tokens if t in FILLER_WORDS)
        low = " " + text.lower() + " "
        for phrase in FILLER_PHRASES:
            filler += low.count(" " + phrase + " ")
        sig.filler_count = filler
        if sig.duration_sec > 0:
            sig.filler_rate_per_min = round(filler / sig.duration_sec * 60.0, 1)

        # Inter-word gaps -> long-pause count + mean gap.
        gaps = []
        for prev, cur in zip(words, words[1:]):
            gap = (cur.get("start") or 0.0) - (prev.get("end") or 0.0)
            if gap > 0:
                gaps.append(gap)
        if gaps:
            sig.long_pause_count = sum(1 for g in gaps if g >= LONG_PAUSE_SEC)
            sig.mean_gap_sec = round(sum(gaps) / len(gaps), 3)

        return sig


# Singleton, mirroring the other interview services.
_stt_instance: Optional[STTService] = None


def get_stt_service() -> STTService:
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = STTService()
    return _stt_instance
