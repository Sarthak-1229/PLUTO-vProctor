"""Video analysis pipeline using MediaPipe FaceLandmarker, iris tracking, and posture evaluation.

Implements Section 5.5 of docs/spec/5b-interview-analysis.md with Phase C overhaul:
- 10+ FPS sampling rate
- MediaPipe 478-landmark iris + 3D head-pose tracking via GazeTracker
- Directional look-away classification (LOOK_DOWN, LOOK_SIDE, LOOK_UP)
- Strict/Normal/Relaxed presets loaded from backend/app/config/gaze.json
- Neutral calibration baseline subtraction
- Inter-ocular distance normalized body motion and posture evaluation
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.app.algorithms.interval_ops import merge_intervals, total_duration
from backend.app.config import settings
from backend.app.pipelines.gaze_tracker import CalibrationData, FrameGazeResult, GazeTracker


class VideoAnalysisPipeline:
    """Offline and server-side video proctoring pipeline analyzing gaze, head pose, posture, and face continuity."""

    def __init__(self, target_fps: float = 10.0, preset_name: Optional[str] = None):
        self.target_fps = target_fps
        self.gaze_tracker = GazeTracker(preset_name=preset_name)

    def _iter_frames(self, video_path: Path):
        """Decode video frames resiliently using PyAV, with OpenCV as fallback."""
        try:
            import av
            container = av.open(str(video_path))
            video_stream = next((s for s in container.streams if s.type == "video"), None)
            if video_stream is not None:
                duration_sec = float(container.duration or 0) / av.time_base if container.duration else 300.0
                min_interval = 1.0 / max(1.0, self.target_fps)
                last_t = -1.0
                frame_count = 0

                for packet in container.demux(video_stream):
                    for frame in packet.decode():
                        t = float(frame.time) if frame.time is not None else round(frame_count / 30.0, 2)
                        frame_count += 1
                        if t - last_t >= min_interval or last_t < 0:
                            last_t = t
                            bgr = frame.to_ndarray(format="bgr24")
                            yield bgr, round(t, 2), duration_sec
                container.close()
                return
        except Exception as e:
            print(f"PyAV decoding notice, falling back to OpenCV: {e}")

        # Fallback to OpenCV
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return
        orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if orig_fps <= 0 or np.isnan(orig_fps) or orig_fps > 65.0 or orig_fps < 5.0:
            orig_fps = 30.0
        raw_total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1800
        duration_sec = raw_total_frames / orig_fps if raw_total_frames > 0 else 300.0
        frame_step = max(1, int(round(orig_fps / self.target_fps)))
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % frame_step == 0:
                t = round(idx / orig_fps, 2)
                yield frame, t, duration_sec
            idx += 1
        cap.release()

    def analyze_video(
        self,
        video_path: Path,
        *,
        calibration: Optional[Dict[str, Any]] = None,
        preset_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        """Process video and generate timestamped proctoring violation events and aggregate metrics."""
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Set calibration and preset if provided
        if calibration:
            self.gaze_tracker.set_calibration(CalibrationData.from_dict(calibration))
        if preset_name:
            self.gaze_tracker.set_preset(preset_name)

        self.gaze_tracker.reset()

        analyzed_frames = 0
        direct_eye_contact_count = 0
        last_sampled_t = 0.0

        # Violation tracking state
        look_away_events: List[Dict[str, Any]] = []
        face_missing_intervals: List[Tuple[float, float]] = []
        multi_face_intervals: List[Tuple[float, float]] = []
        motion_intervals: List[Tuple[float, float]] = []
        posture_intervals: List[Tuple[float, float]] = []

        curr_lookaway_start: Optional[float] = None
        curr_lookaway_type: Optional[str] = None
        curr_missing_start: Optional[float] = None
        curr_multiface_start: Optional[float] = None

        prev_face_center: Optional[Tuple[float, float]] = None
        attention_scores: List[float] = []

        event_min_dur = self.gaze_tracker.preset.get("event_deduction_sec", 1.0)
        body_cfg = self.gaze_tracker.body_config
        penalties = self.gaze_tracker.penalties

        for frame, t_current, est_dur in self._iter_frames(video_path):
            last_sampled_t = t_current
            analyzed_frames += 1

            if progress_callback and analyzed_frames % 20 == 0:
                if est_dur and est_dur > 0:
                    est_prog = min(0.95, t_current / est_dur)
                    progress_callback(est_prog)

            # Process frame through GazeTracker
            try:
                res: FrameGazeResult = self.gaze_tracker.process_frame(frame, t_current)
            except Exception as e:
                print(f"Warning: Frame at t={t_current} processing error: {e}")
                continue

            attention_scores.append(res.attention_score)

            # 1. Face continuity & Multi-face tracking
            if not res.face_detected:
                if curr_missing_start is None:
                    curr_missing_start = t_current
            else:
                if curr_missing_start is not None:
                    if (t_current - curr_missing_start) >= 1.0:
                        face_missing_intervals.append((curr_missing_start, t_current))
                    curr_missing_start = None

                if res.num_faces > 1:
                    if curr_multiface_start is None:
                        curr_multiface_start = t_current
                else:
                    if curr_multiface_start is not None:
                        if (t_current - curr_multiface_start) >= 0.5:
                            multi_face_intervals.append((curr_multiface_start, t_current))
                        curr_multiface_start = None

            # 2. Eye Contact & Directional Look-Away Tracking
            if res.is_looking_direct:
                direct_eye_contact_count += 1
                if curr_lookaway_start is not None:
                    dur = t_current - curr_lookaway_start
                    if dur >= event_min_dur:
                        look_away_events.append({
                            "start": curr_lookaway_start,
                            "end": t_current,
                            "duration": dur,
                            "type": curr_lookaway_type or "LOOK_SIDE",
                        })
                    curr_lookaway_start = None
                    curr_lookaway_type = None
            else:
                if curr_lookaway_start is None:
                    curr_lookaway_start = t_current
                    curr_lookaway_type = res.look_away_type
                elif res.look_away_type == "LOOK_DOWN" and curr_lookaway_type != "LOOK_DOWN":
                    # Upgrade to LOOK_DOWN if looking down during glance
                    curr_lookaway_type = "LOOK_DOWN"

            # 3. Body Motion & Posture Slump Tracking (Normalized by face scale)
            if res.face_detected:
                scale = max(0.05, res.face_scale)
                if prev_face_center is not None:
                    dx = (res.face_center[0] - prev_face_center[0]) / scale
                    dy = (res.face_center[1] - prev_face_center[1]) / scale
                    motion_dist = math.sqrt(dx * dx + dy * dy)

                    motion_thresh = body_cfg.get("motion_threshold_norm", 0.08)
                    if motion_dist > motion_thresh:
                        motion_intervals.append((max(0.0, t_current - 0.5), t_current))

                    # Posture slump
                    baseline_y = self.gaze_tracker.calibration.baseline_nose_y
                    slump_thresh = body_cfg.get("posture_y_slump_norm", 0.12)
                    if (res.face_center[1] - baseline_y) / scale > slump_thresh:
                        posture_intervals.append((max(0.0, t_current - 0.5), t_current))

                prev_face_center = res.face_center

        # Flush open intervals at video end
        final_time = round(last_sampled_t, 2)
        if curr_lookaway_start is not None:
            dur = final_time - curr_lookaway_start
            if dur >= event_min_dur:
                look_away_events.append({
                    "start": curr_lookaway_start,
                    "end": final_time,
                    "duration": dur,
                    "type": curr_lookaway_type or "LOOK_SIDE",
                })
        if curr_missing_start is not None and (final_time - curr_missing_start) >= 1.0:
            face_missing_intervals.append((curr_missing_start, final_time))
        if curr_multiface_start is not None and (final_time - curr_multiface_start) >= 0.5:
            multi_face_intervals.append((curr_multiface_start, final_time))

        if progress_callback:
            progress_callback(1.0)

        # Merge intervals to eliminate overlaps
        merged_missing = merge_intervals(face_missing_intervals)
        merged_multiface = merge_intervals(multi_face_intervals)
        merged_motion = merge_intervals(motion_intervals)
        merged_posture = merge_intervals(posture_intervals)

        # Format events
        events: List[Dict[str, Any]] = []

        # Look-away deduction events
        down_count = 0
        side_count = 0
        up_count = 0

        for la in look_away_events:
            la_type = la["type"]
            dur = la["duration"]

            if la_type == "LOOK_DOWN":
                down_count += 1
                rate = penalties.get("look_down_per_sec", 1.5)
                sev = "HIGH"
                reason = f"Candidate looked downward (reading notes/screen) for {dur:.1f}s"
            elif la_type == "LOOK_UP":
                up_count += 1
                rate = penalties.get("look_up_per_sec", 0.5)
                sev = "LOW"
                reason = f"Candidate glanced upward (thinking) for {dur:.1f}s"
            else:
                side_count += 1
                rate = penalties.get("look_side_per_sec", 1.0)
                sev = "MEDIUM"
                reason = f"Candidate looked away from camera/screen for {dur:.1f}s"

            pts = round(rate * dur, 1)

            events.append({
                "id": f"evt_lookaway_{uuid.uuid4().hex[:8]}",
                "t_start": la["start"],
                "t_end": la["end"],
                "category": "Eye contact",
                "type": la_type,
                "severity": sev,
                "points_deducted": pts,
                "reason": reason,
            })

        # Face missing events
        for start, end in merged_missing:
            dur = end - start
            events.append({
                "id": f"evt_missing_{uuid.uuid4().hex[:8]}",
                "t_start": start,
                "t_end": end,
                "category": "Proctoring integrity",
                "type": "FACE_MISSING",
                "severity": "HIGH",
                "points_deducted": round(penalties.get("face_missing_per_sec", 2.0) * dur, 1),
                "reason": f"Candidate face completely missing from frame for {dur:.1f}s",
            })

        # Multiple face events
        for start, end in merged_multiface:
            dur = end - start
            events.append({
                "id": f"evt_multiface_{uuid.uuid4().hex[:8]}",
                "t_start": start,
                "t_end": end,
                "category": "Proctoring integrity",
                "type": "MULTIPLE_FACES",
                "severity": "HIGH",
                "points_deducted": round(penalties.get("multiple_faces_per_sec", 2.5) * dur, 1),
                "reason": f"Multiple individuals detected in camera view for {dur:.1f}s",
            })

        # Excessive motion events
        for start, end in merged_motion:
            dur = end - start
            events.append({
                "id": f"evt_motion_{uuid.uuid4().hex[:8]}",
                "t_start": start,
                "t_end": end,
                "category": "Body language and motion",
                "type": "EXCESSIVE_MOTION",
                "severity": "MEDIUM",
                "points_deducted": penalties.get("excessive_motion_each", 1.0),
                "reason": f"Frequent or sudden posture shift/fidgeting ({dur:.1f}s)",
            })

        # Posture slump events
        for start, end in merged_posture:
            dur = end - start
            events.append({
                "id": f"evt_posture_{uuid.uuid4().hex[:8]}",
                "t_start": start,
                "t_end": end,
                "category": "Body language and motion",
                "type": "POSTURE_SLUMP",
                "severity": "LOW",
                "points_deducted": penalties.get("posture_slump_each", 0.5),
                "reason": f"Pronounced posture slouching/leaning detected ({dur:.1f}s)",
            })

        eye_contact_pct = (
            round((direct_eye_contact_count / float(analyzed_frames)) * 100.0, 1)
            if analyzed_frames > 0
            else 0.0
        )
        avg_attention = (
            round(sum(attention_scores) / len(attention_scores), 1)
            if attention_scores
            else 0.0
        )

        return {
            "duration_sec": final_time,
            "analyzed_frames": analyzed_frames,
            "sample_rate_fps": round(analyzed_frames / max(1.0, final_time), 1),
            "metrics": {
                "face_detected": analyzed_frames > 0 and len(merged_missing) < (analyzed_frames * 0.8),
                "eye_contact_percentage": eye_contact_pct,
                "average_attention_score": avg_attention,
                "look_away_count": len(look_away_events),
                "look_down_count": down_count,
                "look_side_count": side_count,
                "look_up_count": up_count,
                "face_missing_count": len(merged_missing),
                "multiple_faces_count": len(merged_multiface),
                "excessive_motion_count": len(merged_motion),
                "posture_slump_count": len(merged_posture),
                "active_preset": self.gaze_tracker.preset_name,
                "calibration": self.gaze_tracker.calibration.to_dict(),
            },
            "events": events,
        }


video_pipeline = VideoAnalysisPipeline()
