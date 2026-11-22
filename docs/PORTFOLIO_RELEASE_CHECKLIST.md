# GitHub release checklist

## Before the first public push

- [ ] Create a new, empty GitHub repository named `SkillVar` (or your chosen name).
- [ ] Review the repository for credentials, `.env` files, private resumes, database dumps, and personal data.
- [ ] Keep `.env.example`; create your own local `.env` from it. Never commit `.env`.
- [ ] Run the project locally with PostgreSQL and confirm the main user flows.
- [ ] Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `pytest`, and `ruff check .`.
- [ ] Add real screenshots of the landing page, dashboard, resume analysis, and match analysis to `docs/screenshots/`.
- [ ] Update the README if the screenshots, deployment, or verified test results change.
- [ ] Confirm the repository visibility and license are what you intend.

## First push (PowerShell)

Run these commands from the project root after creating the empty GitHub repository:

```powershell
git init
git branch -M main
git add .
git status
git commit -m "Prepare SkillVar for GitHub"
git remote add origin https://github.com/YOUR_USERNAME/SkillVar.git
git push -u origin main
```

Review `git status` before committing. It must not list `.env`, `.venv`, `private_media`, uploaded resumes, or database files.

## After publishing

- [ ] Open the GitHub Actions tab and confirm the CI workflow passes.
- [ ] Add a short repository description and topics such as `django`, `python`, `postgresql`, `career-platform`, and `data-processing`.
- [ ] Pin the repository on your GitHub profile.
- [ ] Add a demo URL only after deployment and end-to-end testing.
