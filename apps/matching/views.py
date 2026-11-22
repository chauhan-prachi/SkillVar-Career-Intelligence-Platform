from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.evidence.profile import build_signals
from apps.skills.models import Skill

from . import services
from .models import JobMatch, ReadinessSnapshot
from .scoring import CLASS_LABELS, LABELS, skill_credit


@login_required
def match_detail(request, pk):
    m = get_object_or_404(JobMatch.objects.select_related("job"), pk=pk, user=request.user)
    groups = {}
    for s in m.result["skills"]:
        groups.setdefault(s["status"], []).append(s)
    return render(request, "matching/detail.html", {"m": m, "r": m.result, "groups": groups, "class_labels": CLASS_LABELS,
                                                    "weights": settings.MATCH_WEIGHTS})


@login_required
def match_list(request):
    page = Paginator(JobMatch.objects.filter(user=request.user).select_related("job"), 15).get_page(request.GET.get("page"))
    return render(request, "matching/list.html", {"page": page})


@login_required
def readiness(request):
    role = request.user.profile.career_goal
    if role is None:
        return redirect("onboarding")
    result = services.readiness(request.user, role)
    snaps = list(ReadinessSnapshot.objects.filter(user=request.user, role=role))
    return render(request, "matching/readiness.html", {
        "role": role, "r": result, "snaps": snaps, "class_labels": CLASS_LABELS,
        "strengths": [s for s in result.skills if s.status == "confirmed"], "gaps": [s for s in result.skills if s.status in ("missing", "not_demonstrated")],
        "unverified": [s for s in result.skills if s.status in ("insufficient", "possible")]})


@login_required
def my_skills(request):
    signals, _ = build_signals(request.user)
    rows = []
    for skill in Skill.objects.select_related("category").order_by("category__position", "name"):
        sig = signals.get(skill.slug)
        if sig is None or (sig.claimed is None and not sig.resume and not sig.assessed):
            continue
        status, code, exp, cons = skill_credit(sig, settings.MATCH_CREDITS, settings.UNDECIDED_ASSESSMENT_CAP)
        rows.append({"skill": skill, "sig": sig, "status": status, "code": code, "expected": exp, "status_label": CLASS_LABELS[status]})
    for r in rows:
        r["label"] = LABELS[r["code"]]
    return render(request, "matching/skills.html", {"rows": rows})
