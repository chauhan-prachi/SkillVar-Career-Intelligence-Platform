from __future__ import annotations

import hashlib
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.skills.matcher import SkillMatcher
from apps.skills.models import Skill, SkillPrerequisite

from .analyzer import analyze_job_text
from .models import JobDescription, JobRequirement


def prerequisite_map() -> dict[str, list[str]]:
    m: dict[str, list[str]] = defaultdict(list)
    for s, p in SkillPrerequisite.objects.values_list("skill__slug", "prerequisite__slug"):
        m[s].append(p)
    return m


def clean_text(text: str) -> str:
    text = (text or "").replace("\x00", "").strip()
    if len(text) < 40:
        raise ValidationError("Please paste a longer job description (at least a few sentences).")
    if len(text) > settings.JOB_TEXT_MAX_CHARS:
        raise ValidationError(f"The description is longer than {settings.JOB_TEXT_MAX_CHARS:,} characters.")
    return text


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


@transaction.atomic
def create_job(user, text: str, matcher: SkillMatcher | None = None, **extra) -> JobDescription:
    text = clean_text(text)
    analysis = analyze_job_text(text, matcher or SkillMatcher.from_db(), prerequisite_map())
    job = JobDescription.objects.create(
        user=user, source=extra.pop("source", JobDescription.PASTED), raw_text=text, content_hash=content_hash(text),
        title=extra.pop("title", "") or analysis.title, company=extra.pop("company", "") or analysis.company,
        years_required=analysis.years_required, education_required=analysis.education_required,
        responsibilities=analysis.responsibilities, **extra)
    skills = {s.slug: s for s in Skill.objects.filter(slug__in=[r.slug for r in analysis.requirements])}
    JobRequirement.objects.bulk_create([
        JobRequirement(job=job, skill=skills[r.slug], kind=r.kind, origin=r.origin, snippet=r.snippet)
        for r in analysis.requirements if r.slug in skills])
    return job


def set_requirement(job: JobDescription, skill: Skill, kind: str) -> JobRequirement:
    req, _ = JobRequirement.objects.update_or_create(job=job, skill=skill, defaults={
        "kind": kind, "origin": JobRequirement.EXPLICIT, "edited_by_user": True, "snippet": "Set by you"})
    return req


def remove_requirement(job: JobDescription, skill_id: int) -> None:
    job.requirements.filter(skill_id=skill_id).delete()


def promote_inferred(job: JobDescription, skill_id: int) -> None:
    job.requirements.filter(skill_id=skill_id, origin=JobRequirement.INFERRED).update(origin=JobRequirement.EXPLICIT, edited_by_user=True)
