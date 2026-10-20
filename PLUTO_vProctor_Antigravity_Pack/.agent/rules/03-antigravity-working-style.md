# Rule: how to work in Antigravity (Always On)

- Use **Planning mode** for each phase. Produce the implementation plan and task list artifacts FIRST, then wait for my review before large edits.
- One phase per conversation/task. Do not start the next phase until I say so. Keep each run small to save quota.
- Read only the spec files named by the current workflow. Do not re-read the whole spec every turn.
- Terminal: Windows-safe commands, create a venv in `backend/.venv`, never run destructive commands (rm -rf, format, drive-wide deletes). Ask before installing anything large (torch, CUDA builds).
- After each phase: run the tests and the phase's acceptance checks, then produce a short **walkthrough artifact** with what was built, commands to run it, and the metrics/outputs.
- Frontend phases: use the browser agent to verify pages load and flows work. The real webcam/mic tests are done by me manually; for automated checks use mocked media or a sample video.
- Commit with git at the end of each phase with a clear message.
- Where something is ambiguous, choose a sensible default, log it in `docs/DECISIONS.md`, and continue. Ask me only for blockers (missing dataset path, missing system dependency).
