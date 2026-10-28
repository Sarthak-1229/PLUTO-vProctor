"""ASR Provider abstraction for PLUTO vProctor.

Defines a unified interface for speech-to-text engines with word-level timestamps,
filler detection, and technical keyword hints.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class WordSource(str, Enum):
    ASR = "asr"
    ACOUSTIC = "acoustic"
    MERGED = "merged"


@dataclass
class Word:
    """A single transcribed word with timing, confidence and filler flag."""
    text: str
    start: float  # seconds on the recording clock
    end: float
    confidence: float = 1.0
    is_filler: bool = False
    filler_type: Optional[str] = None  # "hard", "soft", "phrase", "acoustic"
    source: WordSource = WordSource.ASR


@dataclass
class Segment:
    """A transcription segment (usually one utterance or sentence)."""
    text: str
    start: float
    end: float
    words: List[Word] = field(default_factory=list)
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    language: str = "en"


@dataclass
class TranscriptionResult:
    """Complete result from an ASR provider for a single audio segment."""
    segments: List[Segment] = field(default_factory=list)
    full_text: str = ""
    words: List[Word] = field(default_factory=list)
    duration_sec: float = 0.0
    provider_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def word_count(self) -> int:
        return len([w for w in self.words if w.text.strip()])


class ASRProvider(ABC):
    """Abstract base class for speech-to-text providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string."""
        ...

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str = "en",
        keywords: Optional[List[str]] = None,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file and return word-level results.

        Args:
            audio_path: Path to a 16 kHz mono WAV file.
            language: BCP-47 language code.
            keywords: Technical terms to boost recognition accuracy.
            initial_prompt: Contextual prompt to guide the model.

        Returns:
            TranscriptionResult with word-level timestamps and confidence.
        """
        ...

    def is_available(self) -> bool:
        """Check if this provider is configured and ready to use."""
        return True

