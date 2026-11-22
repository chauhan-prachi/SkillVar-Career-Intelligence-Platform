import pytest
from django.utils import timezone

from apps.accounts import services
from apps.evidence.models import Evidence
from apps.skills.models import Role


@pytest.fixture
def role(seeded):
    return Role.objects.get(slug="junior-data-engineer")


PROFILE = {"education_level": "bachelor", "field_of_study": "Computer Science", "experience_level": "entry",
           "years_experience": "1.5", "preferred_location": "Remote"}


def test_profile_step_saves_goal_and_details(auth_client, user, role):
    r = auth_client.post("/accounts/onboarding/", {**PROFILE, "career_goal": role.pk, "preferred_roles": [Role.objects.get(slug="data-analyst").pk]})
    assert r.status_code == 302 and r.url == "/accounts/onboarding/skills/"
    p = user.profile; p.refresh_from_db()
    assert p.career_goal == role and p.field_of_study == "Computer Science" and float(p.years_experience) == 1.5
    assert list(p.preferred_roles.values_list("slug", flat=True)) == ["data-analyst"] and not p.onboarding_completed


def test_career_goal_is_required_and_inputs_validated(auth_client, role):
    r = auth_client.post("/accounts/onboarding/", {**PROFILE})
    assert r.status_code == 200 and "required" in r.content.decode().lower()
    r = auth_client.post("/accounts/onboarding/", {**PROFILE, "career_goal": role.pk, "years_experience": "-3"})
    assert r.status_code == 200 and "greater than or equal to 0" in r.content.decode()
    assert auth_client.post("/accounts/onboarding/", {**PROFILE, "career_goal": 9999}).status_code == 200


def test_skills_step_requires_a_goal(auth_client, seeded):
    assert auth_client.get("/accounts/onboarding/skills/").url == "/accounts/onboarding/"


def test_self_assessment_saves_claims_and_completes_onboarding(goal_client, goal_user):
    r = goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "0.85", "skill_python": "0.6", "skill_etl": ""})
    assert r.status_code == 302 and r.url == "/dashboard/"
    claims = services.current_claims(goal_user)
    assert claims == {"sql": 0.85, "python": 0.6}
    goal_user.profile.refresh_from_db()
    assert goal_user.profile.onboarding_completed and goal_user.profile.onboarding_completed_at <= timezone.now()


def test_unchanged_claims_do_not_write_duplicate_events(goal_client, goal_user):
    goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "0.85"})
    goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "0.85"})
    assert Evidence.objects.filter(source="self_report").count() == 1
    goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "0.3"})
    assert Evidence.objects.filter(source="self_report").count() == 2 and services.current_claims(goal_user)["sql"] == 0.3


def test_only_goal_relevant_skills_are_offered_and_others_are_ignored(goal_client, goal_user):
    page = goal_client.get("/accounts/onboarding/skills/").content.decode()
    assert "SQL" in page and "Tableau" not in page and "not verified skills" in page.lower()
    goal_client.post("/accounts/onboarding/skills/", {"skill_tableau": "0.85"})
    assert services.current_claims(goal_user) == {}


def test_invalid_level_is_rejected(goal_client, goal_user):
    r = goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "9.9"})
    assert r.status_code == 200 and services.current_claims(goal_user) == {}


def test_previous_levels_are_prefilled(goal_client):
    goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "0.85"})
    page = goal_client.get("/accounts/onboarding/skills/").content.decode()
    assert 'value="0.85" selected' in page


def test_profile_completion_counts_concrete_items(goal_user):
    pct, missing = services.profile_completion(goal_user)
    assert pct == round(100 / 7) and "Career goal" not in missing and "A resume" in missing
    p = goal_user.profile
    p.education_level, p.experience_level, p.years_experience, p.preferred_location = "bachelor", "entry", 1, "Remote"
    p.save()
    Evidence.objects.create(user=goal_user, skill=__import__("apps.skills.models", fromlist=["Skill"]).Skill.objects.get(slug="sql"), source="self_report", score=0.6)
    assert services.profile_completion(goal_user)[0] == round(100 * 6 / 7)


def test_profiles_are_isolated_between_users(goal_client, goal_user, other_user):
    goal_client.post("/accounts/onboarding/skills/", {"skill_sql": "0.85"})
    assert services.current_claims(other_user) == {} and other_user.profile.career_goal is None
