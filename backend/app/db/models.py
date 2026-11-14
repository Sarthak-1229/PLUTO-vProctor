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


def _utcnow_naive() -> datetime.datetime:
    """Return timezone-neutral UTC datetime compatible with existing SQLite & PG TIMESTAMP columns."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


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
    candidate_user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_name = Column(String(128), default="Candidate")
    interview_mode = Column(String(32), nullable=False, default="self_practice", server_default="self_practice")
    room_id = Column(String(64), nullable=True, index=True)
    resume_filename = Column(String(256), nullable=True)
    resume_text = Column(Text, nullable=True)
    parsed_resume = Column(JSON, nullable=True)
    screening_fit = Column(Float, default=0.0)
    screening_status = Column(String(32), default="PENDING")  # PASSED, REJECTED
    screening_details = Column(JSON, nullable=True)
    interview_status = Column(String(32), default="CREATED", index=True)  # CREATED, IN_PROGRESS, RECORDED, ANALYZED
    video_filename = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    job = relationship("Job", back_populates="sessions")
    candidate_user = relationship("User", back_populates="sessions", foreign_keys=[candidate_user_id])
    questions = relationship("SessionQuestion", back_populates="session", cascade="all, delete-orphan", order_by="SessionQuestion.order_index")
    proctoring_events = relationship("ProctoringEvent", back_populates="session", cascade="all, delete-orphan")
    report = relationship("InterviewReport", back_populates="session", uselist=False, cascade="all, delete-orphan")


class SessionQuestion(Base):
    """Questions selected and asked in a specific interview session."""
    __tablename__ = "session_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False, index=True)
    question_id = Column(String(64), ForeignKey("questions.id"), nullable=True)
    order_index = Column(Integer, nullable=False, default=0, index=True)
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
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False, index=True)
    question_id = Column(String(64), nullable=True)
    t_start = Column(Float, nullable=False, index=True)
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
    created_at = Column(DateTime, default=_utcnow_naive)

    session = relationship("InterviewSession", back_populates="report")


class User(Base):
    """Authenticated user account (candidate, admin, or super_admin)."""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="candidate", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    token_version = Column(Integer, nullable=False, default=0)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    profile = relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("InterviewSession", back_populates="candidate_user", foreign_keys=[InterviewSession.candidate_user_id])
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    one_time_tokens = relationship("OneTimeToken", back_populates="user", cascade="all, delete-orphan")
    created_rooms = relationship("InterviewRoom", back_populates="created_by_admin", foreign_keys="InterviewRoom.created_by_admin_id")
    assigned_rooms = relationship("InterviewRoom", back_populates="assigned_candidate", foreign_keys="InterviewRoom.assigned_candidate_id")
    room_participations = relationship("RoomParticipant", back_populates="user", cascade="all, delete-orphan")


class CandidateProfile(Base):
    """Database-backed candidate personal, educational, technical, and experience profile."""
    __tablename__ = "candidate_profiles"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    headline = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    location = Column(String(128), nullable=True)
    education_level = Column(String(64), nullable=True)
    education_details_json = Column(JSON, nullable=True)
    experience_years = Column(Float, nullable=False, default=0.0)
    experience_summary_json = Column(JSON, nullable=True)
    technical_skills_json = Column(JSON, nullable=True)
    preferred_roles_json = Column(JSON, nullable=True)
    portfolio_links_json = Column(JSON, nullable=True)
    bio = Column(Text, nullable=True)
    profile_completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    user = relationship("User", back_populates="profile")


class Resume(Base):
    """Securely stored uploaded candidate resume metadata and extracted text."""
    __tablename__ = "resumes"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(255), unique=True, nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    raw_text = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    user = relationship("User", back_populates="resumes")
    parsed_profile = relationship("ResumeProfile", back_populates="resume", uselist=False, cascade="all, delete-orphan")


class ResumeProfile(Base):
    """Parsed and candidate-reviewed/confirmed structured resume profile."""
    __tablename__ = "resume_profiles"

    id = Column(String(64), primary_key=True)
    resume_id = Column(String(64), ForeignKey("resumes.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    extracted_data_json = Column(JSON, nullable=False)
    edited_data_json = Column(JSON, nullable=True)
    field_provenance_json = Column(JSON, nullable=True)
    confirmed_by_user = Column(Boolean, nullable=False, default=False)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    resume = relationship("Resume", back_populates="parsed_profile")


class JobRoleTemplate(Base):
    """Seeded industry & entry-level role templates used for universal job recommendations."""
    __tablename__ = "job_role_templates"

    id = Column(String(64), primary_key=True)
    slug = Column(String(128), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    level = Column(String(32), nullable=False, default="entry")
    domain = Column(String(128), nullable=False)
    required_skills_json = Column(JSON, nullable=False)
    preferred_skills_json = Column(JSON, nullable=False)
    min_experience_years = Column(Float, nullable=False, default=0.0)
    education_levels_json = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    mapped_job_id = Column(String(64), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)


class JobRecommendation(Base):
    """Computed job and role-template recommendations persisted per candidate."""
    __tablename__ = "job_recommendations"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False)
    target_type = Column(String(32), nullable=False)
    target_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    match_score = Column(Float, nullable=False)
    matched_skills_json = Column(JSON, nullable=False)
    missing_skills_json = Column(JSON, nullable=False)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive)


class RefreshToken(Base):
    """Hashed rotating refresh sessions with family-level reuse revocation."""
    __tablename__ = "refresh_tokens"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    rotation_family_id = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_id = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)

    user = relationship("User", back_populates="refresh_tokens")


class OneTimeToken(Base):
    """Single-use hashed expiring tokens for password reset and email verification."""
    __tablename__ = "one_time_tokens"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(32), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)

    user = relationship("User", back_populates="one_time_tokens")


class AuditLog(Base):
    """Immutable security and administrative audit trail."""
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True)
    actor_user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_role = Column(String(32), nullable=True)
    action = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(64), nullable=True, index=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive, index=True)


class QuestionSet(Base):
    """Admin-managed interview question collections and templates."""
    __tablename__ = "question_sets"

    id = Column(String(64), primary_key=True)
    owner_admin_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_filename = Column(String(255), nullable=True)
    schema_version = Column(String(32), nullable=False, default="1.0")
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="active", index=True)
    checksum = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive)
    updated_at = Column(DateTime, nullable=False, default=_utcnow_naive, onupdate=_utcnow_naive)

    owner = relationship("User", foreign_keys=[owner_admin_id])
    items = relationship("QuestionSetItem", back_populates="question_set", cascade="all, delete-orphan", order_by="QuestionSetItem.ordinal")


class QuestionSetItem(Base):
    """Individual question items within an admin question set."""
    __tablename__ = "question_set_items"

    id = Column(String(64), primary_key=True)
    question_set_id = Column(String(64), ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    source_question_id = Column(String(64), nullable=True)
    question_text = Column(Text, nullable=False)
    domain = Column(String(128), nullable=False, default="General")
    difficulty = Column(String(32), nullable=False, default="Intermediate")
    target_skills_json = Column(JSON, nullable=False)
    ideal_criteria_json = Column(JSON, nullable=False)
    ordinal = Column(Integer, nullable=False, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive)

    question_set = relationship("QuestionSet", back_populates="items")


class InterviewRoom(Base):
    """Admin-hosted collaborative interview room state and orchestration."""
    __tablename__ = "interview_rooms"

    id = Column(String(64), primary_key=True)
    created_by_admin_id = Column(String(64), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_candidate_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    room_code_hash = Column(String(64), nullable=False, index=True)
    invite_token_hash = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    duration_seconds = Column(Integer, nullable=False, default=3600)
    mode = Column(String(32), nullable=False, default="hosted")
    proctoring_preset = Column(String(32), nullable=False, default="strict")
    current_sequence_version = Column(Integer, nullable=False, default=0)
    current_question_ordinal = Column(Integer, nullable=False, default=0)
    question_set_id = Column(String(64), ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True)
    active_session_id = Column(String(64), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    timezone = Column(String(64), nullable=False, default="UTC")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive)
    updated_at = Column(DateTime, nullable=False, default=_utcnow_naive, onupdate=_utcnow_naive)

    created_by_admin = relationship("User", foreign_keys=[created_by_admin_id], back_populates="created_rooms")
    assigned_candidate = relationship("User", foreign_keys=[assigned_candidate_id], back_populates="assigned_rooms")
    question_set = relationship("QuestionSet")
    session = relationship("InterviewSession", foreign_keys=[active_session_id])
    questions = relationship("RoomQuestion", back_populates="room", cascade="all, delete-orphan", order_by="RoomQuestion.ordinal")
    participants = relationship("RoomParticipant", back_populates="room", cascade="all, delete-orphan")
    events = relationship("RoomEvent", back_populates="room", cascade="all, delete-orphan", order_by="RoomEvent.sequence_no")


class RoomParticipant(Base):
    """Candidates, admins, and observers associated with an interview room."""
    __tablename__ = "room_participants"

    id = Column(String(64), primary_key=True)
    room_id = Column(String(64), ForeignKey("interview_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="candidate")
    status = Column(String(32), nullable=False, default="invited")
    joined_at = Column(DateTime, nullable=True)
    left_at = Column(DateTime, nullable=True)
    reconnect_count = Column(Integer, nullable=False, default=0)
    device_checks_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive)
    updated_at = Column(DateTime, nullable=False, default=_utcnow_naive, onupdate=_utcnow_naive)

    room = relationship("InterviewRoom", back_populates="participants")
    user = relationship("User", back_populates="room_participations")


class RoomQuestion(Base):
    """Server-synchronized questions planned or active in an interview room."""
    __tablename__ = "room_questions"

    id = Column(String(64), primary_key=True)
    room_id = Column(String(64), ForeignKey("interview_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    source_question_id = Column(String(64), nullable=True)
    question_text = Column(Text, nullable=False)
    domain = Column(String(128), nullable=False, default="General")
    difficulty = Column(String(32), nullable=False, default="Intermediate")
    target_skills_json = Column(JSON, nullable=False)
    ideal_criteria_json = Column(JSON, nullable=False)
    ordinal = Column(Integer, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")
    time_limit_seconds = Column(Integer, nullable=False, default=180)
    asked_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    room = relationship("InterviewRoom", back_populates="questions")


class RoomEvent(Base):
    """Append-only sequence-ordered room state and signaling audit event log."""
    __tablename__ = "room_events"

    id = Column(String(64), primary_key=True)
    room_id = Column(String(64), ForeignKey("interview_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload_json_redacted = Column(JSON, nullable=True)
    sequence_no = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, index=True)

    room = relationship("InterviewRoom", back_populates="events")
