#!/usr/bin/env python3
"""Generate synthetic benchmark fixtures for CI regression testing.

Renders synthetic video (face with controlled look-away intervals) and synthetic audio
(carrier tones with silence gaps and filler sounds) to evaluate pipeline accuracy deterministically.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List

import av
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = ROOT_DIR / "backend" / "tests" / "fixtures" / "recordings"


def draw_synthetic_face(w: int, h: int, gaze_state: str, eye_offset_x: float = 0.0) -> np.ndarray:
    """Render a synthetic face with head, eyes, and pupils."""
    img = np.full((h, w, 3), 240, dtype=np.uint8)  # Light gray background

    center_x = int(w * 0.5)
    center_y = int(h * 0.45)
    face_w = int(w * 0.22)
    face_h = int(h * 0.32)

    if gaze_state == "LOOK_AWAY":
        # Displace head/eyes to the side
        center_x += int(w * 0.20)
    elif gaze_state == "LOOK_DOWN":
        center_y += int(h * 0.15)

    # Face ellipse
    cv2.ellipse(img, (center_x, center_y), (face_w, face_h), 0, 0, 360, (180, 210, 240), -1)
    cv2.ellipse(img, (center_x, center_y), (face_w, face_h), 0, 0, 360, (0, 0, 0), 2)

    # Eyes
    eye_y = center_y - int(face_h * 0.15)
    left_eye_x = center_x - int(face_w * 0.4)
    right_eye_x = center_x + int(face_w * 0.4)
    eye_radius = int(face_w * 0.12)

    cv2.circle(img, (left_eye_x, eye_y), eye_radius, (255, 255, 255), -1)
    cv2.circle(img, (left_eye_x, eye_y), eye_radius, (0, 0, 0), 2)
    cv2.circle(img, (right_eye_x, eye_y), eye_radius, (255, 255, 255), -1)
    cv2.circle(img, (right_eye_x, eye_y), eye_radius, (0, 0, 0), 2)

    # Pupils
    pupil_offset = int(eye_radius * 0.6) if gaze_state == "LOOK_AWAY" else int(eye_offset_x * eye_radius)
    pupil_radius = max(2, int(eye_radius * 0.4))
    cv2.circle(img, (left_eye_x + pupil_offset, eye_y), pupil_radius, (20, 20, 20), -1)
    cv2.circle(img, (right_eye_x + pupil_offset, eye_y), pupil_radius, (20, 20, 20), -1)

    # Mouth
    mouth_y = center_y + int(face_h * 0.45)
    cv2.line(img, (center_x - int(face_w * 0.3), mouth_y), (center_x + int(face_w * 0.3), mouth_y), (0, 0, 0), 2)

    return img


def generate_synthetic_fixture(
    fixture_id: str = "fixture_synth_001",
    duration_sec: float = 15.0,
    fps: int = 30,
):
    """Generate a combined synthetic WebM video and ground-truth JSON labels."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out_webm = FIXTURES_DIR / f"{fixture_id}.webm"
    out_json = FIXTURES_DIR / f"{fixture_id}.labels.json"

    width, height = 640, 480
    total_frames = int(duration_sec * fps)

    # Ground-truth scheduled events
    labels: List[Dict[str, Any]] = [
        {"type": "LOOK_AWAY", "start": 3.0, "end": 5.5, "duration": 2.5},
        {"type": "PAUSE", "start": 7.0, "end": 9.2, "duration": 2.2},
        {"type": "LOOK_AWAY", "start": 10.5, "end": 12.0, "duration": 1.5},
        {"type": "FILLER", "start": 6.2, "end": 6.8, "text": "umm"},
    ]

    container = av.open(str(out_webm), mode="w", format="webm")
    v_stream = container.add_stream("vp8", rate=fps)
    v_stream.width = width
    v_stream.height = height
    v_stream.pix_fmt = "yuv420p"

    a_stream = container.add_stream("opus", rate=48000)
    a_stream.layout = "mono"

    # Render video frames
    for i in range(total_frames):
        t = i / float(fps)
        gaze = "CENTER"
        for l in labels:
            if l["type"] == "LOOK_AWAY" and l["start"] <= t <= l["end"]:
                gaze = "LOOK_AWAY"
                break

        img = draw_synthetic_face(width, height, gaze)
        frame = av.VideoFrame.from_ndarray(img, format="bgr24")
        for packet in v_stream.encode(frame):
            container.mux(packet)

    for packet in v_stream.encode(None):
        container.mux(packet)

    # Render audio frames (48 kHz mono)
    sample_rate = 48000
    total_samples = int(duration_sec * sample_rate)
    audio_data = np.zeros(total_samples, dtype=np.float32)

    # Generate carrier audio tone except during pauses
    t_arr = np.linspace(0, duration_sec, total_samples, endpoint=False)
    carrier = 0.2 * np.sin(2 * np.pi * 220.0 * t_arr)  # 220 Hz low tone

    # Silence during pause intervals
    for l in labels:
        if l["type"] == "PAUSE":
            idx_start = int(l["start"] * sample_rate)
            idx_end = int(l["end"] * sample_rate)
            carrier[idx_start:idx_end] = 0.0

    audio_int16 = (carrier * 32767).astype(np.int16)

    # Encode audio packets in chunks of 960 samples (20ms frames)
    frame_size = 960
    for s_idx in range(0, len(audio_int16) - frame_size, frame_size):
        chunk = audio_int16[s_idx : s_idx + frame_size].reshape(1, -1)
        a_frame = av.AudioFrame.from_ndarray(chunk, format="s16", layout="mono")
        a_frame.sample_rate = sample_rate
        for packet in a_stream.encode(a_frame):
            container.mux(packet)

    for packet in a_stream.encode(None):
        container.mux(packet)

    container.close()

    # Save JSON labels
    payload = {
        "fixture_id": fixture_id,
        "is_synthetic": True,
        "duration_sec": duration_sec,
        "reference_transcript": "Synthetic carrier speech with deliberate pause and look-away intervals.",
        "labels": labels,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Generated synthetic fixture: {out_webm.name} ({duration_sec}s, {total_frames} frames)")


if __name__ == "__main__":
    generate_synthetic_fixture()
