"""Answer evaluation service combining multimodal algorithmic models and local LLM rubric.

Implements Section 5.7 of docs/spec/5c-scoring-report.md:
Blend: 60% algorithmic (Logistic Regression over embeddings/BM25/TF-IDF) + 40% LLM.
Fallback: 100% algorithmic if LLM is unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np
from pydantic import BaseModel, Field

from backend.app.algorithms.bm25 import BM25
from backend.app.algorithms.edit_distance import levenshtein
from backend.app.algorithms.similarity import TFIDFVectorizer, cosine_similarity, tokenize
from backend.app.config import settings
from backend.app.services.llm_client import llm_client

MODEL_PATH = settings.PROCESSED_DATA_DIR / "models" / "answer_relevance_model.joblib"
QUESTIONS_JSON = settings.PROCESSED_DATA_DIR / "questions.json"


class LLMRubricResponse(BaseModel):
    relevance: float = Field(ge=0, le=10, description="Relevance to question (0-10)")
    clarity: float = Field(ge=0, le=10, description="Clarity of explanation (0-10)")
    depth: float = Field(ge=0, le=10, description="Technical depth (0-10)")
    one_line_feedback: str = Field(description="One concise line of constructive feedback")


class AnswerEvaluationService:
    """Evaluates candidate answers against gold dataset references using hybrid algorithmic + LLM scoring."""

    def __init__(self):
        self.model = None
        self.tfidf = None
        self.bm25 = None
        self.st_model = None
        self._load_components()

    def _load_components(self):
        if MODEL_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
            except Exception as e:
                print(f"Warning: Could not load answer relevance model: {e}")

        if QUESTIONS_JSON.exists():
            try:
                with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
                    corpus = [q["answer"] for q in json.load(f) if q.get("split") == "train"]
                self.tfidf = TFIDFVectorizer().fit(corpus)
                self.bm25 = BM25().fit(corpus)
            except Exception as e:
                print(f"Warning: Could not fit answer retrieval baselines: {e}")

    def _get_st_model(self):
        if self.st_model is None:
            from sentence_transformers import SentenceTransformer
            self.st_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        return self.st_model

    def evaluate_answer_algorithmic(
        self,
        question: str,
        reference_answer: str,
        expected_keywords: List[str],
        candidate_transcript: str,
    ) -> Dict[str, Any]:
        """Compute objective algorithmic score (0-100) using trained model and keyword recall."""
        if not candidate_transcript or len(candidate_transcript.strip().split()) < 3:
            return {
                "algorithmic_score": 0.0,
                "keyword_recall": 0.0,
                "matched_keywords": [],
                "missed_keywords": expected_keywords,
                "embedding_similarity": 0.0,
            }

        st = self._get_st_model()
        q_emb = st.encode(question, normalize_embeddings=True)
        cand_emb = st.encode(candidate_transcript, normalize_embeddings=True)
        ref_emb = st.encode(reference_answer, normalize_embeddings=True)

        emb_sim = float(np.dot(cand_emb, ref_emb))

        # Off-topic gate: if semantic similarity to reference is very low (< 0.25), score near zero
        if emb_sim < 0.25:
            return {
                "algorithmic_score": round(max(0.0, emb_sim * 20.0), 1),
                "keyword_recall": 0.0,
                "matched_keywords": [],
                "missed_keywords": expected_keywords,
                "embedding_similarity": round(emb_sim, 3),
            }

        # TF-IDF cosine
        tfidf_sim = 0.0
        if self.tfidf:
            qv = self.tfidf.transform(question)
            cv = self.tfidf.transform(candidate_transcript)
            tfidf_sim = float(cosine_similarity(qv, cv))

        # Keyword recall with fuzzy tolerance
        cand_tokens = set(tokenize(candidate_transcript))
        matched_kw = []
        missed_kw = []

        for kw in expected_keywords:
            kw_clean = kw.lower()
            if any(t == kw_clean or (len(t) > 3 and levenshtein(t, kw_clean) <= 1) for t in cand_tokens):
                matched_kw.append(kw)
            else:
                missed_kw.append(kw)

        kw_recall = len(matched_kw) / max(len(expected_keywords), 1)

        # Length ratio
        q_len = max(1, len(question.split()))
        c_len = max(1, len(candidate_transcript.split()))
        len_ratio = min(q_len, c_len) / float(max(q_len, c_len))

        # BM25 score
        bm25_val = float(self.bm25.score(question, 0)) if self.bm25 else 0.5

        # Predict probability from trained model or robust formula
        if self.model:
            feats = [[emb_sim, tfidf_sim, kw_recall, len_ratio, bm25_val]]
            prob = self.model.predict_proba(feats)[0][1]
            raw_score = prob * 100.0
        else:
            raw_score = (0.50 * emb_sim + 0.35 * kw_recall + 0.15 * tfidf_sim) * 100.0

        # Cap very short answers (< 7 words)
        if len(candidate_transcript.split()) < 7:
            raw_score = min(45.0, raw_score)

        algorithmic_score = round(max(0.0, min(100.0, raw_score)), 1)

        return {
            "algorithmic_score": algorithmic_score,
            "keyword_recall": round(kw_recall, 2),
            "matched_keywords": matched_kw,
            "missed_keywords": missed_kw,
            "embedding_similarity": round(emb_sim, 3),
        }

    async def evaluate_answer(
        self,
        question: str,
        reference_answer: str,
        expected_keywords: List[str],
        candidate_transcript: str,
    ) -> Dict[str, Any]:
        """Hybrid evaluation blending 60% algorithmic and 40% local LLM rubric."""
        algo_res = self.evaluate_answer_algorithmic(
            question=question,
            reference_answer=reference_answer,
            expected_keywords=expected_keywords,
            candidate_transcript=candidate_transcript,
        )

        algorithmic_score = algo_res["algorithmic_score"]

        # If transcript is empty or negligible, return zero
        if not candidate_transcript or len(candidate_transcript.split()) < 3:
            return {
                "overall_answer_score": 0.0,
                "algorithmic_score": 0.0,
                "llm_score": 0.0,
                "feedback": "No answer provided.",
                "reference_answer": reference_answer,
                "matched_keywords": [],
                "missed_keywords": expected_keywords,
            }

        # Prompt LLM for structured rubric (0-10)
        system_prompt = (
            "You are a strict, objective technical interview evaluator. Rate the candidate's spoken answer "
            "against the question and the gold reference answer. Provide scores from 0 to 10 for relevance, clarity, and depth, "
            "and one concise sentence of constructive feedback."
        )

        user_prompt = (
            f"Question: {question}\n\n"
            f"Reference Answer: {reference_answer}\n\n"
            f"Candidate Spoken Answer: {candidate_transcript[:800]}\n\n"
            'Respond strictly in JSON: {"relevance": 0-10, "clarity": 0-10, "depth": 0-10, "one_line_feedback": "..."}'
        )

        def fallback():
            return None

        llm_rubric: Optional[LLMRubricResponse] = await llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=LLMRubricResponse,
            fallback_factory=fallback,
        )

        if llm_rubric:
            llm_avg = (llm_rubric.relevance + llm_rubric.clarity + llm_rubric.depth) / 3.0
            llm_score = llm_avg * 10.0  # Scale 0-10 to 0-100
            # 60% algorithmic + 40% LLM
            combined_score = round(0.60 * algorithmic_score + 0.40 * llm_score, 1)
            feedback = llm_rubric.one_line_feedback
        else:
            # Fallback: 100% algorithmic
            combined_score = algorithmic_score
            llm_score = algorithmic_score
            feedback = f"Algorithmic evaluation: {len(algo_res['matched_keywords'])} of {len(expected_keywords)} core concepts mentioned."

        return {
            "overall_answer_score": combined_score,
            "algorithmic_score": algorithmic_score,
            "llm_score": round(llm_score, 1),
            "feedback": feedback,
            "reference_answer": reference_answer,
            "matched_keywords": algo_res["matched_keywords"],
            "missed_keywords": algo_res["missed_keywords"],
            "embedding_similarity": algo_res["embedding_similarity"],
        }


answer_eval_service = AnswerEvaluationService()
