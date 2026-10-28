#!/usr/bin/env python3
"""Diagnostic CLI for PLUTO vProctor recording analysis.

Inspects container health, audio statistics, Whisper ASR word timestamps,
filler/pause occurrences, and outputs gaze/motion CSV traces + PNG plots.

Usage:
    python backend/scripts/diagnose_recording.py <path_to_recording.webm>
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import av
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile

# PyAV 14+ compatibility patch for faster-whisper
_orig_av_open = av.open
def _safe_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _orig_av_open(*args, **kwargs)
av.open = _safe_av_open

# Ensure root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.algorithms.edit_distance import levenshtein
from backend.app.algorithms.sliding_window import EMAFilter, SlidingWindowStats
from backend.app.algorithms.string_match import kmp_search, rabin_karp_search
from backend.app.config import settings


def inspect_container(video_path: Path) -> Dict[str, Any]:
    """Inspect WebM / MP4 container structure, streams, codecs, and timestamp validity."""
    container = av.open(str(video_path))
    info: Dict[str, Any] = {
        "file_name": video_path.name,
        "file_size_bytes": video_path.stat().st_size,
        "format_name": container.format.name,
        "format_long_name": container.format.long_name,
        "duration_sec": float(container.duration / av.time_base) if container.duration is not None else None,
        "bit_rate": container.bit_rate,
        "streams": [],
        "has_valid_duration": container.duration is not None and container.duration > 0,
        "timestamp_warnings": [],
    }

    has_video = False
    has_audio = False

    for stream in container.streams:
        s_info: Dict[str, Any] = {
            "index": stream.index,
            "type": stream.type,
            "codec_name": stream.codec_context.name if stream.codec_context else None,
            "time_base": str(stream.time_base),
            "start_time": stream.start_time,
            "duration": float(stream.duration * stream.time_base) if (stream.duration and stream.time_base) else None,
            "frames": stream.frames,
        }
        if stream.type == "video":
            has_video = True
            s_info["width"] = stream.codec_context.width
            s_info["height"] = stream.codec_context.height
            s_info["average_rate"] = float(stream.rate) if (hasattr(stream, "rate") and stream.rate) else None
        elif stream.type == "audio":
            has_audio = True
            s_info["sample_rate"] = stream.codec_context.sample_rate
            s_info["channels"] = stream.codec_context.channels
            s_info["format"] = stream.codec_context.format.name if stream.codec_context.format else None

        info["streams"].append(s_info)

    container.close()

    if not info["has_valid_duration"]:
        info["timestamp_warnings"].append(
            "Container duration is missing or None (common with browser MediaRecorder WebM streams)."
        )
    if not has_video:
        info["timestamp_warnings"].append("No video stream found in container.")
    if not has_audio:
        info["timestamp_warnings"].append("No audio stream found in container.")

    return info


def extract_audio_and_profile(video_path: Path, out_wav_path: Path) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Extract 16 kHz mono audio using PyAV and compute acoustic stats."""
    container = av.open(str(video_path))
    audio_stream = next((s for s in container.streams if s.type == "audio"), None)
    if not audio_stream:
        container.close()
        raise ValueError(f"No audio stream found in {video_path}")

    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    pcm_chunks = []

    for frame in container.decode(audio_stream):
        for rf in resampler.resample(frame):
            pcm_chunks.append(rf.to_ndarray())

    container.close()

    if pcm_chunks:
        audio_int16 = np.concatenate(pcm_chunks, axis=-1).flatten()
    else:
        audio_int16 = np.zeros(16000, dtype=np.int16)

    # Save 16 kHz wav
    wavfile.write(str(out_wav_path), 16000, audio_int16)

    # Compute acoustic metrics
    samples = audio_int16.astype(np.float32) / 32768.0
    duration_sec = len(samples) / 16000.0

    rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0
    rms_dbfs = 20.0 * math.log10(rms + 1e-9)

    peak = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0
    peak_dbfs = 20.0 * math.log10(peak + 1e-9)
    clipping_samples = int(np.sum(np.abs(samples) >= 0.999))

    # Frame-wise energy for silence ratio and noise floor estimation (window = 30ms, hop = 10ms)
    frame_len = int(16000 * 0.030)
    hop_len = int(16000 * 0.010)
    num_frames = max(1, (len(samples) - frame_len) // hop_len)

    energies = []
    for i in range(num_frames):
        seg = samples[i * hop_len : i * hop_len + frame_len]
        e = np.sqrt(np.mean(seg ** 2))
        energies.append(e)

    energies = np.array(energies)
    energies_dbfs = 20.0 * np.log10(energies + 1e-9)

    # Silence is frames with energy < -42 dBFS
    silence_frames = np.sum(energies_dbfs < -42.0)
    silence_ratio = float(silence_frames / len(energies_dbfs)) if len(energies_dbfs) > 0 else 0.0

    # Noise floor: 10th percentile energy in dBFS
    noise_floor_dbfs = float(np.percentile(energies_dbfs, 10)) if len(energies_dbfs) > 0 else -90.0

    stats = {
        "audio_duration_sec": round(duration_sec, 2),
        "sample_count": len(samples),
        "rms_amplitude": round(rms, 5),
        "rms_dbfs": round(rms_dbfs, 2),
        "peak_amplitude": round(peak, 4),
        "peak_dbfs": round(peak_dbfs, 2),
        "clipping_samples": clipping_samples,
        "silence_ratio": round(silence_ratio, 3),
        "estimated_noise_floor_dbfs": round(noise_floor_dbfs, 2),
    }

    return samples, stats


def run_asr_and_filler_analysis(samples: np.ndarray) -> Dict[str, Any]:
    """Transcribe audio with faster-whisper, extract timestamps, confidence, and disfluencies."""
    from faster_whisper import WhisperModel

    model = WhisperModel(
        settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )

    # Run without vad_filter to inspect raw verbatim behavior
    segments, info = model.transcribe(
        samples,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt="Umm, uh, ahh, like, you know, so, basically, I mean...",
        beam_size=3,
    )

    raw_segments: List[Dict[str, Any]] = []
    all_words: List[Dict[str, Any]] = []
    full_text_pieces: List[str] = []

    for seg in segments:
        seg_dict = {
            "id": seg.id,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text,
            "avg_logprob": round(seg.avg_logprob, 3),
            "no_speech_prob": round(seg.no_speech_prob, 3),
            "words": [],
        }
        full_text_pieces.append(seg.text)
        if seg.words:
            for w in seg.words:
                clean_w = re.sub(r"[^\w']", "", w.word.strip().lower())
                w_dict = {
                    "word": clean_w,
                    "raw_word": w.word,
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "prob": round(w.probability, 3),
                }
                seg_dict["words"].append(w_dict)
                all_words.append(w_dict)

        raw_segments.append(seg_dict)

    full_transcript = " ".join(full_text_pieces).strip()

    # Load fillers dictionary
    fillers_file = settings.BASE_DIR / "backend" / "app" / "data" / "fillers.json"
    single_fillers = set()
    phrase_fillers = []
    if fillers_file.exists():
        with open(fillers_file, "r", encoding="utf-8") as f:
            fdata = json.load(f)
            single_fillers = set(fdata.get("single_word_fillers", []))
            phrase_fillers = fdata.get("phrase_fillers", [])

    detected_fillers: List[Dict[str, Any]] = []

    # 1. Single word fillers
    for w in all_words:
        word = w["word"]
        if not word:
            continue
        is_filler = False
        match_type = ""
        if word in single_fillers:
            is_filler = True
            match_type = "exact"
        else:
            for sf in ["um", "umm", "uh", "er", "ah", "ahh", "hmm"]:
                if abs(len(word) - len(sf)) <= 2 and levenshtein(word, sf) <= 1:
                    is_filler = True
                    match_type = f"fuzzy({sf})"
                    break

        if is_filler:
            detected_fillers.append({
                "type": "HARD_FILLER",
                "match_type": match_type,
                "text": w["raw_word"],
                "start": w["start"],
                "end": w["end"],
                "prob": w["prob"],
            })

    # 2. Phrase fillers via KMP & Rabin-Karp
    text_lower = full_transcript.lower()
    for phrase in phrase_fillers:
        kmp_m = kmp_search(text_lower, phrase)
        rk_m = rabin_karp_search(text_lower, phrase)
        combined_m = sorted(list(set(kmp_m + rk_m)))
        for pos in combined_m:
            detected_fillers.append({
                "type": "PHRASE_FILLER",
                "match_type": "kmp_rk",
                "text": phrase,
                "char_offset": pos,
                "start": None,
                "end": None,
                "prob": 1.0,
            })

    # 3. Inter-word pause analysis
    detected_pauses: List[Dict[str, Any]] = []
    for i in range(len(all_words) - 1):
        gap = round(all_words[i + 1]["start"] - all_words[i]["end"], 2)
        if gap >= 1.2:
            detected_pauses.append({
                "type": "LONG_PAUSE",
                "start": all_words[i]["end"],
                "end": all_words[i + 1]["start"],
                "duration": gap,
                "before_word": all_words[i]["word"],
                "after_word": all_words[i + 1]["word"],
            })
        elif gap >= 0.6:
            detected_pauses.append({
                "type": "HESITATION",
                "start": all_words[i]["end"],
                "end": all_words[i + 1]["start"],
                "duration": gap,
                "before_word": all_words[i]["word"],
                "after_word": all_words[i + 1]["word"],
            })

    return {
        "full_transcript": full_transcript,
        "segment_count": len(raw_segments),
        "word_count": len(all_words),
        "raw_segments": raw_segments,
        "words": all_words,
        "detected_fillers": detected_fillers,
        "detected_pauses": detected_pauses,
    }


def trace_video_motion_and_gaze(video_path: Path, csv_path: Path, target_fps: float = 10.0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Sample video frames, record gaze/motion trace, and write detailed CSV."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if orig_fps <= 0 or np.isnan(orig_fps) or orig_fps > 65.0:
        orig_fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    if total_frames <= 0 or total_frames > 1e10:
        total_frames = 1800

    frame_step = max(1, int(round(orig_fps / target_fps)))
    actual_sampling_fps = orig_fps / frame_step

    cv_data_dir = Path(cv2.__file__).resolve().parent / "data"
    face_cascade_path = cv_data_dir / "haarcascade_frontalface_default.xml"
    eye_cascade_path = cv_data_dir / "haarcascade_eye.xml"

    face_cascade = cv2.CascadeClassifier(str(face_cascade_path)) if face_cascade_path.exists() else None
    eye_cascade = cv2.CascadeClassifier(str(eye_cascade_path)) if eye_cascade_path.exists() else None

    gaze_ema = EMAFilter(alpha=0.35)
    motion_stats = SlidingWindowStats(window_size=10)

    trace_records: List[Dict[str, Any]] = []
    frame_idx = 0
    prev_face_center: Optional[Tuple[float, float]] = None

    t0 = time.time()
    processed_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step != 0:
            frame_idx += 1
            continue

        t_current = round(frame_idx / orig_fps, 3)
        h, w, _ = frame.shape
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60)) if face_cascade else ()
        face_count = len(faces)

        face_detected = face_count > 0
        face_center_x = 0.5
        face_center_y = 0.5
        eyes_detected_count = 0
        raw_offset_x = 0.0
        smoothed_offset_x = 0.0
        is_lookaway_raw = False
        motion_var = 0.0

        if face_count == 1:
            (fx, fy, fw, fh) = faces[0]
            face_center_x = (fx + fw / 2.0) / w
            face_center_y = (fy + fh / 2.0) / h

            roi_gray = gray[fy : fy + int(fh * 0.6), fx : fx + fw]
            if eye_cascade and not eye_cascade.empty():
                eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=3)
                eyes_detected_count = len(eyes)

            raw_offset_x = abs(face_center_x - 0.5)
            smoothed_offset_x = gaze_ema.update(raw_offset_x)

            # Look away condition as currently coded: smoothed_offset_x > tolerance
            is_lookaway_raw = smoothed_offset_x > settings.GAZE_CENTER_TOLERANCE_X

            if prev_face_center is not None:
                disp = math.hypot(face_center_x - prev_face_center[0], face_center_y - prev_face_center[1])
                motion_stats.push(disp)
                motion_var = motion_stats.variance()

            prev_face_center = (face_center_x, face_center_y)
        elif face_count == 0:
            is_lookaway_raw = True

        rec = {
            "frame_idx": frame_idx,
            "timestamp": t_current,
            "face_detected": int(face_detected),
            "face_count": face_count,
            "eyes_detected": eyes_detected_count,
            "face_center_x": round(face_center_x, 4),
            "face_center_y": round(face_center_y, 4),
            "raw_offset_x": round(raw_offset_x, 4),
            "smoothed_offset_x": round(smoothed_offset_x, 4),
            "motion_variance": round(motion_var, 6),
            "is_lookaway_raw": int(is_lookaway_raw),
        }
        trace_records.append(rec)
        processed_count += 1
        frame_idx += 1

    cap.release()
    elapsed = time.time() - t0
    achieved_fps = processed_count / max(0.001, elapsed)

    # Write CSV
    if trace_records:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(trace_records[0].keys()))
            writer.writeheader()
            writer.writerows(trace_records)

    stats = {
        "orig_video_fps": round(orig_fps, 2),
        "total_video_frames": total_frames,
        "processed_sample_frames": processed_count,
        "target_sampling_fps": target_fps,
        "actual_sampling_fps": round(actual_sampling_fps, 2),
        "trace_processing_fps": round(achieved_fps, 1),
        "face_presence_ratio": round(sum(r["face_detected"] for r in trace_records) / max(1, processed_count), 3),
        "raw_lookaway_ratio": round(sum(r["is_lookaway_raw"] for r in trace_records) / max(1, processed_count), 3),
    }

    return trace_records, stats


def plot_diagnostics(
    trace: List[Dict[str, Any]],
    fillers: List[Dict[str, Any]],
    pauses: List[Dict[str, Any]],
    plot_path: Path,
):
    """Plot multi-panel timeline of gaze offset, motion variance, and speech disfluencies."""
    if not trace:
        return

    ts = [r["timestamp"] for r in trace]
    offsets = [r["smoothed_offset_x"] for r in trace]
    raw_offsets = [r["raw_offset_x"] for r in trace]
    motion = [r["motion_variance"] for r in trace]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)

    # Panel 1: Gaze Offset & Look-Away Threshold
    ax1.plot(ts, raw_offsets, color="#cbd5e1", label="Raw Head Offset X", alpha=0.7, lw=1)
    ax1.plot(ts, offsets, color="#2563eb", label="EMA Smoothed Gaze Offset X", lw=2)
    ax1.axhline(
        settings.GAZE_CENTER_TOLERANCE_X,
        color="#dc2626",
        linestyle="--",
        label=f"Current Tolerance ({settings.GAZE_CENTER_TOLERANCE_X})",
    )

    # Plot Look-away ground truth / events
    lookaway_ts = [r["timestamp"] for r in trace if r["is_lookaway_raw"]]
    if lookaway_ts:
        ax1.scatter(
            lookaway_ts,
            [settings.GAZE_CENTER_TOLERANCE_X * 1.05] * len(lookaway_ts),
            color="#ef4444",
            marker="|",
            s=50,
            label="Raw Look-away Flag",
            zorder=5,
        )

    ax1.set_ylabel("Normalized Offset from Center")
    ax1.set_title("PLUTO vProctor Diagnostic Trace: Visual Gaze Offset vs. Threshold")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Motion Variance + Filler & Pause Events
    ax2.plot(ts, motion, color="#16a34a", label="Motion Variance", lw=1.5)
    ax2.axhline(0.0012, color="#eab308", linestyle=":", label="Motion Threshold (0.0012)")

    # Mark spoken fillers
    for f in fillers:
        if f.get("start") is not None:
            ax2.axvline(f["start"], color="#9333ea", linestyle="-.", alpha=0.8, lw=1.5)
            ax2.text(
                f["start"],
                ax2.get_ylim()[1] * 0.7,
                f["text"],
                color="#7e22ce",
                fontsize=8,
                rotation=90,
                va="bottom",
            )

    # Mark pauses
    for p in pauses:
        if p.get("start") is not None and p.get("end") is not None:
            ax2.axvspan(p["start"], p["end"], color="#f97316", alpha=0.25)

    ax2.set_xlabel("Recording Timestamp (Seconds)")
    ax2.set_ylabel("Motion Variance / Events")
    ax2.set_title("Body Motion Variance & Audio Disfluency Events (Purple=Filler, Orange=Pause)")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(plot_path, dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Diagnose PLUTO vProctor WebM recording.")
    parser.add_argument("recording_path", type=str, help="Path to recording .webm file")
    parser.add_argument("--fps", type=float, default=10.0, help="Target sampling FPS for visual trace")
    args = parser.parse_args()
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    rec_path = Path(args.recording_path)
    if not rec_path.exists():
        print(f"Error: File not found: {rec_path}")
        sys.exit(1)

    print("=" * 80)
    print(f"  PLUTO vProctor Recording Diagnostic Tool: {rec_path.name}")
    print("=" * 80)

    # 1. Container check
    print("\n[1/4] Inspecting Container & Stream Headers...")
    container_info = inspect_container(rec_path)
    print(f"  - Container Format:    {container_info['format_name']} ({container_info['format_long_name']})")
    print(f"  - Duration Reported:   {container_info['duration_sec']} s")
    print(f"  - Valid Duration Tag:  {container_info['has_valid_duration']}")
    print(f"  - Stream Count:        {len(container_info['streams'])}")
    for s in container_info["streams"]:
        print(f"    * Stream #{s['index']} ({s['type'].upper()}): codec={s['codec_name']}, time_base={s['time_base']}")
    if container_info["timestamp_warnings"]:
        for w in container_info["timestamp_warnings"]:
            print(f"    ! WARNING: {w}")

    # 2. Audio extraction and acoustic profiling
    print("\n[2/4] Profiling Audio Stream & Acoustics...")
    out_wav = rec_path.with_suffix(".diag.16k.wav")
    samples, audio_stats = extract_audio_and_profile(rec_path, out_wav)
    print(f"  - Duration:            {audio_stats['audio_duration_sec']} s")
    print(f"  - RMS Energy:          {audio_stats['rms_dbfs']} dBFS")
    print(f"  - Peak Amplitude:      {audio_stats['peak_dbfs']} dBFS (clipping samples: {audio_stats['clipping_samples']})")
    print(f"  - Silence Ratio:       {audio_stats['silence_ratio'] * 100:.1f}%")
    print(f"  - Noise Floor Est.:    {audio_stats['estimated_noise_floor_dbfs']} dBFS")

    # 3. Whisper ASR & Filler/Pause analysis
    print("\n[3/4] Running Faster-Whisper ASR & Filler Detection...")
    asr_results = run_asr_and_filler_analysis(samples)
    print(f"  - Transcribed Words:   {asr_results['word_count']}")
    print(f"  - Full Transcript:     \"{asr_results['full_transcript'][:140]}...\"")
    print(f"  - Fillers Detected:    {len(asr_results['detected_fillers'])}")
    for f in asr_results["detected_fillers"]:
        print(f"    * {f['type']} '{f['text']}' @ t={f['start']}s (confidence={f.get('prob', 'N/A')})")
    print(f"  - Pauses Detected:     {len(asr_results['detected_pauses'])}")
    for p in asr_results["detected_pauses"][:5]:
        print(f"    * {p['type']} duration={p['duration']}s between '{p['before_word']}' and '{p['after_word']}' (t={p['start']}s)")

    # 4. Video Vision & Gaze Trace
    print(f"\n[4/4] Tracing Visual Gaze & Head Motion at {args.fps} FPS...")
    csv_path = rec_path.with_suffix(".trace.csv")
    plot_path = rec_path.with_suffix(".plot.png")
    trace_records, video_stats = trace_video_motion_and_gaze(rec_path, csv_path, target_fps=args.fps)
    print(f"  - Sampling Achieved:   {video_stats['actual_sampling_fps']} FPS (pipeline speed: {video_stats['trace_processing_fps']} FPS)")
    print(f"  - Face Presence:       {video_stats['face_presence_ratio'] * 100:.1f}% of frames")
    print(f"  - Raw Look-away Ratio: {video_stats['raw_lookaway_ratio'] * 100:.1f}% of frames")
    print(f"  - Trace CSV Saved:     {csv_path.name}")

    plot_diagnostics(trace_records, asr_results["detected_fillers"], asr_results["detected_pauses"], plot_path)
    print(f"  - Plot PNG Saved:      {plot_path.name}")

    # Output full JSON
    json_path = rec_path.with_suffix(".diagnostics.json")
    diagnostics_payload = {
        "file": str(rec_path),
        "container": container_info,
        "audio_stats": audio_stats,
        "asr_analysis": {
            "transcript": asr_results["full_transcript"],
            "word_count": asr_results["word_count"],
            "fillers_count": len(asr_results["detected_fillers"]),
            "fillers": asr_results["detected_fillers"],
            "pauses_count": len(asr_results["detected_pauses"]),
            "pauses": asr_results["detected_pauses"],
            "segments": asr_results["raw_segments"],
        },
        "video_stats": video_stats,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diagnostics_payload, f, indent=2)

    print(f"\n[OK] Diagnostic JSON written to: {json_path.name}")
    print("=" * 80)


if __name__ == "__main__":
    main()
