"""SQLAlchemy ORM models matching the relational database design."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    target = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="draft")  # draft | live | closed
    deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    versions = relationship("SurveyVersion", back_populates="survey", cascade="all, delete-orphan")
    quotas = relationship("Quota", back_populates="survey", cascade="all, delete-orphan")
    respondents = relationship("Respondent", back_populates="survey", cascade="all, delete-orphan")


class SurveyVersion(Base):
    __tablename__ = "survey_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(String(64), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    raw_dsl = Column(Text, nullable=False)
    is_approved = Column(Boolean, nullable=False, default=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    survey = relationship("Survey", back_populates="versions")
    questions = relationship(
        "Question",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    respondents = relationship("Respondent", back_populates="version")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey("survey_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(32), nullable=False)
    order_index = Column(Integer, nullable=False)
    type = Column(String(32), nullable=False)
    text = Column(Text, nullable=False)
    required = Column(Boolean, nullable=False, default=False)
    show_if = Column(Text, nullable=True)
    options_from = Column(String(32), nullable=True)
    terminate_on = Column(String(255), nullable=True)
    termination_reason = Column(String(255), nullable=True)
    silent_terminate = Column(Boolean, nullable=False, default=False)
    min_val = Column(Integer, nullable=True)
    max_val = Column(Integer, nullable=True)
    min_length = Column(Integer, nullable=True)
    format_rule = Column(String(32), nullable=True)
    shuffle = Column(Boolean, nullable=False, default=False)
    low_label = Column(String(64), nullable=True)
    high_label = Column(String(64), nullable=True)

    version = relationship("SurveyVersion", back_populates="questions")
    options = relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.order_index",
    )
    rows = relationship(
        "MatrixRow",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="MatrixRow.order_index",
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(255), nullable=False)
    order_index = Column(Integer, nullable=False)
    is_fixed = Column(Boolean, nullable=False, default=False)
    is_other = Column(Boolean, nullable=False, default=False)
    is_exclusive = Column(Boolean, nullable=False, default=False)
    skip_to = Column(String(32), nullable=True)

    question = relationship("Question", back_populates="options")


class MatrixRow(Base):
    __tablename__ = "matrix_rows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(255), nullable=False)
    order_index = Column(Integer, nullable=False)

    question = relationship("Question", back_populates="rows")


class Quota(Base):
    __tablename__ = "quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(String(64), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String(32), nullable=False)
    match_value = Column(String(255), nullable=False)
    target_count = Column(Integer, nullable=False)
    current_count = Column(Integer, nullable=False, default=0)

    survey = relationship("Survey", back_populates="quotas")


class Respondent(Base):
    __tablename__ = "respondents"

    id = Column(String(64), primary_key=True)
    survey_id = Column(String(64), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(Integer, ForeignKey("survey_versions.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="in_progress")  # in_progress | completed | terminated
    is_test = Column(Boolean, nullable=False, default=False)
    termination_reasons = Column(Text, nullable=True)
    current_question_id = Column(String(32), nullable=True)
    quality_flags = Column(JSON, nullable=True)  # e.g. ["speeder", "straight_lining"]
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_active_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    survey = relationship("Survey", back_populates="respondents")
    version = relationship("SurveyVersion", back_populates="respondents")
    answers = relationship("Answer", back_populates="respondent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_respondents_survey_status", "survey_id", "status"),
    )


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    respondent_id = Column(String(64), ForeignKey("respondents.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(String(32), nullable=False)
    selected_options = Column(JSON, nullable=True)
    text_value = Column(Text, nullable=True)
    numeric_value = Column(Float, nullable=True)
    matrix_answers = Column(JSON, nullable=True)
    row_order = Column(JSON, nullable=True)
    answered_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    respondent = relationship("Respondent", back_populates="answers")

    __table_args__ = (
        UniqueConstraint("respondent_id", "question_id", name="uq_respondent_question"),
    )
