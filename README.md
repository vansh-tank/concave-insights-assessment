# Custom Survey System

An in-house survey platform built for Concave Insights to replace manual survey creation with a file-driven workflow. Researchers upload plain-text questionnaire files (`.txt`), which the system parses, validates, and renders into mobile-first surveys with dynamic skip logic, piping, quotas, and clean data exports.

---

## Tech Stack

- **Backend:** Python (FastAPI), SQLAlchemy, Pydantic, OpenPyXL
- **Database:** SQLite (local development) / PostgreSQL compatible
- **Frontend:** React, Tailwind CSS *(in progress)*

---

## Quick Start (Backend)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Load sample survey & demo respondent links
python seed_demo.py

# Run API server
uvicorn app.main:app --reload --port 8000
```

- **Swagger API Docs:** `http://localhost:8000/docs`
- **Backend & API Reference:** [`backend/README.md`](./backend/README.md)

### Run Tests

```bash
cd backend
.venv/bin/pytest -v
```

---

## Design Documentation

Completed under [`/design`](./design):
- [User Flow Diagram & Documentation](./design/user_flow.md)
- [Database Schema & ER Diagram](./design/schema.md)

---

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── database.py            # SQLAlchemy engine & session setup
│   │   ├── models.py              # Relational DB models
│   │   ├── schemas.py             # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── admin.py           # Upload, approve, links, dashboard, export APIs
│   │   │   └── respondent.py      # Survey taking, auto-save, resume, back APIs
│   │   └── services/
│   │       ├── dsl_parser.py      # Questionnaire DSL parser & line-number validator
│   │       ├── logic_engine.py    # Show-if, skip-to, piping, shuffle, quotas, flags
│   │       └── export_service.py  # Standardized CSV & Excel export
│   ├── tests/
│   │   └── test_api.py            # End-to-end API & logic tests
│   ├── seed_demo.py               # Demo data seeder
│   ├── requirements.txt
│   └── README.md                  # Detailed API documentation
├── design/                        # Day 2 design artifacts
├── concave_sample_questionnaire.txt
├── concave_broken_questionnaire.txt
└── README.md
```
