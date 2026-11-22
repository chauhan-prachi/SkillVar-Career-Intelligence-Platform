from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .models import RoadmapItem


@login_required
def roadmap(request):
    role = request.user.profile.career_goal
    if role is None:
        messages.info(request, "Choose a career goal to build a roadmap.")
        return redirect("onboarding")
    rm = services.active_roadmap(request.user, role)
    items = list(rm.items.all()) if rm else []
    done = sum(1 for i in items if i.status == RoadmapItem.DONE)
    return render(request, "roadmaps/roadmap.html", {"role": role, "roadmap": rm, "items": items, "done": done,
                                                     "pct": round(100 * done / len(items)) if items else 0})


@login_required
@require_POST
def generate(request):
    role = request.user.profile.career_goal
    if role is None:
        return redirect("onboarding")
    services.generate_roadmap(request.user, role)
    messages.success(request, "Roadmap generated from your current evidence.")
    return redirect("roadmap")


@login_required
@require_POST
def item_action(request, pk):
    item = get_object_or_404(RoadmapItem.objects.select_related("roadmap", "skill"), pk=pk, roadmap__user=request.user)
    action = request.POST.get("action")
    if action == "complete":
        services.complete_item(request.user, item, request.POST.get("note", ""))
        messages.success(request, f"Marked {item.skill.name} as done. Re-test it to turn practice into assessed evidence.")
    elif action in ("todo", "doing"):
        services.set_status(request.user, item, action)
    return redirect("roadmap")
