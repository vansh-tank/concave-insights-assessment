# Backend - Custom Survey System

FastAPI + SQLAlchemy backend for parsing, validating, running, and exporting custom surveys.

---

## Setup & Run Locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Load demo survey (smartphone_study) and sample links
python seed_demo.py

# Start the API server
uvicorn app.main:app --reload --port 8000
```

Interactive Swagger docs are available at `http://localhost:8000/docs`.

---

## Running Tests

```bash
cd backend
.venv/bin/pytest -v
```

---

## API Endpoints

### Admin (`/api/admin`)

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/admin/surveys/validate` | Dry-run parse & validate DSL text, returning line-numbered errors |
| `POST` | `/api/admin/surveys/upload` | Upload `.txt` questionnaire file and create a new draft version |
| `POST` | `/api/admin/surveys/upload-text` | Upload raw DSL string as JSON and create a new draft version |
| `GET` | `/api/admin/surveys` | List all surveys with status and version numbers |
| `GET` | `/api/admin/surveys/{survey_id}` | Get survey details, versions, and quota status |
| `POST` | `/api/admin/surveys/{survey_id}/approve` | Approve and freeze a survey version |
| `PATCH` | `/api/admin/surveys/{survey_id}/status` | Change survey status (`draft`, `live`, `closed`) and deadline |
| `POST` | `/api/admin/surveys/{survey_id}/links` | Generate unique respondent links (`is_test=true` for preview mode) |
| `POST` | `/api/admin/surveys/{survey_id}/clone` | Clone an existing survey as a new wave |
| `GET` | `/api/admin/surveys/{survey_id}/dashboard` | Live metrics: counts, quotas, termination reasons, drop-offs, flags |
| `GET` | `/api/admin/surveys/{survey_id}/export` | Download completed responses (`?format=csv` or `?format=xlsx`) |

### Respondent (`/api/respond`)

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/respond/{token}` | Validate link, resume from last unanswered question, or return end screen |
| `POST` | `/api/respond/{token}/answer` | Validate and auto-save answer, run logic/quotas, return next question |
| `POST` | `/api/respond/{token}/back` | Move back to the previous visible question with saved answer pre-filled |

#### Sample Request & Response (`POST /api/respond/{token}/answer`)

Request:
```json
{
  "question_id": "q6",
  "selected_options": ["Samsung", "Other (specify)"],
  "text_value": "Lava"
}
```

Response:
```json
{
  "respondent_id": "5b1c2d3e-...",
  "survey_id": "smartphone_study",
  "survey_title": "Smartphone Usage Study",
  "version_number": 1,
  "status": "in_progress",
  "end_screen": null,
  "is_test": false,
  "progress_percent": 38,
  "current_question": {
    "question_id": "q7",
    "order_index": 7,
    "type": "single",
    "text": "Which of these brands do you use now?",
    "required": true,
    "options": [
      {"text": "Samsung", "is_fixed": false, "is_other": false, "is_exclusive": false},
      {"text": "Lava", "is_fixed": false, "is_other": false, "is_exclusive": false}
    ],
    "rows": [],
    "previous_answer": null
  },
  "can_go_back": true
}
```
