---
description: PLUTO Phase 8: error handling, privacy, performance and docs
---

# Phase 8: Polish

Read: `docs/spec/08-quality-and-done.md`.

1. Error handling and fallbacks (camera denied, no face, LLM down, dataset missing), loading states, structured logging.
2. Consent screen, "Delete my data" button, settings panel for adjustable thresholds.
3. Performance for 6 GB VRAM: log peak VRAM, tune `keep_alive`, batch sizes.
4. Finish `README.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`.
5. Run the full test suite and every `evaluate_*.py` script.
