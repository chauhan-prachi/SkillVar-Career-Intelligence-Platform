# SkillVar local setup for Windows PowerShell. Run from the project folder. Nothing destructive.
# NOTE: written for Windows but only verified logic-wise; see docs/INSTALL_WINDOWS.md for the manual steps.
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) { & py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Edit DATABASE_URL and SECRET_KEY before continuing." -ForegroundColor Yellow
}
Write-Host "Next: create the PostgreSQL database (docs/INSTALL_WINDOWS.md step 4), then run:"
Write-Host "  .\.venv\Scripts\python.exe manage.py migrate"
Write-Host "  .\.venv\Scripts\python.exe manage.py createcachetable"
Write-Host "  .\.venv\Scripts\python.exe manage.py seed_data"
Write-Host "  .\.venv\Scripts\python.exe manage.py runserver"
