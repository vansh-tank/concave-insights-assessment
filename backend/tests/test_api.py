"""End-to-end pytest suite for the DSL parser, logic engine, quotas, and API."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_DSL = (ROOT_DIR / "concave_sample_questionnaire.txt").read_text(encoding="utf-8")
BROKEN_DSL = (ROOT_DIR / "concave_broken_questionnaire.txt").read_text(encoding="utf-8")


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_survey.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_broken_questionnaire_reports_line_errors(client):
    r = client.post(
        "/api/admin/surveys/upload",
        files={"file": ("broken.txt", BROKEN_DSL.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 422
    data = r.json()
    assert data["valid"] is False
    lines = {err["line"] for err in data["errors"]}
    # Key broken lines in concave_broken_questionnaire.txt
    assert 11 in lines  # unknown type 'singel'
    assert 16 in lines  # missing id
    assert 21 in lines  # terminate-on='Never' invalid for yesno
    assert 31 in lines  # options-from='q66' missing
    assert 35 in lines  # duplicate id q6
    assert 39 in lines  # show-if='q10=Yes' forward ref
    assert 45 in lines  # skip-to='q20' missing


def test_full_survey_flow_piping_skip_other_and_export(client):
    # 1. Upload valid sample questionnaire
    r = client.post(
        "/api/admin/surveys/upload",
        files={"file": ("sample.txt", SAMPLE_DSL.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200
    up = r.json()
    assert up["valid"] is True
    assert up["survey_id"] == "smartphone_study"
    assert up["version_number"] == 1
    assert up["question_count"] == 18

    # 2. Cannot set live before approving
    r = client.patch("/api/admin/surveys/smartphone_study/status", json={"status": "live"})
    assert r.status_code == 400

    # 3. Approve & set live
    r = client.post("/api/admin/surveys/smartphone_study/approve")
    assert r.status_code == 200
    assert r.json()["is_approved"] is True

    r = client.patch("/api/admin/surveys/smartphone_study/status", json={"status": "live"})
    assert r.status_code == 200
    assert r.json()["status"] == "live"

    # 4. Generate 1 live link + 1 test link
    r = client.post("/api/admin/surveys/smartphone_study/links", json={"count": 1, "is_test": False})
    assert r.status_code == 200
    live_token = r.json()[0]["token"]

    r = client.post("/api/admin/surveys/smartphone_study/links", json={"count": 1, "is_test": True})
    assert r.status_code == 200
    test_token = r.json()[0]["token"]

    # 5. Walk through live survey
    state = client.get(f"/api/respond/{live_token}").json()
    assert state["current_question"]["question_id"] == "q0"

    # q0 info -> q1 consent -> q2 age -> q3 gender -> q4 city -> q5 smartphone
    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q0"}).json()
    assert state["current_question"]["question_id"] == "q1"

    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q1", "selected_options": ["Yes"]}).json()
    assert state["current_question"]["question_id"] == "q2"

    # Invalid age (too young)
    bad = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q2", "numeric_value": 15})
    assert bad.status_code == 422

    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q2", "numeric_value": 25}).json()
    assert state["current_question"]["question_id"] == "q3"

    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q3", "selected_options": ["Male"]}).json()
    assert state["current_question"]["question_id"] == "q4"

    # Test Back button to q3 and resume
    back_state = client.post(f"/api/respond/{live_token}/back", json={"current_question_id": "q4"}).json()
    assert back_state["current_question"]["question_id"] == "q3"
    assert back_state["current_question"]["previous_answer"]["selected_options"] == ["Male"]

    # Re-submit q3 -> q4 -> q5 -> q6
    client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q3", "selected_options": ["Male"]})
    client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q4", "selected_options": ["Mumbai"]})
    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q5", "selected_options": ["Yes"]}).json()
    assert state["current_question"]["question_id"] == "q6"

    # q6 multi with Other (specify) = "Lava"
    state = client.post(
        f"/api/respond/{live_token}/answer",
        json={"question_id": "q6", "selected_options": ["Samsung", "Other (specify)"], "text_value": "Lava"},
    ).json()
    assert state["current_question"]["question_id"] == "q7"
    q7_opts = [o["text"] for o in state["current_question"]["options"]]
    assert q7_opts == ["Samsung", "Lava"]

    # q7 pick Lava -> q8 rating=2 (triggers show-if on q9!)
    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q7", "selected_options": ["Lava"]}).json()
    assert "Lava" in state["current_question"]["text"]  # piping [q7]

    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q8", "numeric_value": 2}).json()
    assert state["current_question"]["question_id"] == "q9"
    assert "Lava" in state["current_question"]["text"]

    # q9 longtext -> q10 nps -> q11 matrix -> q12 No (skip-to q16!)
    client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q9", "text_value": "Battery drains quickly on heavy use"})
    client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q10", "numeric_value": 6})
    state = client.post(
        f"/api/respond/{live_token}/answer",
        json={
            "question_id": "q11",
            "matrix_answers": {
                "The battery lasts a full day": "Disagree",
                "The camera takes good photos": "Agree",
                "It works smoothly without lag": "Neutral",
                "It was good value for money": "Agree",
            },
        },
    ).json()
    assert state["current_question"]["question_id"] == "q12"

    # q12 = No skips directly to q16
    state = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q12", "selected_options": ["No"]}).json()
    assert state["current_question"]["question_id"] == "q16"

    client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q16", "text_value": "Rahul Verma"})
    done = client.post(f"/api/respond/{live_token}/answer", json={"question_id": "q17", "text_value": "400001"}).json()
    assert done["status"] == "completed"
    assert done["end_screen"] == "completed"

    # Duplicate visit shows already_completed
    revisit = client.get(f"/api/respond/{live_token}").json()
    assert revisit["end_screen"] == "already_completed"

    # Test respondent termination does not affect real dashboard
    client.post(f"/api/respond/{test_token}/answer", json={"question_id": "q0"})
    client.post(f"/api/respond/{test_token}/answer", json={"question_id": "q1", "selected_options": ["Yes"]})
    client.post(f"/api/respond/{test_token}/answer", json={"question_id": "q2", "numeric_value": 30})
    client.post(f"/api/respond/{test_token}/answer", json={"question_id": "q3", "selected_options": ["Male"]})
    term_state = client.post(f"/api/respond/{test_token}/answer", json={"question_id": "q4", "selected_options": ["Other city"]}).json()
    assert term_state["status"] == "terminated"
    assert term_state["end_screen"] == "not_eligible"

    # 6. Dashboard check (only 1 real respondent, test respondent excluded)
    dash = client.get("/api/admin/surveys/smartphone_study/dashboard").json()
    assert dash["started"] == 1
    assert dash["completed"] == 1
    assert dash["terminated"] == 0

    # 7. Export CSV & XLSX
    csv_resp = client.get("/api/admin/surveys/smartphone_study/export?format=csv")
    assert csv_resp.status_code == 200
    csv_text = csv_resp.text
    assert "Respondent ID" in csv_text
    assert "Version" in csv_text
    assert "Other-Lava" in csv_text

    xlsx_resp = client.get("/api/admin/surveys/smartphone_study/export?format=xlsx")
    assert xlsx_resp.status_code == 200
    assert len(xlsx_resp.content) > 100

    # 8. Clone survey
    clone_resp = client.post(
        "/api/admin/surveys/smartphone_study/clone",
        json={"new_id": "smartphone_study_wave2", "new_title": "Smartphone Study Wave 2"},
    )
    assert clone_resp.status_code == 200
    assert clone_resp.json()["survey_id"] == "smartphone_study_wave2"
