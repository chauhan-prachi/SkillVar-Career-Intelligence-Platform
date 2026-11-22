# Optional Google sign-in

SkillVar works fully without Google. If `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` are empty the button is
hidden. Implemented with django-allauth (only its Google provider; sign-up/login pages stay SkillVar's own).

**Verification status:** the *code path* is tested (button visibility, a CSRF-protected POST redirecting to
accounts.google.com with the configured client id, GET not starting a login, allauth's own login/sign-up pages redirecting
to SkillVar's). **A real Google sign-in has not been performed**, because that needs your credentials.

## Setup
1. Open Google Cloud Console, create or choose a project, then APIs & Services -> OAuth consent screen: choose External,
   set the app name, support email and scopes `openid`, `email`, `profile`.
2. Credentials -> Create credentials -> OAuth client ID -> *Web application*.
3. Authorized redirect URIs (exact match):
   * local: `http://127.0.0.1:8000/auth/google/login/callback/` and `http://localhost:8000/auth/google/login/callback/`
   * production: `https://YOUR-DOMAIN/auth/google/login/callback/`
4. Put the values in `.env` (never in source control):
   ```
   GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```
5. Restart the server; "Continue with Google" appears on the login and register pages.

## Account-linking behaviour
`SOCIALACCOUNT_EMAIL_AUTHENTICATION` is off: a Google login is **not** automatically attached to an existing local account
with the same email (that would let anyone who controls a matching Google address take over the account). Because email
addresses are unique, such a Google sign-up is refused by allauth; the person should log in locally. A verified linking
flow (log in, then connect Google from the account page) is future work. Email verification for local accounts is also
not implemented.
