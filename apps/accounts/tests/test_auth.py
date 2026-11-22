import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import Profile

PW = "a-long-strong-pass-9"
PROTECTED = ["/dashboard/", "/accounts/onboarding/", "/accounts/onboarding/skills/", "/accounts/account/", "/resumes/", "/resumes/upload/",
             "/jobs/", "/jobs/analyze/", "/jobs/samples/", "/matches/", "/readiness/", "/skills/", "/assessments/", "/assessments/history/",
             "/assessments/python-fundamentals/", "/roadmap/", "/api/v1/me/skills/", "/api/v1/me/readiness/", "/api/v1/me/matches/"]


def register(client, **kw):
    data = {"username": "newbie", "email": "newbie@example.com", "password1": PW, "password2": PW, **kw}
    return client.post("/accounts/register/", data)


@pytest.mark.django_db
@pytest.mark.parametrize("url", PROTECTED)
def test_protected_pages_require_login(client, url):
    r = client.get(url)
    assert r.status_code in (302, 403)
    if r.status_code == 302:
        assert "/accounts/login/" in r.url


@pytest.mark.django_db
def test_registration_creates_user_profile_and_logs_in(client):
    r = register(client)
    assert r.status_code == 302 and r.url == "/accounts/onboarding/"
    from django.contrib.auth import get_user_model
    u = get_user_model().objects.get(username="newbie")
    assert Profile.objects.filter(user=u).exists() and u.password.startswith(("pbkdf2_", "argon2", "bcrypt"))
    assert client.get("/dashboard/").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("pw,expected", [("short1A!", "too short"), ("password1234", "too common"), ("48392017265", "entirely numeric")])
def test_password_validators_are_enforced(client, pw, expected):
    r = register(client, password1=pw, password2=pw)
    assert r.status_code == 200 and expected in r.content.decode().lower()


@pytest.mark.django_db
def test_password_similar_to_username_is_rejected(client):
    r = register(client, username="prachigupta", password1="prachigupta", password2="prachigupta")
    assert r.status_code == 200 and "too similar" in r.content.decode().lower() or "too common" in r.content.decode().lower()


@pytest.mark.django_db
def test_duplicate_email_is_rejected_case_insensitively(client, user):
    r = register(client, username="other", email="ANA@Example.com")
    assert r.status_code == 200 and "already exists" in r.content.decode()


@pytest.mark.django_db
def test_database_enforces_unique_email_case_insensitively(user, django_user_model):
    from django.db import IntegrityError, transaction
    with pytest.raises(IntegrityError), transaction.atomic():
        django_user_model.objects.create_user("dup", email="ANA@EXAMPLE.COM", password=PW)


@pytest.mark.django_db
def test_passwordmismatch_and_missing_fields_show_errors(client):
    r = register(client, password2="different-password-1")
    assert r.status_code == 200 and "didn’t match" in r.content.decode() or "didn't match" in r.content.decode()
    assert register(client, email="").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("ident", ["ana", "ANA", "ana@example.com", "Ana@Example.com"])
def test_login_with_username_or_email_any_case(client, user, ident):
    r = client.post("/accounts/login/", {"username": ident, "password": PW})
    assert r.status_code == 302 and r.url == "/dashboard/"


@pytest.mark.django_db
def test_wrong_password_shows_error_and_does_not_log_in(client, user):
    r = client.post("/accounts/login/", {"username": "ana", "password": "nope"})
    assert r.status_code == 200 and client.get("/dashboard/").status_code == 302


@pytest.mark.django_db
def test_logout_requires_post_and_ends_session(auth_client):
    assert auth_client.get("/accounts/logout/").status_code == 405
    assert auth_client.post("/accounts/logout/").status_code == 302
    assert auth_client.get("/dashboard/").status_code == 302


@pytest.mark.django_db
def test_login_lockout_after_repeated_failures(client, user, settings):
    for _ in range(settings.AXES_FAILURE_LIMIT):
        client.post("/accounts/login/", {"username": "ana", "password": "wrong"})
    locked = client.post("/accounts/login/", {"username": "ana", "password": PW})
    assert locked.status_code == 429 and "Too many failed" in locked.content.decode()
    assert client.get("/dashboard/").status_code == 302      # the correct password did not get in either


@pytest.mark.django_db
def test_lockout_is_per_username_and_ip_not_global(client, user, other_user, settings):
    for _ in range(settings.AXES_FAILURE_LIMIT):
        client.post("/accounts/login/", {"username": "ana", "password": "wrong"})
    assert client.post("/accounts/login/", {"username": "bob", "password": PW}).status_code == 302


@pytest.mark.django_db
def test_csrf_is_enforced():
    from django.test import Client
    c = Client(enforce_csrf_checks=True)
    assert c.post("/accounts/register/", {"username": "x", "email": "x@x.io", "password1": PW, "password2": PW}).status_code == 403


@pytest.mark.django_db
def test_password_reset_flow(client, user):
    r = client.post("/accounts/password-reset/", {"email": "ana@example.com"})
    assert r.status_code == 302 and len(mail.outbox) == 1
    link = next(ln for ln in mail.outbox[0].body.splitlines() if "/accounts/reset/" in ln).split("testserver")[-1].strip()
    page = client.get(link, follow=True)
    assert page.status_code == 200
    r = client.post(page.request["PATH_INFO"], {"new_password1": "another-strong-pass-77", "new_password2": "another-strong-pass-77"})
    assert r.status_code == 302
    assert client.post("/accounts/login/", {"username": "ana", "password": "another-strong-pass-77"}).status_code == 302


@pytest.mark.django_db
def test_password_reset_does_not_reveal_whether_an_email_exists(client, user):
    r1 = client.post("/accounts/password-reset/", {"email": "nobody@example.com"})
    assert r1.status_code == 302 and r1.url == reverse("password_reset_done") and len(mail.outbox) == 0


@pytest.mark.django_db
def test_google_button_hidden_without_credentials(client):
    assert "Continue with Google" not in client.get("/accounts/login/").content.decode()


@pytest.mark.django_db
def test_google_button_shown_and_flow_starts_when_configured(client, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET = "test-client-id", "test-secret"
    settings.SOCIALACCOUNT_PROVIDERS = {"google": {"SCOPE": ["profile", "email"],
                                                   "APP": {"client_id": "test-client-id", "secret": "test-secret", "key": ""}}}
    assert "Continue with Google" in client.get("/accounts/login/").content.decode()
    r = client.post("/auth/google/login/", {"process": "login"})
    assert r.status_code == 302 and "accounts.google.com" in r.url and "client_id=test-client-id" in r.url


@pytest.mark.django_db
def test_google_login_cannot_start_with_a_get_request(client, settings):
    settings.SOCIALACCOUNT_PROVIDERS = {"google": {"APP": {"client_id": "x", "secret": "y", "key": ""}}}
    r = client.get("/auth/google/login/")
    assert r.status_code == 200      # shows a confirmation page; no redirect to Google without a CSRF-protected POST


@pytest.mark.django_db
def test_allauth_local_pages_redirect_to_skillvar_pages(client):
    assert client.get("/auth/login/").url == "/accounts/login/"
    assert client.get("/auth/signup/").url == "/accounts/register/"


@pytest.mark.django_db
def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
