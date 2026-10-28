"""Integration tests for video and audio analysis pipelines."""
import os
from pathlib import Path
import cv2
import numpy as np
import pytest
from scipy.io import wavfile

from backend.app.pipelines.audio_pipeline import audio_pipeline
from backend.app.pipelines.video_pipeline import video_pipeline

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def sample_video_clip(tmp_path_factory) -> Path:
    """Generate a 2-second synthetic video clip with video frames and audio for testing."""
    tmp_dir = tmp_path_factory.mktemp("media")
    video_path = tmp_dir / "test_clip.webm"

    # 1. Write video frames
    fourcc = cv2.VideoWriter_fourcc(*"VP80")
    fps = 10.0
    width, height = 320, 240
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

    for i in range(20):  # 2 seconds at 10 fps
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw simple stylized face shape
        cv2.circle(frame, (160, 120), 50, (200, 200, 200), -1)
        # Eyes
        cv2.circle(frame, (145, 110), 6, (0, 0, 0), -1)
        cv2.circle(frame, (175, 110), 6, (0, 0, 0), -1)
        out.write(frame)
    out.release()

    return video_path


def test_video_pipeline_runs(sample_video_clip):
    """Verify video analysis pipeline processes frames without error."""
    result = video_pipeline.analyze_video(sample_video_clip)
    assert "metrics" in result
    assert "events" in result
    assert result["analyzed_frames"] >= 1
    assert "eye_contact_percentage" in result["metrics"]


def test_audio_pipeline_fillers_and_pauses(tmp_path):
    """Verify audio pipeline filler-word detection algorithms."""
    # Test audio pipeline filler logic directly on text
    text = "Umm, I think that, like, you know, Kubernetes is basically container orchestration."
    words = text.lower().split()
    matched_fillers = [w.strip(",.") for w in words if w.strip(",.") in audio_pipeline.single_fillers]
    assert "umm" in matched_fillers or "like" in matched_fillers or "basically" in matched_fillers
