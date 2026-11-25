"""Respondent API routes for taking surveys, atomic auto-saving, resuming, and navigating back."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Answer, Question, Quota, Respondent, Survey, SurveyVersion
from app.schemas import BackRequest, RespondentStateResponse, SubmitAnswerRequest
from app.services.logic_engine import (
    AnswerValidationError,
    build_rendered_question,
    check_termination_and_quotas,
    compute_quality_flags,
    compute_visible_question_path,
    evaluate_show_if,
    find_next_question,
    validate_answer,
)

router = APIRouter(prefix="/api/respond", tags=["Respondent"])


def _load_respondent_context(db: Session, token: str):
    respondent = (
        db.query(Respondent)
        .options(joinedload(Respondent.answers))
        .filter(Respondent.token == token)
        .first()
    )
    if not respondent:
        raise HTTPException(status_code=404, detail="Invalid or unknown survey link.")

    survey = (
        db.query(Survey)
        .options(joinedload(Survey.quotas))
        .filter(Survey.id == respondent.survey_id)
        .first()
    )
    version = (
        db.query(SurveyVersion)
        .options(
            joinedload(SurveyVersion.questions).joinedload(Question.options),
            joinedload(SurveyVersion.questions).joinedload(Question.rows),
        )
        .filter(SurveyVersion.id == respondent.version_id)
        .first()
    )
    return respondent, survey, version


def _is_survey_closed(db: Session, survey: Survey, is_test: bool) -> bool:
    if is_test:
        return False
    if survey.status == "closed":
        return True
    if survey.status != "live":
        return True
    if survey.deadline:
        deadline = survey.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > deadline:
            survey.status = "closed"
            db.commit()
            return True
    if survey.target > 0:
        completed_count = (
            db.query(Respondent)
            .filter(
                Respondent.survey_id == survey.id,
                Respondent.status == "completed",
                Respondent.is_test.is_(False),
            )
            .count()
        )
        if completed_count >= survey.target:
            survey.status = "closed"
            db.commit()
            return True
    return False


def _calculate_progress(questions: list[Question], current_q: Question | None) -> int:
    if not questions or current_q is None:
        return 100
    return min(99, int((current_q.order_index / max(1, len(questions))) * 100))


@router.get("/{token}", response_model=RespondentStateResponse)
def get_respondent_state(token: str, db: Session = Depends(get_db)):
    """Fetch current survey state and question for a respondent link (supports resume)."""
    respondent, survey, version = _load_respondent_context(db, token)
    questions = sorted(version.questions, key=lambda q: q.order_index)
    questions_by_id = {q.question_id: q for q in questions}
    answers_map = {a.question_id: a for a in respondent.answers}

    if respondent.status == "completed":
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="already_completed",
            end_screen="already_completed",
            is_test=respondent.is_test,
            progress_percent=100,
        )

    if respondent.status == "terminated":
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="terminated",
            end_screen="not_eligible",
            is_test=respondent.is_test,
            progress_percent=100,
        )

    if _is_survey_closed(db, survey, respondent.is_test):
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="closed",
            end_screen="survey_closed",
            is_test=respondent.is_test,
            progress_percent=0,
        )

    # Determine current question (resume bookmark or first visible unanswered question)
    current_q = None
    if respondent.current_question_id and respondent.current_question_id in questions_by_id:
        candidate = questions_by_id[respondent.current_question_id]
        if evaluate_show_if(candidate.show_if, answers_map):
            current_q = candidate

    if current_q is None:
        path = compute_visible_question_path(questions, answers_map)
        current_q = path[-1] if path else (questions[0] if questions else None)
        if current_q:
            respondent.current_question_id = current_q.question_id
            db.commit()

    rendered = (
        build_rendered_question(current_q, respondent.id, questions_by_id, answers_map)
        if current_q
        else None
    )
    can_go_back = bool(current_q and current_q.order_index > 0 and len(answers_map) > 0)

    return RespondentStateResponse(
        respondent_id=respondent.id,
        survey_id=survey.id,
        survey_title=survey.title,
        version_number=version.version_number,
        status="in_progress",
        is_test=respondent.is_test,
        progress_percent=_calculate_progress(questions, current_q),
        current_question=rendered,
        can_go_back=can_go_back,
    )


@router.post("/{token}/answer", response_model=RespondentStateResponse)
def submit_answer(token: str, payload: SubmitAnswerRequest, db: Session = Depends(get_db)):
    """Atomically save an answer, run logic/termination/quotas, and return the next question or end screen."""
    respondent, survey, version = _load_respondent_context(db, token)

    if respondent.status == "completed":
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="already_completed",
            end_screen="already_completed",
            is_test=respondent.is_test,
            progress_percent=100,
        )

    if respondent.status == "terminated":
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="terminated",
            end_screen="not_eligible",
            is_test=respondent.is_test,
            progress_percent=100,
        )

    if _is_survey_closed(db, survey, respondent.is_test):
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="closed",
            end_screen="survey_closed",
            is_test=respondent.is_test,
            progress_percent=0,
        )

    questions = sorted(version.questions, key=lambda q: q.order_index)
    questions_by_id = {q.question_id: q for q in questions}

    if payload.question_id not in questions_by_id:
        raise HTTPException(status_code=404, detail=f"Question '{payload.question_id}' not found in this version.")

    current_q = questions_by_id[payload.question_id]
    current_idx = next(i for i, q in enumerate(questions) if q.question_id == current_q.question_id)

    # Validate answer constraints
    try:
        validate_answer(current_q, payload)
    except AnswerValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Upsert answer immediately (atomic save)
    ans = (
        db.query(Answer)
        .filter(Answer.respondent_id == respondent.id, Answer.question_id == current_q.question_id)
        .first()
    )
    if ans is None:
        ans = Answer(
            respondent_id=respondent.id,
            question_id=current_q.question_id,
        )
        db.add(ans)

    ans.selected_options = payload.selected_options
    ans.text_value = payload.text_value
    ans.numeric_value = payload.numeric_value
    ans.matrix_answers = payload.matrix_answers
    ans.row_order = payload.row_order
    ans.answered_at = datetime.now(timezone.utc)
    respondent.last_active_at = datetime.now(timezone.utc)
    db.flush()

    # Refresh answers map
    answers_map = {a.question_id: a for a in respondent.answers}
    answers_map[current_q.question_id] = ans

    # Check termination & quotas
    is_term, reasons, is_silent = check_termination_and_quotas(
        current_q, payload, survey.quotas, respondent.is_test
    )
    if is_term:
        existing_reasons = [r.strip() for r in (respondent.termination_reasons or "").split("|") if r.strip()]
        for r in reasons:
            if r not in existing_reasons:
                existing_reasons.append(r)
        respondent.status = "terminated"
        respondent.termination_reasons = " | ".join(existing_reasons)
        db.commit()
        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="terminated",
            end_screen="completed" if is_silent else "not_eligible",
            is_test=respondent.is_test,
            progress_percent=100,
        )

    # Find next visible question
    next_q = find_next_question(questions, current_idx, payload.selected_options, answers_map)
    if next_q is None:
        # Finalize completion and atomically verify/increment quotas
        if not respondent.is_test:
            if _is_survey_closed(db, survey, False):
                respondent.status = "terminated"
                respondent.termination_reasons = "Survey target reached before completion"
                db.commit()
                return RespondentStateResponse(
                    respondent_id=respondent.id,
                    survey_id=survey.id,
                    survey_title=survey.title,
                    version_number=version.version_number,
                    status="closed",
                    end_screen="survey_closed",
                    is_test=respondent.is_test,
                    progress_percent=100,
                )

            # Check and increment matching quotas
            matched_quotas: list[Quota] = []
            for qt in survey.quotas:
                q_ans = answers_map.get(qt.question_id)
                if q_ans and q_ans.selected_options and qt.match_value in q_ans.selected_options:
                    if qt.current_count >= qt.target_count:
                        respondent.status = "terminated"
                        respondent.termination_reasons = f"{qt.question_id}: Quota full for {qt.match_value}"
                        db.commit()
                        return RespondentStateResponse(
                            respondent_id=respondent.id,
                            survey_id=survey.id,
                            survey_title=survey.title,
                            version_number=version.version_number,
                            status="terminated",
                            end_screen="not_eligible",
                            is_test=respondent.is_test,
                            progress_percent=100,
                        )
                    matched_quotas.append(qt)

            for qt in matched_quotas:
                qt.current_count += 1

        respondent.status = "completed"
        respondent.completed_at = datetime.now(timezone.utc)
        respondent.current_question_id = None
        respondent.quality_flags = compute_quality_flags(respondent, questions, answers_map)
        db.commit()

        # Check if total target is now reached
        _is_survey_closed(db, survey, respondent.is_test)

        return RespondentStateResponse(
            respondent_id=respondent.id,
            survey_id=survey.id,
            survey_title=survey.title,
            version_number=version.version_number,
            status="completed",
            end_screen="completed",
            is_test=respondent.is_test,
            progress_percent=100,
        )

    # Advance to next question
    respondent.current_question_id = next_q.question_id
    db.commit()

    rendered = build_rendered_question(next_q, respondent.id, questions_by_id, answers_map)
    return RespondentStateResponse(
        respondent_id=respondent.id,
        survey_id=survey.id,
        survey_title=survey.title,
        version_number=version.version_number,
        status="in_progress",
        is_test=respondent.is_test,
        progress_percent=_calculate_progress(questions, next_q),
        current_question=rendered,
        can_go_back=True,
    )


@router.post("/{token}/back", response_model=RespondentStateResponse)
def go_back(token: str, payload: BackRequest = BackRequest(), db: Session = Depends(get_db)):
    """Navigate back to the previous visible question while preserving all saved answers."""
    respondent, survey, version = _load_respondent_context(db, token)
    if respondent.status != "in_progress":
        raise HTTPException(status_code=400, detail="Cannot navigate back on a finished survey.")

    questions = sorted(version.questions, key=lambda q: q.order_index)
    questions_by_id = {q.question_id: q for q in questions}
    answers_map = {a.question_id: a for a in respondent.answers}

    path = compute_visible_question_path(questions, answers_map)
    current_qid = payload.current_question_id or respondent.current_question_id

    target_q = questions[0]
    if current_qid:
        path_ids = [q.question_id for q in path]
        if current_qid in path_ids:
            pos = path_ids.index(current_qid)
            if pos > 0:
                target_q = path[pos - 1]
        elif len(path) >= 2:
            target_q = path[-2]

    respondent.current_question_id = target_q.question_id
    db.commit()

    rendered = build_rendered_question(target_q, respondent.id, questions_by_id, answers_map)
    return RespondentStateResponse(
        respondent_id=respondent.id,
        survey_id=survey.id,
        survey_title=survey.title,
        version_number=version.version_number,
        status="in_progress",
        is_test=respondent.is_test,
        progress_percent=_calculate_progress(questions, target_q),
        current_question=rendered,
        can_go_back=target_q.order_index > 0,
    )
