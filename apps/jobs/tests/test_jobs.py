import pytest

from apps.jobs.analyzer import analyze_job_text
from apps.jobs.models import JobDescription, JobRequirement
from apps.jobs.services import create_job
from apps.skills.matcher import SkillMatcher

JOB = """Job Title: Junior Data Engineer
Company: Example Corp
We are hiring.

Responsibilities:
- Build and maintain data pipelines for analytics
- Monitor data quality and fix failing jobs

Requirements:
- 2+ years of experience in a data role
- Strong SQL and Python
- Experience with Airflow
- Bachelor's degree in a related field

Nice to have:
- Docker
- Experience with Kafka is a plus
"""


@pytest.fixture
def matcher(seeded):
    return SkillMatcher.from_db()


def kinds(a):
    return {r.slug: (r.kind, r.origin) for r in a.requirements}


def test_title_company_years_education_and_responsibilities(matcher):
    a = analyze_job_text(JOB, matcher)
    assert a.title == "Junior Data Engineer" and a.company == "Example Corp"
    assert a.years_required == 2.0 and a.education_required == "Bachelor's degree"
    assert len(a.responsibilities) == 2 and "pipelines" in a.responsibilities[0]


def test_required_vs_preferred_from_sections_and_cues(matcher):
    k = kinds(analyze_job_text(JOB, matcher))
    assert k["sql"] == ("required", "explicit") and k["python"][0] == "required" and k["airflow"][0] == "required"
    assert k["docker"] == ("preferred", "explicit") and k["kafka"][0] == "preferred"


def test_skill_in_responsibilities_counts_as_required(matcher):
    k = kinds(analyze_job_text(JOB, matcher))
    assert k["data-quality"][0] == "required"


def test_required_mention_wins_over_a_later_preferred_one(matcher):
    k = kinds(analyze_job_text("Requirements:\n- Python\nNice to have:\n- Python and Docker", matcher))
    assert k["python"][0] == "required"


def test_inferred_prerequisites_are_labelled_and_not_explicit(matcher):
    from apps.jobs.services import prerequisite_map
    a = analyze_job_text("Requirements:\n- Experience with Django", matcher, prerequisite_map())
    k = kinds(a)
    assert k["django"] == ("required", "explicit") and k["python"] == ("required", "inferred")


def test_nothing_is_invented_for_unrelated_text(matcher):
    a = analyze_job_text("We sell shoes and are looking for a friendly cashier.", matcher)
    assert a.requirements == [] and a.years_required is None and a.education_required == ""


@pytest.mark.parametrize("text,years", [("3-5 years of experience required", 3.0), ("minimum 5+ years of Python experience", 5.0),
                                        ("no experience needed", None)])
def test_years_parsing(matcher, text, years):
    assert analyze_job_text(text, matcher).years_required == years


def test_create_job_persists_requirements_and_ownership(seeded, user):
    job = create_job(user, JOB)
    assert job.user == user and job.requirements.filter(origin="explicit").count() >= 6
    assert job.requirements.get(skill__slug="docker").kind == "preferred"


# ---------- views ----------
def test_analyze_flow_and_detail_page(goal_client, goal_user):
    r = goal_client.post("/jobs/analyze/", {"text": JOB})
    assert r.status_code == 302
    page = goal_client.get(r.url).content.decode()
    assert "Junior Data Engineer" in page and "Required skills" in page and "Implied by prerequisites" in page and "Bachelor" in page


@pytest.mark.parametrize("text,msg", [("", "required"), ("too short", "longer job description"), ("x" * 25000, "longer than")])
def test_analyze_validates_input(goal_client, text, msg):
    r = goal_client.post("/jobs/analyze/", {"text": text})
    assert r.status_code == 200 and msg in r.content.decode() and not JobDescription.objects.exists()


def test_other_users_cannot_open_edit_match_or_delete_my_job(goal_client, goal_user, client, other_user):
    job = create_job(goal_user, JOB)
    client.force_login(other_user)
    for method, url in [("get", f"/jobs/{job.pk}/"), ("post", f"/jobs/{job.pk}/requirements/"), ("post", f"/jobs/{job.pk}/delete/"),
                        ("post", f"/jobs/{job.pk}/match/")]:
        assert getattr(client, method)(url).status_code == 404, url
    assert JobDescription.objects.filter(pk=job.pk).exists()


def test_shared_dataset_jobs_are_viewable_but_not_editable_or_deletable(goal_client, seeded, user):
    shared = JobDescription.objects.create(user=None, source="dataset", is_synthetic=True, title="Sample", raw_text=JOB, content_hash="h" * 64)
    assert goal_client.get(f"/jobs/{shared.pk}/").status_code == 200
    assert goal_client.post(f"/jobs/{shared.pk}/delete/").status_code == 404
    assert goal_client.post(f"/jobs/{shared.pk}/requirements/", {"action": "remove", "skill_id": 1}).status_code == 404


def test_manual_correction_of_requirements(goal_client, goal_user):
    from apps.skills.models import Skill
    job = create_job(goal_user, JOB)
    sid = Skill.objects.get(slug="docker").pk
    goal_client.post(f"/jobs/{job.pk}/requirements/", {"action": "toggle", "skill_id": sid})
    r = job.requirements.get(skill_id=sid)
    assert r.kind == "required" and r.edited_by_user
    goal_client.post(f"/jobs/{job.pk}/requirements/", {"action": "remove", "skill_id": sid})
    assert not job.requirements.filter(skill_id=sid).exists()
    goal_client.post(f"/jobs/{job.pk}/requirements/", {"action": "add", "new_skill": Skill.objects.get(slug="tableau").pk, "kind": "preferred"})
    assert job.requirements.get(skill__slug="tableau").kind == "preferred"


def test_promoting_an_inferred_requirement_makes_it_explicit(goal_client, goal_user):
    job = create_job(goal_user, "Requirements:\n- Django experience is essential for this role, plus more text here")
    inferred = job.requirements.get(origin="inferred")
    goal_client.post(f"/jobs/{job.pk}/requirements/", {"action": "promote", "skill_id": inferred.skill_id})
    assert JobRequirement.objects.get(pk=inferred.pk).origin == "explicit"


def test_job_list_is_paginated_and_private(goal_client, goal_user, other_user):
    for _ in range(12):
        create_job(goal_user, JOB)
    create_job(other_user, JOB)
    page = goal_client.get("/jobs/").content.decode()
    assert "Page 1 of 2" in page
    assert goal_client.get("/jobs/?page=2").status_code == 200


def test_sample_jobs_search_and_empty_state(goal_client, seeded):
    assert "No sample jobs found" in goal_client.get("/jobs/samples/").content.decode()
    JobDescription.objects.create(user=None, source="dataset", title="Data Analyst", raw_text=JOB, content_hash="a" * 64)
    JobDescription.objects.create(user=None, source="dataset", title="Backend Dev", raw_text=JOB + "x", content_hash="b" * 64)
    page = goal_client.get("/jobs/samples/?q=analyst").content.decode()
    assert "Data Analyst" in page and "Backend Dev" not in page


def test_job_text_is_escaped_in_pages(goal_client, goal_user):
    job = create_job(goal_user, "Job Title: <script>alert(1)</script>\nRequirements:\n- Python and SQL experience required here please")
    page = goal_client.get(f"/jobs/{job.pk}/").content.decode()
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_database_rejects_ownerless_pasted_jobs(seeded):
    from django.db import IntegrityError, transaction
    with pytest.raises(IntegrityError), transaction.atomic():
        JobDescription.objects.create(user=None, source="pasted", raw_text="x" * 50, content_hash="z" * 64)


@pytest.mark.parametrize("line,slug,kind", [
    ("- SQL", "sql", "required"), ("AWS", "aws", "required"), ("- Experience with Kafka is a plus", "kafka", "preferred"),
    ("Kafka is a plus", "kafka", "preferred"), ("* Docker (preferred)", "docker", "preferred"),
])
def test_short_or_cue_lines_are_content_not_headers(matcher, line, slug, kind):
    k = kinds(analyze_job_text(f"Requirements:\n{line}\n", matcher))
    assert slug in k and k[slug][0] == kind
