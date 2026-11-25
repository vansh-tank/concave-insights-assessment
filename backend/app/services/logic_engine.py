"""
Survey execution logic engine:
- Answer validation (required, min/max, minlength, format, exclusive, other)
- Conditional show-if evaluation (AND / OR)
- Dynamic piping [qN] and options-from resolution
- Deterministic per-respondent option shuffling (keeping fixed options last)
- Skip-to navigation, termination checks, quota checks, and quality flags
"""

from __future__ import annotations

import random
import re
from typing import Any, Optional

from app.models import Answer, Question, Quota, Respondent
from app.schemas import OptionRenderSchema, QuestionRenderSchema, SubmitAnswerRequest

_PINCODE_RE = re.compile(r"^\d{6}$")
_PHONE_RE = re.compile(r"^(\+91)?[6-9]\d{9}$|^\d{10}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PIPING_RE = re.compile(r"\[([a-zA-Z0-9_-]+)\]")
_COND_RE = re.compile(r"^\s*([a-zA-Z0-9_-]+)\s*(=|!=)\s*(.+?)\s*$")


class AnswerValidationError(ValueError):
    """Raised when a submitted answer violates question constraints."""


def format_numeric(val: Optional[float]) -> str:
    if val is None:
        return ""
    return str(int(val)) if float(val).is_integer() else str(val)


def get_display_answer_for_question(
    question: Optional[Question], answer: Optional[Answer]
) -> str:
    """Return human-readable answer text for piping [qN] and single-value checks."""
    if answer is None:
        return ""

    if question and question.type in ("number", "rating", "nps"):
        return format_numeric(answer.numeric_value)

    if answer.selected_options:
        opts = list(answer.selected_options)
        if question:
            other_labels = {o.text for o in question.options if o.is_other}
            resolved = []
            for sel in opts:
                if sel in other_labels and answer.text_value:
                    resolved.append(answer.text_value.strip())
                else:
                    resolved.append(sel)
            return ", ".join(resolved)
        return ", ".join(opts)

    if answer.text_value:
        return answer.text_value.strip()

    if answer.numeric_value is not None:
        return format_numeric(answer.numeric_value)

    return ""


def apply_piping(
    text: str,
    questions_by_id: dict[str, Question],
    answers_map: dict[str, Answer],
) -> str:
    """Replace [qN] tokens in text with earlier answers."""

    def _repl(match: re.Match) -> str:
        ref_id = match.group(1)
        val = get_display_answer_for_question(
            questions_by_id.get(ref_id), answers_map.get(ref_id)
        )
        return val if val else match.group(0)

    return _PIPING_RE.sub(_repl, text)


def _match_clause(clause: str, answers_map: dict[str, Answer]) -> bool:
    m = _COND_RE.match(clause)
    if not m:
        return False
    qid, op, expected = m.group(1), m.group(2), m.group(3).strip()
    ans = answers_map.get(qid)
    if ans is None:
        return op == "!="

    actual_values: list[str] = []
    if ans.selected_options:
        actual_values.extend(str(v) for v in ans.selected_options)
    if ans.numeric_value is not None:
        actual_values.append(format_numeric(ans.numeric_value))
    if ans.text_value is not None and not ans.selected_options:
        actual_values.append(ans.text_value.strip())

    matched = any(v.lower() == expected.lower() for v in actual_values)
    return matched if op == "=" else not matched


def evaluate_show_if(expr: Optional[str], answers_map: dict[str, Answer]) -> bool:
    """Evaluate show-if condition supporting AND / OR (AND binds tighter than OR)."""
    if not expr or not expr.strip():
        return True

    or_groups = re.split(r"\s+OR\s+", expr, flags=re.IGNORECASE)
    for group in or_groups:
        and_clauses = re.split(r"\s+AND\s+", group, flags=re.IGNORECASE)
        if all(_match_clause(c, answers_map) for c in and_clauses):
            return True
    return False


def validate_answer(question: Question, payload: SubmitAnswerRequest) -> None:
    """Validate submitted answer against question type, required, min/max, and format."""
    qtype = question.type

    if qtype == "info":
        return

    selected = payload.selected_options or []
    text_val = (payload.text_value or "").strip()
    num_val = payload.numeric_value
    matrix_ans = payload.matrix_answers or {}

    if qtype in ("single", "dropdown", "yesno", "consent"):
        if question.required and len(selected) == 0:
            raise AnswerValidationError("Please select an option to continue.")
        if len(selected) > 1:
            raise AnswerValidationError("Only one option can be selected.")
        if selected:
            other_labels = {o.text for o in question.options if o.is_other}
            if selected[0] in other_labels and not text_val:
                raise AnswerValidationError("Please specify your answer in the text box.")

    elif qtype == "multi":
        if question.required and len(selected) == 0:
            raise AnswerValidationError("Please select at least one option.")
        exclusive_labels = {o.text for o in question.options if o.is_exclusive}
        if any(s in exclusive_labels for s in selected) and len(selected) > 1:
            raise AnswerValidationError("Exclusive option cannot be combined with other selections.")
        if question.max_val is not None and len(selected) > question.max_val:
            raise AnswerValidationError(f"You can select at most {question.max_val} options.")
        other_labels = {o.text for o in question.options if o.is_other}
        if any(s in other_labels for s in selected) and not text_val:
            raise AnswerValidationError("Please specify your 'Other' answer.")

    elif qtype in ("number", "rating", "nps"):
        if question.required and num_val is None:
            raise AnswerValidationError("Please enter a valid number.")
        if num_val is not None:
            min_v = 0 if qtype == "nps" and question.min_val is None else question.min_val
            max_v = 10 if qtype == "nps" and question.max_val is None else question.max_val
            if min_v is not None and num_val < min_v:
                raise AnswerValidationError(f"Value must be at least {min_v}.")
            if max_v is not None and num_val > max_v:
                raise AnswerValidationError(f"Value must be at most {max_v}.")

    elif qtype in ("text", "longtext"):
        if question.required and not text_val:
            raise AnswerValidationError("This field is required.")
        if text_val and question.min_length is not None and len(text_val) < question.min_length:
            raise AnswerValidationError(f"Please enter at least {question.min_length} characters.")

    elif qtype == "formatted":
        if question.required and not text_val:
            raise AnswerValidationError("This field is required.")
        if text_val:
            fmt = question.format_rule
            if fmt == "pincode" and not _PINCODE_RE.match(text_val):
                raise AnswerValidationError("Pincode must be exactly 6 digits.")
            elif fmt == "phone" and not _PHONE_RE.match(text_val):
                raise AnswerValidationError("Please enter a valid 10-digit phone number.")
            elif fmt == "email" and not _EMAIL_RE.match(text_val):
                raise AnswerValidationError("Please enter a valid email address.")

    elif qtype == "matrix":
        if question.required:
            missing = [r.text for r in question.rows if not matrix_ans.get(r.text)]
            if missing:
                raise AnswerValidationError("Please select an answer for every row.")


def build_rendered_question(
    question: Question,
    respondent_id: str,
    questions_by_id: dict[str, Question],
    answers_map: dict[str, Answer],
) -> QuestionRenderSchema:
    """Build the rendered question payload with piping, options-from, and shuffle."""
    rendered_text = apply_piping(question.text, questions_by_id, answers_map)

    options_list: list[OptionRenderSchema] = []
    if question.options_from:
        src_q = questions_by_id.get(question.options_from)
        src_ans = answers_map.get(question.options_from)
        if src_ans and src_ans.selected_options:
            other_labels = {o.text for o in src_q.options if o.is_other} if src_q else set()
            exclusive_labels = {o.text for o in src_q.options if o.is_exclusive} if src_q else set()
            for sel in src_ans.selected_options:
                if sel in exclusive_labels:
                    continue
                if sel in other_labels and src_ans.text_value:
                    options_list.append(OptionRenderSchema(text=src_ans.text_value.strip()))
                else:
                    options_list.append(OptionRenderSchema(text=sel))
    else:
        non_fixed = [o for o in question.options if not o.is_fixed]
        fixed = [o for o in question.options if o.is_fixed]
        if question.shuffle and len(non_fixed) > 1:
            rng = random.Random(f"{respondent_id}:{question.question_id}")
            non_fixed = list(non_fixed)
            rng.shuffle(non_fixed)
        for o in non_fixed + fixed:
            options_list.append(
                OptionRenderSchema(
                    text=o.text,
                    is_fixed=o.is_fixed,
                    is_other=o.is_other,
                    is_exclusive=o.is_exclusive,
                )
            )

    rows_list = [r.text for r in question.rows]

    prev_ans_dict = None
    if question.question_id in answers_map:
        a = answers_map[question.question_id]
        prev_ans_dict = {
            "selected_options": a.selected_options,
            "text_value": a.text_value,
            "numeric_value": a.numeric_value,
            "matrix_answers": a.matrix_answers,
        }

    return QuestionRenderSchema(
        question_id=question.question_id,
        order_index=question.order_index,
        type=question.type,
        text=rendered_text,
        required=question.required,
        min_val=question.min_val,
        max_val=question.max_val,
        min_length=question.min_length,
        format_rule=question.format_rule,
        low_label=question.low_label,
        high_label=question.high_label,
        options=options_list,
        rows=rows_list,
        previous_answer=prev_ans_dict,
    )


def check_termination_and_quotas(
    question: Question,
    payload: SubmitAnswerRequest,
    quotas: list[Quota],
    is_test: bool,
) -> tuple[bool, list[str], bool]:
    """
    Check if the current answer triggers termination or hits a full quota.
    Returns (is_terminated, reasons_list, is_silent).
    """
    reasons: list[str] = []
    is_silent = False
    selected = payload.selected_options or []

    # 1. Explicit terminate-on rule
    if question.terminate_on and any(s.lower() == question.terminate_on.lower() for s in selected):
        reason_text = question.termination_reason or f"Terminated on {question.question_id}={question.terminate_on}"
        reasons.append(f"{question.question_id}: {reason_text}")
        is_silent = question.silent_terminate

    # 2. Consent decline
    if question.type == "consent" and any(s.lower() == "no" for s in selected) and not reasons:
        reasons.append(f"{question.question_id}: Did not consent")

    # 3. Quota check (skip for test respondents)
    if not is_test and quotas:
        q_quotas = [qt for qt in quotas if qt.question_id == question.question_id]
        for qt in q_quotas:
            if any(s.lower() == qt.match_value.lower() for s in selected):
                if qt.current_count >= qt.target_count:
                    reasons.append(f"{question.question_id}: Quota full for {qt.match_value}")

    return (len(reasons) > 0, reasons, is_silent)


def find_next_question(
    questions: list[Question],
    current_idx: int,
    selected_options: Optional[list[str]],
    answers_map: dict[str, Answer],
) -> Optional[Question]:
    """Resolve skip-to jump or sequential advance, skipping questions whose show-if is false."""
    q_index_map = {q.question_id: idx for idx, q in enumerate(questions)}
    current_q = questions[current_idx]

    next_idx = current_idx + 1
    if selected_options:
        opt_map = {o.text: o for o in current_q.options}
        for sel in selected_options:
            opt = opt_map.get(sel)
            if opt and opt.skip_to and opt.skip_to in q_index_map:
                next_idx = q_index_map[opt.skip_to]
                break

    while next_idx < len(questions):
        candidate = questions[next_idx]
        if evaluate_show_if(candidate.show_if, answers_map):
            return candidate
        next_idx += 1

    return None


def compute_visible_question_path(
    questions: list[Question],
    answers_map: dict[str, Answer],
) -> list[Question]:
    """Reconstruct the sequence of visible questions up to the current point."""
    if not questions:
        return []
    path: list[Question] = []
    idx = 0
    while idx < len(questions):
        q = questions[idx]
        if evaluate_show_if(q.show_if, answers_map):
            path.append(q)
            ans = answers_map.get(q.question_id)
            if ans is None:
                break
            next_q = find_next_question(questions, idx, ans.selected_options, answers_map)
            if next_q is None:
                break
            idx = next(i for i, item in enumerate(questions) if item.question_id == next_q.question_id)
        else:
            idx += 1
    return path


def compute_quality_flags(
    respondent: Respondent,
    questions: list[Question],
    answers_map: dict[str, Answer],
) -> list[str]:
    """Detect speeders and matrix straight-lining without deleting responses."""
    flags: list[str] = []

    if respondent.completed_at and respondent.started_at:
        completed = respondent.completed_at.replace(tzinfo=None)
        started = respondent.started_at.replace(tzinfo=None)
        duration_sec = (completed - started).total_seconds()
        min_expected = max(8.0, len(answers_map) * 1.5)
        if duration_sec < min_expected:
            flags.append("speeder")

    for q in questions:
        if q.type == "matrix" and len(q.rows) >= 3:
            ans = answers_map.get(q.question_id)
            if ans and ans.matrix_answers and len(ans.matrix_answers) == len(q.rows):
                distinct_vals = set(ans.matrix_answers.values())
                if len(distinct_vals) == 1:
                    flags.append("straight_lining")
                    break

    return flags
