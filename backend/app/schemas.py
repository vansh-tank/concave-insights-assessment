"""Pydantic v2 request and response schemas."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ParseErrorSchema(BaseModel):
    line: int
    message: str


class SurveyUploadTextRequest(BaseModel):
    dsl_text: str = Field(..., min_length=1)
    deadline: Optional[datetime] = None


class SurveyUploadResponse(BaseModel):
    valid: bool
    survey_id: Optional[str] = None
    version_id: Optional[int] = None
    version_number: Optional[int] = None
    title: Optional[str] = None
    question_count: int = 0
    quota_count: int = 0
    errors: list[ParseErrorSchema] = []


class QuotaSchema(BaseModel):
    id: int
    question_id: str
    match_value: str
    target_count: int
    current_count: int
    remaining: int


class SurveySummarySchema(BaseModel):
    id: str
    title: str
    target: int
    status: str
    deadline: Optional[datetime] = None
    latest_version: Optional[int] = None
    approved_version: Optional[int] = None
    created_at: datetime


class SurveyStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(draft|live|closed)$")
    deadline: Optional[datetime] = None


class CloneSurveyRequest(BaseModel):
    new_id: str = Field(..., min_length=2, max_length=64)
    new_title: Optional[str] = None


class CreateLinksRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=500)
    is_test: bool = False


class RespondentLinkSchema(BaseModel):
    respondent_id: str
    token: str
    url: str
    is_test: bool


class OptionRenderSchema(BaseModel):
    text: str
    is_fixed: bool = False
    is_other: bool = False
    is_exclusive: bool = False


class QuestionRenderSchema(BaseModel):
    question_id: str
    order_index: int
    type: str
    text: str
    required: bool = False
    min_val: Optional[int] = None
    max_val: Optional[int] = None
    min_length: Optional[int] = None
    format_rule: Optional[str] = None
    low_label: Optional[str] = None
    high_label: Optional[str] = None
    options: list[OptionRenderSchema] = []
    rows: list[str] = []
    previous_answer: Optional[dict[str, Any]] = None


class RespondentStateResponse(BaseModel):
    respondent_id: str
    survey_id: str
    survey_title: str
    version_number: int
    status: str  # in_progress | completed | terminated | closed | already_completed
    end_screen: Optional[str] = None  # completed | not_eligible | survey_closed | already_completed
    is_test: bool
    progress_percent: int
    current_question: Optional[QuestionRenderSchema] = None
    can_go_back: bool = False


class SubmitAnswerRequest(BaseModel):
    question_id: str
    selected_options: Optional[list[str]] = None
    text_value: Optional[str] = None
    numeric_value: Optional[float] = None
    matrix_answers: Optional[dict[str, str]] = None
    row_order: Optional[list[str]] = None


class BackRequest(BaseModel):
    current_question_id: Optional[str] = None


class DashboardStatsResponse(BaseModel):
    survey_id: str
    title: str
    status: str
    target: int
    started: int
    completed: int
    terminated: int
    in_progress: int
    quotas: list[QuotaSchema]
    termination_reasons: dict[str, int]
    drop_off_by_question: dict[str, int]
    quality_flag_counts: dict[str, int]
