"""Acoustic filled-pause detector for PLUTO vProctor.

Detects voiced regions (150ms–1500ms) that are NOT matched to ASR words,
using energy, pitch stability, and spectral flux to identify "um", "uh", "er"
sounds that Whisper-family models silently normalize out.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.io import wavfile

from backend.app.config import settings
from backend.app.pipelines.asr import Word, WordSource

# Load acoustic filler config
_CONFIG_PATH = settings.BASE_DIR / "backend" / "app" / "config" / "disfluency.json"


def _load_acoustic_config() -> Dict[str, Any]:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("acoustic_filler_detector", {})
    return {}


def compute_energy_frames(
    samples: np.ndarray, sr: int, frame_ms: int = 20, hop_ms: int = 10
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute frame-level RMS energy and timestamps."""
    frame_len = int(sr * frame_ms / 1000)
    hop_len = int(sr * hop_ms / 1000)
    n_frames = max(1, (len(samples) - frame_len) // hop_len)

    energies = np.zeros(n_frames)
    timestamps = np.zeros(n_frames)

    for i in range(n_frames):
        start = i * hop_len
        chunk = samples[start : start + frame_len]
        energies[i] = np.sqrt(np.mean(chunk ** 2))
        timestamps[i] = start / float(sr)

    return energies, timestamps


def compute_spectral_flux(
    samples: np.ndarray, sr: int, frame_ms: int = 20, hop_ms: int = 10
) -> np.ndarray:
    """Compute spectral flux between successive frames."""
    frame_len = int(sr * frame_ms / 1000)
    hop_len = int(sr * hop_ms / 1000)
    n_frames = max(1, (len(samples) - frame_len) // hop_len)

    prev_spectrum = None
    flux = np.zeros(n_frames)

    for i in range(n_frames):
        start = i * hop_len
        chunk = samples[start : start + frame_len]
        windowed = chunk * np.hanning(len(chunk))
        spectrum = np.abs(np.fft.rfft(windowed))
        spectrum = spectrum / (np.max(spectrum) + 1e-9)

        if prev_spectrum is not None and len(spectrum) == len(prev_spectrum):
            diff = spectrum - prev_spectrum
            flux[i] = np.sum(np.maximum(diff, 0.0)) / (len(spectrum) + 1e-9)

        prev_spectrum = spectrum

    return flux


def estimate_pitch_stability(
    samples: np.ndarray, sr: int, t_start: float, t_end: float
) -> float:
    """Estimate pitch stability in a region using autocorrelation.

    Returns a value 0.0 (unstable/noisy) to 1.0 (very stable pitch).
    Nasal fillers like "umm" have highly stable pitch.
    """
    start_idx = int(t_start * sr)
    end_idx = min(int(t_end * sr), len(samples))
    segment = samples[start_idx:end_idx]

    if len(segment) < int(sr * 0.02):
        return 0.0

    # Autocorrelation-based pitch detection
    # Look for F0 in range 70-400 Hz (typical voice)
    min_lag = int(sr / 400)
    max_lag = min(int(sr / 70), len(segment) - 1)

    if max_lag <= min_lag or max_lag >= len(segment):
        return 0.0

    # Normalized autocorrelation
    windowed = segment * np.hanning(len(segment))
    energy = np.sum(windowed ** 2)
    if energy < 1e-9:
        return 0.0

    # Split into overlapping sub-frames and check pitch consistency
    sub_frame_len = min(int(sr * 0.04), len(windowed) // 2)
    if sub_frame_len < min_lag:
        return 0.0

    pitches = []
    step = sub_frame_len // 2
    for offset in range(0, len(windowed) - sub_frame_len, step):
        sub = windowed[offset : offset + sub_frame_len]
        corr = np.correlate(sub, sub, mode="full")
        corr = corr[len(corr) // 2 :]

        search_start = max(min_lag, 1)
        search_end = min(max_lag, len(corr) - 1)
        if search_end <= search_start:
            continue

        peak_lag = search_start + np.argmax(corr[search_start:search_end])
        peak_val = corr[peak_lag] / (corr[0] + 1e-9)

        if peak_val > 0.3:
            pitches.append(sr / float(peak_lag))

    if len(pitches) < 2:
        return 0.3

    pitch_std = np.std(pitches)
    pitch_mean = np.mean(pitches)
    cv = pitch_std / (pitch_mean + 1e-9)

    # Low coefficient of variation → stable pitch → likely a filler
    stability = max(0.0, min(1.0, 1.0 - cv * 3.0))
    return round(stability, 3)


def detect_acoustic_fillers(
    audio_path: Path,
    asr_words: List[Word],
) -> List[Word]:
    """Detect acoustic filled pauses that ASR missed.

    Finds voiced regions of 150ms–1500ms not covered by any ASR word,
    with stable pitch and low spectral flux → flagged as FILLER_ACOUSTIC.
    """
    cfg = _load_acoustic_config()
    min_dur_ms = cfg.get("min_duration_ms", 150)
    max_dur_ms = cfg.get("max_duration_ms", 1500)
    min_energy_above_noise_db = cfg.get("min_energy_above_noise_db", 10.0)
    max_flux = cfg.get("max_spectral_flux", 0.15)
    min_pitch_stab = cfg.get("min_pitch_stability", 0.6)
    iou_thresh = cfg.get("overlap_iou_dedup_threshold", 0.3)

    min_dur_sec = min_dur_ms / 1000.0
    max_dur_sec = max_dur_ms / 1000.0

    sr, audio_data = wavfile.read(str(audio_path))
    if audio_data.dtype == np.int16:
        samples = audio_data.astype(np.float32) / 32768.0
    else:
        samples = audio_data.astype(np.float32)
    if len(samples.shape) > 1:
        samples = samples.mean(axis=1)

    # 1. Compute frame-level energy and find voiced regions
    energies, timestamps = compute_energy_frames(samples, sr)
    noise_floor = np.percentile(energies, 10) if len(energies) > 0 else 1e-9
    noise_floor_db = 20.0 * math.log10(noise_floor + 1e-9)
    energy_threshold_db = noise_floor_db + min_energy_above_noise_db
    energy_threshold_linear = 10.0 ** (energy_threshold_db / 20.0)

    # Find contiguous voiced regions
    is_voiced = energies > energy_threshold_linear
    voiced_regions: List[Tuple[float, float]] = []
    region_start: Optional[float] = None
    hop_sec = 0.01  # 10ms hops

    for i, v in enumerate(is_voiced):
        t = timestamps[i]
        if v and region_start is None:
            region_start = t
        elif not v and region_start is not None:
            voiced_regions.append((region_start, t))
            region_start = None
    if region_start is not None:
        voiced_regions.append((region_start, timestamps[-1]))

    # 2. Filter by duration
    candidates = [
        (s, e) for s, e in voiced_regions
        if min_dur_sec <= (e - s) <= max_dur_sec
    ]

    # 3. Remove candidates that overlap with ASR words
    def overlaps_asr_word(start: float, end: float) -> bool:
        for w in asr_words:
            # Check temporal overlap
            overlap_start = max(start, w.start)
            overlap_end = min(end, w.end)
            if overlap_end > overlap_start:
                overlap_dur = overlap_end - overlap_start
                region_dur = end - start
                if overlap_dur / region_dur > iou_thresh:
                    return True
        return False

    uncovered = [(s, e) for s, e in candidates if not overlaps_asr_word(s, e)]

    # 4. Compute spectral flux for the entire audio
    flux = compute_spectral_flux(samples, sr)

    # 5. Score each uncovered region
    acoustic_fillers: List[Word] = []
    for reg_start, reg_end in uncovered:
        # Average spectral flux in this region
        flux_start_idx = int(reg_start / hop_sec)
        flux_end_idx = min(int(reg_end / hop_sec), len(flux) - 1)
        if flux_end_idx <= flux_start_idx:
            continue
        mean_flux = float(np.mean(flux[flux_start_idx : flux_end_idx + 1]))

        # Pitch stability
        pitch_stab = estimate_pitch_stability(samples, sr, reg_start, reg_end)

        # Decision: low spectral flux + stable pitch → nasal filler
        if mean_flux <= max_flux and pitch_stab >= min_pitch_stab:
            confidence = round(0.5 + 0.3 * pitch_stab + 0.2 * (1.0 - mean_flux / max_flux), 3)
            confidence = min(0.95, max(0.50, confidence))

            acoustic_fillers.append(Word(
                text="[filler]",
                start=round(reg_start, 3),
                end=round(reg_end, 3),
                confidence=confidence,
                is_filler=True,
                filler_type="acoustic",
                source=WordSource.ACOUSTIC,
            ))

    return acoustic_fillers

