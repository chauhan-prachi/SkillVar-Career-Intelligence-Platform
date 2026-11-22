# Security and privacy notes

Treat resumes, assessment results and career profiles as private data.

## Implemented and tested
* **Authentication**: Django password hashing; four password validators; login by username or email; lockout after 5 failed
  attempts per (IP, username) for 15 minutes (django-axes); CSRF on all forms; logout is POST-only; session and CSRF
  cookies are `Secure` when `DEBUG=0`; `X-Frame-Options: DENY`, `nosniff`, same-origin referrer policy.
* **Authorization**: every user-owned object is fetched with the requesting user in the query; other users' ids return 404;
  tested for resumes, jobs, matches, attempts, roadmap items and the API.
* **Secrets**: only from environment/`.env`; `.env` is git-ignored; with `DEBUG=0` the app refuses to start with a
  missing, short or placeholder `SECRET_KEY`; a missing `DATABASE_URL` is a clear startup error.
* **Uploads**: size limit; extension and *content signature* checked (PDF header / DOCX package structure) and they must
  agree; parsed, never executed or rendered; encrypted PDFs, page bombs and zip bombs rejected; server-chosen filenames;
  stored outside static/media routes with a storage class that refuses to produce URLs; downloads only through an
  ownership-checked view; per-user rate limit (10 uploads/hour). Duplicate files are rejected by SHA-256.
* **Deletion**: deleting a resume removes the stored file, extracted text and derived skills. Deleting a job analysis removes its
  requirements and matches.
* **SQL assessments**: learner SQL runs in a throw-away in-memory SQLite database (never the application database) with
  a read-only authorizer (SELECT only), a single statement, a 1 s deadline, a 1,000-row cap, SQLite hard limits on value
  size, SQL length, expression depth, compound selects and function arguments, and a 5,000-character answer cap. This is
  defense in depth for *SQLite-dialect teaching queries*; it has had no independent security review and runs in-process.
* **Python code** submitted by learners is never executed (Python topics are multiple choice).
* **Logging**: only identifiers and counts; never resume text, passwords or tokens.
* **Output**: Django auto-escaping; user text (job titles, filenames, extracted text) is escaped (tested).

## Not implemented / known limits
* No email verification, no two-factor authentication, no account self-deletion page (contact the administrator).
* No malware scanning of uploads; relies on parse-only handling and signature checks.
* The cache-based rate limiter uses the database cache (shared across workers). Behind a proxy, configure
  `BEHIND_PROXY` and the client IP headers for django-axes (`AXES_IPWARE_PROXY_COUNT`) or lockout will key on the proxy IP.
* HSTS and HTTPS redirect are off by default and must be enabled with `SECURE_HSTS_SECONDS` and `SECURE_SSL_REDIRECT`
  once HTTPS works (`manage.py check --deploy` reports both until you do).
* Backups: resumes live in `PRIVATE_MEDIA_ROOT` on the server's disk and the text in PostgreSQL; deleting a resume does not
  purge copies already captured in your own backups.
* The SQL sandbox should move to a separate low-privilege worker before exposing the app to untrusted users at scale.
* External AI is **not** used anywhere: no resume or job text leaves the server.
