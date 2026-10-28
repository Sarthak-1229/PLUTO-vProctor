# PLUTO vProctor: AI Ethics, Gaze Norms & Fairness Charter

Automated video interview proctoring systems can inadvertently introduce bias if baseline human variability is ignored. This document outlines PLUTO vProctor's architectural safeguards regarding neurodiversity, cultural differences, and speech variability.

---

## 1. Neurodiversity & Cultural Gaze Norms

Direct, unwavering eye contact is not a universal marker of honesty or competence:
- **Cultural Differences:** In several Asian and Indigenous cultures, prolonged direct eye contact with an authority figure or interviewer is considered disrespectful; natural downward gaze reflects attentiveness.
- **Neurodiversity:** Individuals with ADHD, autism spectrum conditions, or cognitive processing differences frequently avert gaze when recalling complex technical details or formulating sentences.
- **Visual Impairments:** Strabismus, nystagmus, and asymmetric facial geometry affect default pupil positioning.

### Safeguards Implemented:
1. **Interactive Neutral Calibration:** The 4-second Pre-Flight Calibration captures the candidate's personal neutral baseline posture and eye geometry, subtracting natural offsets rather than enforcing an arbitrary geometric origin.
2. **Directional Tagging:** The engine distinguishes `LOOK_DOWN` (reading prepared cheat-sheets) from natural horizontal or upward glancing (`LOOK_SIDE`, `LOOK_UP`).
3. **Adjustable Sensitivity Presets:** Evaluators can select between `Strict`, `Normal`, and `Relaxed` presets, or disable look-away penalties entirely for accommodations.

---

## 2. Accents & Speech Fluency Variance

Whisper-family speech models and acoustic detectors can exhibit higher error rates with regional accents or non-native English speakers.

### Safeguards Implemented:
1. **Multimodal Dual-Tier Answer Grading:** Answer evaluation combines semantic embeddings (60%) with lexical keyword matching and rubric scoring (40%). Candidates are not penalized for syntactic phrasing differences as long as conceptual correctness is demonstrated.
2. **Fuzzy Distance Matching with English Stop-Word Guarding:** Common English short words ("a", "an", "the", "he", "him", "her") are protected from false-positive filler word matching.
3. **Non-Punitive Natural Pauses:** Pauses under 3.5 seconds are treated as normal thoughtful synthesis and carry zero penalty.

---

## 3. Human-in-the-Loop Decision Support

PLUTO vProctor's evaluation dossier is strictly an **advisory decision-support tool**:
- Automated reports provide timestamped evidence, video scrubbing links, and rubric breakdowns so human hiring managers can review context before making decisions.
- Overrides ("Proceed Anyway") ensure candidates are never unilaterally screened out by automated parsers without human review.

