import pytest
from django.db import IntegrityError, transaction

from apps.evidence.models import Evidence
from apps.evidence.profile import build_signals, replay
from apps.resumes.models import Resume, ResumeSkill
from apps.skills.models import Skill


def claim(user, slug, level):
    Evidence.objects.create(user=user, skill=Skill.objects.get(slug=slug), source="self_report", score=level)


def answer(user, slug, score, weight=1.0, difficulty=0.5):
    """An assessment evidence row needs an AnswerRecord (enforced by a database constraint)."""
    from apps.assessments.models import AnswerRecord, Assessment, Attempt, Question
    a = Assessment.objects.first()
    q = Question.objects.filter(skill__slug=slug).first() or Question.objects.first()
    attempt = Attempt.objects.create(user=user, assessment=a)
    rec = AnswerRecord.objects.create(attempt=attempt, question=q, question_version=1, score=score, weight_applied=weight)
    return Evidence.objects.create(user=user, skill=Skill.objects.get(slug=slug), source="assessment", score=score,
                                   difficulty=difficulty, weight=weight, answer=rec)


def test_claim_is_not_evidence(seeded, user):
    claim(user, "etl", 0.85)
    sig, _ = build_signals(user)
    assert sig["etl"].claimed == 0.85 and not sig["etl"].assessed and sig["etl"].performance == "unverified_claim"


def test_claim_can_be_revised_before_assessment(seeded, user):
    claim(user, "etl", 0.85); claim(user, "etl", 0.3)
    assert build_signals(user)[0]["etl"].claimed < 0.7


def test_claim_never_overrides_assessment_evidence(seeded, user):
    for _ in range(3):
        answer(user, "sql", 0.0)
    before = build_signals(user)[0]["sql"].mean
    claim(user, "sql", 0.85)
    assert build_signals(user)[0]["sql"].mean == before


def test_zero_weight_evidence_is_audit_only(seeded, user):
    answer(user, "sql", 1.0, weight=0.0)
    sig = build_signals(user)[0]["sql"]
    assert not sig.assessed and sig.n_assessments == 0


def test_counted_assessment_changes_the_estimate(seeded, user):
    for _ in range(4):
        answer(user, "python", 1.0)
    sig = build_signals(user)[0]["python"]
    assert sig.assessed and sig.mean > 0.7 and sig.performance == "demonstrated"


def test_replay_is_deterministic(seeded, user):
    for s in (1.0, 0.0, 1.0):
        answer(user, "python", s)
    a, b = replay(user).states["python"], replay(user).states["python"]
    assert (a.alpha, a.beta) == (b.alpha, b.beta)


def test_practice_marks_skill_as_practised(seeded, user):
    answer(user, "python", 0.0)
    Evidence.objects.create(user=user, skill=Skill.objects.get(slug="python"), source="practice")
    assert replay(user).states["python"].practiced_since_assessment


def _resume(user, sha="a"):
    return Resume.objects.create(user=user, original_filename="r.pdf", file="x", file_format="pdf", size_bytes=1, sha256=sha, status="processed")


def test_resume_tiers_contextual_beats_stated_and_rejected_is_ignored(seeded, user):
    r = _resume(user)
    ResumeSkill.objects.create(resume=r, skill=Skill.objects.get(slug="python"), contextual=False)
    ResumeSkill.objects.create(resume=_resume(user, "b"), skill=Skill.objects.get(slug="python"), contextual=True)
    ResumeSkill.objects.create(resume=r, skill=Skill.objects.get(slug="git"), contextual=True, review="rejected")
    sig = build_signals(user)[0]
    assert sig["python"].resume == "contextual" and sig["git"].resume is None


def test_other_users_data_never_leaks_into_signals(seeded, user, other_user):
    claim(other_user, "etl", 0.85)
    answer(other_user, "sql", 1.0)
    sig = build_signals(user)[0]
    assert sig["etl"].claimed is None and not sig["sql"].assessed


def test_database_rejects_invalid_evidence_rows(seeded, user):
    sql = Skill.objects.get(slug="sql")
    for bad in (dict(source="self_report", score=None), dict(source="self_report", score=1.5), dict(source="assessment", score=0.5),
                dict(source="practice", weight=-1)):
        with pytest.raises(IntegrityError), transaction.atomic():
            Evidence.objects.create(user=user, skill=sql, **bad)
