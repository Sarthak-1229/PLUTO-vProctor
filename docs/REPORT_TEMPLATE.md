# PLUTO vProctor: Academic Project Report Template & Submission Guide

This document serves as the project report template and submission guide for your academic presentation and technical evaluation. All quantitative tables are populated with real benchmark measurements from `docs/DATASET_REPORT.md` and `docs/EVALUATION_SUMMARY.md`.

---

## Academic Project Checklist

- [x] **Problem Definition & Motivation**: Local, offline mock-interviewing with multi-modal proctoring under 6 GB VRAM constraints.
- [x] **Dataset Authenticity**: 1,799 verified technical questions ingested from `datasets/data*/`; zero hallucinated questions.
- [x] **Algorithmic Rigor**: 16 handmade algorithms implemented, tested (101 unit/integration tests), and benchmarked.
- [x] **Model Evaluation**: Full held-out test split evaluations (Domain Classification, Question Retrieval, Answer Relevance, Resume Screening, Question Selection).
- [x] **Full-Stack Implementation**: FastAPI backend + React Vite frontend + MediaPipe/OpenCV + faster-whisper + ReportLab.
- [x] **Privacy & Fairness Compliance**: 100% offline local processing, candidate consent checkbox, dynamic settings panel, and instant data deletion.

---

## 1. Project Specifications Summary

| Property | Value / Implementation |
|---|---|
| **Project Title** | PLUTO vProctor: Local Offline AI Mock-Interview & Proctoring Platform |
| **System Architecture** | Client-Server (React SPA + FastAPI REST Server) |
| **Host Environment** | Windows PC, 6 GB VRAM GPU, Offline Local Operation |
| **Local LLM** | `qwen2.5:3b` via Ollama (`format: "json"`, `keep_alive: 30s`) |
| **Speech-to-Text** | `faster-whisper` (int8, CPU/CUDA dynamic scheduling) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, CPU) |
| **Database** | SQLite 3 via SQLAlchemy ORM (`pluto.db`) |
| **Total Clean Questions** | 1,799 unique technical Q&A pairs (Train: 1,258, Val: 269, Test: 272) |
| **Verified Job Profiles** | 12 enterprise profiles across 11 technical domains |
| **Unit & E2E Test Suite** | 101 tests, 100% passing (`pytest backend/tests`) |

---

## 2. Quantitative Evaluation Results (Fillable / Final)

### A. Question-to-Answer Retrieval Evaluation (Held-Out Test Split)
*Protocol: 272 gold (Question, Answer) pairs from test split.*

| Model | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| TF-IDF (Cosine) | 63.2% | 77.6% | 80.5% | 0.713 |
| Handmade BM25 | 62.1% | 76.1% | 78.7% | 0.704 |
| **MiniLM Embeddings (Dense)** | **80.9%** | **92.6%** | **96.0%** | **0.875** |

### B. Answer Relevance Classification Evaluation (Test Split)
*Protocol: 272 true pairs + 272 domain-clustered hard negative pairs.*

| Model | Accuracy | Precision | Recall | F1-Score | ROC-AUC |
|---|---|---|---|---|---|
| **Logistic Regression** | **99.63%** | 99.27% | 100.00% | 0.9963 | 1.0000 |
| **Gradient Boosting** | **99.82%** | 99.63% | 100.00% | 0.9982 | 1.0000 |

### C. Resume Screening Evaluation (Test Split)
*Protocol: 200 synthetic resume-job profile test pairs.*

| Metric | Score |
|---|---|
| **Accuracy** | 97.50% |
| **Precision** | 96.00% |
| **Recall** | 85.71% |
| **F1-Score** | 90.57% |

### D. Question Selection & Diversification Evaluation
*Protocol: Information Security Analyst pool (1,051 candidate questions, 12-minute knapsack budget).*

| Strategy | Questions | Topic Coverage | Mean Redundancy | Duration |
|---|---|---|---|---|
| Random Selection | 8 | 1 domain, 7 skills | 0.259 | 8.2 min |
| Relevance Only | 8 | 3 domains, 7 skills | 0.393 | 10.3 min |
| Relevance + MMR | 8 | 2 domains, 7 skills | 0.289 | 11.3 min |
| **Relevance + MMR + Knapsack** | **6** | **3 domains, 7 skills** | **0.279** | **8.9 min** |

---

## 3. Demonstration & Presentation Script

### Step 1: Bootstrapping
1. Run `run_dev.bat` on Windows.
2. Observe backend API launching on `http://127.0.0.1:8000` and frontend on `http://localhost:5173`.
3. Open browser to `http://localhost:5173`.

### Step 2: Role Selection & Resume Screening
1. Use the search input to filter roles (e.g., search "Security" or "Cloud").
2. Select **"Information Security Analyst"**.
3. Upload `backend/tests/fixtures/resume_senior_sec_analyst.pdf`.
4. Click **"Screen Resume & Continue"**.
5. Observe parsed candidate skills, 5 years experience, and **PASSED SCREENING (88% Fit)**.
6. Check the local AI proctoring consent checkbox and click **"Proceed to Pre-Check"**.

### Step 3: Pre-Check & Live Mock Interview
1. Inspect live camera feed, lighting rating ("Good"), distance rating ("Optimal"), and audio level meter.
2. Click **"Start Mock Interview"**.
3. Listen as the system uses Text-to-Speech to voice the first question.
4. Intentionally look away from the camera for 3 seconds to demonstrate the real-time proctoring HUD alert (`LOOK_AWAY` warning and live score deduction).
5. Switch browser tabs to demonstrate the tab switch detection alert.
6. Navigate through the questions using **"Next Question"**, concluding with **"Finish Interview"**.

### Step 4: Multimodal Analysis & Scrubbable Report
1. Watch the post-interview progress screen display parallel Video and Audio analysis pipeline execution.
2. In the interactive Report View:
   - Point out the **Overall Score** and **Grade Badge**.
   - Show the 4 category cards: Technical Depth, Communication, Proctoring Integrity, Resume Relevance.
   - Click a deduction item in the **Deduction Timeline** table (e.g. `00:15 - LOOK_AWAY`) and observe the video player scrub directly to that timestamp.
   - Expand questions to show candidate transcripts compared against the **Authoritative Dataset Ground Truth**.
   - Click **"Download Official PDF Report"** to view the generated PDF.
   - Click **"Delete My Data & Recording"** to demonstrate complete privacy data eradication.
