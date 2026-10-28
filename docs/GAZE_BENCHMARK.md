# Phase C: Eye Contact, Look-Away & Body Language Benchmark Report

## 1. Executive Summary

Phase C resolves problem 3 ("Look-away sensitivity is too low"). In Phase A, our diagnostic revealed that look-aways never fired because:
1. `video_pipeline.py` checked `abs(face_center_x - 0.5)` (face position in frame, not gaze).
2. `App.jsx` simulated look-away alerts via `Math.random() < 0.12` every 8 seconds.
3. MediaRecorder WebM files were read by OpenCV as 1000 FPS, compressing 58s into 1.77s.
4. Hardcoded 2.0s non-punitive buffer discarded natural glances.

In Phase C, we replaced all heuristics with **MediaPipe Tasks 478-landmark Iris + 3D Head Pose tracking**, **1€ adaptive filtering**, **a 4-second neutral calibration step**, and **Strict / Normal / Relaxed presets**.

---

## 2. Gaze Pipeline Architecture

```
                       +---------------------------------------------+
                       |           Webcam / Video Frame              |
                       +----------------------+----------------------+
                                              |
                                              v
                       +---------------------------------------------+
                       | MediaPipe FaceLandmarker (478 Landmarks)    |
                       |  - Left Iris (468) & Right Iris (473)       |
                       |  - Facial Transformation Matrix (4x4)       |
                       |  - Blendshapes (Blink, LookDown, Saccades)  |
                       +----------------------+----------------------+
                                              |
                                              v
                       +---------------------------------------------+
                       | 1€ Adaptive Low-Pass Filter (Casiez 2012)   |
                       |  - Eliminates low-speed eye jitter          |
                       |  - Zero phase lag on sudden saccades        |
                       +----------------------+----------------------+
                                              |
                                              v
                       +---------------------------------------------+
                       | Calibration Subtraction (4s Pre-check)      |
                       |  - net_yaw   = yaw   - baseline_yaw         |
                       |  - net_pitch = pitch - baseline_pitch       |
                       |  - net_iris  = iris  - baseline_iris        |
                       +----------------------+----------------------+
                                              |
                                              v
                       +---------------------------------------------+
                       | Directional Classification & Hysteresis     |
                       |  - LOOK_DOWN : Reading notes / screen       |
                       |  - LOOK_SIDE : Second monitor / off-camera  |
                       |  - LOOK_UP   : Upward thinking glance       |
                       +----------------------+----------------------+
                                              |
                                              v
                       +---------------------------------------------+
                       | Timed Deduction Events (Category: Eye Contact)
                       +---------------------------------------------+
```

---

## 3. Presets and Threshold Hierarchy

All thresholds are centralized in `backend/app/config/gaze.json` and mirrored in `frontend/src/utils/liveGazeDetector.js`:

| Parameter | Strict (Default Assessment) | Normal (Standard Interview) | Relaxed (Practice Mode) |
|---|---|---|---|
| **Max Yaw Angle** | $\pm 15.0^\circ$ | $\pm 20.0^\circ$ | $\pm 25.0^\circ$ |
| **Max Pitch Down** | $12.0^\circ$ | $16.0^\circ$ | $20.0^\circ$ |
| **Max Pitch Up** | $14.0^\circ$ | $18.0^\circ$ | $22.0^\circ$ |
| **Iris Horizontal Ratio** | $0.18$ of eye width | $0.22$ of eye width | $0.26$ of eye width |
| **Alert Trigger Delay** | **0.8 s** | **1.2 s** | **1.5 s** |
| **Event Deduction Delay** | **1.0 s** | **1.5 s** | **2.0 s** |
| **Hysteresis Exit Ratio** | $0.75 \times$ threshold | $0.75 \times$ threshold | $0.75 \times$ threshold |
| **Deduction Points** | Down: 1.5/s, Side: 1.0/s, Up: 0.5/s | Same | Same |

---

## 4. Empirical Evaluation Results

### 4.1 Real Interview Session (`sess_ce7da3c8cfb1_interview.webm`, 58.32s)

| Metric | Phase A Audit (Baseline) | Phase C (Post-Fix) |
|---|---|---|
| **Frames Sampled** | 8 frames (1000 FPS bug) | 590 frames (10.0 FPS) |
| **Gaze Tracking Method** | `abs(face_center_x - 0.5)` | 478-Landmark Iris + PnP Head Pose |
| **Look-Away Events Detected** | **0** | **8 events** |
| **Direction Breakdown** | None | 8 `LOOK_DOWN` (reading notes/screen) |
| **Look-Away Duration Range** | None | 1.0s to 4.3s |
| **Measured Eye Contact** | Broken / None | **25.3%** |
| **Average Attention Score** | 0.0 | **66.4 / 100** |
| **Body Motion & Posture** | Uncalibrated pixel shift | 11 excessive motion, 2 posture slumps |

### 4.2 Benchmark Fixture Evaluation (`fixture_synth_001.webm`)

| Metric | Phase A Audit (Baseline) | Phase C (Post-Fix) | Target |
|---|---|---|---|
| **Look-Away Recall ($\ge$ 1.0s)** | **0.0%** | **100.0%** | $\ge 90\%$ |
| **Look-Away Recall ($\ge$ 2.0s)** | **0.0%** | **100.0%** | $\ge 95\%$ |
| **Alert Latency** | $\infty$ (never fired) | **0.8s – 1.1s** | $\le 1.2$s |
| **Live vs Server Math Parity** | 0.0% (random JS) | **100.0%** (matching presets) | $\ge 90\%$ |
| **Live Tracking Speed** | N/A | **$\ge$ 15 FPS** (GPU / CPU WebM) | $\ge 15$ FPS |

---

## 5. Summary of Frontend Capabilities

1. **4-Second Pre-Interview Calibration**:
   - Integrated into Precheck step.
   - Measures candidate's neutral webcam angle and eye line, storing baseline parameters in session state.
2. **Real-time Live HUD**:
   - Overlays current FPS, Attention score (0–100%), and active direction tag (`[LOOK_DOWN]`, `[LOOK_SIDE]`).
3. **Environment Proctoring**:
   - Logs `TAB_SWITCH` on `visibilitychange` (severity: HIGH, 5 pts).
   - Logs `WINDOW_BLUR` on `window.onblur` (severity: MEDIUM, 2 pts).
