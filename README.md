<div align="center">

# SkillVar

### Evidence-based career intelligence

Understand your skills, compare them with job requirements, and identify what to improve next.

[Features](#features) · [Tech stack](#technology-stack) · [Setup](#local-setup) · [Architecture](#how-it-works) · [Limitations](#known-limitations)

</div>

---

## Overview

SkillVar is a Django web application that helps users evaluate their skills against target roles. It brings resume analysis, skill assessments, job-description analysis, explainable matching, and learning roadmaps into one workflow.

Its central idea is simple: **a skill claim, a resume mention, and an assessment result are different kinds of evidence.** SkillVar keeps those signals separate and explains how they contribute to a match estimate.

SkillVar is a decision-support and learning tool. It does not predict hiring outcomes, provide an ATS score, or automatically reject candidates.

## Features

| Feature | What it does |
|---|---|
| Resume analysis | Accepts PDF and DOCX files, extracts text, detects skills, and lets users review the results. |
| Job analysis | Extracts required and preferred skills, experience, education, tools, and responsibilities from a job description. |
| Explainable matching | Compares job requirements with user evidence and shows expected score, conservative score, evidence coverage, and per-skill credit. |
| Skill assessments | Offers multiple-choice and executed-SQL tasks with feedback and attempt history. |
| Readiness | Summarizes evidence against a selected target role. |
| Learning roadmaps | Creates prerequisite-aware learning tasks with progress and completion criteria. |
| Data ingestion | Imports CSV and JSON job records, validates them, and tracks rejected rows and pipeline runs. |
| Dashboard and API | Displays user progress and exposes authenticated, read-only JSON endpoints. |

## Technology stack

| Layer | Technologies |
|---|---|
| Language | Python 3.11 |
| Backend | Django 5.2, Django REST Framework |
| Database | PostgreSQL 16+, Psycopg 3 |
| Frontend | Django Templates, HTML, CSS, JavaScript, Bootstrap 5.3 |
| Charts | Chart.js 4 |
| Data processing | pandas, NumPy |
| Document parsing | pypdf, python-docx |
| Authentication | Django authentication, django-allauth (optional Google sign-in), django-axes |
| Static files / serving | WhiteNoise, Gunicorn |
| Quality | pytest, pytest-django, Ruff, GitHub Actions |

Bootstrap and Chart.js are vendored in `static/vendor/`; the application does not require a Node build step or a CDN for these libraries.

**Privacy note:** the current implementation does not send resume or job-description text to an external AI service.

## How it works

1. **Build a profile** — select a target role and add skills you want to track.
2. **Upload a resume** — SkillVar extracts text and identifies taxonomy skills for user review.
3. **Analyze a job** — extract the role's required and preferred skills from a job description.
4. **Compare evidence** — the matching engine assigns different credit to assessed, contextual, and self-reported evidence.
5. **Improve** — use assessments and the learning roadmap to address skill gaps.

### Matching model

The matching engine is implemented as pure Python scoring logic in `apps/matching/scoring.py`. It distinguishes:

- **Assessment evidence:** evaluated performance contributes to expected and conservative values.
- **Contextual resume evidence:** a skill appearing in a project or experience section receives partial expected credit.
- **Self-reported or resume-listed evidence:** treated as an unverified claim and receives lower expected credit.
- **No evidence:** receives no skill credit.

The overall score combines applicable components (required skills, preferred skills, and experience) using configured starting weights. If a component is unavailable, the remaining weights are renormalized. The conservative score excludes unverified evidence.

These weights are product heuristics, not empirically calibrated hiring predictors. See [`docs/MATCHING.md`](docs/MATCHING.md).

## Architecture

```text
Browser
  |
  v
Django templates + Bootstrap + JavaScript
  |
  v
Django views / forms / REST endpoints
  |
  +--> Resume extraction and skill analysis
  +--> Job-description analysis
  +--> Evidence profile and assessment engine
  +--> Explainable matching and readiness
  +--> Learning roadmap services
  +--> CSV / JSON ingestion pipeline
  |
  v
PostgreSQL
```

The code is organized by Django app under `apps/`:

- `accounts` — user accounts, onboarding, profile and authentication
- `skills` — skill taxonomy, normalization and role data
- `resumes` — upload, extraction, review and analysis
- `jobs` — job-description analysis and requirements
- `evidence` — evidence profile and assessment engine
- `assessments` — question bank, attempts and SQL task evaluation
- `matching` — match scoring and readiness
- `roadmaps` — learning plans and progress
- `dataops` — ingestion, validation and pipeline history
- `web` — dashboard, templates and read-only API

## Local setup

### Requirements

- Python 3.11
- PostgreSQL 16 or newer
- Git
- Windows, macOS, or Linux (the verification report currently covers Linux)

### 1. Get the project

```bash
git clone <your-repository-url>
cd SkillVar
```

### 2. Create and activate a virtual environment

**Windows PowerShell**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

On Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a unique `SECRET_KEY` and your local PostgreSQL connection in `DATABASE_URL`. Generate a key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(60))"
```

Never commit `.env`, credentials, private resume files, or production data.

### 5. Create the database

Example PostgreSQL commands (change the password before use):

```sql
CREATE ROLE skillvar_app LOGIN PASSWORD 'choose-a-strong-password' CREATEDB;
CREATE DATABASE skillvar OWNER skillvar_app;
```

Set `DATABASE_URL` in `.env`, for example:

```text
postgres://skillvar_app:your-password@localhost:5432/skillvar
```

### 6. Initialize and run

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py seed_data
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

Optional: create an administrator account with `python manage.py createsuperuser`.

For detailed Windows instructions and troubleshooting, see [`docs/INSTALL_WINDOWS.md`](docs/INSTALL_WINDOWS.md) and [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Tests and code quality

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
ruff check .
```

The repository includes a GitHub Actions workflow that runs checks against PostgreSQL 16 on pushes and pull requests.

A verification report recorded **327 passing tests**, clean Ruff checks, a clean Django system check, and no pending migrations on Linux with Python 3.11 / Django 5.2 / PostgreSQL 16. This is a dated verification snapshot, not a guarantee that every future change or Windows environment has been tested. See [`docs/VERIFICATION.md`](docs/VERIFICATION.md).

## API

Authenticated, read-only endpoints are available:

- `GET /api/v1/skills/`
- `GET /api/v1/me/skills/`
- `GET /api/v1/me/readiness/`
- `GET /api/v1/me/matches/`
- `GET /healthz/` — database health check

The API uses session authentication and requires a signed-in user for user-specific endpoints.

## Security and privacy

- Resume uploads are private and size-limited.
- User-owned records are scoped to the authenticated account.
- CSRF protection, login throttling/lockout, and upload rate limits are configured.
- Resume and job text are processed locally by the application; no external AI API is configured.
- The SQL assessment sandbox runs in-process and has not received an independent security audit. Do not expose it to untrusted public traffic without additional isolation and review.

Read [`docs/SECURITY.md`](docs/SECURITY.md) before deploying.

## Known limitations

- Resume parsing is rule-based; scanned PDFs/OCR, deep context, and negation handling are not supported.
- Skill taxonomy, role definitions, and assessment coverage are limited and need further validation.
- Matching weights are starting heuristics, not calibrated predictors.
- Sample job postings are synthetic and are not live vacancies.
- A real Google OAuth configuration and production email delivery require external credentials and setup.
- The SQL sandbox has not been independently security-reviewed.
- The verification report covers Linux; Windows and a production hosting environment still need end-to-end validation.
- Resume files use local filesystem storage by default; production deployments need persistent/private object storage.

## Project documentation

- [Windows installation](docs/INSTALL_WINDOWS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database design](docs/DATABASE.md)
- [Matching model](docs/MATCHING.md)
- [Security](docs/SECURITY.md)
- [Google OAuth](docs/GOOGLE_OAUTH.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Verification report](docs/VERIFICATION.md)
- [GitHub release checklist](docs/PORTFOLIO_RELEASE_CHECKLIST.md)

## License and attribution

See [`LICENSE`](LICENSE). Bootstrap and Chart.js are included under their respective vendor license files in `static/vendor/`.

This project was developed with AI assistance. See the repository history and documentation for project provenance.
