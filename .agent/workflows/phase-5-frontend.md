---
description: PLUTO Phase 5: frontend setup, interview UI, live proctoring, recording
---

# Phase 5: Frontend and interview experience

Read: `docs/spec/5b-interview-analysis.md` (section 5.4) and `docs/spec/07-api.md`.

1. Pages: job/company select + resume upload + screening result (with "Proceed anyway"), consent, pre-check (camera/mic, distance, lighting), interview, processing, report shell.
2. Interview page: question text + `speechSynthesis`, progress, per-question timer, Next / auto-advance on silence.
3. Live proctoring in the browser with MediaPipe Tasks Vision (face landmarks with iris, pose): look-away alert after about 2 s, motion/posture/face-missing/multiple-faces/tab-switch events, live score gauge.
4. MediaRecorder recording, per-question timestamps, upload endpoint and WebSocket events.
5. Use the browser agent to verify page flows load; I will test the real webcam manually.

Acceptance: full flow from upload to a stored recording works end to end with a mocked or real camera.
