# Antigravity Working Rules — PLUTO vProctor v2

1. Read root `GEMINI.md`, `.agent/rules/*`, `.agent/workflows/*`, `KICKOFF.md`, README and this upgrade pack before work.
2. Actual repository state outranks any inventory document. Verify all claims.
3. Never rebuild from scratch; preserve working modules and offline mode.
4. Start with audit and cleanup proposal. No destructive cleanup without explicit approval.
5. Back up DB and storage before migrations or cleanup.
6. Never delete datasets, model weights, migrations, fixtures, source, reports or user media as “unused” without proof and approval.
7. Keep GPU locks and current model concurrency constraints.
8. Keep curated question datasets as ground truth. No synthetic replacement.
9. Use Alembic for schema changes; test upgrade on a copy of current DB and clean PostgreSQL.
10. Backend authorization is mandatory; frontend hiding is not security.
11. Use tests before/with implementation. Do not claim success without running commands and reporting output.
12. Keep phases small. Stop at each phase gate.
13. Do not log secrets, resumes, transcripts, recordings or biometric data.
14. Treat proctoring signals as uncertain evidence, not proof of cheating.
15. Preserve API compatibility where possible and document breaking changes.
16. Use feature flags for hosted interview mode and live media.
17. Do not introduce cloud AI/media providers without explicit opt-in and documented data flow.
18. Keep documentation, migration notes, environment examples and deployment runbooks current.
