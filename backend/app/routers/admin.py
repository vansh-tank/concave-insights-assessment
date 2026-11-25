"""Admin / Researcher API routes for survey upload, validation, approval, links, dashboard, and export."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    MatrixRow,
    Question,
    QuestionOption,
    Quota,
    Respondent,
    Survey,
    SurveyVersion,
)
from app.schemas import (
    CloneSurveyRequest,
    CreateLinksRequest,
    DashboardStatsResponse,
    ParseErrorSchema,
    QuotaSchema,
    RespondentLinkSchema,
    SurveyStatusUpdateRequest,
    SurveySummarySchema,
    SurveyUploadResponse,
    SurveyUploadTextRequest,
)
from app.services.dsl_parser import ParsedSurvey, parse_and_validate_dsl
from app.services.export_service import (
    build_export_table,
    export_to_csv_bytes,
    export_to_excel_bytes,
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _persist_parsed_survey(
    db: Session,
    parsed: ParsedSurvey,
    raw_dsl: str,
    deadline: Optional[datetime] = None,
) -> tuple[Survey, SurveyVersion]:
    survey = db.query(Survey).filter(Survey.id == parsed.survey_id).first()
    if survey is None:
        survey = Survey(
            id=parsed.survey_id,
            title=parsed.title,
            target=parsed.target,
            status="draft",
            deadline=deadline,
        )
        db.add(survey)
        db.flush()
    else:
        survey.title = parsed.title
        survey.target = parsed.target
        if deadline is not None:
            survey.deadline = deadline

    # Sync quotas for the survey (preserve current_count for matching rules)
    existing_quotas = {
        (qt.question_id, qt.match_value): qt.current_count
        for qt in db.query(Quota).filter(Quota.survey_id == survey.id).all()
    }
    db.query(Quota).filter(Quota.survey_id == survey.id).delete()
    for pq in parsed.quotas:
        db.add(
            Quota(
                survey_id=survey.id,
                question_id=pq.question_id or "",
                match_value=pq.match_value or "",
                target_count=pq.target_count or 0,
                current_count=existing_quotas.get((pq.question_id, pq.match_value), 0),
            )
        )

    latest_ver = (
        db.query(SurveyVersion)
        .filter(SurveyVersion.survey_id == survey.id)
        .order_by(SurveyVersion.version_number.desc())
        .first()
    )
    next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

    version = SurveyVersion(
        survey_id=survey.id,
        version_number=next_ver_num,
        raw_dsl=raw_dsl,
        is_approved=False,
    )
    db.add(version)
    db.flush()

    for pq in parsed.questions:
        q_model = Question(
            version_id=version.id,
            question_id=pq.question_id or "",
            order_index=pq.order_index,
            type=pq.q_type or "text",
            text=pq.text,
            required=pq.required,
            show_if=pq.show_if,
            options_from=pq.options_from,
            terminate_on=pq.terminate_on,
            termination_reason=pq.termination_reason,
            silent_terminate=pq.silent_terminate,
            min_val=pq.min_val,
            max_val=pq.max_val,
            min_length=pq.min_length,
            format_rule=pq.format_rule,
            shuffle=pq.shuffle,
            low_label=pq.low_label,
            high_label=pq.high_label,
        )
        db.add(q_model)
        db.flush()

        for opt in pq.options:
            db.add(
                QuestionOption(
                    question_id=q_model.id,
                    text=opt.text,
                    order_index=opt.order_index,
                    is_fixed=opt.is_fixed,
                    is_other=opt.is_other,
                    is_exclusive=opt.is_exclusive,
                    skip_to=opt.skip_to,
                )
            )
        for row in pq.rows:
            db.add(
                MatrixRow(
                    question_id=q_model.id,
                    text=row.text,
                    order_index=row.order_index,
                )
            )

    db.commit()
    db.refresh(survey)
    db.refresh(version)
    return survey, version


@router.post("/surveys/validate", response_model=SurveyUploadResponse)
def validate_questionnaire(payload: SurveyUploadTextRequest):
    """Dry-run parse and validation of questionnaire DSL text without saving."""
    result = parse_and_validate_dsl(payload.dsl_text)
    if not result.valid or result.survey is None:
        return SurveyUploadResponse(
            valid=False,
            errors=[ParseErrorSchema(**e.to_dict()) for e in result.errors],
        )
    return SurveyUploadResponse(
        valid=True,
        survey_id=result.survey.survey_id,
        title=result.survey.title,
        question_count=len(result.survey.questions),
        quota_count=len(result.survey.quotas),
        errors=[],
    )


@router.post("/surveys/upload", response_model=SurveyUploadResponse)
async def upload_questionnaire_file(
    file: UploadFile = File(...),
    deadline: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Upload a .txt questionnaire file, validate it, and save as a new draft version."""
    raw_bytes = await file.read()
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded plain text.")

    result = parse_and_validate_dsl(raw_text)
    if not result.valid or result.survey is None:
        return JSONResponse(
            status_code=422,
            content=SurveyUploadResponse(
                valid=False,
                errors=[ParseErrorSchema(**e.to_dict()) for e in result.errors],
            ).model_dump(),
        )

    survey, version = _persist_parsed_survey(db, result.survey, raw_text, deadline=deadline)
    return SurveyUploadResponse(
        valid=True,
        survey_id=survey.id,
        version_id=version.id,
        version_number=version.version_number,
        title=survey.title,
        question_count=len(result.survey.questions),
        quota_count=len(result.survey.quotas),
        errors=[],
    )


@router.post("/surveys/upload-text", response_model=SurveyUploadResponse)
def upload_questionnaire_text(
    payload: SurveyUploadTextRequest,
    db: Session = Depends(get_db),
):
    """Upload questionnaire DSL as JSON text, validate it, and save as a new draft version."""
    result = parse_and_validate_dsl(payload.dsl_text)
    if not result.valid or result.survey is None:
        return JSONResponse(
            status_code=422,
            content=SurveyUploadResponse(
                valid=False,
                errors=[ParseErrorSchema(**e.to_dict()) for e in result.errors],
            ).model_dump(),
        )

    survey, version = _persist_parsed_survey(db, result.survey, payload.dsl_text, deadline=payload.deadline)
    return SurveyUploadResponse(
        valid=True,
        survey_id=survey.id,
        version_id=version.id,
        version_number=version.version_number,
        title=survey.title,
        question_count=len(result.survey.questions),
        quota_count=len(result.survey.quotas),
        errors=[],
    )


@router.get("/surveys", response_model=list[SurveySummarySchema])
def list_surveys(db: Session = Depends(get_db)):
    """List all surveys with their status and version numbers."""
    surveys = db.query(Survey).options(joinedload(Survey.versions)).order_by(Survey.created_at.desc()).all()
    out: list[SurveySummarySchema] = []
    for s in surveys:
        latest = max((v.version_number for v in s.versions), default=None)
        approved = max((v.version_number for v in s.versions if v.is_approved), default=None)
        out.append(
            SurveySummarySchema(
                id=s.id,
                title=s.title,
                target=s.target,
                status=s.status,
                deadline=s.deadline,
                latest_version=latest,
                approved_version=approved,
                created_at=s.created_at,
            )
        )
    return out


@router.get("/surveys/{survey_id}")
def get_survey_detail(survey_id: str, db: Session = Depends(get_db)):
    """Retrieve survey metadata, versions, and quotas."""
    survey = (
        db.query(Survey)
        .options(joinedload(Survey.versions), joinedload(Survey.quotas))
        .filter(Survey.id == survey_id)
        .first()
    )
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found.")
    return {
        "id": survey.id,
        "title": survey.title,
        "target": survey.target,
        "status": survey.status,
        "deadline": survey.deadline,
        "created_at": survey.created_at,
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "is_approved": v.is_approved,
                "approved_at": v.approved_at,
                "created_at": v.created_at,
            }
            for v in sorted(survey.versions, key=lambda x: x.version_number, reverse=True)
        ],
        "quotas": [
            {
                "id": q.id,
                "question_id": q.question_id,
                "match_value": q.match_value,
                "target_count": q.target_count,
                "current_count": q.current_count,
                "remaining": max(0, q.target_count - q.current_count),
            }
            for q in survey.quotas
        ],
    }


@router.post("/surveys/{survey_id}/approve")
def approve_survey_version(
    survey_id: str,
    version_number: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Approve and freeze a survey version (defaults to the latest version)."""
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found.")

    query = db.query(SurveyVersion).filter(SurveyVersion.survey_id == survey_id)
    if version_number is not None:
        version = query.filter(SurveyVersion.version_number == version_number).first()
    else:
        version = query.order_by(SurveyVersion.version_number.desc()).first()

    if not version:
        raise HTTPException(status_code=404, detail="Survey version not found.")

    version.is_approved = True
    version.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return {
        "survey_id": survey_id,
        "version_id": version.id,
        "version_number": version.version_number,
        "is_approved": version.is_approved,
        "approved_at": version.approved_at,
    }


@router.patch("/surveys/{survey_id}/status")
def update_survey_status(
    survey_id: str,
    payload: SurveyStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """Transition survey status (draft | live | closed). Setting live requires an approved version."""
    survey = db.query(Survey).options(joinedload(Survey.versions)).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found.")

    if payload.status == "live":
        has_approved = any(v.is_approved for v in survey.versions)
        if not has_approved:
            raise HTTPException(
                status_code=400,
                detail="Cannot set survey to live before approving at least one version.",
            )

    survey.status = payload.status
    if payload.deadline is not None:
        survey.deadline = payload.deadline
    db.commit()
    return {"survey_id": survey.id, "status": survey.status, "deadline": survey.deadline}


@router.post("/surveys/{survey_id}/links", response_model=list[RespondentLinkSchema])
def generate_respondent_links(
    survey_id: str,
    payload: CreateLinksRequest,
    db: Session = Depends(get_db),
):
    """Generate unique tokenized links for real respondents or preview/test mode."""
    survey = db.query(Survey).options(joinedload(Survey.versions)).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found.")

    if payload.is_test:
        # Test mode can run against the latest version (even if draft)
        version = max(survey.versions, key=lambda v: v.version_number, default=None)
    else:
        approved = [v for v in survey.versions if v.is_approved]
        version = max(approved, key=lambda v: v.version_number, default=None)

    if not version:
        raise HTTPException(status_code=400, detail="No suitable survey version available.")

    created: list[RespondentLinkSchema] = []
    for _ in range(payload.count):
        resp_id = str(uuid.uuid4())
        token = uuid.uuid4().hex[:16]
        resp = Respondent(
            id=resp_id,
            survey_id=survey.id,
            version_id=version.id,
            token=token,
            status="in_progress",
            is_test=payload.is_test,
        )
        db.add(resp)
        created.append(
            RespondentLinkSchema(
                respondent_id=resp_id,
                token=token,
                url=f"/survey/{survey.id}?token={token}",
                is_test=payload.is_test,
            )
        )

    db.commit()
    return created


@router.post("/surveys/{survey_id}/clone", response_model=SurveyUploadResponse)
def clone_survey(
    survey_id: str,
    payload: CloneSurveyRequest,
    db: Session = Depends(get_db),
):
    """Clone an existing survey into a new separate survey (second wave)."""
    if db.query(Survey).filter(Survey.id == payload.new_id).first():
        raise HTTPException(status_code=409, detail=f"Survey ID '{payload.new_id}' already exists.")

    src = db.query(Survey).options(joinedload(Survey.versions)).filter(Survey.id == survey_id).first()
    if not src or not src.versions:
        raise HTTPException(status_code=404, detail="Source survey not found.")

    latest_ver = max(src.versions, key=lambda v: v.version_number)
    result = parse_and_validate_dsl(latest_ver.raw_dsl)
    if not result.valid or result.survey is None:
        raise HTTPException(status_code=400, detail="Source survey DSL could not be cloned.")

    result.survey.survey_id = payload.new_id
    if payload.new_title:
        result.survey.title = payload.new_title

    new_survey, new_ver = _persist_parsed_survey(db, result.survey, latest_ver.raw_dsl)
    return SurveyUploadResponse(
        valid=True,
        survey_id=new_survey.id,
        version_id=new_ver.id,
        version_number=new_ver.version_number,
        title=new_survey.title,
        question_count=len(result.survey.questions),
        quota_count=len(result.survey.quotas),
        errors=[],
    )


@router.get("/surveys/{survey_id}/dashboard", response_model=DashboardStatsResponse)
def get_survey_dashboard(survey_id: str, db: Session = Depends(get_db)):
    """Live dashboard metrics excluding test responses."""
    survey = db.query(Survey).options(joinedload(Survey.quotas)).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found.")

    respondents = (
        db.query(Respondent)
        .filter(Respondent.survey_id == survey_id, Respondent.is_test.is_(False))
        .all()
    )

    started = len(respondents)
    completed = sum(1 for r in respondents if r.status == "completed")
    terminated = sum(1 for r in respondents if r.status == "terminated")
    in_progress = sum(1 for r in respondents if r.status == "in_progress")

    term_counts: Counter[str] = Counter()
    drop_off_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()

    for r in respondents:
        if r.status == "terminated" and r.termination_reasons:
            for part in r.termination_reasons.split("|"):
                cleaned = part.strip()
                if cleaned:
                    term_counts[cleaned] += 1
        if r.status == "in_progress" and r.current_question_id:
            drop_off_counts[r.current_question_id] += 1
        if r.quality_flags:
            for fl in r.quality_flags:
                flag_counts[fl] += 1

    quotas_out = [
        QuotaSchema(
            id=q.id,
            question_id=q.question_id,
            match_value=q.match_value,
            target_count=q.target_count,
            current_count=q.current_count,
            remaining=max(0, q.target_count - q.current_count),
        )
        for q in survey.quotas
    ]

    return DashboardStatsResponse(
        survey_id=survey.id,
        title=survey.title,
        status=survey.status,
        target=survey.target,
        started=started,
        completed=completed,
        terminated=terminated,
        in_progress=in_progress,
        quotas=quotas_out,
        termination_reasons=dict(term_counts),
        drop_off_by_question=dict(drop_off_counts),
        quality_flag_counts=dict(flag_counts),
    )


@router.get("/surveys/{survey_id}/export")
def export_survey_data(
    survey_id: str,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
):
    """Export completed (non-test) responses in standardized CSV or Excel format."""
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found.")

    versions_list = (
        db.query(SurveyVersion)
        .options(
            joinedload(SurveyVersion.questions).joinedload(Question.options),
            joinedload(SurveyVersion.questions).joinedload(Question.rows),
        )
        .filter(SurveyVersion.survey_id == survey_id)
        .all()
    )
    versions_map = {v.id: v for v in versions_list}

    respondents = (
        db.query(Respondent)
        .options(joinedload(Respondent.answers))
        .filter(
            Respondent.survey_id == survey_id,
            Respondent.status == "completed",
            Respondent.is_test.is_(False),
        )
        .order_by(Respondent.completed_at.asc())
        .all()
    )

    headers, rows = build_export_table(versions_map, respondents)

    if format == "xlsx":
        data = export_to_excel_bytes(headers, rows, sheet_title=survey_id)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{survey_id}_export.xlsx"'},
        )

    data = export_to_csv_bytes(headers, rows)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{survey_id}_export.csv"'},
    )
