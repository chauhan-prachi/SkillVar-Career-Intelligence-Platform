from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from apps.evidence.models import Evidence
from apps.matching.services import snapshot_if_goal

from . import sandbox
from .models import AnswerRecord, Assessment, Attempt, Question

MAX_SQL_CHARS = sandbox.MAX_ANSWER_CHARS


def grade_question(q: Question, answer: str) -> sandbox.Grade:
    if q.kind == Question.SQL:
        c = q.sql_config
        return sandbox.grade_sql(c["fixture"], c["reference"], answer, c.get("order_matters", False))
    try:
        choice = int(answer)
    except (TypeError, ValueError):
        return sandbox.Grade(0.0, "Answer must be one of the options.")
    ok = choice == q.correct_index
    return sandbox.Grade(1.0 if ok else 0.0, ("Correct. " if ok else "Not quite. ") + q.explanation)


def evidence_weight(user, q: Question) -> float:
    """Repeat-attempt policy: first attempt counts fully; a re-attempt counts half only after the learner has
    completed practice for that skill since their last attempt; any other re-attempt is audit-only (weight 0)."""
    last = (Evidence.objects.filter(user=user, source=Evidence.ASSESSMENT, answer__question=q)
            .order_by("-id").values_list("id", flat=True).first())
    if last is None:
        return q.weight
    practised = Evidence.objects.filter(user=user, source=Evidence.PRACTICE, skill=q.skill, id__gt=last).exists()
    return q.weight * 0.5 if practised else 0.0


def is_eligible(user, q: Question) -> bool:
    return evidence_weight(user, q) > 0


@transaction.atomic
def submit_attempt(user, assessment: Assessment, raw_answers: dict[int, str]) -> Attempt:
    questions = {q.id: q for q in assessment.questions.filter(is_active=True)}
    answered = {}
    for qid, text in raw_answers.items():
        q = questions.get(qid)
        text = (text or "").strip()
        if q is None or text == "":
            continue
        if q.kind == Question.MCQ:
            if not text.isdigit() or int(text) >= len(q.options):
                raise ValidationError("One of your answers is not a valid option.")
        elif len(text) > MAX_SQL_CHARS:
            raise ValidationError(f"Keep each SQL answer under {MAX_SQL_CHARS:,} characters.")
        answered[q.id] = text
    if not answered:
        raise ValidationError("Answer at least one question before submitting.")
    attempt = Attempt.objects.create(user=user, assessment=assessment)
    scores, counted = [], False
    for qid, text in answered.items():
        q = questions[qid]
        grade = grade_question(q, text)
        weight = evidence_weight(user, q)
        record = AnswerRecord.objects.create(attempt=attempt, question=q, question_version=q.version, answer_text=text[:5000],
                                             score=grade.score, feedback=grade.feedback, weight_applied=weight)
        Evidence.objects.create(user=user, skill=q.skill, source=Evidence.ASSESSMENT, score=grade.score,
                                difficulty=q.difficulty, weight=weight, answer=record)
        scores.append(grade.score)
        counted = counted or weight > 0
    attempt.score = sum(scores) / len(scores)
    attempt.save(update_fields=["score"])
    if counted:
        snapshot_if_goal(user)
    return attempt


def eligible_question(user, skill_slug: str, target_difficulty: float = 0.5) -> Question | None:
    qs = list(Question.objects.filter(skill__slug=skill_slug, is_active=True, assessment__is_active=True))
    unseen_ids = set(Question.objects.filter(id__in=[q.id for q in qs]).exclude(
        answers__attempt__user=user).values_list("id", flat=True))
    pool = [q for q in qs if q.id in unseen_ids] or [q for q in qs if is_eligible(user, q)]
    return min(pool, key=lambda q: abs(q.difficulty - target_difficulty)) if pool else None


def assessable_skills(user) -> set[str]:
    """Slugs of skills that still have at least one question able to produce counted evidence for this user.
    Computed with three queries in total (not per skill); it applies the same repeat-attempt policy as evidence_weight."""
    questions = Question.objects.filter(is_active=True, assessment__is_active=True).values_list("id", "skill__slug")
    last_attempt = dict(Evidence.objects.filter(user=user, source=Evidence.ASSESSMENT, answer__isnull=False)
                        .values("answer__question_id").annotate(last=Max("id")).values_list("answer__question_id", "last"))
    last_practice = dict(Evidence.objects.filter(user=user, source=Evidence.PRACTICE)
                         .values("skill__slug").annotate(last=Max("id")).values_list("skill__slug", "last"))
    return {slug for qid, slug in questions if qid not in last_attempt or last_practice.get(slug, 0) > last_attempt[qid]}
