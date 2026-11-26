# Custom Survey System — Concave Insights

## 1. Project Overview

An in-house survey platform built for Concave Insights to replace manual survey link creation. Researchers upload a plain-text questionnaire file (`.txt`), and the system parses and checks it with line numbers, lets them preview and approve a locked version, runs multiple surveys concurrently with unique links and quotas, auto-saves every answer on mobile, and exports clean standardized CSV/Excel files.

---

## 2. Tech Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2.1, Pydantic v2, OpenPyXL
- **Database:** SQLite (`survey_system.db` for zero-config local setup; PostgreSQL compatible)
- **Frontend:** React 19, TypeScript, Vite 6, Tailwind CSS 4, React Router, Lucide Icons
- **Testing:** Pytest, FastAPI TestClient (HTTPX)

---

## 3. Setup and Run

Follow these steps to run the entire app locally in under 5 minutes:

### 1. Start the Backend (Terminal 1)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Load the sample questionnaire (smartphone_study) and demo links
python seed_demo.py

# Start FastAPI server on port 8000
uvicorn app.main:app --reload --port 8000
```

### 2. Start the Frontend (Terminal 2)
```bash
cd frontend
npm install
npm run dev
```

- **Admin Studio & Dashboard:** `http://localhost:5173/`
- **Backend Swagger Docs:** `http://localhost:8000/docs`

### 3. Run Backend Tests
```bash
cd backend
.venv/bin/pytest -v
```

---

## 4. Demo Logins and Test Data

No authentication gate is required for the local demo—opening `http://localhost:5173/` lands directly on the Admin Studio.

After running `python seed_demo.py`, the following demo data is pre-loaded:
- **Sample Survey (`smartphone_study`):** `Smartphone Usage Study` (Version 1 approved & live, target 200, quotas on `q3` Male/Female and `q4` Mumbai).
- **Pre-loaded Respondent Links:**
  - **Fresh Live Link 1:** `http://localhost:5173/survey/smartphone_study?token=live-user-01`
  - **Fresh Live Link 2:** `http://localhost:5173/survey/smartphone_study?token=live-user-02`
  - **Preview / Test Mode Link:** `http://localhost:5173/survey/smartphone_study?token=test-preview-01`
  - **Already Completed Link:** `http://localhost:5173/survey/smartphone_study?token=demo-completed-01`
- **Test Questionnaire Files (in root directory):**
  - `concave_sample_questionnaire.txt` — Valid questionnaire file.
  - `concave_broken_questionnaire.txt` — Broken questionnaire file to test line-number validation errors.

---

## 5. Features

### Core Requirements
| Feature | Status | Notes |
| :--- | :--- | :--- |
| Upload `.txt` & Line-number Validation | **Done** | Catches missing/duplicate IDs, unknown types, broken `show-if`/`skip-to`/`options-from`, invalid `terminate-on`, and bad quotas with exact line numbers |
| Preview & Test Mode | **Done** | Isolated via `is_test=true`; excluded from quotas, dashboard stats, and exports |
| Approve & Version Freeze | **Done** | Freezing locks a version (`v1`, `v2`); every respondent records `version_id` |
| All 11 Question Types | **Done** | `single`, `multi`, `dropdown` (searchable), `yesno`, `rating`, `nps`, `matrix`, `text`, `longtext`, `number`, `formatted`, `info`, `consent` |
| Question Rules (`required`, `other`, `exclusive`, `shuffle`) | **Done** | Deterministic per-respondent shuffle keeping `fixed="true"` last; `Other (specify)` text used everywhere |
| Logic (`skip-to`, `show-if` AND/OR, piping `[qN]`, `options-from`) | **Done** | Evaluated dynamically on every step |
| Termination & Silent Termination | **Done** | Logs reasons joined with `\|`; `silent="true"` shows polite completion screen |
| Running Many Surveys, Unique Links & Quotas | **Done** | Draft/Live/Closed states, unique tokens, duplicate prevention, auto-close on target/deadline |
| Mobile-First Survey Runner (Auto-save, Resume, Back, 4 End Screens) | **Done** | Atomic save per answer, progress bar, resume from last unanswered question, Back with pre-filled values |
| Live Dashboard & Standardized CSV / Excel Export | **Done** | Started/Completed/In-Progress/Terminated counts, quotas, termination reasons, standard CSV & `.xlsx` |

### Bonus Features
| Feature | Status | Notes |
| :--- | :--- | :--- |
| Quality Flags (Speeders & Straight-lining) | **Done** | Flags fast completions and identical matrix row answers without deleting data |
| Survey Clone | **Done** | Clone an existing survey into a separate wave (`/clone`) |
| Drop-off Report | **Done** | Tracks last reached question for in-progress drop-offs on the dashboard |
| Nested Quota | **Not done** | Single-question quotas supported; multi-question composite quotas planned |
| Shuffle Matrix Rows & Save Order | **Partly done** | `row_order` column exists in `answers` table; UI shuffle toggle not yet exposed |
| Balanced Rotation (AB/BA) | **Not done** | Planned for future release |
| Two Languages (Bilingual) | **Not done** | Planned for future release |

---

## 6. Database Design

The relational schema is documented in [`/design/schema.md`](./design/schema.md) with visual diagrams in [`/design/database_diagram.png`](./design/database_diagram.png) and [`/design/user_flow.png`](./design/user_flow.png).

Main tables:
- **`surveys`** — Top-level study metadata (`id`, `title`, `target`, `status`, `deadline`).
- **`survey_versions`** — Immutable questionnaire snapshots (`version_number`, `raw_dsl`, `is_approved`).
- **`questions`**, **`question_options`**, **`matrix_rows`** — Normalized question definitions, logic attributes, choices, and matrix statements per version.
- **`quotas`** — Target and current counts per `(survey_id, question_id, match_value)`.
- **`respondents`** — Unique tokenized sessions (`token`, `version_id`, `status`, `is_test`, `current_question_id`, `termination_reasons`, `quality_flags`).
- **`answers`** — Atomic per-question responses (`selected_options`, `text_value`, `numeric_value`, `matrix_answers`).

---

## 7. API Endpoints

Full interactive documentation is available at `http://localhost:8000/docs` when running the server.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/admin/surveys/upload` | Upload `.txt` file, validate with line numbers, save draft version |
| `POST` | `/api/admin/surveys/validate` | Dry-run validation without saving |
| `GET` | `/api/admin/surveys` | List all surveys |
| `POST` | `/api/admin/surveys/{id}/approve` | Approve & freeze latest version |
| `PATCH` | `/api/admin/surveys/{id}/status` | Update status (`draft`, `live`, `closed`) |
| `POST` | `/api/admin/surveys/{id}/links` | Generate unique respondent or test links |
| `POST` | `/api/admin/surveys/{id}/clone` | Clone survey into a new wave |
| `GET` | `/api/admin/surveys/{id}/dashboard` | Live counts, quotas, termination reasons, drop-offs |
| `GET` | `/api/admin/surveys/{id}/export` | Download CSV (`?format=csv`) or Excel (`?format=xlsx`) |
| `GET` | `/api/respond/{token}` | Fetch current question / resume / end screen |
| `POST` | `/api/respond/{token}/answer` | Auto-save answer, run logic & quotas, return next question |
| `POST` | `/api/respond/{token}/back` | Navigate back while preserving saved answers |

### Sample Request & Response (`POST /api/respond/{token}/answer`)

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

---

## 8. Assumptions and Decisions

1. **In-Progress Responses When a New Version (v2) Is Approved:**
   - Each respondent session is pinned to the `version_id` they started on. If v2 is approved while a respondent is halfway through v1, they finish against v1's schema so their answers never break or mismatch. New links use v2, and the export includes a `Version` column (`v1`, `v2`).
2. **In-Progress Responses When a Survey Closes (Target or Deadline Reached):**
   - If the survey's total target or a demographic quota fills up while a respondent is mid-survey, the final submission check catches it before marking complete and routes them to the `Survey Closed` or `Not Eligible` screen. Their partial answers stay in the database for drop-off analysis but are not counted as completes or exported.
3. **Boolean Precedence in `show-if`:**
   - `AND` binds tighter than `OR`, matching standard boolean evaluation.
4. **Deterministic Option Shuffling:**
   - Options are shuffled using a seed derived from `respondent_id + question_id` so refreshing the page or clicking Back keeps the exact same order for that respondent.

---

## 9. Known Issues and Next Steps

- **Known Issues / Limitations:**
  - The Admin Studio has no login/auth screen in local demo mode.
  - Export merges columns across versions using the latest version's question order; if two versions reuse the same `question_id` with completely different text, the latest version's header is used.
- **Next Steps:**
  - Add JWT authentication for Researcher vs Viewer roles.
  - Implement nested composite quotas (`Mumbai + Male = 25`), AB/BA balanced rotation, and bilingual question rendering.
  - Add Alembic migrations and PostgreSQL configuration for production deployment.
