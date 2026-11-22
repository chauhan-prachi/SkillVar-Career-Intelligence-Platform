
from apps.evidence.models import Evidence
from apps.evidence.tests.test_profile import answer, claim
from apps.jobs.models import JobDescription
from apps.jobs.services import create_job
from apps.matching import services
from apps.matching.models import JobMatch, ReadinessSnapshot
from apps.skills.models import Role, Skill

JOB = "Job Title: Data Engineer\nRequirements:\n- 4+ years of experience\n- Python\n- SQL\nNice to have:\n- Docker\n"


def test_match_is_saved_with_a_full_explainable_breakdown(goal_user):
    job = create_job(goal_user, JOB)
    result, record = services.match_job(goal_user, job)
    assert record.score == result.score == 0.0 and record.result["explanation"] and record.formula_version
    assert {s["slug"] for s in record.result["skills"]} == {"python", "sql", "docker"}


def test_stored_numbers_equal_a_fresh_recalculation(goal_user):
    for _ in range(4):
        answer(goal_user, "python", 1.0)
    claim(goal_user, "sql", 0.85)
    job = create_job(goal_user, JOB)
    _, record = services.match_job(goal_user, job)
    again, _ = services.match_job(goal_user, job, save=False)
    assert record.score == again.score and record.result["components"] == again.to_dict()["components"]


def test_assessment_evidence_beats_a_claim_in_the_match(goal_user):
    job = create_job(goal_user, JOB)
    claim(goal_user, "python", 0.85)
    claimed_only, _ = services.match_job(goal_user, job, save=False)
    for _ in range(4):
        answer(goal_user, "python", 1.0)
    proven, _ = services.match_job(goal_user, job, save=False)
    assert proven.score > claimed_only.score and proven.by_status("confirmed")[0].slug == "python"
    assert claimed_only.by_status("insufficient")[0].slug in ("python", "sql") and claimed_only.conservative == 0


def test_experience_uses_profile_years_when_available(goal_user):
    job = create_job(goal_user, JOB)
    assert job.years_required == 4
    assert services.match_job(goal_user, job, save=False)[0].components["experience"]["value"] is None
    goal_user.profile.years_experience = 2
    goal_user.profile.save()
    assert services.match_job(goal_user, job, save=False)[0].components["experience"]["value"] == 0.5


def test_inferred_requirements_are_not_scored_by_default(goal_user):
    job = create_job(goal_user, "Requirements:\n- Django experience is essential here, with more text to analyze")
    slugs = {r.slug for r in services.job_requirements(job)}
    assert "django" in slugs and "python" not in slugs
    assert "python" in {r.slug for r in services.job_requirements(job, include_inferred=True)}


def test_job_with_no_recognised_skills_is_not_scored(goal_client, goal_user):
    job = create_job(goal_user, "We sell shoes and need a friendly cashier for the weekend shifts in our shop.")
    r = goal_client.post(f"/jobs/{job.pk}/match/", follow=True)
    assert "no recognized requirements" in r.content.decode() and not JobMatch.objects.exists()


def test_match_view_flow_and_ownership(goal_client, goal_user, client, other_user):
    job = create_job(goal_user, JOB)
    r = goal_client.post(f"/jobs/{job.pk}/match/")
    page = goal_client.get(r.url).content.decode()
    assert "not the probability of being hired" in page and "How the score was calculated" in page and "Missing" in page
    client.force_login(other_user)
    assert client.get(r.url).status_code == 404


def test_matching_a_shared_dataset_job(goal_client, goal_user):
    shared = JobDescription.objects.create(user=None, source="dataset", title="S", raw_text=JOB, content_hash="s" * 64)
    from apps.jobs.models import JobRequirement
    from apps.skills.models import Skill as S
    JobRequirement.objects.create(job=shared, skill=S.objects.get(slug="python"), kind="required")
    r = goal_client.post(f"/jobs/{shared.pk}/match/")
    assert r.status_code == 302 and JobMatch.objects.get().user == goal_user


def test_readiness_uses_role_requirements_and_weights(goal_user):
    role = goal_user.profile.career_goal
    base = services.readiness(goal_user, role)
    assert base.score == 0 and len(base.skills) == role.requirements.count()
    for _ in range(4):
        answer(goal_user, "sql", 1.0)
    better = services.readiness(goal_user, role)
    assert better.score > 0 and better.by_status("confirmed")[0].slug == "sql"


def test_readiness_snapshots_are_saved_only_when_asked(goal_user):
    role = goal_user.profile.career_goal
    services.readiness(goal_user, role)
    assert not ReadinessSnapshot.objects.exists()
    services.readiness(goal_user, role, save=True)
    assert ReadinessSnapshot.objects.count() == 1


def test_readiness_page_and_empty_states(goal_client):
    page = goal_client.get("/readiness/").content.decode()
    assert "Expected readiness" in page and "No skill is" not in page and "Needs verification" in page and "not a probability of being hired" in page


def test_readiness_without_a_goal_redirects_to_onboarding(client, user):
    client.force_login(user)
    assert client.get("/readiness/").url == "/accounts/onboarding/"


def test_my_skills_lists_only_skills_with_evidence(goal_client, goal_user):
    assert "no skills with evidence yet" in goal_client.get("/skills/").content.decode()
    claim(goal_user, "etl", 0.6)
    page = goal_client.get("/skills/").content.decode()
    assert "ETL" in page and "Self-reported" in page and "Intermediate" in page


def test_other_users_matches_are_hidden_from_lists(goal_client, goal_user, other_user):
    job = create_job(other_user, JOB)
    services.match_job(other_user, job)
    assert "Data Engineer" not in goal_client.get("/matches/").content.decode()


def test_role_requirements_mapping(goal_user):
    reqs = services.role_requirements(Role.objects.get(slug="data-analyst"))
    assert any(r.kind == "preferred" and r.slug == "tableau" for r in reqs) and all(0 < r.importance <= 1 for r in reqs)
    assert Skill.objects.filter(slug="tableau").exists() and Evidence.objects.count() == 0
