"""
Standardized CSV and Excel (.xlsx) export generator.

Format specification:
- First column: Respondent ID
- Second column: Version
- Single / dropdown / yesno / consent / rating / nps / number / text / longtext / formatted:
    Header: "Q<ID>. <Text>" -> Value: selected option or typed text/number
    (If "Other (specify)" selected on single, formats as "Other-<typed>")
- Multi select:
    One column per option: "Q<ID>. <Text> - <Option>" -> Value: option name if picked, "" if not
    For Other option: "Q<ID>. <Text> - Other" -> Value: "Other-<typed>"
- Matrix:
    One column per row: "Q<ID>. <Text> - <Row>" -> Value: chosen rating
"""

from __future__ import annotations

import csv
import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Font

from app.models import Answer, Question, Respondent, SurveyVersion
from app.services.logic_engine import format_numeric


def _q_prefix(question: Question) -> str:
    return f"{question.question_id.upper()}. {question.text}"


def build_export_table(
    versions: dict[int, SurveyVersion],
    respondents: Iterable[Respondent],
) -> tuple[list[str], list[list[str]]]:
    """
    Build standardized tabular headers and rows for completed non-test respondents.
    Uses the latest/highest version's question structure as the canonical column order,
    and includes any additional questions from earlier versions if needed.
    """
    ordered_questions: list[Question] = []
    seen_qids: set[str] = set()

    for ver in sorted(versions.values(), key=lambda v: v.version_number, reverse=True):
        for q in ver.questions:
            if q.type == "info":
                continue
            if q.question_id not in seen_qids:
                seen_qids.add(q.question_id)
                ordered_questions.append(q)

    # Sort by original order_index so columns follow questionnaire flow
    ordered_questions.sort(key=lambda q: q.order_index)

    headers: list[str] = ["Respondent ID", "Version"]
    column_specs: list[tuple[str, Question, str | None]] = []

    for q in ordered_questions:
        prefix = _q_prefix(q)
        if q.type == "multi":
            for opt in q.options:
                if opt.is_other:
                    headers.append(f"{prefix} - Other")
                    column_specs.append(("multi_other", q, opt.text))
                else:
                    headers.append(f"{prefix} - {opt.text}")
                    column_specs.append(("multi_opt", q, opt.text))
        elif q.type == "matrix":
            for row in q.rows:
                headers.append(f"{prefix} - {row.text}")
                column_specs.append(("matrix_row", q, row.text))
        else:
            headers.append(prefix)
            column_specs.append(("single_val", q, None))

    rows_data: list[list[str]] = []
    for resp in respondents:
        ver = versions.get(resp.version_id)
        ver_label = f"v{ver.version_number}" if ver else str(resp.version_id)
        ans_map: dict[str, Answer] = {a.question_id: a for a in resp.answers}

        row_cells: list[str] = [resp.id, ver_label]
        for kind, q, sub_key in column_specs:
            ans = ans_map.get(q.question_id)
            if ans is None:
                row_cells.append("")
                continue

            if kind == "multi_opt":
                picked = ans.selected_options or []
                row_cells.append(sub_key if sub_key in picked else "")
            elif kind == "multi_other":
                picked = ans.selected_options or []
                if sub_key in picked:
                    typed = (ans.text_value or "").strip()
                    row_cells.append(f"Other-{typed}" if typed else "Other")
                else:
                    row_cells.append("")
            elif kind == "matrix_row":
                m_ans = ans.matrix_answers or {}
                row_cells.append(str(m_ans.get(sub_key, "")))
            else:
                if q.type in ("number", "rating", "nps"):
                    row_cells.append(format_numeric(ans.numeric_value))
                elif ans.selected_options:
                    sel = ans.selected_options[0]
                    other_labels = {o.text for o in q.options if o.is_other}
                    if sel in other_labels and ans.text_value:
                        row_cells.append(f"Other-{ans.text_value.strip()}")
                    else:
                        row_cells.append(sel)
                elif ans.text_value is not None:
                    row_cells.append(ans.text_value)
                elif ans.numeric_value is not None:
                    row_cells.append(format_numeric(ans.numeric_value))
                else:
                    row_cells.append("")

        rows_data.append(row_cells)

    return headers, rows_data


def export_to_csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def export_to_excel_bytes(headers: list[str], rows: list[list[str]], sheet_title: str = "Responses") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    ws.append(headers)
    bold_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = bold_font

    for r in rows:
        ws.append(r)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
