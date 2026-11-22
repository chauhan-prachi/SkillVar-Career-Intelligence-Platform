# Installing SkillVar on Windows (PowerShell + VS Code)

> These steps were written for Windows 10/11 and Python 3.11. SkillVar itself was built and tested on Linux with
> Python 3.11 and PostgreSQL 16; **the Windows commands below have not been run on a Windows machine by the author.**
> If a step fails, see `docs/TROUBLESHOOTING.md`.

## 1. What you need
Python 3.11 (python.org, tick "Add python.exe to PATH"), Git, VS Code, and PostgreSQL 16 or newer.

## 2. Get the code and open it
```powershell
cd C:\Users\YourUser\Projects\SkillVar      # or wherever you extracted the zip
code .                                    # opens VS Code here
```

## 3. Create a virtual environment and install dependencies
A *virtual environment* is a private folder of Python packages for this project only, so SkillVar's exact versions never
clash with other projects.
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1              # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python --version                          # should say 3.11.x
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip check                                 # expect: No broken requirements found.
```
(`scripts\setup_windows.ps1` does the same steps for you.)

## 4. Install PostgreSQL and create the database
Download the Windows installer from postgresql.org/download/windows, keep port 5432, and remember the `postgres`
superuser password you choose. Then (adjust `16` to your version):
```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE ROLE skillvar_app LOGIN PASSWORD 'choose-a-password' CREATEDB;"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE skillvar OWNER skillvar_app;"
```
`CREATEDB` lets Django create its temporary `test_skillvar` database when you run tests. Check the service is running:
```powershell
Get-Service | Where-Object { $_.Name -like "*postgres*" }     # Status should be Running
```

## 5. Configure `.env`
```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(60))"    # copy the output into SECRET_KEY=
notepad .env
```
Set `DATABASE_URL=postgres://skillvar_app:choose-a-password@localhost:5432/skillvar`. If the password has special
characters (`@ : / # %`), URL-encode them. `.env` is git-ignored: never commit or share it.

## 6. Create the tables and load starter data
```powershell
python manage.py migrate            # creates all tables from the migration files
python manage.py createcachetable   # a small table used for rate limiting
python manage.py seed_data          # skills, roles, assessments, learning resources (safe to re-run)
python manage.py createsuperuser    # optional: for /admin/ and the Data pipeline page
```

## 7. Run it
```powershell
python manage.py runserver
```
Open http://127.0.0.1:8000/ . Password-reset emails print in this terminal in development.

## 8. Optional: load synthetic sample jobs (for the Sample jobs page)
```powershell
python manage.py generate_synthetic_jobs --count 1000 --seed 1 --out data\synthetic_jobs.csv
python manage.py ingest_jobs data\synthetic_jobs.csv --dataset synthetic-jobs --synthetic
```
These are **synthetic** postings, not real vacancies. Staff users can inspect runs at `/data/`.

## 9. Test everything
```powershell
pytest                                                  # about 330 tests, a few minutes
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py runserver                              # terminal 1
python scripts\smoke_test.py http://127.0.0.1:8000      # terminal 2: live end-to-end test (use a new --user each run)
```

## 10. Save your work with Git
```powershell
git status                       # .env and private_media/ must NOT be listed
git add .
git commit -m "Describe your change"
```
