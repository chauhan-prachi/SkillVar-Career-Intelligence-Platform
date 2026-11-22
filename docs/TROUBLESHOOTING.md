# Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `connection refused` / `could not connect to server` | PostgreSQL is not running | Windows: `Get-Service *postgres*`, then `Start-Service <name>`. Linux: `pg_ctlcluster 16 main start`. |
| `password authentication failed for user "skillvar_app"` | Wrong password in `DATABASE_URL` | Fix `.env`; URL-encode special characters; or `ALTER ROLE skillvar_app PASSWORD '...'`. |
| `database "skillvar" does not exist` | Step 4 not done | Run the `CREATE DATABASE` command. |
| `permission denied to create database` when running tests | Role lacks `CREATEDB` | `ALTER ROLE skillvar_app CREATEDB;` as the postgres user. |
| `ImproperlyConfigured: DATABASE_URL is not set` | No `.env`, or run from the wrong folder | `Copy-Item .env.example .env`, run commands from the folder containing `manage.py`. |
| `SECRET_KEY is not set` / `...at least 32 characters` | Missing or weak key with `DEBUG=0` | Generate with `python -c "import secrets; print(secrets.token_urlsafe(60))"`. |
| `relation "skillvar_cache" does not exist` | Cache table missing | `python manage.py createcachetable`. |
| Pages are empty / no assessments | Seed data not loaded | `python manage.py seed_data`. |
| `Error loading psycopg module` | Dependencies not installed in the active venv | Activate `.venv`, `pip install -r requirements.txt`. |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | PowerShell execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. |
| CSS missing in production (`DEBUG=0`) | Static files not collected | `python manage.py collectstatic --noinput`. |
| Resume upload says "Very little text" | Scanned/image PDF | Export a text-based PDF or use DOCX. OCR is not supported. |
| 429 "Too many failed sign-in attempts" | django-axes lockout (5 failures, 15 minutes) | Wait, or in dev: `python manage.py axes_reset`. |
| 429 "Too many requests" on uploads/analysis | Built-in rate limit | Wait for the window to pass (1 hour limits). |
| `makemigrations --check` fails | A model changed without a migration | `python manage.py makemigrations` and commit the new file. |
