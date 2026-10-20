<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 7. API (design and document in `docs/API.md`)

- `GET /api/jobs`, `GET /api/jobs/search?q=` (trie-based)
- `POST /api/resume/upload` (multipart: file, job_id) → `{session_id, parsed, fit, screening}`
- `POST /api/interview/{sid}/start` → filtered question list
- `WS /ws/interview/{sid}` → events: `question_started`, `question_ended`, `live_event`, `follow_up`
- `POST /api/interview/{sid}/recording` (upload webm)
- `POST /api/analysis/{sid}/run` → starts parallel pipelines; `GET /api/analysis/{sid}/status` (progress per pipeline)
- `GET /api/report/{sid}` (JSON), `GET /api/report/{sid}/pdf`
