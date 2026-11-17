"""Tests verifying thread-safe lazy initialization, model loading fallbacks, and performance."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
import pytest

from backend.app.services.resume_service import resume_service, ResumeService
from backend.app.services.answer_eval_service import answer_eval_service
from backend.app.services.analysis_service import analysis_service

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_lazy_screening_model_thread_safety():
    """Verify concurrent first-access to screening model initializes safely without race condition."""
    service = ResumeService()
    assert service._model_loaded is False
    assert service._screening_model is None

    results = []

    def load_task():
        return service.get_screening_model()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(load_task) for _ in range(20)]
        for f in futures:
            results.append(f.result())

    # All 20 threads should receive the exact same model object
    first_model = results[0]
    assert first_model is not None
    assert all(m is first_model for m in results)
    assert service._model_loaded is True
    assert hasattr(first_model, "predict_proba")


def test_lazy_screening_model_property_accessor():
    """Verify .screening_model property accessor triggers lazy load and setter works."""
    service = ResumeService()
    assert service._model_loaded is False
    model = service.screening_model
    assert model is not None
    assert service._model_loaded is True

    # Setter override for testing/mocking
    service.screening_model = "mock_model"
    assert service.screening_model == "mock_model"


def test_lazy_screening_model_fallback_when_file_missing(monkeypatch, tmp_path):
    """Verify screening service falls back gracefully to deterministic fit if model file is missing."""
    import backend.app.services.resume_service as rs_module
    non_existent = tmp_path / "does_not_exist.joblib"
    monkeypatch.setattr(rs_module, "MODEL_PATH", non_existent)

    service = ResumeService()
    model = service.get_screening_model()
    assert model is None
    assert service._model_loaded is True

    # Execute calculate_fit - must succeed with deterministic score
    parsed_sample = {
        "skills": ["Python", "Docker"],
        "experience_years": 5.0,
        "education": {"degree": "Bachelor", "rank": 2},
    }
    job_sample = {
        "required_skills": ["Python"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 3,
        "education_levels": ["Bachelor"],
        "pass_threshold": 0.6,
    }
    result = service.calculate_fit(
        parsed_resume=parsed_sample,
        job_dict=job_sample,
    )
    assert result["status"] == "PASSED"
    assert result["ml_probability"] == result["fit_score"]


def test_lazy_answer_eval_components_thread_safety():
    """Verify answer_eval_service lazy loading is thread safe across 20 concurrent workers."""
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(lambda: (answer_eval_service.model, answer_eval_service.tfidf, answer_eval_service.bm25)) for _ in range(20)]
        results = [f.result() for f in futures]

    first_m, first_t, first_b = results[0]
    assert first_m is not None
    assert first_t is not None
    assert first_b is not None
    for m, t, b in results:
        assert m is first_m
        assert t is first_t
        assert b is first_b


def test_lazy_analysis_pipeline_properties():
    """Verify video_pipeline and audio_pipeline on analysis_service initialize on demand."""
    vp = analysis_service.video_pipeline
    ap = analysis_service.audio_pipeline
    assert vp is not None
    assert ap is not None
    assert hasattr(vp, "analyze_video")
    assert hasattr(ap, "analyze_audio")


def test_resume_parsing_pdf_docx_lazy_imports():
    """Verify PDF and DOCX text extraction functions properly with on-demand library imports."""
    pdf_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    docx_path = FIXTURES_DIR / "resume_cloud_devops_lead.docx"

    if pdf_path.exists():
        pdf_bytes = pdf_path.read_bytes()
        text_pdf = resume_service.extract_text(pdf_bytes, pdf_path.name)
        assert "Alex Vance" in text_pdf or len(text_pdf) > 50

    if docx_path.exists():
        docx_bytes = docx_path.read_bytes()
        text_docx = resume_service.extract_text(docx_bytes, docx_path.name)
        assert "Marcus Brody" in text_docx or len(text_docx) > 50

    # Plain text
    txt_bytes = b"Jane Doe\nSoftware Engineer\nPython, FastAPI, SQL\n"
    text_txt = resume_service.extract_text(txt_bytes, "resume.txt")
    assert "Jane Doe" in text_txt


def test_first_request_vs_subsequent_latency():
    """Verify first request initializes model and subsequent requests are faster."""
    fresh_service = ResumeService()
    parsed_sample = {
        "skills": ["Python", "FastAPI", "Docker", "SQL"],
        "experience_years": 4.0,
        "education": {"degree": "Bachelor", "rank": 2},
    }
    job_sample = {
        "required_skills": ["Python", "SQL"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 2,
        "education_levels": ["Bachelor"],
    }

    t0 = time.perf_counter()
    res1 = fresh_service.calculate_fit(
        parsed_resume=parsed_sample,
        job_dict=job_sample,
    )
    t_first = time.perf_counter() - t0

    t1 = time.perf_counter()
    res2 = fresh_service.calculate_fit(
        parsed_resume=parsed_sample,
        job_dict=job_sample,
    )
    t_subsequent = time.perf_counter() - t1

    assert res1["fit_score"] == res2["fit_score"]
    assert res1["ml_probability"] == res2["ml_probability"]
    assert res1["status"] == res2["status"]
    # Subsequent execution should be faster or comparable
    assert t_subsequent <= t_first or t_subsequent < 0.05
