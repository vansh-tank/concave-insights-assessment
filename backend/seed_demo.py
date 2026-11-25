"""Seed script to load the sample questionnaire and create demo data in under 5 seconds."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.models import Answer, Quota, Respondent, Survey
from app.routers.admin import _persist_parsed_survey
from app.services.dsl_parser import parse_and_validate_dsl


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        sample_path = Path(__file__).resolve().parent.parent / "concave_sample_questionnaire.txt"
        raw_dsl = sample_path.read_text(encoding="utf-8")
        result = parse_and_validate_dsl(raw_dsl)
        if not result.valid or result.survey is None:
            print("Failed to parse sample questionnaire:", result.errors)
            return

        existing = db.query(Survey).filter(Survey.id == result.survey.survey_id).first()
        if existing:
            print(f"Survey '{existing.id}' already seeded.")
            return

        survey, version = _persist_parsed_survey(
            db,
            result.survey,
            raw_dsl,
            deadline=datetime.now(timezone.utc) + timedelta(days=15),
        )
        version.is_approved = True
        version.approved_at = datetime.now(timezone.utc)
        survey.status = "live"

        # Add 1 completed demo respondent so dashboard & export show data immediately
        demo_resp = Respondent(
            id=str(uuid.uuid4()),
            survey_id=survey.id,
            version_id=version.id,
            token="demo-completed-01",
            status="completed",
            is_test=False,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=4),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(demo_resp)
        db.flush()

        demo_answers = [
            Answer(respondent_id=demo_resp.id, question_id="q1", selected_options=["Yes"]),
            Answer(respondent_id=demo_resp.id, question_id="q2", numeric_value=26),
            Answer(respondent_id=demo_resp.id, question_id="q3", selected_options=["Female"]),
            Answer(respondent_id=demo_resp.id, question_id="q4", selected_options=["Mumbai"]),
            Answer(respondent_id=demo_resp.id, question_id="q5", selected_options=["Yes"]),
            Answer(respondent_id=demo_resp.id, question_id="q6", selected_options=["Apple", "Samsung"]),
            Answer(respondent_id=demo_resp.id, question_id="q7", selected_options=["Apple"]),
            Answer(respondent_id=demo_resp.id, question_id="q8", numeric_value=5),
            Answer(respondent_id=demo_resp.id, question_id="q10", numeric_value=9),
            Answer(
                respondent_id=demo_resp.id,
                question_id="q11",
                matrix_answers={
                    "The battery lasts a full day": "Agree",
                    "The camera takes good photos": "Strongly agree",
                    "It works smoothly without lag": "Strongly agree",
                    "It was good value for money": "Neutral",
                },
            ),
            Answer(respondent_id=demo_resp.id, question_id="q12", selected_options=["No"]),
            Answer(respondent_id=demo_resp.id, question_id="q16", text_value="Ananya Sharma"),
            Answer(respondent_id=demo_resp.id, question_id="q17", text_value="400001"),
        ]
        db.add_all(demo_answers)

        for qt in db.query(Quota).filter(Quota.survey_id == survey.id).all():
            if (qt.question_id == "q3" and qt.match_value == "Female") or (
                qt.question_id == "q4" and qt.match_value == "Mumbai"
            ):
                qt.current_count += 1

        # Add 2 fresh live links and 1 test link
        for tok, is_test in [("live-user-01", False), ("live-user-02", False), ("test-preview-01", True)]:
            db.add(
                Respondent(
                    id=str(uuid.uuid4()),
                    survey_id=survey.id,
                    version_id=version.id,
                    token=tok,
                    status="in_progress",
                    is_test=is_test,
                )
            )

        db.commit()
        print("Seeded 'smartphone_study' (v1 approved & live).")
        print("Demo links:")
        print("  Live respondent 1: /survey/smartphone_study?token=live-user-01")
        print("  Live respondent 2: /survey/smartphone_study?token=live-user-02")
        print("  Preview/Test link: /survey/smartphone_study?token=test-preview-01")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
