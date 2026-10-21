"""Resume parsing, section extraction, layered skill detection, and fit scoring service.

Implements Section 5.2 of docs/spec/5a-jobs-resume-questions.md.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import docx
import joblib
import pdfplumber

from backend.app.algorithms.edit_distance import is_fuzzy_match
from backend.app.algorithms.interval_ops import merge_intervals, total_duration
from backend.app.algorithms.trie import Trie
from backend.app.config import settings

TAXONOMY_FILE = settings.BASE_DIR / "backend" / "app" / "data" / "skills_taxonomy.json"
MODEL_PATH = settings.PROCESSED_DATA_DIR / "models" / "screening_model.joblib"

DEGREE_RANKS = {
    "phd": 4,
    "doctorate": 4,
    "master": 3,
    "m.s.": 3,
    "m.tech": 3,
    "msc": 3,
    "bachelor": 2,
    "b.s.": 2,
    "b.tech": 2,
    "b.e.": 2,
    "bsc": 2,
    "diploma": 1,
    "associate": 1,
}

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}


class ResumeService:
    """Core service for resume text extraction, NLP parsing, and candidate screening."""

    def __init__(self):
        self.taxonomy: List[Dict[str, Any]] = []
        self.skill_trie = Trie()
        self.canonical_skills: Dict[str, str] = {}  # alias/kw -> canonical name
        self.screening_model = None
        self._load_taxonomy()
        self._load_model()

    def _load_taxonomy(self):
        if TAXONOMY_FILE.exists():
            with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.taxonomy = data.get("skills", [])

            for s in self.taxonomy:
                canonical = s["name"]
                # Insert canonical
                self.skill_trie.insert(canonical.lower())
                self.canonical_skills[canonical.lower()] = canonical

                # Insert aliases
                for alias in s.get("aliases", []):
                    self.skill_trie.insert(alias.lower())
                    self.canonical_skills[alias.lower()] = canonical

                # Insert keywords
                for kw in s.get("keywords", []):
                    self.skill_trie.insert(kw.lower())
                    self.canonical_skills[kw.lower()] = canonical

    def _load_model(self):
        if MODEL_PATH.exists():
            try:
                self.screening_model = joblib.load(MODEL_PATH)
            except Exception as e:
                print(f"Warning: Could not load screening model from {MODEL_PATH}: {e}")

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Extract clean text from PDF, DOCX, or plain text bytes."""
        fn_low = filename.lower()
        text = ""

        if fn_low.endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
                text = "\n".join(pages_text)
        elif fn_low.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            paragraphs.append(cell.text.strip())
            text = "\n".join(paragraphs)
        else:
            # Fallback as plain text
            text = file_bytes.decode("utf-8", errors="ignore")

        # Normalize line breaks and spaces
        text = re.sub(r"\r\n|\r", "\n", text)
        return text.strip()

    def segment_sections(self, text: str) -> Dict[str, str]:
        """Segment resume into major sections (Skills, Experience, Education, Projects)."""
        sections = {
            "summary": "",
            "skills": "",
            "experience": "",
            "education": "",
            "projects": "",
            "other": "",
        }

        # Heading patterns
        patterns = [
            (r"(?i)^(skills|technical skills|technologies|core competencies|competencies)\b", "skills"),
            (r"(?i)^(experience|work experience|employment history|work history|professional experience)\b", "experience"),
            (r"(?i)^(education|academic background|qualifications)\b", "education"),
            (r"(?i)^(projects|academic projects|key projects|personal projects)\b", "projects"),
            (r"(?i)^(summary|professional summary|profile|about me|objective)\b", "summary"),
        ]

        lines = text.split("\n")
        current_section = "summary"
        section_lines: Dict[str, List[str]] = {k: [] for k in sections}

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check if line matches a section header
            matched_sec = None
            if len(line_str) <= 45:
                for pat, sec_name in patterns:
                    if re.search(pat, line_str):
                        matched_sec = sec_name
                        break

            if matched_sec:
                current_section = matched_sec
            else:
                section_lines[current_section].append(line_str)

        for sec, lns in section_lines.items():
            sections[sec] = "\n".join(lns)

        return sections

    def extract_skills(self, text: str) -> List[str]:
        """Layered skill extraction: Trie match -> Fuzzy Levenshtein match -> Alias normalization."""
        found_canonical: Set[str] = set()
        text_lower = " " + text.lower() + " "

        # Layer 1: Trie & Exact Trigger match
        for alias, canonical in self.canonical_skills.items():
            pattern = r"(?<![a-zA-Z0-9])" + re.escape(alias) + r"(?![a-zA-Z0-9])"
            if re.search(pattern, text_lower):
                found_canonical.add(canonical)

        # Layer 2: Fuzzy match for skill phrases (Levenshtein distance <= 1 for longer words)
        words = re.findall(r"\b[a-z]{4,15}\b", text_lower)
        for w in words:
            for s in self.taxonomy:
                name_low = s["name"].lower()
                if abs(len(w) - len(name_low)) <= 1 and is_fuzzy_match(w, name_low, max_distance=1):
                    found_canonical.add(s["name"])

        return sorted(list(found_canonical))

    def parse_experience_years(self, text: str) -> Tuple[float, List[Tuple[float, float]]]:
        """Extract date ranges, convert to year intervals, merge overlaps, and compute total experience."""
        current_year = datetime.now().year + (datetime.now().month / 12.0)
        intervals: List[Tuple[float, float]] = []

        # Pattern 1: e.g. "Jan 2020 - Mar 2023" or "2019 - Present"
        date_pattern = re.compile(
            r"\b([A-Za-z]{3,9}\.?\s+)?(20\d{2}|19\d{2})\s*(?:-|–|—|to)\s*([A-Za-z]{3,9}\.?\s+)?(20\d{2}|19\d{2}|present|current)\b",
            re.IGNORECASE,
        )

        for match in date_pattern.finditer(text):
            m1, y1, m2, y2 = match.groups()
            start_y = float(y1)
            if m1:
                month_str = re.sub(r"[^a-z]", "", m1.lower())[:3]
                if month_str in MONTH_MAP:
                    start_y += (MONTH_MAP[month_str] - 1) / 12.0

            if y2.lower() in ["present", "current"]:
                end_y = current_year
            else:
                end_y = float(y2)
                if m2:
                    month_str = re.sub(r"[^a-z]", "", m2.lower())[:3]
                    if month_str in MONTH_MAP:
                        end_y += (MONTH_MAP[month_str] - 1) / 12.0

            if end_y >= start_y and (end_y - start_y) <= 35:
                intervals.append((start_y, end_y))

        # Pattern 2: Explicit mentions like "3+ years of experience" or "5 years"
        exp_mention = re.findall(r"\b(\d{1,2})\+?\s*(?:years?|yrs?)(?:\s+of)?\s+experience\b", text, re.IGNORECASE)
        explicit_years = [float(y) for y in exp_mention if 1 <= float(y) <= 40]

        if intervals:
            merged = merge_intervals(intervals)
            calculated_duration = total_duration(merged)
            if explicit_years:
                final_years = max(calculated_duration, max(explicit_years))
            else:
                final_years = calculated_duration
            return round(final_years, 1), merged

        if explicit_years:
            return round(max(explicit_years), 1), []

        return 0.0, []

    def detect_education(self, text: str) -> Dict[str, Any]:
        """Detect highest degree level, fields of study, and institutions."""
        text_low = text.lower()
        highest_rank = 0
        detected_degree = "None"

        for term, rank in DEGREE_RANKS.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text_low):
                if rank > highest_rank:
                    highest_rank = rank
                    # Map to canonical degree name
                    if rank == 4:
                        detected_degree = "PhD"
                    elif rank == 3:
                        detected_degree = "Master"
                    elif rank == 2:
                        detected_degree = "Bachelor"
                    elif rank == 1:
                        detected_degree = "Diploma"

        # Detect majors / fields
        fields = []
        field_keywords = ["computer science", "software engineering", "data science", "information technology", "bioinformatics", "electrical engineering", "cybersecurity"]
        for fk in field_keywords:
            if fk in text_low:
                fields.append(fk.title())

        return {
            "degree": detected_degree,
            "rank": highest_rank,
            "fields": fields,
        }

    def parse_resume(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Parse raw resume file into structured sections, skills, experience, and education."""
        raw_text = self.extract_text(file_bytes, filename)
        sections = self.segment_sections(raw_text)

        skills = self.extract_skills(raw_text)
        exp_years, intervals = self.parse_experience_years(sections["experience"] or raw_text)
        education = self.detect_education(sections["education"] or raw_text)

        # Extract name heuristic (first line or first non-empty string in summary)
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        candidate_name = lines[0] if lines and len(lines[0]) <= 50 else "Candidate"

        return {
            "candidate_name": candidate_name,
            "raw_text": raw_text,
            "sections": sections,
            "skills": skills,
            "experience_years": exp_years,
            "experience_intervals": intervals,
            "education": education,
        }

    def calculate_fit(self, parsed_resume: Dict[str, Any], job_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Compute deterministic fit score and screening status per Section 5.2."""
        required_skills = job_dict.get("required_skills", [])
        preferred_skills = job_dict.get("preferred_skills", [])
        min_exp = job_dict.get("min_experience_years", 0)
        required_edu_levels = job_dict.get("education_levels", ["Bachelor"])
        pass_threshold = job_dict.get("pass_threshold", 0.65)
        skill_weights = job_dict.get("skill_weights", {})

        candidate_skills = set(parsed_resume.get("skills", []))
        candidate_exp = parsed_resume.get("experience_years", 0.0)
        candidate_edu = parsed_resume.get("education", {})
        cand_edu_rank = candidate_edu.get("rank", 0)

        # 1. Skill Score
        matched_required = [s for s in required_skills if s in candidate_skills]
        missing_required = [s for s in required_skills if s not in candidate_skills]
        matched_preferred = [s for s in preferred_skills if s in candidate_skills]

        # Calculate weighted required coverage
        if skill_weights and any(s in skill_weights for s in required_skills):
            total_req_w = sum(skill_weights.get(s, 1.0) for s in required_skills)
            req_score = sum(skill_weights.get(s, 1.0) for s in matched_required) / max(total_req_w, 0.001)
        else:
            req_score = len(matched_required) / max(len(required_skills), 1)

        pref_score = len(matched_preferred) / max(len(preferred_skills), 1) if preferred_skills else 1.0
        skill_score = min(1.0, 0.80 * req_score + 0.20 * pref_score)

        # 2. Experience Score
        if min_exp == 0:
            exp_score = 1.0
        else:
            ratio = candidate_exp / float(min_exp)
            if ratio >= 1.0:
                exp_score = 1.0
            else:
                # Smooth penalty curve
                exp_score = max(0.0, ratio ** 1.2)

        # 3. Education Score
        req_ranks = [DEGREE_RANKS.get(e.lower(), 2) for e in required_edu_levels]
        min_req_rank = min(req_ranks) if req_ranks else 2
        if cand_edu_rank >= min_req_rank:
            edu_score = 1.0
        elif cand_edu_rank == min_req_rank - 1:
            edu_score = 0.6
        else:
            edu_score = 0.3

        # Combined deterministic fit: 55% skill + 25% experience + 20% education
        deterministic_fit = round(0.55 * skill_score + 0.25 * exp_score + 0.20 * edu_score, 3)

        # Rejection reasons
        reasons = []
        if missing_required:
            reasons.append(f"Missing required skills: {', '.join(missing_required)}")
        if candidate_exp < min_exp:
            reasons.append(f"Experience deficit: {candidate_exp} years vs {min_exp} years required")
        if cand_edu_rank < min_req_rank:
            reasons.append(f"Education level below requirement ({candidate_edu.get('degree')} vs {', '.join(required_edu_levels)})")

        status = "PASSED" if (deterministic_fit >= pass_threshold and not missing_required) else "REJECTED"

        # ML Model screening prediction
        ml_probability = deterministic_fit
        if self.screening_model:
            try:
                features = [
                    skill_score,
                    exp_score,
                    edu_score,
                    deterministic_fit,
                    len(matched_required),
                    len(missing_required),
                ]
                ml_prob = self.screening_model.predict_proba([features])[0][1]
                ml_probability = round(float(ml_prob), 3)
            except Exception:
                pass

        return {
            "fit_score": deterministic_fit,
            "status": status,
            "pass_threshold": pass_threshold,
            "ml_probability": ml_probability,
            "category_scores": {
                "skills": round(skill_score, 3),
                "experience": round(exp_score, 3),
                "education": round(edu_score, 3),
            },
            "matched_required_skills": matched_required,
            "missing_required_skills": missing_required,
            "matched_preferred_skills": matched_preferred,
            "reasons": reasons,
        }


# Global singleton instance
resume_service = ResumeService()
