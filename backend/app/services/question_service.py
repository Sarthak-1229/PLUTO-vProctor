"""Question filtering, selection, MMR diversification, Knapsack budget, and ordering engine.

Implements Section 5.3 of docs/spec/5a-jobs-resume-questions.md.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from backend.app.algorithms.heap_topk import top_k
from backend.app.algorithms.knapsack import KnapsackItem, knapsack_01
from backend.app.algorithms.mmr import mmr_select
from backend.app.algorithms.sorting import merge_sort
from backend.app.config import settings
from backend.app.db.models import InterviewSession, Job, Question, SessionQuestion

QUESTIONS_JSON = settings.PROCESSED_DATA_DIR / "questions.json"
EMBEDDINGS_NPY = settings.PROCESSED_DATA_DIR / "embeddings.npy"
EMBEDDINGS_IDS = settings.PROCESSED_DATA_DIR / "embeddings_ids.json"


class QuestionService:
    """Core question retrieval, scoring, diversification, and scheduling engine."""

    def __init__(self):
        self.questions_by_id: Dict[str, Dict[str, Any]] = {}
        self.spoken_questions: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.qid_to_emb_idx: Dict[str, int] = {}
        self.inverted_index: Dict[str, Set[str]] = defaultdict(set)
        self._load_data()

    def _load_data(self):
        if not QUESTIONS_JSON.exists():
            return

        with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
            all_q = json.load(f)

        for q in all_q:
            qid = q["id"]
            self.questions_by_id[qid] = q
            if q.get("spoken_ok", True):
                self.spoken_questions.append(q)

                # Build inverted index
                domain = q.get("domain", "")
                if domain:
                    self.inverted_index[f"domain:{domain.lower()}"].add(qid)

                cluster_id = q.get("cluster_id")
                if cluster_id is not None:
                    self.inverted_index[f"cluster:{cluster_id}"].add(qid)

                for skill in q.get("skills", []):
                    self.inverted_index[f"skill:{skill.lower()}"].add(qid)

        if EMBEDDINGS_NPY.exists() and EMBEDDINGS_IDS.exists():
            try:
                self.embeddings = np.load(EMBEDDINGS_NPY)
                with open(EMBEDDINGS_IDS, "r", encoding="utf-8") as f:
                    ids = json.load(f)
                self.qid_to_emb_idx = {qid: idx for idx, qid in enumerate(ids)}
            except Exception as e:
                print(f"Warning: Could not load embeddings: {e}")

    def get_embedding(self, qid: str) -> Optional[np.ndarray]:
        """Retrieve precomputed MiniLM embedding for a question."""
        if self.embeddings is not None and qid in self.qid_to_emb_idx:
            idx = self.qid_to_emb_idx[qid]
            return self.embeddings[idx]
        return None

    def candidate_pool_for_job(self, job_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve candidate questions matching target job domains and skills using the inverted index."""
        target_domains = [d.lower() for d in job_dict.get("question_domains", [])]
        req_skills = [s.lower() for s in job_dict.get("required_skills", [])]

        candidate_ids: Set[str] = set()
        for dom in target_domains:
            candidate_ids.update(self.inverted_index.get(f"domain:{dom}", set()))

        for sk in req_skills:
            candidate_ids.update(self.inverted_index.get(f"skill:{sk}", set()))

        # Fallback to all spoken questions if candidate set is too small
        if len(candidate_ids) < 15:
            return self.spoken_questions

        return [self.questions_by_id[qid] for qid in candidate_ids if qid in self.questions_by_id]

    def compute_relevance(
        self,
        question: Dict[str, Any],
        job_dict: Dict[str, Any],
        resume_skills: Set[str],
        candidate_exp: float,
    ) -> float:
        """Compute multi-factor relevance score for a question."""
        q_skills = set(question.get("skills", []))
        req_skills = set(job_dict.get("required_skills", []))
        pref_skills = set(job_dict.get("preferred_skills", []))

        # 1. Job required skill overlap
        req_overlap = len(q_skills.intersection(req_skills))
        # 2. Candidate resume skill overlap (boost questions on candidate's strengths)
        resume_overlap = len(q_skills.intersection(resume_skills))
        # 3. Preferred skill overlap
        pref_overlap = len(q_skills.intersection(pref_skills))

        # 4. Difficulty alignment with candidate experience
        diff = question.get("difficulty", 1)
        if candidate_exp < 2.0:
            diff_fit = 1.0 if diff == 1 else (0.7 if diff == 2 else 0.4)
        elif candidate_exp <= 5.0:
            diff_fit = 1.0 if diff == 2 else 0.8
        else:
            diff_fit = 1.0 if diff == 3 else (0.85 if diff == 2 else 0.6)

        # Domain match bonus
        domain = question.get("domain", "")
        job_domains = job_dict.get("question_domains", [])
        domain_bonus = 1.0 if domain in job_domains else 0.5

        # Weighted combination
        score = (
            (req_overlap * 2.5)
            + (resume_overlap * 1.5)
            + (pref_overlap * 0.8)
            + (diff_fit * 1.5)
            + (domain_bonus * 1.0)
        )
        return float(score)

    def select_questions(
        self,
        job_dict: Dict[str, Any],
        parsed_resume: Dict[str, Any],
        target_duration_seconds: int = 720,  # 12 minutes default
        top_k_candidates: int = 40,
        lambda_mmr: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """Complete question selection pipeline:
        1. Inverted index retrieval
        2. Relevance scoring
        3. Manual min-heap Top-K
        4. MMR diversification with cluster and domain caps
        5. 0/1 Knapsack time budget allocation
        6. Merge-sort chronological ordering with warm-up prompt
        """
        pool = self.candidate_pool_for_job(job_dict)
        if not pool:
            pool = self.spoken_questions[:50]

        resume_skills = set(parsed_resume.get("skills", []))
        candidate_exp = parsed_resume.get("experience_years", 2.0)

        # Step 2: Relevance scoring
        scored_candidates: List[Tuple[float, Dict[str, Any]]] = []
        for q in pool:
            rel = self.compute_relevance(q, job_dict, resume_skills, candidate_exp)
            scored_candidates.append((rel, q))

        # Step 3: Top-K selection using hand-implemented min-heap
        k = min(top_k_candidates, len(scored_candidates))
        top_candidates = top_k(scored_candidates, k=k)

        # Prepare for MMR
        candidate_items = [q for _, q in top_candidates]
        candidate_scores = [rel for rel, _ in top_candidates]
        cand_embeddings = []
        fallback_dim = 384

        for q in candidate_items:
            emb = self.get_embedding(q["id"])
            if emb is not None:
                cand_embeddings.append(emb)
            else:
                cand_embeddings.append(np.zeros(fallback_dim))
        cand_embeddings = np.array(cand_embeddings)

        # Step 4: MMR Diversification
        # Cap questions per cluster and domain
        max_per_cluster = 2
        max_per_domain = 4

        mmr_pool_size = min(20, len(candidate_items))
        query_vec = cand_embeddings[0].tolist() if len(cand_embeddings) > 0 else [0.0] * fallback_dim
        cand_list = [emb.tolist() for emb in cand_embeddings]
        diverse_indices = mmr_select(
            query_embedding=query_vec,
            candidate_embeddings=cand_list,
            candidate_scores=candidate_scores,
            k=mmr_pool_size,
            lambda_=lambda_mmr,
        )

        diverse_questions: List[Dict[str, Any]] = []
        cluster_counts: Dict[int, int] = defaultdict(int)
        domain_counts: Dict[str, int] = defaultdict(int)

        for idx in diverse_indices:
            q = candidate_items[idx]
            cid = q.get("cluster_id", 0)
            dom = q.get("domain", "")

            if cluster_counts[cid] < max_per_cluster and domain_counts[dom] < max_per_domain:
                diverse_questions.append(q)
                cluster_counts[cid] += 1
                domain_counts[dom] += 1

        if len(diverse_questions) < 5:
            # Fallback if caps were too strict
            diverse_questions = [candidate_items[idx] for idx in diverse_indices[:8]]

        # Step 5: 0/1 Knapsack time budget allocation
        # Value = relevance score, Weight = est_seconds
        # Target duration: default 12 min = 720s (reserve 90s for warm-up and closing)
        budget = max(300, target_duration_seconds - 90)

        knapsack_items = []
        for i, q in enumerate(diverse_questions):
            weight = max(30, int(q.get("est_seconds", 70)))
            val = int(round(candidate_scores[diverse_indices[i]] * 10))
            knapsack_items.append(KnapsackItem(id=q["id"], weight=weight, value=val))

        max_val, chosen_ids = knapsack_01(knapsack_items, capacity=budget)
        chosen_set = set(chosen_ids)
        selected_questions = [q for q in diverse_questions if q["id"] in chosen_set]

        if not selected_questions:
            selected_questions = diverse_questions[:5]

        # Step 6: Order questions using custom merge sort
        # Order priority:
        # Group 1: definition (type_rank = 1)
        # Group 2: explain (type_rank = 2)
        # Group 3: how_why / compare / scenario (type_rank = 3)
        type_priority = {
            "definition": 1,
            "explain": 2,
            "how_why": 3,
            "compare": 3,
            "scenario": 4,
            "coding": 5,
        }

        def question_sort_key(q: Dict[str, Any]):
            t_rank = type_priority.get(q.get("type", "explain"), 2)
            diff = q.get("difficulty", 1)
            # Sort ascending by type_rank, then descending by difficulty (negated)
            return (t_rank, diff)

        ordered_questions = merge_sort(selected_questions, key=question_sort_key)

        # Inject Warm-up question at index 0 (not from dataset)
        primary_skill = (job_dict.get("required_skills") or ["Software Engineering"])[0]
        warmup = {
            "id": "q_warmup_intro",
            "question": f"To begin, please introduce yourself and walk me through your technical background and experience with {primary_skill}.",
            "answer": "Candidate provides a coherent career overview highlighting core skills and relevant project experience.",
            "type": "warmup",
            "spoken_ok": True,
            "is_warmup": True,
            "est_seconds": 90,
            "domain": "General",
            "difficulty": 1,
            "expected_keywords": ["experience", "projects", "background", "skills", "engineering"],
        }

        final_list = [warmup] + ordered_questions
        return final_list

    def find_nearest_neighbors(self, query_text: str, k: int = 2) -> List[Dict[str, Any]]:
        """Retrieve top-K nearest dataset Q&A pairs via cosine similarity (for RAG follow-up grounding)."""
        if self.embeddings is None or not self.spoken_questions:
            return self.spoken_questions[:k]

        from sentence_transformers import SentenceTransformer
        # Use simple TF-IDF or vector dot product if MiniLM is available
        try:
            model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            q_emb = model.encode(query_text, normalize_embeddings=True)
            # Dot product with normalized embeddings = cosine similarity
            sims = np.dot(self.embeddings, q_emb)
            top_indices = np.argsort(sims)[::-1][:k]

            ids_list = list(self.qid_to_emb_idx.keys())
            results = []
            for idx in top_indices:
                if idx < len(ids_list):
                    qid = ids_list[idx]
                    if qid in self.questions_by_id:
                        results.append(self.questions_by_id[qid])
            return results
        except Exception:
            return self.spoken_questions[:k]


# Global instance
question_service = QuestionService()
