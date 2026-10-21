"""SQLAlchemy ORM models for PLUTO vProctor."""
from __future__ import annotations

import datetime
from typing import Any, Dict, List
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Company(Base):
    """Fictional hiring organization."""
    __tablename__ = "companies"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    industry = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

    jobs = relationship("Job", back_populates="company_rel", cascade="all, delete-orphan")


class Job(Base):
    """Job profile with required qualifications, skill weights, and target domains."""
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    title = Column(String(128), nullable=False)
    company = Column(String(128), nullable=False)
    company_id = Column(String(64), ForeignKey("companies.id"), nullable=True)
    required_skills = Column(JSON, default=list)
    preferred_skills = Column(JSON, default=list)
    min_experience_years = Column(Integer, default=0)
    education_levels = Column(JSON, default=list)
    skill_weights = Column(JSON, default=dict)
    question_domains = Column(JSON, default=list)
    pass_threshold = Column(Float, default=0.65)

    company_rel = relationship("Company", back_populates="jobs")
    sessions = relationship("InterviewSession", back_populates="job")


class Question(Base):
    """Technical interview question derived only from the clean dataset."""
    __tablename__ = "questions"

    id = Column(String(64), primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    split = Column(String(16), nullable=False, default="train")
    source_folder = Column(String(32), nullable=True)
    type = Column(String(32), nullable=False, default="explain")
    spoken_ok = Column(Boolean, nullable=False, default=True)
    skills = Column(JSON, default=list)
    domain = Column(String(64), nullable=False, default="General")
    cluster_id = Column(Integer, default=0)
    difficulty = Column(Integer, default=1)
    expected_keywords = Column(JSON, default=list)
    ideal_answer_summary = Column(Text, nullable=True)
    est_seconds = Column(Integer, default=70)


class InterviewSession(Base):
    """Candidate mock interview session lifecycle."""
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=False)
    candidate_name = Column(String(128), default="Candidate")
    resume_filename = Column(String(256), nullable=True)
    resume_text = Column(Text, nullable=True)
    parsed_resume = Column(JSON, nullable=True)
    screening_fit = Column(Float, default=0.0)
    screening_status = Column(String(32), default="PENDING")  # PASSED, REJECTED
    screening_details = Column(JSON, nullable=True)
    interview_status = Column(String(32), default="CREATED")  # CREATED, IN_PROGRESS, RECORDED, ANALYZED
    video_filename = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    job = relationship("Job", back_populates="sessions")
    questions = relationship("SessionQuestion", back_populates="session", cascade="all, delete-orphan", order_by="SessionQuestion.order_index")
    proctoring_events = relationship("ProctoringEvent", back_populates="session", cascade="all, delete-orphan")
    report = relationship("InterviewReport", back_populates="session", uselist=False, cascade="all, delete-orphan")


class SessionQuestion(Base):
    """Questions selected and asked in a specific interview session."""
    __tablename__ = "session_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False)
    question_id = Column(String(64), ForeignKey("questions.id"), nullable=True)
    order_index = Column(Integer, nullable=False, default=0)
    is_warmup = Column(Boolean, default=False)
    is_follow_up = Column(Boolean, default=False)
    custom_question_text = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    start_time_sec = Column(Float, nullable=True)
    end_time_sec = Column(Float, nullable=True)
    answer_score = Column(JSON, nullable=True)

    session = relationship("InterviewSession", back_populates="questions")
    question_rel = relationship("Question")


class ProctoringEvent(Base):
    """Proctoring violation deduction event."""
    __tablename__ = "proctoring_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False)
    question_id = Column(String(64), nullable=True)
    t_start = Column(Float, nullable=False)
    t_end = Column(Float, nullable=False)
    category = Column(String(64), nullable=False)  # Eye Contact, Motion, Fluency, etc.
    type = Column(String(64), nullable=False)      # LOOK_AWAY, EXCESSIVE_MOTION, FILLER_WORD, etc.
    severity = Column(String(32), default="MEDIUM")
    points_deducted = Column(Float, default=1.0)
    reason = Column(Text, nullable=False)

    session = relationship("InterviewSession", back_populates="proctoring_events")


class InterviewReport(Base):
    """Final comprehensive evaluation report."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), unique=True, nullable=False)
    overall_score = Column(Float, nullable=False, default=0.0)
    grade = Column(String(8), default="B")
    readiness_label = Column(String(64), default="Ready with minor revision")
    category_scores = Column(JSON, default=dict)
    summary = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("InterviewSession", back_populates="report")
