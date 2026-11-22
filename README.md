<div align="center">

# SkillVar

### Evidence-Based Career Intelligence

**Turn skills into career opportunities.**

Analyze resumes, evaluate skills, identify gaps, and discover what to learn next.

[Features](#features) · [Tech Stack](#tech-stack) · [Setup](#local-setup) · [Architecture](#architecture)

</div>

---

## Overview

SkillVar is a Django-powered career intelligence platform that helps users understand their career readiness through resume analysis, skill assessments, job requirement analysis, and explainable job matching.

It distinguishes between self-reported skills, resume evidence, and assessed abilities to provide more transparent skill-gap insights and personalized learning roadmaps.

**SkillVar is a career decision-support tool, not a hiring predictor or ATS scoring system.**

## Features

| Feature | Description |
|---|---|
| Resume Analysis | Upload PDF/DOCX resumes and extract relevant skills. |
| Job Analysis | Identify required skills, experience, and qualifications from job descriptions. |
| Skill Matching | Compare candidate evidence against job requirements with explainable scores. |
| Skill Assessments | Evaluate knowledge through MCQs and SQL challenges. |
| Skill Gap Analysis | Identify missing and underdeveloped skills. |
| Learning Roadmaps | Generate structured learning tasks with progress tracking. |
| Data Ingestion | Import and validate job data from CSV and JSON. |
| Dashboard & API | Track career readiness and access authenticated JSON endpoints. |

## Tech Stack

- **Backend:** Python 3.11, Django 5.2, Django REST Framework
- **Database:** PostgreSQL, Psycopg 3
- **Frontend:** Django Templates, HTML, CSS, JavaScript, Bootstrap 5.3
- **Data Processing:** pandas, NumPy
- **Document Processing:** pypdf, python-docx
- **Authentication:** Django Auth, django-allauth, django-axes
- **Deployment:** Gunicorn, WhiteNoise
- **Testing & Quality:** pytest, pytest-django, Ruff, GitHub Actions

Bootstrap and Chart.js are included locally; no Node.js build step or CDN is required.

## Architecture

```text
                 Browser
                    |
                    v
          Django Templates / API
                    |
                    v
              Django Apps
                    |
       +------------+-------------+
       |            |             |
   Resume &      Evidence &     Job Analysis
   Skill Engine  Assessments    & Matching
       |            |             |
       +------------+-------------+
                    |
             Learning Roadmaps
                    |
                    v
                PostgreSQL
```

The application follows a modular Django architecture:

- `accounts` — authentication and user profiles
- `skills` — skill taxonomy and normalization
- `resumes` — resume upload and analysis
- `jobs` — job requirement extraction
- `evidence` — skill evidence management
- `assessments` — MCQs and SQL evaluations
- `matching` — explainable matching and readiness
- `roadmaps` — personalized learning plans
- `dataops` — job data ingestion and validation
- `web` — dashboard and API

## How Matching Works

SkillVar uses a rule-based evidence scoring engine.

- **Assessed skills:** Evidence from completed assessments.
- **Contextual evidence:** Skills identified in resume projects or experience.
- **Self-reported skills:** Unverified skills declared by users.
- **Missing skills:** Requirements without supporting evidence.

Expected and conservative scores help distinguish claimed skills from stronger evidence. Matching weights are configurable product heuristics, not empirically validated hiring predictors.

See `docs/MATCHING.md`.

## Local Setup

### Requirements
- Python 3.11
- PostgreSQL 16+
- Git

### 1. Clone the repository

```bash
git clone https://github.com/chauhan-prachi/SkillVar-Career-Intelligence-Platform.git
cd SkillVar-Career-Intelligence-Platform
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4. Configure environment

```powershell
Copy-Item .env.example .env
```

Configure your PostgreSQL connection and a unique `SECRET_KEY` in `.env`.

### 5. Initialize the application

Create a PostgreSQL database, then run:

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py seed_data
python manage.py runserver
```

Open **http://127.0.0.1:8000/**.

## Tests & Quality Checks

Run the following commands:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
ruff check .
```

The project includes GitHub Actions CI with PostgreSQL-backed checks.

A recorded verification snapshot reports 327 passing tests, clean Ruff checks, and no pending migrations. See `docs/VERIFICATION.md` for environment details.

## API

Authenticated, read-only endpoints:

| Method | Endpoint |
|---|---|
| GET | `/api/v1/skills/` |
| GET | `/api/v1/me/skills/` |
| GET | `/api/v1/me/readiness/` |
| GET | `/api/v1/me/matches/` |
| GET | `/healthz/` |

## Security & Limitations

- Resume uploads are private and size-limited.
- User-owned data is scoped to authenticated accounts.
- Resume and job-description processing is local; no external AI API is configured.
- Resume extraction is rule-based and does not currently support OCR.
- Matching scores are heuristic estimates, not hiring predictions.
- Sample job postings are synthetic, not live vacancies.
- The SQL assessment sandbox has not undergone an independent security audit.
- Production deployment requires additional review, persistent private file storage, and production configuration.

## Documentation

Explore the `docs/` directory for:

- Architecture and database design
- Matching methodology
- Security considerations
- Windows installation and troubleshooting
- Deployment and Google OAuth configuration
- Verification and release checklist

---

<div align="center">

**SkillVar — Understand your skills. Identify your gaps. Build your next opportunity.**

</div>