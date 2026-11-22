from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.evidence.models import Evidence
from apps.skills.models import Skill


def current_claims(user) -> dict[str, float]:
    claims: dict[str, float] = {}
    for slug, score in Evidence.objects.filter(user=user, source=Evidence.SELF_REPORT).order_by("id").values_list("skill__slug", "score"):
        claims[slug] = score
    return claims


@transaction.atomic
def save_self_assessment(user, levels: dict[str, float]) -> int:
    """Append a new self-report row only when the level changed (the log stays honest and free of duplicates)."""
    existing, written = current_claims(user), 0
    skills = {s.slug: s for s in Skill.objects.filter(slug__in=levels)}
    for slug, level in levels.items():
        if slug in skills and abs(existing.get(slug, -1) - level) > 0.01:
            Evidence.objects.create(user=user, skill=skills[slug], source=Evidence.SELF_REPORT, score=level)
            written += 1
    return written


def complete_onboarding(user) -> None:
    profile = user.profile
    if not profile.onboarding_completed_at:
        profile.onboarding_completed_at = timezone.now()
        profile.save(update_fields=["onboarding_completed_at"])


def profile_completion(user) -> tuple[int, list[str]]:
    """Share of 7 concrete profile items that are filled in, and the list of what is missing."""
    p = user.profile
    items = [("Career goal", p.career_goal_id), ("Education level", p.education_level), ("Experience level", p.experience_level),
             ("Years of experience", p.years_experience is not None), ("Preferred location", p.preferred_location),
             ("At least one skill self-assessment", Evidence.objects.filter(user=user, source=Evidence.SELF_REPORT).exists()),
             ("A resume", user.resumes.exists())]
    missing = [name for name, ok in items if not ok]
    return round(100 * (len(items) - len(missing)) / len(items)), missing
