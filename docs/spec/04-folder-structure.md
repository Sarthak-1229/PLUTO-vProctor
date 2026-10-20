<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 4. Folder structure to create

```
pluto-vproctor/
├─ datasets/                      # MY real data (copied in by me, read-only, never edited)
│  ├─ data/  (train, val, test)
│  └─ data1/ (train, val, test)
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ db.py, models.py, schemas.py
│  │  ├─ routers/ (jobs.py, resume.py, interview.py, analysis.py, report.py)
│  │  ├─ services/ (resume_service.py, question_service.py, interview_service.py,
│  │  │             analysis_service.py, scoring_engine.py, report_service.py,
│  │  │             answer_eval_service.py, llm_client.py)
│  │  ├─ pipelines/ (video_pipeline.py, audio_pipeline.py)
│  │  ├─ algorithms/ (each file standalone + unit tested)
│  │  │   ├─ trie.py, sorting.py, searching.py, heap_topk.py, knapsack.py,
│  │  │   ├─ string_match.py, edit_distance.py, interval_ops.py,
│  │  │   ├─ similarity.py, bm25.py, minhash.py, mmr.py, smoothing.py,
│  │  │   ├─ sliding_window.py, keyword_extraction.py, ml_models.py
│  │  └─ data/
│  │      ├─ jobs.json                 # hand-written job profiles (the only hand-written data)
│  │      ├─ skills_taxonomy.json      # built from the datasets + curated
│  │      ├─ fillers.json
│  │      └─ processed/ (qa_clean.jsonl, questions.json, embeddings.npy, models/*.joblib)
│  ├─ tests/
│  ├─ scripts/ (ingest_datasets.py, enrich_questions.py, seed_db.py, train_models.py,
│  │            evaluate_domain.py, evaluate_retrieval.py, evaluate_answer_relevance.py,
│  │            evaluate_screening.py, evaluate_selection.py, benchmark_algorithms.py)
│  └─ requirements.txt
├─ frontend/ (Vite + React + Tailwind)
├─ docs/ (ARCHITECTURE.md, ALGORITHMS.md, DATASET_REPORT.md, DECISIONS.md, API.md, REPORT_TEMPLATE.md, figures/)
├─ run_dev.bat, run_dev.sh
└─ README.md
```
