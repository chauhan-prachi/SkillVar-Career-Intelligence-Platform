import pytest
from django.core.exceptions import ValidationError

from apps.assessments import services
from apps.assessments.models import AnswerRecord, Assessment, Attempt, Question
from apps.evidence.models import Evidence
from apps.evidence.profile import build_signals
from apps.matching.models import ReadinessSnapshot


def answers(assessment, **by_slug):
    return {q.id: by_slug[q.slug] for q in assessment.questions.all() if q.slug in by_slug}


@pytest.fixture
def py(seeded):
    return Assessment.objects.get(slug="python-fundamentals")


def test_mcq_is_graded_on_the_server_and_recorded(py, user):
    a = services.submit_attempt(user, py, answers(py, **{"py-listcomp": "2", "py-set-len": "0"}))
    assert a.score == 0.5 and a.answers.count() == 2 and Evidence.objects.filter(user=user, source="assessment").count() == 2
    right = a.answers.get(question__slug="py-listcomp")
    assert right.score == 1 and right.feedback.startswith("Correct") and right.question_version == 1 and right.counted


def test_unanswered_questions_are_not_scored(py, user):
    a = services.submit_attempt(user, py, answers(py, **{"py-listcomp": "2", "py-split": ""}))
    assert a.answers.count() == 1


def test_nothing_answered_is_an_error(py, user):
    with pytest.raises(ValidationError, match="at least one"):
        services.submit_attempt(user, py, {})
    assert not Attempt.objects.exists()


@pytest.mark.parametrize("bad", ["9", "-1", "abc", "1.5"])
def test_invalid_option_is_rejected_and_nothing_is_saved(py, user, bad):
    with pytest.raises(ValidationError, match="valid option"):
        services.submit_attempt(user, py, answers(py, **{"py-listcomp": bad}))
    assert not Attempt.objects.exists() and not Evidence.objects.exists()


def test_sql_questions_are_executed_not_pattern_matched(seeded, user):
    sp = Assessment.objects.get(slug="sql-practice")
    a = services.submit_attempt(user, sp, answers(sp, **{
        "sqlp-count": "select count(*) from orders where status = 'completed'", "sqlp-india": "SELECT name FROM customers"}))
    by = {r.question.slug: r for r in a.answers.all()}
    assert by["sqlp-count"].score == 1.0 and by["sqlp-india"].score == 0.0      # wrong row count: no partial credit


def test_dangerous_sql_scores_zero(seeded, user):
    sp = Assessment.objects.get(slug="sql-practice")
    a = services.submit_attempt(user, sp, answers(sp, **{"sqlp-count": "DROP TABLE orders"}))
    assert a.answers.get().score == 0 and "could not run" in a.answers.get().feedback


def test_overlong_sql_is_rejected(seeded, user):
    sp = Assessment.objects.get(slug="sql-practice")
    with pytest.raises(ValidationError, match="under"):
        services.submit_attempt(user, sp, answers(sp, **{"sqlp-count": "x" * 5001}))


def test_attempt_stores_the_question_version_for_later_interpretation(py, user):
    q = Question.objects.get(slug="py-listcomp")
    services.submit_attempt(user, py, {q.id: "2"})
    q.version = 2; q.prompt = "changed"; q.save()
    assert AnswerRecord.objects.get().question_version == 1 and q.version == 2


def test_assessment_changes_the_skill_estimate(py, user):
    for slug in ("py-listcomp", "py-set-len", "py-split", "py-dict-order"):
        services.submit_attempt(user, py, answers(py, **{slug: str(Question.objects.get(slug=slug).correct_index)}))
    sig = build_signals(user)[0]["python"]
    assert sig.assessed and sig.n_assessments == 4 and sig.mean > 0.6


# ---------- repeat-attempt policy ----------
def test_first_attempt_counts_fully_and_a_repeat_counts_nothing(py, user):
    q = Question.objects.get(slug="py-listcomp")
    services.submit_attempt(user, py, {q.id: "0"})
    services.submit_attempt(user, py, {q.id: "2"})
    weights = list(Evidence.objects.order_by("id").values_list("weight", flat=True))
    assert weights == [q.weight, 0.0]


def test_repeating_one_question_cannot_inflate_the_estimate(py, user):
    q = Question.objects.get(slug="py-listcomp")
    services.submit_attempt(user, py, {q.id: "0"})
    before = build_signals(user)[0]["python"].mean
    for _ in range(8):
        services.submit_attempt(user, py, {q.id: "2"})
    assert build_signals(user)[0]["python"].mean == before


def test_a_repeat_after_practice_counts_at_half_weight(py, user):
    from apps.skills.models import Skill
    q = Question.objects.get(slug="py-listcomp")
    services.submit_attempt(user, py, {q.id: "0"})
    Evidence.objects.create(user=user, skill=Skill.objects.get(slug="python"), source="practice")
    services.submit_attempt(user, py, {q.id: "2"})
    assert list(Evidence.objects.filter(source="assessment").order_by("id").values_list("weight", flat=True)) == [q.weight, q.weight * 0.5]


def test_eligibility_helpers_follow_the_policy(py, user):
    from apps.skills.models import Skill
    q = Question.objects.get(slug="py-listcomp")
    assert services.is_eligible(user, q)
    services.submit_attempt(user, py, {q.id: "2"})
    assert not services.is_eligible(user, q)
    Evidence.objects.create(user=user, skill=Skill.objects.get(slug="python"), source="practice")
    assert services.is_eligible(user, q)


def test_eligible_question_prefers_unseen_and_returns_none_when_exhausted(seeded, user):
    ab = Assessment.objects.get(slug="engineering-essentials")
    git_qs = list(Question.objects.filter(skill__slug="git"))
    first = services.eligible_question(user, "git", 0.3)
    assert first in git_qs
    services.submit_attempt(user, ab, {q.id: "0" for q in git_qs})
    assert services.eligible_question(user, "git") is None
    assert services.eligible_question(user, "no-such-skill") is None


def test_readiness_snapshot_is_recorded_when_the_user_has_a_goal(goal_user):
    sp = Assessment.objects.get(slug="sql-practice")
    services.submit_attempt(goal_user, sp, answers(sp, **{"sqlp-count": "SELECT COUNT(*) FROM orders WHERE status='completed'"}))
    assert ReadinessSnapshot.objects.filter(user=goal_user).count() == 1


def test_no_snapshot_when_nothing_counted(goal_user):
    py = Assessment.objects.get(slug="python-fundamentals")
    q = Question.objects.get(slug="py-listcomp")
    services.submit_attempt(goal_user, py, {q.id: "2"})
    n = ReadinessSnapshot.objects.count()
    services.submit_attempt(goal_user, py, {q.id: "2"})          # repeat, weight 0
    assert ReadinessSnapshot.objects.count() == n


# ---------- views ----------
def test_take_and_result_pages(goal_client, goal_user):
    page = goal_client.get("/assessments/python-fundamentals/").content.decode()
    assert "range(3)" in page
    assert "range(3) yields 0, 1, 2" not in page          # the explanation is only shown after submitting
    q = Question.objects.get(slug="py-listcomp")
    r = goal_client.post("/assessments/python-fundamentals/", {f"q{q.id}": "2"})
    assert r.status_code == 302
    result = goal_client.get(r.url).content.decode()
    assert "Correct" in result and "100%" in result


def test_answers_are_never_leaked_before_submission(goal_client):
    page = goal_client.get("/assessments/sql-practice/").content.decode()
    assert "ORDER BY 2 DESC" not in page and "ROW_NUMBER" not in page and "rn = 1" not in page


def test_view_errors_for_invalid_submissions(goal_client):
    r = goal_client.post("/assessments/python-fundamentals/", {})
    assert r.status_code == 200 and "Answer at least one question" in r.content.decode()


def test_attempt_results_are_private(goal_client, goal_user, client, other_user):
    q = Question.objects.get(slug="py-listcomp")
    r = goal_client.post("/assessments/python-fundamentals/", {f"q{q.id}": "2"})
    client.force_login(other_user)
    assert client.get(r.url).status_code == 404 and "Python fundamentals" not in client.get("/assessments/history/").content.decode()


def test_repeat_warning_is_shown_on_the_form_and_result(goal_client):
    q = Question.objects.get(slug="py-listcomp")
    goal_client.post("/assessments/python-fundamentals/", {f"q{q.id}": "0"})
    assert "will not change your estimate" in goal_client.get("/assessments/python-fundamentals/").content.decode()
    r = goal_client.post("/assessments/python-fundamentals/", {f"q{q.id}": "2"})
    assert "did not change your estimates" in goal_client.get(r.url).content.decode()


def test_submission_rate_limit(goal_client):
    q = Question.objects.get(slug="py-listcomp")
    codes = [goal_client.post("/assessments/python-fundamentals/", {f"q{q.id}": "2"}).status_code for _ in range(62)]
    assert codes[0] == 302 and codes[-1] == 200 and "too quickly" in goal_client.post("/assessments/python-fundamentals/", {f"q{q.id}": "2"}).content.decode()


def test_assessment_list_and_history_empty_states(goal_client):
    assert "Start" in goal_client.get("/assessments/").content.decode()
    assert "not taken an assessment yet" in goal_client.get("/assessments/history/").content.decode()


def test_assessable_skills_matches_the_per_question_policy(seeded, user):
    from apps.evidence.models import Evidence
    from apps.skills.models import Skill
    every = {q.skill.slug for q in Question.objects.all()}
    assert services.assessable_skills(user) == every
    for q in Question.objects.filter(skill__slug="git"):
        services.submit_attempt(user, q.assessment, {q.id: "0"})
    assert "git" not in services.assessable_skills(user) and "python" in services.assessable_skills(user)
    Evidence.objects.create(user=user, skill=Skill.objects.get(slug="git"), source="practice")
    assert "git" in services.assessable_skills(user)
    for slug in every:                                    # the fast set-based version agrees with the per-question rule
        slow = any(services.is_eligible(user, q) for q in Question.objects.filter(skill__slug=slug))
        assert (slug in services.assessable_skills(user)) == slow


def test_assessable_skills_uses_a_constant_number_of_queries(seeded, user, django_assert_num_queries):
    with django_assert_num_queries(3):
        services.assessable_skills(user)
