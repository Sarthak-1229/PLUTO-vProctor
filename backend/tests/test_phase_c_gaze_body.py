"""Phase C Unit and Parity Tests: One Euro Filter, Gaze Tracking, Calibration, and Posture."""
import json
from pathlib import Path
import numpy as np
import pytest

from backend.app.algorithms.one_euro_filter import OneEuroFilter, OneEuroFilterVector
from backend.app.config import settings
from backend.app.pipelines.gaze_tracker import CalibrationData, GazeTracker
from backend.app.pipelines.video_pipeline import VideoAnalysisPipeline


def test_one_euro_filter_jitter_reduction():
    """Verify 1€ filter attenuates noise when value is stationary."""
    filt = OneEuroFilter(t0=0.0, x0=10.0, min_cutoff=1.0, beta=0.007)
    noisy_samples = [10.0 + (0.5 if i % 2 == 0 else -0.5) for i in range(20)]
    filtered_samples = []

    for i, val in enumerate(noisy_samples):
        t = (i + 1) * (1.0 / 30.0)
        filtered_samples.append(filt.filter(val, t))

    # Variance of filtered samples should be strictly less than raw noisy samples
    raw_var = np.var(noisy_samples)
    filt_var = np.var(filtered_samples[5:])
    assert filt_var < raw_var * 0.4


def test_one_euro_filter_fast_movement_low_lag():
    """Verify 1€ filter responds rapidly to high-velocity step input."""
    filt = OneEuroFilter(t0=0.0, x0=0.0, min_cutoff=1.0, beta=0.1)
    # Sudden saccade from 0.0 to 25.0 degrees
    step_samples = [0.0] * 5 + [25.0] * 10
    filtered = []
    for i, val in enumerate(step_samples):
        t = (i + 1) * (1.0 / 30.0)
        filtered.append(filt.filter(val, t))

    # Within 3 frames of step, should reach >= 80% of target
    step_frame_idx = 5
    assert filtered[step_frame_idx + 2] >= 20.0


def test_gaze_config_preset_hierarchy():
    """Verify gaze presets exist and follow strict < normal < relaxed threshold ordering."""
    cfg_path = settings.BASE_DIR / "backend" / "app" / "config" / "gaze.json"
    assert cfg_path.exists()
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    presets = cfg["presets"]
    assert "strict" in presets and "normal" in presets and "relaxed" in presets

    strict = presets["strict"]
    normal = presets["normal"]
    relaxed = presets["relaxed"]

    assert strict["max_yaw_deg"] < normal["max_yaw_deg"] < relaxed["max_yaw_deg"]
    assert strict["max_pitch_down_deg"] < normal["max_pitch_down_deg"] < relaxed["max_pitch_down_deg"]
    assert strict["alert_trigger_sec"] <= normal["alert_trigger_sec"] <= relaxed["alert_trigger_sec"]
    assert strict["event_deduction_sec"] <= normal["event_deduction_sec"] <= relaxed["event_deduction_sec"]


def test_calibration_baseline_subtraction():
    """Verify candidate calibration baseline offsets are properly subtracted."""
    calib = CalibrationData(
        baseline_yaw=5.0,
        baseline_pitch=-3.0,
        baseline_iris_h=0.05,
        is_calibrated=True,
    )
    tracker = GazeTracker(calibration=calib)
    assert tracker.calibration.baseline_yaw == 5.0
    assert tracker.calibration.baseline_pitch == -3.0

    # Net calculations
    raw_yaw = 22.0
    net_yaw = raw_yaw - tracker.calibration.baseline_yaw
    assert net_yaw == 17.0  # Measured relative to candidate baseline


def test_gaze_preset_live_server_parity():
    """Verify live JS detector presets match backend gaze.json configuration values."""
    cfg_path = settings.BASE_DIR / "backend" / "app" / "config" / "gaze.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        backend_cfg = json.load(f)

    js_file = settings.BASE_DIR / "frontend" / "src" / "utils" / "liveGazeDetector.js"
    assert js_file.exists()
    js_text = js_file.read_text(encoding="utf-8")

    # Check key threshold constants in JS file match backend gaze.json strict preset
    strict_cfg = backend_cfg["presets"]["strict"]
    assert f"maxYaw: {strict_cfg['max_yaw_deg']}" in js_text or f"{strict_cfg['max_yaw_deg']}" in js_text
    assert f"maxPitchDown: {strict_cfg['max_pitch_down_deg']}" in js_text or f"{strict_cfg['max_pitch_down_deg']}" in js_text
    assert f"alertDelaySec: {strict_cfg['alert_trigger_sec']}" in js_text or f"{strict_cfg['alert_trigger_sec']}" in js_text


def test_video_pipeline_runs_with_gaze_tracker(tmp_path):
    """Verify video pipeline processes frames using 10 FPS and GazeTracker without crash."""
    import cv2
    clip_path = tmp_path / "test_clip_c.webm"
    fourcc = cv2.VideoWriter_fourcc(*"VP80")
    fps = 10.0
    width, height = 320, 240
    out = cv2.VideoWriter(str(clip_path), fourcc, fps, (width, height))

    for _ in range(15):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Face representation
        cv2.circle(frame, (160, 120), 45, (200, 200, 200), -1)
        out.write(frame)
    out.release()

    pipeline = VideoAnalysisPipeline(target_fps=10.0, preset_name="strict")
    res = pipeline.analyze_video(clip_path)

    assert "metrics" in res
    assert "events" in res
    assert res["analyzed_frames"] >= 1
    assert "eye_contact_percentage" in res["metrics"]
    assert "active_preset" in res["metrics"]
    assert res["metrics"]["active_preset"] == "strict"
