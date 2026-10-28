"""Phase B Unit and Integration Tests: ASR, Fillers, Pauses, Pace, and Disfluency Engine."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from scipy.io import wavfile

from backend.app.pipelines.asr import (
    ASRProvider, Segment, TranscriptionResult, Word, WordSource,
)
from backend.app.pipelines.asr.registry import get_asr_provider
from backend.app.pipelines.acoustic_filler import (
    compute_energy_frames, compute_spectral_flux, detect_acoustic_fillers,
)
from backend.app.pipelines.audio_pipeline import AudioAnalysisPipeline
from backend.app.pipelines.disfluency_engine import DisfluencyEngine


def test_asr_registry_auto_fallback():
    """Verify registry selects faster_whisper when no cloud API keys are present."""
    with patch.dict("os.environ", {}, clear=True):
        provider = get_asr_provider(preferred="auto")
        assert provider.name == "faster_whisper"
        assert provider.is_available() is True


def test_asr_registry_explicit_provider():
    """Verify registry respects preferred argument."""
    with patch.dict("os.environ", {"DEEPGRAM_API_KEY": "test_key"}):
        provider = get_asr_provider(preferred="deepgram")
        assert provider.name == "deepgram"
        assert provider.is_available() is True


def test_disfluency_engine_hard_fillers():
    """Verify exact and fuzzy detection of hard fillers ('um', 'uh', 'umm', 'err')."""
    engine = DisfluencyEngine()
    assert engine.is_hard_filler("um") is True
    assert engine.is_hard_filler("umm") is True
    assert engine.is_hard_filler("uh") is True
    assert engine.is_hard_filler("ahh") is True
    assert engine.is_hard_filler("hmm") is True
    assert engine.is_hard_filler("kubernetes") is False
    assert engine.is_hard_filler("python") is False


def test_disfluency_engine_soft_filler_context():
    """Verify context rules distinguish 'like' as verb/comparison from hesitation filler."""
    engine = DisfluencyEngine()

    # Case 1: "I like python" -> 'like' is verb, NOT filler
    words_verb = [
        Word(text="i", start=1.0, end=1.2),
        Word(text="like", start=1.25, end=1.5),
        Word(text="python", start=1.55, end=1.9),
    ]
    is_filler, reason = engine.is_soft_filler(1, words_verb)
    assert is_filler is False
    assert reason == "verb_usage"

    # Case 2: "looks like an error" -> 'like' is comparison, NOT filler
    words_comp = [
        Word(text="looks", start=1.0, end=1.3),
        Word(text="like", start=1.32, end=1.5),
        Word(text="an", start=1.52, end=1.6),
    ]
    is_filler, reason = engine.is_soft_filler(1, words_comp)
    assert is_filler is False
    assert reason == "comparison_usage"

    # Case 3: "...pause... like ...pause..." -> 'like' is hesitation filler
    words_filler = [
        Word(text="well", start=1.0, end=1.3),
        Word(text="like", start=2.0, end=2.3),  # 0.7s gap before
        Word(text="we", start=3.0, end=3.2),    # 0.7s gap after
    ]
    is_filler, reason = engine.is_soft_filler(1, words_filler)
    assert is_filler is True
    assert reason == "hesitation_like"


def test_disfluency_engine_phrase_filler_kmp():
    """Verify multi-word phrase fillers detected via KMP search."""
    engine = DisfluencyEngine()
    words = [
        Word(text="in", start=1.0, end=1.2),
        Word(text="my", start=1.25, end=1.4),
        Word(text="view", start=1.45, end=1.7),
        Word(text="you", start=2.0, end=2.2),
        Word(text="know", start=2.25, end=2.5),
        Word(text="it", start=2.6, end=2.8),
        Word(text="works", start=2.85, end=3.1),
    ]
    phrase_events = engine.detect_phrase_fillers(words)
    assert len(phrase_events) >= 1
    assert any(pe.text.lower() == "you know" for pe in phrase_events)
    assert phrase_events[0].start == 2.0
    assert phrase_events[0].end == 2.5


def test_disfluency_engine_pause_detection_and_pacing():
    """Verify pause categorization (hesitation vs long pause) and WPM pace."""
    engine = DisfluencyEngine()
    words = [
        Word(text="first", start=1.0, end=1.5),
        # Gap of 0.8s: hesitation
        Word(text="second", start=2.3, end=2.8),
        # Gap of 1.5s: long pause
        Word(text="third", start=4.3, end=4.8),
    ]
    result = engine.analyze(words)
    assert result.hesitation_count == 1
    assert result.long_pause_count == 1
    assert result.total_pause_duration >= 2.0

    pause_events = [e for e in result.events if e.event_type == "pause"]
    assert len(pause_events) == 2
    types = [e.sub_type for e in pause_events]
    assert "hesitation" in types
    assert "long_pause" in types


def test_tts_window_filtering():
    """Verify words spoken during interviewer TTS playback are stripped."""
    words = [
        Word(text="welcome", start=1.0, end=1.8),     # Inside TTS window [0.5, 3.0]
        Word(text="candidate", start=2.0, end=2.8),   # Inside TTS window [0.5, 3.0]
        Word(text="thank", start=3.5, end=3.8),       # Candidate answer
        Word(text="you", start=3.85, end=4.1),        # Candidate answer
    ]
    tts_windows = [(0.5, 3.0)]
    filtered = AudioAnalysisPipeline.filter_tts_windows(words, tts_windows)
    assert len(filtered) == 2
    assert [w.text for w in filtered] == ["thank", "you"]


def test_acoustic_energy_and_flux_computation(tmp_path):
    """Verify acoustic energy and spectral flux computation on synthetic audio."""
    sr = 16000
    duration_sec = 1.0
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # Sine wave 440 Hz
    samples = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    energies, timestamps = compute_energy_frames(samples, sr)
    assert len(energies) > 0
    assert np.mean(energies) > 0.1

    flux = compute_spectral_flux(samples, sr)
    assert len(flux) > 0
    # Pure tone has low spectral flux
    assert np.mean(flux) < 0.20

