# Custom Survey System

An in-house survey platform built for Concave Insights to replace manual survey creation with a file-driven workflow. Researchers upload plain-text questionnaire files (`.txt`), which the system parses, validates, and renders into mobile-first surveys with dynamic skip logic, piping, quotas, and clean data exports.

---

## Tech Stack

- **Backend:** Python (FastAPI), SQLAlchemy, Pydantic
- **Database:** SQLite (local development) / PostgreSQL compatible
- **Frontend:** React, Tailwind CSS

---

## Project Status

- **Day 2 Milestone:** Design documentation completed under [`/design`](./design).
  - [User Flow Diagram & Documentation](./design/user_flow.md)
  - [Database Schema & ER Diagram](./design/schema.md)

---

## Repository Structure

```
.
├── design/
│   ├── README.md              # Design overview
│   ├── user_flow.md           # Admin and respondent flows
│   ├── user_flow.png          # Flowchart image
│   ├── schema.md              # Database tables and relationships
│   └── database_diagram.png   # ER diagram image
├── concave_sample_questionnaire.txt  # Sample valid questionnaire
├── concave_broken_questionnaire.txt  # Sample broken questionnaire for testing
└── README.md
```
