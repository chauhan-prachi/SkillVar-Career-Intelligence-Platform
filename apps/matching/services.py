from __future__ import annotations

from django.conf import settings

from apps.evidence.profile import build_signals, load_graph
from apps.jobs.models import JobDescription, JobRequirement
from apps.skills.models import Role

from .models import JobMatch, ReadinessSnapshot
from .scoring import MatchResult, Requirement, score_requirements


def _score(requirements, signals, **kw) -> MatchResult:
    return score_requirements(requirements, signals, weights=settings.MATCH_WEIGHTS, credits=settings.MATCH_CREDITS,
                              undecided_cap=settings.UNDECIDED_ASSESSMENT_CAP, **kw)


def job_requirements(job: JobDescription, include_inferred: bool = False) -> list[Requirement]:
    qs = job.requirements.select_related("skill")
    if not include_inferred:
        qs = qs.filter(origin=JobRequirement.EXPLICIT)
    return [Requirement(r.skill.slug, r.skill.name, r.kind, 1.0, r.origin) for r in qs]


def match_job(user, job: JobDescription, save: bool = True) -> tuple[MatchResult, JobMatch | None]:
    signals, _ = build_signals(user, load_graph())
    years = getattr(user.profile, "years_experience", None)
    result = _score(job_requirements(job), signals, years_required=float(job.years_required) if job.years_required is not None else None,
                    user_years=float(years) if years is not None else None)
    record = None
    if save and result.score is not None:
        record = JobMatch.objects.create(user=user, job=job, score=result.score, result=result.to_dict(),
                                         formula_version=settings.FORMULA_VERSION)
    return result, record


def role_requirements(role: Role) -> list[Requirement]:
    return [Requirement(r.skill.slug, r.skill.name, "required" if r.is_required else "preferred", r.importance)
            for r in role.requirements.select_related("skill")]


def readiness(user, role: Role, save: bool = False) -> MatchResult:
    signals, _ = build_signals(user, load_graph())
    result = _score(role_requirements(role), signals)
    if save and result.score is not None:
        ReadinessSnapshot.objects.create(user=user, role=role, score=result.score, conservative=result.conservative,
                                         evidence_coverage=result.evidence_coverage, result=result.to_dict(),
                                         formula_version=settings.FORMULA_VERSION)
    return result


def snapshot_if_goal(user) -> None:
    role = getattr(user.profile, "career_goal", None)
    if role:
        readiness(user, role, save=True)
