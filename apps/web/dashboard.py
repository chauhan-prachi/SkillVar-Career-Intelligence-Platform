"""Assembles dashboard data from real database records. Nothing here is hard-coded or invented."""
from __future__ import annotations

from django.conf import settings

from apps.accounts.services import profile_completion
from apps.assessments.models import Attempt
from apps.dataops.models import IngestionRun
from apps.evidence.profile import build_signals
from apps.matching import services as matching
from apps.matching.models import JobMatch, ReadinessSnapshot
from apps.matching.scoring import LABELS, skill_credit
from apps.roadmaps import services as roadmaps


def build(user) -> dict:
    profile = user.profile
    pct, missing = profile_completion(user)
    ctx = {"completion": pct, "missing": missing, "goal": profile.career_goal, "has_resume": user.resumes.exists(),
           "resume_count": user.resumes.count(),
           "attempts": list(Attempt.objects.filter(user=user).select_related("assessment")[:5]),
           "matches": list(JobMatch.objects.filter(user=user).select_related("job")[:5])}
    signals, _ = build_signals(user)
    counts: dict[str, int] = {}
    for sig in signals.values():
        if sig.claimed is None and not sig.resume and not sig.assessed:
            continue
        code = skill_credit(sig, settings.MATCH_CREDITS, settings.UNDECIDED_ASSESSMENT_CAP)[1]
        counts[LABELS[code]] = counts.get(LABELS[code], 0) + 1
    ctx["evidence_chart"] = {"labels": list(counts), "values": list(counts.values())}
    ctx["evidence_total"] = sum(counts.values())
    ctx["readiness"] = ctx["gaps"] = ctx["next"] = ctx["roadmap"] = None
    ctx["trend"] = {"labels": [], "score": [], "conservative": []}
    if profile.career_goal:
        role = profile.career_goal
        r = matching.readiness(user, role)
        ctx["readiness"] = r
        ctx["gaps"] = sorted([s for s in r.skills if s.status in ("missing", "not_demonstrated")], key=lambda s: -s.importance)[:5]
        ctx["next"] = roadmaps.next_action(user, role)
        rm = roadmaps.active_roadmap(user, role)
        if rm:
            items = list(rm.items.all())
            done = sum(1 for i in items if i.status == "done")
            ctx["roadmap"] = {"done": done, "total": len(items), "pct": round(100 * done / len(items)) if items else 0}
        snaps = list(ReadinessSnapshot.objects.filter(user=user, role=role).order_by("-created_at")[:20])[::-1]
        ctx["trend"] = {"labels": [s.created_at.strftime("%d %b %H:%M") for s in snaps],
                        "score": [round(s.score * 100) for s in snaps], "conservative": [round(s.conservative * 100) for s in snaps]}
    if user.is_staff:
        ctx["last_run"] = IngestionRun.objects.select_related("dataset").first()
    return ctx
