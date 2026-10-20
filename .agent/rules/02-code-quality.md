# Rule: code quality (Always On)

- Type hints and docstrings (include time/space complexity for algorithms). Pydantic schemas for all API I/O.
- pytest for algorithms, parsers, scoring engine, plus one end-to-end test (resume -> questions -> mocked analysis -> report).
- No magic numbers in logic: constants in `backend/app/config.py`.
- Stream video/audio in chunks; never load a whole recording into RAM.
- Handle failures gracefully: camera denied, no face, LLM down, dataset file missing.
- Privacy: consent screen, local-only storage under `/storage/{session_id}`, "Delete my data" button.
- Fairness: thresholds adjustable in a settings panel; document limits (gaze norms, accents, neurodiversity) in `docs/DECISIONS.md`.
