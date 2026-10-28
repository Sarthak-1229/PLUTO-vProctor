# PLUTO vProctor: API Reference Specification

All endpoints are hosted locally at `http://127.0.0.1:8000`.  
Interactive Swagger/OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

---

## 1. System & Health

### `GET /health`
Returns system status, active environment, and local Ollama endpoint status.
- **Response:** `200 OK`
```json
{
  "status": "ok",
  "app_name": "PLUTO vProctor",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-21T05:30:00Z",
  "ollama_endpoint": "http://localhost:11434",
  "model": "qwen2.5:3b"
}
```

---

## 2. Job Profiles & Search

### `GET /api/jobs`
List all 12 verified enterprise job profiles.
- **Response:** `200 OK`
```json
[
  {
    "id": "job_sec_analyst_01",
    "title": "Information Security Analyst",
    "company": "CyberNova Sentinel",
    "domain": "Security",
    "min_experience_years": 3,
    "pass_threshold": 0.65,
    "required_skills": ["Network Security & Cryptography", "Application Security", "Zero Trust"],
    "preferred_skills": ["SIEM & Threat Hunting", "Firewalls & IDS/IPS"]
  }
]
```

### `GET /api/jobs/search?q={query}`
Search jobs using prefix/substring Trie autocomplete over job titles, domains, and companies.

---

## 3. Resume Parsing & Screening

### `POST /api/resume/upload`
Uploads candidate resume (PDF or DOCX), extracts sections, parses skills via Trie/fuzzy matching, merges experience intervals, and computes candidate fit via trained ML classifier.
- **Request:** `multipart/form-data`
  - `file`: Resume binary (`.pdf` or `.docx`)
  - `job_id`: Target Job ID (string)
- **Response:** `200 OK`
```json
{
  "session_id": "sess_8f29c1b3021a",
  "job_id": "job_sec_analyst_01",
  "job_title": "Information Security Analyst",
  "candidate_name": "Alex Vance",
  "fit_score": 0.88,
  "status": "PASS",
  "decision": "PASS",
  "skill_score": 0.92,
  "experience_years": 5.0,
  "matched_skills": ["Network Security & Cryptography", "Application Security", "Zero Trust"],
  "missing_skills": [],
  "screening": { ... }
}
```

---

## 4. Interview Execution & Delivery

### `POST /api/interview/{sessionId}/start`
Initializes the interview session. Selects questions from the candidate pool using:
1. Inverted index & TF-IDF candidate retrieval
2. Min-Heap Top-K ranking
3. Maximal Marginal Relevance (MMR) diversification ($\lambda = 0.7$)
4. 0/1 Dynamic Programming Knapsack (12-minute budget = 720 seconds)
5. Custom Merge Sort ordering (warm-up $\to$ definition $\to$ explain $\to$ scenario)
- **Response:** `200 OK`
```json
{
  "session_id": "sess_8f29c1b3021a",
  "status": "STARTED",
  "total_questions": 6,
  "questions": [
    {
      "order_index": 1,
      "question_id": "q_468a2d1e",
      "question": "What is the primary objective of a Zero Trust architecture?",
      "est_seconds": 70,
      "is_warmup": true
    }
  ]
}
```

### `POST /api/interview/{sessionId}/followup`
Checks candidate response and generates an adaptive follow-up question grounded in the real dataset if the answer was brief.
- **Request Body:**
```json
{
  "question_id": "q_468a2d1e",
  "transcript": "Zero Trust assumes no user is trusted by default inside the perimeter."
}
```

### `POST /api/interview/{sessionId}/recording`
Uploads the complete candidate webcam and audio recording (`.webm`).
- **Request:** `multipart/form-data` (file: `session_interview.webm`)

### `GET /api/interview/{sessionId}/video`
Streams the recorded `.webm` video for browser playback and deduction timeline scrubbing.

### `DELETE /api/interview/{sessionId}`
Permanently deletes all recording files and database session records for privacy compliance.

---

## 5. Multimodal Analysis Pipelines

### `POST /api/analysis/{sessionId}/run`
Triggers parallel execution of:
- **Video Pipeline:** OpenCV Haar/Vision tracking, EMA smoothing, motion variance sliding window, look-away interval merging.
- **Audio Pipeline:** PyAV 16 kHz mono extraction, `faster-whisper` transcription, KMP & Rabin-Karp filler word detection, speech pause analysis (>1.2s), WPM pace calculation.
- **Response:** `200 OK` (`{"status": "PROCESSING", "session_id": "..."}`)

### `GET /api/analysis/{sessionId}/status`
Polls per-pipeline analysis progress.
- **Response:** `200 OK`
```json
{
  "session_id": "sess_8f29c1b3021a",
  "overall_status": "COMPLETED",
  "video": { "status": "COMPLETED", "violations_count": 3 },
  "audio": { "status": "COMPLETED", "wpm": 128, "filler_count": 4 }
}
```

---

## 6. Evaluation Reports & PDF Generation

### `GET /api/report/{sessionId}`
Aggregates answer scores (60% algorithmic relevance + 40% LLM rubric), proctoring deductions, and resume match into overall weighted score (0–100), letter grade (A/B/C/D), deduction timeline, question review, and LLM summary.

### `GET /api/report/{sessionId}/pdf`
Downloads an official, formatted evaluation report PDF generated dynamically via ReportLab.

---

## 7. Dynamic Settings & Fairness Limits

### `GET /api/settings`
Retrieves current proctoring sensitivity thresholds and category weights.

### `PUT /api/settings`
Dynamically adjusts thresholds (gaze tolerance, head turn limits, speech pause thresholds, filler word penalties, and category weights).
- **Request Body:**
```json
{
  "gaze_tolerance_x": 0.18,
  "head_yaw_deg": 30.0,
  "speech_pause_sec": 4.0,
  "filler_penalty": 0.5
}
```
