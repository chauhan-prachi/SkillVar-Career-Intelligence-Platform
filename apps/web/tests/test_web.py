import os
import subprocess
import sys

import pytest

from apps.assessments import services as assess
from apps.assessments.models import Assessment, Question
from apps.evidence.tests.test_profile import claim
from apps.jobs.services import create_job
from apps.matching import services as matching
from apps.web import ratelimit


def submit(user, slug, correct=True):
    q = Question.objects.get(slug=slug)
    assess.submit_attempt(user, q.assessment, {q.id: str(q.correct_index if correct else (q.correct_index + 1) % 4)})


# ---------- public pages ----------
def test_home_is_public_branded_and_honest(client, db):
    page = client.get("/").content.decode()
    assert "Discover Your Skills." in page and "Prove Your Potential." in page and "Create a free account" in page
    assert "not the probability of getting hired" in page or "not the probability of getting hired" in page.replace("\n", " ")
    for fake in ("users", "testimonial", "% of", "trusted by"):
        assert fake not in page.lower().replace("your users", "")


def test_home_for_authenticated_user_links_to_dashboard(auth_client):
    assert "Open your dashboard" in auth_client.get("/").content.decode()


def test_health_check_reports_the_real_database(client, db):
    r = client.get("/healthz/")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "postgresql"}


def test_custom_404_page(client, db):
    r = client.get("/definitely-not-a-page/")
    assert r.status_code == 404 and "Page not found" in r.content.decode()


def test_media_and_private_files_have_no_public_route(client, db):
    for url in ("/media/resumes/1/a.pdf", "/private_media/resumes/1/a.pdf", "/resumes/1/a.pdf"):
        assert client.get(url).status_code == 404


# ---------- dashboard ----------
def test_new_user_without_goal_sees_onboarding_prompt_and_no_invented_numbers(auth_client):
    page = auth_client.get("/dashboard/").content.decode()
    assert "Let&#x27;s set up your profile" in page or "Let's set up your profile" in page
    assert "No skill evidence yet" in page and "No assessments taken yet" in page and "No matches yet" in page and "You have no roadmap yet" in page


def test_dashboard_for_goal_without_evidence_is_honest(goal_client):
    page = goal_client.get("/dashboard/").content.decode()
    assert "Low evidence" in page and "Recommended next action" in page and "No skill evidence yet" in page
    assert "A trend appears after at least two assessed results" in page


def test_dashboard_numbers_come_from_the_database(goal_client, goal_user):
    before = goal_client.get("/dashboard/").context
    assert before["readiness"].score == 0 and before["evidence_total"] == 0 and before["attempts"] == []
    for slug in ("sql-null", "sql-having"):
        submit(goal_user, slug)
    claim(goal_user, "git", 0.6)
    after = goal_client.get("/dashboard/").context
    assert after["readiness"].score > 0 and after["evidence_total"] >= 2 and len(after["attempts"]) == 2
    assert after["completion"] > before["completion"] or after["completion"] >= before["completion"]
    assert len(after["trend"]["score"]) == 2 and after["trend"]["score"][1] >= 0


def test_trend_chart_only_appears_with_real_history(goal_client, goal_user):
    submit(goal_user, "sql-null")
    assert "id=\"trendChart\"" not in goal_client.get("/dashboard/").content.decode()
    submit(goal_user, "sql-having")
    page = goal_client.get("/dashboard/").content.decode()
    assert "id=\"trendChart\"" in page and "trend-data" in page


def test_dashboard_chart_data_is_valid_json_in_the_page(goal_client, goal_user):
    import json
    import re
    claim(goal_user, "etl", 0.6)
    page = goal_client.get("/dashboard/").content.decode()
    data = json.loads(re.search(r'<script id="evidence-data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert data == {"labels": ["Self-reported"], "values": [1]}


def test_dashboard_shows_gaps_matches_and_roadmap_progress(goal_client, goal_user):
    job = create_job(goal_user, "Job Title: DE\nRequirements:\n- Python\n- SQL\n- Airflow experience is needed")
    matching.match_job(goal_user, job)
    goal_client.post("/roadmap/generate/")
    page = goal_client.get("/dashboard/").content.decode()
    assert "Important skill gaps" in page and "DE" in page and "0 of" in page and "Roadmap progress" in page


def test_dashboard_query_count_is_bounded(goal_client, goal_user, django_assert_max_num_queries):
    for slug in ("sql-null", "sql-having", "py-set-len", "de-idempotent"):
        submit(goal_user, slug)
    create_job(goal_user, "Requirements:\n- Python and SQL and Airflow are all needed for this role")
    with django_assert_max_num_queries(40):          # measured: 32 (was 107 before the N+1 fix)
        assert goal_client.get("/dashboard/").status_code == 200


def test_staff_sees_pipeline_card(client, db, django_user_model):
    staff = django_user_model.objects.create_user("st", email="st@example.com", password="a-long-strong-pass-9", is_staff=True)
    client.force_login(staff)
    assert "Data pipeline (staff)" not in client.get("/dashboard/").content.decode()      # no runs yet
    from apps.dataops.models import Dataset, IngestionRun
    IngestionRun.objects.create(dataset=Dataset.objects.create(slug="d", name="d", kind="jobs"), source_name="x.csv")
    assert "Data pipeline (staff)" in client.get("/dashboard/").content.decode()


# ---------- API ----------
def test_api_requires_authentication(client, db):
    assert client.get("/api/v1/skills/").status_code in (401, 403)


def test_api_skills_and_isolated_user_data(goal_client, goal_user, client, other_user):
    skills = goal_client.get("/api/v1/skills/").json()
    assert len(skills) >= 60 and any("postgres" in s["aliases"] for s in skills if s["slug"] == "postgresql")
    claim(goal_user, "etl", 0.6)
    mine = goal_client.get("/api/v1/me/skills/").json()
    assert [s["slug"] for s in mine] == ["etl"] and mine[0]["evidence"] == "Self-reported"
    client.force_login(other_user)
    assert client.get("/api/v1/me/skills/").json() == []


def test_api_readiness_and_matches(goal_client, goal_user, client, other_user):
    r = goal_client.get("/api/v1/me/readiness/").json()
    assert r["role"] == "junior-data-engineer" and "formula_version" in r and r["skills"]
    job = create_job(goal_user, "Requirements:\n- Python experience is required for this particular role")
    matching.match_job(goal_user, job)
    assert len(goal_client.get("/api/v1/me/matches/").json()) == 1
    client.force_login(other_user)
    assert client.get("/api/v1/me/matches/").json() == []
    assert client.get("/api/v1/me/readiness/").status_code == 409


def test_api_is_read_only(goal_client):
    assert goal_client.post("/api/v1/skills/", {}).status_code == 405


# ---------- rate limiter ----------
def test_rate_limit_counts_per_user_and_scope(rf, db, user, other_user):
    def req(u):
        r = rf.post("/x"); r.user = u; return r
    assert [ratelimit.hit(req(user), "s", 2, 60) for _ in range(3)] == [False, False, True]
    assert ratelimit.hit(req(other_user), "s", 2, 60) is False and ratelimit.hit(req(user), "other-scope", 2, 60) is False


# ---------- production safety ----------
def run_settings(env_extra):
    env = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "DEBUG", "DATABASE_URL")}
    env.update({"SKILLVAR_ENV_FILE": "/nonexistent/.env", "DJANGO_SETTINGS_MODULE": "config.settings", **env_extra})
    return subprocess.run([sys.executable, "-c", "import django; django.setup()"], env=env, capture_output=True, text=True)


@pytest.mark.parametrize("key", ["", "short", "change-me-dev-only-key-not-for-production-padding-padding"])
def test_production_refuses_weak_secret_keys(key):
    out = run_settings({"DEBUG": "0", "SECRET_KEY": key, "DATABASE_URL": "postgres://u:p@localhost/x"})
    assert out.returncode != 0 and "SECRET_KEY" in out.stderr


def test_missing_database_url_gives_a_clear_error():
    out = run_settings({"DEBUG": "1", "SECRET_KEY": "x" * 40})
    assert out.returncode != 0 and "DATABASE_URL is not set" in out.stderr


def test_missing_secret_key_is_an_error_even_in_debug():
    out = run_settings({"DEBUG": "1", "DATABASE_URL": "postgres://u:p@localhost/x"})
    assert out.returncode != 0 and "SECRET_KEY is not set" in out.stderr


def test_production_mode_enables_secure_cookies_and_debug_is_off(settings):
    out = run_settings({"DEBUG": "0", "SECRET_KEY": "k" * 50, "DATABASE_URL": "postgres://u:p@localhost/x"})
    assert out.returncode == 0
    probe = subprocess.run([sys.executable, "-c", "import django;django.setup();from django.conf import settings as s;print(s.DEBUG,s.SESSION_COOKIE_SECURE,s.CSRF_COOKIE_SECURE)"],
                           env={**os.environ, "SKILLVAR_ENV_FILE": "/nonexistent", "DJANGO_SETTINGS_MODULE": "config.settings", "DEBUG": "0",
                                "SECRET_KEY": "k" * 50, "DATABASE_URL": "postgres://u:p@localhost/x"}, capture_output=True, text=True)
    assert probe.stdout.strip().endswith("False True True")


def test_env_file_is_not_tracked_by_git():
    out = subprocess.run(["git", "check-ignore", ".env"], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    assert out.stdout.strip() == ".env"


def test_assessment_templates_hold_no_answers(goal_client):
    for a in Assessment.objects.all():
        page = goal_client.get(f"/assessments/{a.slug}/").content.decode()
        for q in a.questions.all():
            if q.explanation:
                assert q.explanation not in page
