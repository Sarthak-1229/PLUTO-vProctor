# Kickoff: how to start in Antigravity

## One-time setup
1. Create an empty folder `pluto-vproctor/`. Copy everything from this pack into it (`GEMINI.md`, `.agent/`, `docs/spec/`).
2. Copy your datasets into `pluto-vproctor/datasets/data/` and `pluto-vproctor/datasets/data1/` (train, val, test in each).
3. Install and start Ollama, then run `ollama pull qwen2.5:3b`. Install ffmpeg, Python 3.10+ and Node 18+.
4. Open the folder in Antigravity (File > Open Folder). Open the Agent panel / Agent Manager.
5. In the Rules panel confirm `GEMINI.md` and the four files in `.agent/rules/` are active (set Activation Mode to **Always On** for each).
   If your version looks for `.agents/` instead of `.agent/`, rename the folder.
6. Settings: use **Planning** mode for phases. Set the terminal policy so risky commands need review (keep a deny list for destructive commands).

## Run phase by phase (new conversation for each phase)
Type `/phase-0-setup` in the agent panel. Review the plan and task-list artifacts, approve, let it run, read the walkthrough artifact, then start the next one:

`/phase-0-setup` > `/phase-1-algorithms` > `/phase-2-dataset` (review the dataset report!) > `/phase-3-resume` > `/phase-4-questions` > `/phase-5-frontend` > `/phase-6-analysis` > `/phase-7-scoring-report` > `/phase-8-polish` > `/phase-9-project-report`

`/run-all-evals` can be used any time after Phase 7.

## If you prefer one single prompt
Paste this in the Agent Manager in Planning mode:

> Build the project described in `GEMINI.md` and `docs/spec/`. Start with `/phase-0-setup` only. Produce an implementation plan first. Stop after Phase 0 and wait for my approval before any other phase.

## Tips for the 6 GB VRAM machine and quota
- Small scoped phases use less quota than one giant run.
- Do not ask the agent to run Whisper, Ollama and the video pipeline at the same time while testing.
- Test the real webcam and microphone flow yourself; the browser agent cannot stand in for your camera.
