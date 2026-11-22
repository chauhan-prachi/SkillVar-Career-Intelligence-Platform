# Deployment checklist

> **Not deployed or verified on any hosting provider.** `Procfile` and `build.sh` are provided for Linux hosts such as
> Render or Railway but have not been run on one. Nothing in this repository changes DNS or creates paid services.

## Verified locally (Linux, Python 3.11, PostgreSQL 16)
* `DEBUG=0` + strong `SECRET_KEY`: static files served by WhiteNoise after `collectstatic`, custom 404, security headers,
  `/healthz/` returns `{"status":"ok","database":"postgresql"}`.
* `manage.py check --deploy`: only HSTS and SSL-redirect warnings, which depend on your HTTPS setup.

## Steps
1. Create a managed PostgreSQL database; copy its connection string to `DATABASE_URL` (add `?sslmode=require` if the provider requires it).
2. Set environment variables on the host: `DEBUG=0`, `SECRET_KEY` (>= 32 random characters), `ALLOWED_HOSTS=your-domain`,
   `CSRF_TRUSTED_ORIGINS=https://your-domain`, `DATABASE_URL`, `CACHE_URL=dbcache://skillvar_cache`, `EMAIL_URL` (SMTP, for password
   reset, for example `smtp+tls://user:pass@smtp.example.com:587`), `DEFAULT_FROM_EMAIL`, `BEHIND_PROXY=1`, and later
   `SECURE_SSL_REDIRECT=1` and `SECURE_HSTS_SECONDS=31536000` once HTTPS works.
3. Build command: `./build.sh`. Start command: `gunicorn config.wsgi:application`. Health check path: `/healthz/`.
4. **Uploads need persistent storage.** Resumes are written to `PRIVATE_MEDIA_ROOT` (default `./private_media`). Hosts with an
   ephemeral disk will lose them on redeploy: mount a persistent volume and point `PRIVATE_MEDIA_ROOT` at it (object
   storage is future work).
5. Google sign-in: add the production redirect URI (see `docs/GOOGLE_OAUTH.md`).
6. Create an admin: `python manage.py createsuperuser`. Optionally load synthetic jobs (`generate_synthetic_jobs`, `ingest_jobs`).
7. Take regular PostgreSQL backups and back up the private media volume.

## Manual-only items (cannot be done by code)
DNS and HTTPS certificate, SMTP provider account, Google Cloud credentials, persistent disk, backups, monitoring.
