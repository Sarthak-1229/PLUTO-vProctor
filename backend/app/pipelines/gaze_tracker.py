"""MediaPipe Face Landmarker & Iris Gaze Tracking for PLUTO vProctor.

Combines 3D head pose estimation, iris displacement ratios, face blendshapes,
One Euro adaptive filtering, and baseline calibration for sub-second,
direction-aware look-away and posture tracking.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.app.algorithms.one_euro_filter import OneEuroFilterVector
from backend.app.config import settings

# Canonical 468/478 Landmark Indices for Eye and Head Geometry
LEFT_EYE_OUTER = 33
LEFT_EYE_INNER = 133
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145
LEFT_IRIS_CENTER = 468

RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374
RIGHT_IRIS_CENTER = 473

NOSE_TIP = 1
CHIN = 199


@dataclass
class CalibrationData:
    """Neutral calibration baseline recorded during precheck."""
    baseline_yaw: float = 0.0
    baseline_pitch: float = 0.0
    baseline_roll: float = 0.0
    baseline_iris_h: float = 0.0
    baseline_iris_v: float = 0.0
    baseline_nose_y: float = 0.5
    baseline_interocular: float = 0.15
    is_calibrated: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CalibrationData:
        return cls(
            baseline_yaw=float(data.get("baseline_yaw", 0.0)),
            baseline_pitch=float(data.get("baseline_pitch", 0.0)),
            baseline_roll=float(data.get("baseline_roll", 0.0)),
            baseline_iris_h=float(data.get("baseline_iris_h", 0.0)),
            baseline_iris_v=float(data.get("baseline_iris_v", 0.0)),
            baseline_nose_y=float(data.get("baseline_nose_y", 0.5)),
            baseline_interocular=float(data.get("baseline_interocular", 0.15)),
            is_calibrated=bool(data.get("is_calibrated", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_yaw": round(self.baseline_yaw, 2),
            "baseline_pitch": round(self.baseline_pitch, 2),
            "baseline_roll": round(self.baseline_roll, 2),
            "baseline_iris_h": round(self.baseline_iris_h, 3),
            "baseline_iris_v": round(self.baseline_iris_v, 3),
            "baseline_nose_y": round(self.baseline_nose_y, 3),
            "baseline_interocular": round(self.baseline_interocular, 3),
            "is_calibrated": self.is_calibrated,
        }


@dataclass
class FrameGazeResult:
    """Frame-level gaze, head pose and proctoring telemetry."""
    timestamp: float
    face_detected: bool
    num_faces: int = 1
    is_looking_direct: bool = True
    look_away_type: Optional[str] = None  # "LOOK_SIDE", "LOOK_DOWN", "LOOK_UP"
    severity: str = "LOW"
    net_yaw: float = 0.0
    net_pitch: float = 0.0
    net_roll: float = 0.0
    net_iris_h: float = 0.0
    net_iris_v: float = 0.0
    blink_score: float = 0.0
    look_down_score: float = 0.0
    face_center: Tuple[float, float] = (0.5, 0.5)
    face_scale: float = 0.15  # Normalized interocular distance
    attention_score: float = 100.0  # 0 to 100


class GazeTracker:
    """MediaPipe Tasks FaceLandmarker-based gaze and pose tracker."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        preset_name: Optional[str] = None,
        calibration: Optional[CalibrationData] = None,
    ):
        cfg_file = config_path or (settings.BASE_DIR / "backend" / "app" / "config" / "gaze.json")
        with open(cfg_file, "r", encoding="utf-8") as f:
            self.full_config = json.load(f)

        self.preset_name = preset_name or self.full_config.get("active_preset", "strict")
        self.preset = self.full_config["presets"].get(
            self.preset_name, self.full_config["presets"]["strict"]
        )
        self.penalties = self.full_config.get("penalties", {})
        self.body_config = self.full_config.get("body_language", {})
        self.calibration = calibration or CalibrationData()

        # One Euro Filter for 5-DOF signal: [yaw, pitch, roll, iris_h, iris_v]
        filt_cfg = self.full_config.get("filter", {})
        self.filter = OneEuroFilterVector(
            dim=5,
            min_cutoff=filt_cfg.get("one_euro_min_cutoff", 1.0),
            beta=filt_cfg.get("one_euro_beta", 0.007),
            d_cutoff=filt_cfg.get("one_euro_d_cutoff", 1.0),
        )

        # Lazy-loaded MediaPipe detector
        self._detector = None
        self._in_lookaway_state = False

    def _get_detector(self):
        if self._detector is None:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = settings.BASE_DIR / "backend" / "app" / "data" / "face_landmarker.task"
            if not model_path.exists():
                raise FileNotFoundError(f"MediaPipe face_landmarker.task not found at {model_path}")

            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
                num_faces=2,
            )
            self._detector = vision.FaceLandmarker.create_from_options(options)
        return self._detector

    def set_calibration(self, calibration: CalibrationData):
        self.calibration = calibration

    def set_preset(self, preset_name: str):
        if preset_name in self.full_config["presets"]:
            self.preset_name = preset_name
            self.preset = self.full_config["presets"][preset_name]

    def reset(self):
        self.filter.reset()
        self._in_lookaway_state = False

    @staticmethod
    def _extract_euler_angles(transformation_matrix: np.ndarray) -> Tuple[float, float, float]:
        """Extract pitch, yaw, roll in degrees from a 4x4 facial transformation matrix."""
        R = transformation_matrix[:3, :3]
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(R)
        # angles are in degrees: [pitch, yaw, roll]
        pitch, yaw, roll = float(angles[0]), float(angles[1]), float(angles[2])
        return pitch, yaw, roll

    @staticmethod
    def _extract_iris_ratios(
        landmarks: Any,
    ) -> Tuple[float, float]:
        """Compute horizontal and vertical iris displacement within eye sockets."""
        # Left eye
        left_outer = np.array([landmarks[LEFT_EYE_OUTER].x, landmarks[LEFT_EYE_OUTER].y])
        left_inner = np.array([landmarks[LEFT_EYE_INNER].x, landmarks[LEFT_EYE_INNER].y])
        left_top = landmarks[LEFT_EYE_TOP].y
        left_bottom = landmarks[LEFT_EYE_BOTTOM].y
        left_iris = np.array([landmarks[LEFT_IRIS_CENTER].x, landmarks[LEFT_IRIS_CENTER].y])

        left_w = max(1e-4, abs(left_inner[0] - left_outer[0]))
        left_h_ratio = (left_iris[0] - min(left_outer[0], left_inner[0])) / left_w - 0.5
        left_h_h = max(1e-4, abs(left_bottom - left_top))
        left_v_ratio = (left_iris[1] - left_top) / left_h_h - 0.5

        # Right eye
        right_inner = np.array([landmarks[RIGHT_EYE_INNER].x, landmarks[RIGHT_EYE_INNER].y])
        right_outer = np.array([landmarks[RIGHT_EYE_OUTER].x, landmarks[RIGHT_EYE_OUTER].y])
        right_top = landmarks[RIGHT_EYE_TOP].y
        right_bottom = landmarks[RIGHT_EYE_BOTTOM].y
        right_iris = np.array([landmarks[RIGHT_IRIS_CENTER].x, landmarks[RIGHT_IRIS_CENTER].y])

        right_w = max(1e-4, abs(right_outer[0] - right_inner[0]))
        right_h_ratio = (right_iris[0] - min(right_outer[0], right_inner[0])) / right_w - 0.5
        right_h_h = max(1e-4, abs(right_bottom - right_top))
        right_v_ratio = (right_iris[1] - right_top) / right_h_h - 0.5

        iris_h = float((left_h_ratio + right_h_ratio) / 2.0)
        iris_v = float((left_v_ratio + right_v_ratio) / 2.0)
        return iris_h, iris_v

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        timestamp: float,
    ) -> FrameGazeResult:
        """Run landmark, head pose and iris analysis on a single video frame."""
        import mediapipe as mp

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detector = self._get_detector()
        result = detector.detect(mp_image)

        if not result.face_landmarks:
            self._in_lookaway_state = False
            return FrameGazeResult(
                timestamp=timestamp,
                face_detected=False,
                num_faces=0,
                is_looking_direct=False,
                look_away_type="FACE_MISSING",
                severity="HIGH",
                attention_score=0.0,
            )

        num_faces = len(result.face_landmarks)
        landmarks = result.face_landmarks[0]

        # Interocular distance as invariant facial scale
        eye_l = np.array([landmarks[LEFT_EYE_OUTER].x, landmarks[LEFT_EYE_OUTER].y])
        eye_r = np.array([landmarks[RIGHT_EYE_OUTER].x, landmarks[RIGHT_EYE_OUTER].y])
        face_scale = float(np.linalg.norm(eye_l - eye_r))

        face_center = (
            float((landmarks[LEFT_EYE_OUTER].x + landmarks[RIGHT_EYE_OUTER].x) / 2.0),
            float((landmarks[NOSE_TIP].y + landmarks[CHIN].y) / 2.0),
        )

        # 1. 3D Head Pose
        if result.facial_transformation_matrixes:
            raw_pitch, raw_yaw, raw_roll = self._extract_euler_angles(
                result.facial_transformation_matrixes[0]
            )
        else:
            raw_pitch, raw_yaw, raw_roll = 0.0, 0.0, 0.0

        # 2. Iris horizontal and vertical displacement
        raw_iris_h, raw_iris_v = self._extract_iris_ratios(landmarks)

        # 3. Low-latency One Euro Filter
        filtered = self.filter.filter(
            [raw_yaw, raw_pitch, raw_roll, raw_iris_h, raw_iris_v],
            timestamp=timestamp,
        )
        filt_yaw, filt_pitch, filt_roll, filt_iris_h, filt_iris_v = filtered

        # 4. Subtract Baseline Calibration
        net_yaw = filt_yaw - self.calibration.baseline_yaw
        net_pitch = filt_pitch - self.calibration.baseline_pitch
        net_roll = filt_roll - self.calibration.baseline_roll
        net_iris_h = filt_iris_h - self.calibration.baseline_iris_h
        net_iris_v = filt_iris_v - self.calibration.baseline_iris_v

        # 5. Extract Blendshapes
        blink_score = 0.0
        look_down_score = 0.0
        if result.face_blendshapes:
            bs_dict = {b.category_name: b.score for b in result.face_blendshapes[0]}
            blink_score = float((bs_dict.get("eyeBlinkLeft", 0.0) + bs_dict.get("eyeBlinkRight", 0.0)) / 2.0)
            look_down_score = float((bs_dict.get("eyeLookDownLeft", 0.0) + bs_dict.get("eyeLookDownRight", 0.0)) / 2.0)

        # 6. Directional Look-Away Decision with Hysteresis
        max_yaw = self.preset["max_yaw_deg"]
        max_pitch_down = self.preset["max_pitch_down_deg"]
        max_pitch_up = self.preset["max_pitch_up_deg"]
        max_iris_h = self.preset["max_iris_horizontal_ratio"]
        max_iris_v = self.preset["max_iris_vertical_ratio"]
        exit_ratio = self.preset["hysteresis_exit_ratio"]

        # Hysteresis: tighter threshold to exit look-away state
        yaw_limit = max_yaw * exit_ratio if self._in_lookaway_state else max_yaw
        pitch_down_limit = max_pitch_down * exit_ratio if self._in_lookaway_state else max_pitch_down
        pitch_up_limit = max_pitch_up * exit_ratio if self._in_lookaway_state else max_pitch_up
        iris_h_limit = max_iris_h * exit_ratio if self._in_lookaway_state else max_iris_h
        iris_v_limit = max_iris_v * exit_ratio if self._in_lookaway_state else max_iris_v

        # Test directional violations
        look_away_type: Optional[str] = None
        severity = "LOW"

        # Check Downward glance (reading notes, checking phone)
        # In MediaPipe, pitch is negative when looking down, or positive depending on coordinate convention.
        # We test both pitch angle and direct iris downward offset or blendshape.
        is_down = (
            net_pitch < -pitch_down_limit
            or net_iris_v > iris_v_limit
            or look_down_score > 0.45
        )
        is_side = (
            abs(net_yaw) > yaw_limit
            or abs(net_iris_h) > iris_h_limit
        )
        is_up = net_pitch > pitch_up_limit

        # Suppress brief natural eye blinks (< 0.6s) from triggering look-away
        is_eye_closed = blink_score > 0.70

        if is_down:
            look_away_type = "LOOK_DOWN"
            severity = "HIGH"
        elif is_side:
            look_away_type = "LOOK_SIDE"
            severity = "MEDIUM"
        elif is_up:
            look_away_type = "LOOK_UP"
            severity = "LOW"
        elif is_eye_closed:
            look_away_type = "LOOK_DOWN"
            severity = "LOW"

        is_looking_direct = look_away_type is None
        self._in_lookaway_state = not is_looking_direct

        # Compute continuous attention score (100 = centered, 0 = fully deflected)
        yaw_penalty = min(50.0, (abs(net_yaw) / max(1.0, max_yaw)) * 30.0)
        pitch_penalty = min(50.0, (abs(net_pitch) / max(1.0, max_pitch_down)) * 30.0)
        iris_penalty = min(50.0, (abs(net_iris_h) / max(1e-3, max_iris_h)) * 25.0)
        attention = max(0.0, 100.0 - (yaw_penalty + pitch_penalty + iris_penalty))

        return FrameGazeResult(
            timestamp=timestamp,
            face_detected=True,
            num_faces=num_faces,
            is_looking_direct=is_looking_direct,
            look_away_type=look_away_type,
            severity=severity,
            net_yaw=round(net_yaw, 2),
            net_pitch=round(net_pitch, 2),
            net_roll=round(net_roll, 2),
            net_iris_h=round(net_iris_h, 3),
            net_iris_v=round(net_iris_v, 3),
            blink_score=round(blink_score, 3),
            look_down_score=round(look_down_score, 3),
            face_center=(round(face_center[0], 3), round(face_center[1], 3)),
            face_scale=round(face_scale, 3),
            attention_score=round(attention, 1),
        )
