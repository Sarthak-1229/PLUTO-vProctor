<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 9. Quality rules

- Type hints and docstrings everywhere; Pydantic schemas for all API I/O.
- `pytest` coverage for algorithms, scoring engine, parsers; at least one end-to-end test that runs resume → questions → mocked analysis → report.
- Every threshold/weight in `config.py` (no magic numbers in logic).
- Deterministic fallbacks for all LLM calls; log LLM latency and failures.
- Accessibility: keyboard navigable, captions of the spoken question on screen.
- Privacy: all data stays local; add a consent step; store recordings under `/storage/{session_id}` and provide deletion.
- Keep memory in check: stream/read video in chunks, process frames, never load the whole video in RAM.
- Document fairness limits (gaze norms, accents, neurodiversity) in `docs/DECISIONS.md` and make thresholds adjustable in a settings panel.

## 10. Definition of done

0. `python backend/scripts/ingest_datasets.py && python backend/scripts/enrich_questions.py && python backend/scripts/seed_db.py` runs cleanly on my real `datasets/` folders and produces `docs/DATASET_REPORT.md`, with no train/test leakage and every job profile backed by at least 25 real questions.
1. `run_dev.bat` starts backend + frontend; app opens in browser.
2. I can pick a job, upload a resume, see the screening result (including a "rejected but can still interview" flow).
3. I get a filtered, ordered question list and a full spoken interview with live look-away alerts.
4. After the interview, the video and audio pipelines run in parallel and finish, and I see a report with the score breakdown, LLM summary and tips, the reference answer from my dataset for each question, and a deduction timeline where clicking a row seeks the recording to that mm:ss.
5. All tests pass, the benchmark and the five `evaluate_*.py` scripts run on the val/test splits and print their metrics, and the docs are written.
