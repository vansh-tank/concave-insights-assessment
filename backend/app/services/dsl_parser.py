"""
DSL Parser and Validator for Concave Insights plain-text questionnaire files.

Supports XML-like tags with boolean attributes (e.g. `required`), multi-tag lines,
and reports exact line numbers for all syntax and semantic/logic errors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


VALID_QUESTION_TYPES = {
    "single",
    "multi",
    "dropdown",
    "yesno",
    "rating",
    "nps",
    "matrix",
    "text",
    "longtext",
    "number",
    "formatted",
    "info",
    "consent",
}

VALID_FORMATS = {"pincode", "phone", "email"}

OPTION_BEARING_TYPES = {"single", "multi", "dropdown", "yesno", "consent"}


@dataclass
class ParseError:
    line: int
    message: str

    def to_dict(self) -> dict:
        return {"line": self.line, "message": self.message}

    def __str__(self) -> str:
        return f"Line {self.line}: {self.message}"


@dataclass
class ParsedOption:
    text: str
    line: int
    order_index: int
    is_fixed: bool = False
    is_other: bool = False
    is_exclusive: bool = False
    skip_to: Optional[str] = None


@dataclass
class ParsedRow:
    text: str
    line: int
    order_index: int


@dataclass
class ParsedQuestion:
    question_id: Optional[str]
    q_type: Optional[str]
    line: int
    order_index: int
    text: str = ""
    required: bool = False
    show_if: Optional[str] = None
    options_from: Optional[str] = None
    terminate_on: Optional[str] = None
    termination_reason: Optional[str] = None
    silent_terminate: bool = False
    min_val: Optional[int] = None
    max_val: Optional[int] = None
    min_length: Optional[int] = None
    format_rule: Optional[str] = None
    shuffle: bool = False
    low_label: Optional[str] = None
    high_label: Optional[str] = None
    options: list[ParsedOption] = field(default_factory=list)
    rows: list[ParsedRow] = field(default_factory=list)


@dataclass
class ParsedQuota:
    question_id: Optional[str]
    match_value: Optional[str]
    target_count: Optional[int]
    raw_target: Optional[str]
    line: int


@dataclass
class ParsedSurvey:
    survey_id: Optional[str]
    title: str
    target: int
    questions: list[ParsedQuestion] = field(default_factory=list)
    quotas: list[ParsedQuota] = field(default_factory=list)


@dataclass
class ParseResult:
    valid: bool
    survey: Optional[ParsedSurvey]
    errors: list[ParseError] = field(default_factory=list)


_ATTR_PATTERN = re.compile(r'([a-zA-Z_-]+)\s*(?:=\s*"([^"]*)")?')
_TAG_PATTERN = re.compile(r"<(/?)([a-zA-Z_-]+)([^>]*)>")
_PIPING_PATTERN = re.compile(r"\[([a-zA-Z0-9_-]+)\]")
_CONDITION_PART_PATTERN = re.compile(r"^\s*([a-zA-Z0-9_-]+)\s*(=|!=)\s*(.+?)\s*$")


def _parse_attributes(attr_str: str) -> dict[str, str | bool]:
    attrs: dict[str, str | bool] = {}
    cleaned = attr_str.strip()
    if cleaned.endswith("/"):
        cleaned = cleaned[:-1].strip()
    for match in _ATTR_PATTERN.finditer(cleaned):
        key = match.group(1).lower()
        val = match.group(2)
        attrs[key] = True if val is None else val
    return attrs


def _as_bool(val: str | bool | None) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return False


def _as_int(val: str | bool | None) -> Optional[int]:
    if isinstance(val, str) and val.strip():
        try:
            return int(val.strip())
        except ValueError:
            return None
    return None


def parse_and_validate_dsl(raw_text: str) -> ParseResult:
    """
    Parse a plain-text questionnaire DSL and validate syntax, references,
    question types, options, and quotas with exact line numbers.
    """
    errors: list[ParseError] = []

    if not raw_text or not raw_text.strip():
        errors.append(ParseError(1, "Questionnaire file is empty."))
        return ParseResult(valid=False, survey=None, errors=errors)

    # Track line number for every character offset in raw_text
    line_starts = [0]
    for idx, ch in enumerate(raw_text):
        if ch == "\n":
            line_starts.append(idx + 1)

    def offset_to_line(offset: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if line_starts[mid] <= offset:
                lo = mid + 1
            else:
                hi = mid - 1
        return hi + 1

    survey: Optional[ParsedSurvey] = None
    survey_closed = False
    current_question: Optional[ParsedQuestion] = None
    inner_tag: Optional[str] = None
    inner_start_offset: int = 0
    inner_attrs: dict[str, str | bool] = {}
    inner_line: int = 1

    for match in _TAG_PATTERN.finditer(raw_text):
        is_closing = match.group(1) == "/"
        tag_name = match.group(2).lower()
        attr_str = match.group(3)
        is_self_closing = attr_str.strip().endswith("/")
        line_num = offset_to_line(match.start())

        if tag_name == "survey":
            if is_closing:
                if survey is None:
                    errors.append(ParseError(line_num, "Unexpected </survey> without opening <survey>."))
                else:
                    survey_closed = True
            else:
                if survey is not None:
                    errors.append(ParseError(line_num, "Multiple <survey> tags found; only one is allowed."))
                attrs = _parse_attributes(attr_str)
                s_id = attrs.get("id")
                s_title = attrs.get("title")
                s_target_raw = attrs.get("target")
                if not s_id or not isinstance(s_id, str):
                    errors.append(ParseError(line_num, "<survey> is missing required 'id' attribute."))
                if not s_title or not isinstance(s_title, str):
                    errors.append(ParseError(line_num, "<survey> is missing required 'title' attribute."))
                s_target = _as_int(s_target_raw)
                if s_target is None or s_target <= 0:
                    errors.append(ParseError(line_num, "<survey> 'target' must be a positive integer."))
                survey = ParsedSurvey(
                    survey_id=s_id if isinstance(s_id, str) else None,
                    title=s_title if isinstance(s_title, str) else "Untitled Survey",
                    target=s_target or 0,
                )

        elif tag_name == "question":
            if is_closing:
                if current_question is None:
                    errors.append(ParseError(line_num, "Unexpected </question> without opening <question>."))
                else:
                    if survey is not None:
                        survey.questions.append(current_question)
                    current_question = None
            else:
                if survey is None:
                    errors.append(ParseError(line_num, "<question> must appear inside <survey>."))
                if current_question is not None:
                    errors.append(ParseError(line_num, "Nested <question> tags are not allowed; close the previous question first."))
                attrs = _parse_attributes(attr_str)
                q_id = attrs.get("id")
                q_type = attrs.get("type")

                if not q_id or not isinstance(q_id, str):
                    errors.append(ParseError(line_num, "Question is missing required 'id' attribute."))
                    q_id_val = None
                else:
                    q_id_val = q_id.strip()

                if not q_type or not isinstance(q_type, str):
                    errors.append(ParseError(line_num, f"Question '{q_id_val or '?'}' is missing required 'type' attribute."))
                    q_type_val = None
                else:
                    q_type_val = q_type.strip().lower()
                    if q_type_val not in VALID_QUESTION_TYPES:
                        errors.append(
                            ParseError(
                                line_num,
                                f"Question '{q_id_val or '?'}' has unknown type '{q_type}'.",
                            )
                        )

                min_val = _as_int(attrs.get("min"))
                max_val = _as_int(attrs.get("max"))
                if "min" in attrs and min_val is None:
                    errors.append(ParseError(line_num, f"Question '{q_id_val or '?'}' has invalid integer for 'min'."))
                if "max" in attrs and max_val is None:
                    errors.append(ParseError(line_num, f"Question '{q_id_val or '?'}' has invalid integer for 'max'."))
                if min_val is not None and max_val is not None and min_val > max_val:
                    errors.append(ParseError(line_num, f"Question '{q_id_val or '?'}' has min ({min_val}) greater than max ({max_val})."))

                min_length = _as_int(attrs.get("minlength"))
                if "minlength" in attrs and (min_length is None or min_length < 0):
                    errors.append(ParseError(line_num, f"Question '{q_id_val or '?'}' has invalid 'minlength'."))

                fmt = attrs.get("format")
                fmt_val = fmt.strip().lower() if isinstance(fmt, str) else None
                if fmt_val is not None and fmt_val not in VALID_FORMATS:
                    errors.append(ParseError(line_num, f"Question '{q_id_val or '?'}' has unknown format '{fmt_val}'."))

                order_idx = len(survey.questions) if survey else 0
                current_question = ParsedQuestion(
                    question_id=q_id_val,
                    q_type=q_type_val,
                    line=line_num,
                    order_index=order_idx,
                    required=_as_bool(attrs.get("required")),
                    show_if=attrs.get("show-if") if isinstance(attrs.get("show-if"), str) else None,
                    options_from=attrs.get("options-from") if isinstance(attrs.get("options-from"), str) else None,
                    terminate_on=attrs.get("terminate-on") if isinstance(attrs.get("terminate-on"), str) else None,
                    termination_reason=attrs.get("reason") if isinstance(attrs.get("reason"), str) else None,
                    silent_terminate=_as_bool(attrs.get("silent")),
                    min_val=min_val,
                    max_val=max_val,
                    min_length=min_length,
                    format_rule=fmt_val,
                    shuffle=_as_bool(attrs.get("shuffle")),
                    low_label=attrs.get("low-label") if isinstance(attrs.get("low-label"), str) else None,
                    high_label=attrs.get("high-label") if isinstance(attrs.get("high-label"), str) else None,
                )

                # Default Yes/No options for yesno & consent if not explicitly provided
                if is_self_closing and survey is not None:
                    survey.questions.append(current_question)
                    current_question = None

        elif tag_name in ("text", "option", "row"):
            if current_question is None:
                errors.append(ParseError(line_num, f"<{tag_name}> must appear inside a <question> tag."))
                continue
            if not is_closing:
                inner_tag = tag_name
                inner_start_offset = match.end()
                inner_attrs = _parse_attributes(attr_str)
                inner_line = line_num
            else:
                if inner_tag != tag_name:
                    errors.append(ParseError(line_num, f"Mismatched closing tag </{tag_name}>."))
                else:
                    content = raw_text[inner_start_offset : match.start()].strip()
                    if tag_name == "text":
                        current_question.text = content
                    elif tag_name == "option":
                        if not content:
                            errors.append(ParseError(inner_line, "Empty <option> label is not allowed."))
                        skip_to = inner_attrs.get("skip-to")
                        current_question.options.append(
                            ParsedOption(
                                text=content,
                                line=inner_line,
                                order_index=len(current_question.options),
                                is_fixed=_as_bool(inner_attrs.get("fixed")),
                                is_other=_as_bool(inner_attrs.get("other")),
                                is_exclusive=_as_bool(inner_attrs.get("exclusive")),
                                skip_to=skip_to.strip() if isinstance(skip_to, str) else None,
                            )
                        )
                    elif tag_name == "row":
                        if not content:
                            errors.append(ParseError(inner_line, "Empty <row> statement is not allowed."))
                        current_question.rows.append(
                            ParsedRow(
                                text=content,
                                line=inner_line,
                                order_index=len(current_question.rows),
                            )
                        )
                inner_tag = None

        elif tag_name == "quota":
            if is_closing:
                continue
            if survey is None:
                errors.append(ParseError(line_num, "<quota> must appear inside <survey>."))
                continue
            attrs = _parse_attributes(attr_str)
            q_ref = attrs.get("question")
            val_ref = attrs.get("value")
            tgt_raw = attrs.get("target")
            tgt_int = _as_int(tgt_raw)
            if not q_ref or not isinstance(q_ref, str):
                errors.append(ParseError(line_num, "<quota> is missing 'question' attribute."))
            if not val_ref or not isinstance(val_ref, str):
                errors.append(ParseError(line_num, "<quota> is missing 'value' attribute."))
            if tgt_int is None or tgt_int <= 0:
                errors.append(ParseError(line_num, "<quota> 'target' must be a positive integer."))
            survey.quotas.append(
                ParsedQuota(
                    question_id=q_ref.strip() if isinstance(q_ref, str) else None,
                    match_value=val_ref.strip() if isinstance(val_ref, str) else None,
                    target_count=tgt_int,
                    raw_target=str(tgt_raw) if tgt_raw is not None else None,
                    line=line_num,
                )
            )
        else:
            errors.append(ParseError(line_num, f"Unknown tag <{tag_name}>."))

    if survey is None:
        errors.append(ParseError(1, "No <survey> tag found in questionnaire file."))
        return ParseResult(valid=False, survey=None, errors=errors)

    if current_question is not None:
        errors.append(ParseError(current_question.line, f"Question '{current_question.question_id or '?'}' is missing closing </question> tag."))

    if not survey_closed:
        errors.append(ParseError(len(line_starts), "Missing closing </survey> tag."))

    # Semantic & Cross-Reference Validation
    _validate_survey_semantics(survey, errors)

    # Sort errors cleanly by line number
    errors.sort(key=lambda e: e.line)

    return ParseResult(valid=len(errors) == 0, survey=survey, errors=errors)


def _effective_options(q: ParsedQuestion) -> list[str]:
    if q.options:
        return [opt.text for opt in q.options]
    if q.q_type in ("yesno", "consent"):
        return ["Yes", "No"]
    return []


def _validate_survey_semantics(survey: ParsedSurvey, errors: list[ParseError]) -> None:
    seen_ids: dict[str, ParsedQuestion] = {}
    question_order: dict[str, int] = {}

    # Pass 1: Duplicate IDs, missing <text>, and per-question option/row checks
    for idx, q in enumerate(survey.questions):
        if not q.text:
            errors.append(ParseError(q.line, f"Question '{q.question_id or '?'}' is missing <text>."))

        if q.question_id:
            if q.question_id in seen_ids:
                first_line = seen_ids[q.question_id].line
                errors.append(
                    ParseError(
                        q.line,
                        f"Duplicate question ID '{q.question_id}' (already defined at line {first_line}).",
                    )
                )
            else:
                seen_ids[q.question_id] = q
                question_order[q.question_id] = idx

        # Auto-populate Yes/No options on yesno & consent if none explicitly given
        if q.q_type in ("yesno", "consent") and not q.options:
            q.options = [
                ParsedOption(text="Yes", line=q.line, order_index=0),
                ParsedOption(text="No", line=q.line, order_index=1),
            ]

        if q.q_type in ("single", "multi", "dropdown") and not q.options and not q.options_from:
            errors.append(ParseError(q.line, f"Question '{q.question_id or '?'}' (type '{q.q_type}') requires at least one <option> or 'options-from'."))

        if q.q_type == "matrix":
            if not q.rows:
                errors.append(ParseError(q.line, f"Matrix question '{q.question_id or '?'}' must have at least one <row>."))
            if not q.options:
                errors.append(ParseError(q.line, f"Matrix question '{q.question_id or '?'}' must have at least one <option> for the scale."))

        if q.terminate_on:
            valid_opts = _effective_options(q)
            if valid_opts and q.terminate_on not in valid_opts:
                errors.append(
                    ParseError(
                        q.line,
                        f"Question '{q.question_id or '?'}' has terminate-on='{q.terminate_on}', which is not a valid option ({', '.join(valid_opts)}).",
                    )
                )

    # Pass 2: Cross-question references (options-from, show-if, skip-to, piping, quotas)
    for idx, q in enumerate(survey.questions):
        qid_label = q.question_id or f"at line {q.line}"

        # options-from check
        if q.options_from:
            ref_q = seen_ids.get(q.options_from)
            if ref_q is None:
                errors.append(ParseError(q.line, f"Question '{qid_label}' has options-from='{q.options_from}', but '{q.options_from}' does not exist."))
            elif question_order[q.options_from] >= idx:
                errors.append(ParseError(q.line, f"Question '{qid_label}' cannot pull options-from='{q.options_from}' because '{q.options_from}' does not appear earlier."))
            elif ref_q.q_type not in ("multi", "single", "dropdown"):
                errors.append(ParseError(q.line, f"Question '{qid_label}' has options-from='{q.options_from}', which is not a choice question."))

        # show-if check (supports AND / OR)
        if q.show_if:
            clauses = re.split(r"\s+(?:AND|OR)\s+", q.show_if, flags=re.IGNORECASE)
            for clause in clauses:
                m = _CONDITION_PART_PATTERN.match(clause)
                if not m:
                    errors.append(ParseError(q.line, f"Question '{qid_label}' has invalid show-if expression '{clause.strip()}'."))
                    continue
                target_qid, _, target_val = m.group(1), m.group(2), m.group(3).strip()
                ref_q = seen_ids.get(target_qid)
                if ref_q is None:
                    errors.append(ParseError(q.line, f"Question '{qid_label}' shows only if {target_qid} = {target_val}, but '{target_qid}' does not exist."))
                elif question_order[target_qid] >= idx:
                    errors.append(ParseError(q.line, f"Question '{qid_label}' references '{target_qid}' in show-if before '{target_qid}' is asked."))
                else:
                    valid_opts = _effective_options(ref_q)
                    if valid_opts and target_val not in valid_opts:
                        errors.append(
                            ParseError(
                                q.line,
                                f"Question '{qid_label}' show-if checks {target_qid}='{target_val}', which is not a valid option for '{target_qid}'.",
                            )
                        )

        # piping [qN] check
        for pipe_match in _PIPING_PATTERN.finditer(q.text):
            pipe_qid = pipe_match.group(1)
            if pipe_qid not in seen_ids:
                errors.append(ParseError(q.line, f"Question '{qid_label}' pipes [{pipe_qid}], but '{pipe_qid}' does not exist."))
            elif question_order[pipe_qid] >= idx:
                errors.append(ParseError(q.line, f"Question '{qid_label}' pipes [{pipe_qid}], which does not appear earlier."))

        # skip-to check on options
        for opt in q.options:
            if opt.skip_to:
                if opt.skip_to not in seen_ids:
                    errors.append(ParseError(opt.line, f"Option '{opt.text}' in '{qid_label}' has skip-to='{opt.skip_to}', but '{opt.skip_to}' does not exist."))
                elif question_order[opt.skip_to] <= idx:
                    errors.append(ParseError(opt.line, f"Option '{opt.text}' in '{qid_label}' cannot skip backwards or to itself ('{opt.skip_to}')."))

    # Pass 3: Quota checks
    for quota in survey.quotas:
        if not quota.question_id:
            continue
        ref_q = seen_ids.get(quota.question_id)
        if ref_q is None:
            errors.append(ParseError(quota.line, f"Quota references question '{quota.question_id}', which does not exist."))
            continue
        if ref_q.q_type is not None and ref_q.q_type not in OPTION_BEARING_TYPES:
            errors.append(
                ParseError(
                    quota.line,
                    f"Quota on '{quota.question_id}' (type '{ref_q.q_type}') is invalid; quotas only apply to choice questions.",
                )
            )
            continue
        valid_opts = _effective_options(ref_q)
        if quota.match_value and valid_opts and quota.match_value not in valid_opts:
            errors.append(
                ParseError(
                    quota.line,
                    f"Quota value '{quota.match_value}' is not a valid option for question '{quota.question_id}' ({', '.join(valid_opts)}).",
                )
            )
