"""
Résumé parser for PLUTO vProctor (Part 2: résumé ingestion → selection).

Turns an uploaded résumé (PDF / DOCX / plain text) into an explainable
ResumeProfile: canonical skill slugs grounded in data/skill_taxonomy.json, an
inferred target role, and an inferred seniority band. Rule-based and CPU-only
so every selected skill traces back to the exact surface term in the résumé —
no embedding model needed for the MVP. The profile feeds
QuestionBank.select_for_resume(); the adaptive engine orders within that pool.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TAXONOMY_PATH = DATA_DIR / "skill_taxonomy.json"

# Seniority heuristics (title keywords override years-of-experience).
SENIOR_TITLES = {"senior", "sr", "lead", "principal", "staff", "architect", "head"}
JUNIOR_TITLES = {"junior", "jr", "intern", "trainee", "fresher", "graduate",
                 "entry", "apprentice"}
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*years?", re.IGNORECASE)


@dataclass
class ResumeProfile:
    raw_text: str = ""
    char_count: int = 0
    skills: List[str] = field(default_factory=list)               # canonical slugs
    skill_evidence: Dict[str, str] = field(default_factory=dict)  # slug -> surface term
    inferred_role: str = "*"
    role_scores: Dict[str, float] = field(default_factory=dict)
    inferred_seniority: str = "mid"
    seniority_evidence: str = ""

    def to_public(self) -> dict:
        d = self.__dict__.copy()
        d.pop("raw_text", None)   # never echo the whole résumé back
        return d


class ResumeParser:
    """Explainable, rule-based résumé → profile extractor."""

    def __init__(self, taxonomy_path: Optional[Path] = None):
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else TAXONOMY_PATH
        self._taxonomy = self._load(self.taxonomy_path)
        self._skill_aliases = self._build_skill_aliases()   # surface -> skill slug
        self._role_aliases = self._build_role_aliases()     # surface -> role slug
        self._skill_domains = {
            slug: set(meta.get("domains", []))
            for slug, meta in self._taxonomy.get("skills", {}).items()
        }

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("ResumeParser: failed to load taxonomy %s: %s", path, exc)
            return {"roles": {}, "skills": {}}

    def _build_skill_aliases(self) -> Dict[str, str]:
        amap = {}
        for slug, meta in self._taxonomy.get("skills", {}).items():
            amap[slug.lower()] = slug
            for alias in meta.get("aliases", []):
                amap[alias.lower()] = slug
        return amap

    def _build_role_aliases(self) -> Dict[str, str]:
        amap = {}
        for slug, meta in self._taxonomy.get("roles", {}).items():
            amap[slug.lower()] = slug
            if meta.get("label"):
                amap[meta["label"].lower()] = slug
            for alias in meta.get("aliases", []):
                amap[alias.lower()] = slug
        amap.pop("", None)
        return amap

    # ---- text extraction ---------------------------------------------------
    def extract_text(self, path: str) -> str:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Résumé file not found: {path}")
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(p)
        if suffix == ".docx":
            return self._extract_docx(p)
        if suffix in (".txt", ".md", ".text"):
            return p.read_text(encoding="utf-8", errors="ignore")
        raise ValueError(f"Unsupported résumé format '{suffix}' (use PDF, DOCX, or TXT)")

    @staticmethod
    def _extract_pdf(p: Path) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError("PDF parsing needs PyMuPDF: pip install PyMuPDF") from exc
        parts = []
        with fitz.open(p) as doc:
            for page in doc:
                parts.append(page.get_text())
        return "\n".join(parts)

    @staticmethod
    def _extract_docx(p: Path) -> str:
        try:
            import docx  # python-docx
        except ImportError as exc:
            raise RuntimeError("DOCX parsing needs python-docx: pip install python-docx") from exc
        d = docx.Document(str(p))
        return "\n".join(par.text for par in d.paragraphs)

    # ---- matching ----------------------------------------------------------
    @staticmethod
    def _find(surface: str, text_low: str) -> bool:
        # Boundary-aware match; handles multiword + punctuation aliases (react.js, c++).
        return re.search(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text_low) is not None

    def extract_skills(self, text: str) -> Tuple[List[str], Dict[str, str]]:
        text_low = text.lower()
        skills: List[str] = []
        evidence: Dict[str, str] = {}
        # Longest surface first so "spring boot" wins over "spring".
        for surface in sorted(self._skill_aliases, key=len, reverse=True):
            slug = self._skill_aliases[surface]
            if slug in evidence:
                continue
            if self._find(surface, text_low):
                evidence[slug] = surface
                skills.append(slug)
        return skills, evidence

    def infer_role(self, text: str, skills: List[str]) -> Tuple[str, Dict[str, float]]:
        text_low = text.lower()
        scores: Dict[str, float] = {r: 0.0 for r in self._taxonomy.get("roles", {})}
        # (a) explicit role/title mentions weigh more than (b) skill-domain hints.
        for surface, role in self._role_aliases.items():
            if self._find(surface, text_low):
                scores[role] = scores.get(role, 0.0) + 2.0
        for slug in skills:
            for role in self._skill_domains.get(slug, ()):
                scores[role] = scores.get(role, 0.0) + 1.0
        if not scores or max(scores.values(), default=0.0) == 0.0:
            return "*", scores
        return max(scores, key=scores.get), scores

    def infer_seniority(self, text: str) -> Tuple[str, str]:
        text_low = text.lower()
        tokens = set(re.findall(r"[a-z]+", text_low))
        if tokens & SENIOR_TITLES:
            return "senior", "title: " + ", ".join(sorted(tokens & SENIOR_TITLES))
        if tokens & JUNIOR_TITLES:
            return "junior", "title: " + ", ".join(sorted(tokens & JUNIOR_TITLES))
        years = [int(m) for m in YEARS_RE.findall(text_low)]
        if years:
            y = max(years)
            if y < 2:
                return "junior", f"{y} years experience"
            if y <= 5:
                return "mid", f"{y} years experience"
            return "senior", f"{y} years experience"
        return "mid", "no explicit seniority signal (default)"

    # ---- top-level ---------------------------------------------------------
    def parse_text(self, text: str) -> ResumeProfile:
        skills, evidence = self.extract_skills(text)
        role, role_scores = self.infer_role(text, skills)
        seniority, sev = self.infer_seniority(text)
        return ResumeProfile(
            raw_text=text, char_count=len(text), skills=skills,
            skill_evidence=evidence, inferred_role=role, role_scores=role_scores,
            inferred_seniority=seniority, seniority_evidence=sev,
        )

    def parse_file(self, path: str) -> ResumeProfile:
        return self.parse_text(self.extract_text(path))


# Singleton, mirroring the other interview services.
_parser_instance: Optional[ResumeParser] = None


def get_resume_parser() -> ResumeParser:
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ResumeParser()
    return _parser_instance
