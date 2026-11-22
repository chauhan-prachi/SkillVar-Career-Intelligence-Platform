from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.assessments.services import assessable_skills, eligible_question
from apps.evidence.engine import RoleSpec, recommend_next
from apps.evidence.models import Evidence
from apps.evidence.profile import build_signals, load_graph
from apps.matching.scoring import CONFIRMED, NOT_DEMONSTRATED, POSSIBLE, skill_credit
from apps.skills.models import Role, Skill

from .models import LearningResource, Roadmap, RoadmapItem

MAX_ITEMS = 12


def _status(sig):
    return skill_credit(sig, settings.MATCH_CREDITS, settings.UNDECIDED_ASSESSMENT_CAP)[0]


def _reason(name, status, sig, role_title, dependent=None):
    if dependent:
        return f"{name} is a prerequisite of {dependent}. Weak foundations here slow down everything built on top of it."
    est = f"{sig.mean:.0%}"
    if status == NOT_DEMONSTRATED:
        return f"Your assessments indicate a gap in {name} (estimate {est}), and it matters for {role_title}."
    if status == POSSIBLE:
        return f"Your evidence for {name} is promising but not conclusive yet (estimate {est}). More practice and a re-test would settle it."
    if sig.claimed is not None or sig.resume:
        return f"You listed {name}, but nothing verifies it yet. Practice it, then take an assessment to turn the claim into evidence."
    return f"{name} is needed for {role_title} and there is no evidence of it in your profile yet."


@transaction.atomic
def generate_roadmap(user, role: Role) -> Roadmap:
    """Deterministic: unproven role skills + their unproven prerequisites, prerequisites first, then by importance."""
    graph = load_graph()
    signals, _ = build_signals(user, graph)
    reqs = list(role.requirements.select_related("skill"))
    importance = {r.skill.slug: (r.importance + (0.5 if r.is_required else 0)) for r in reqs}
    wanted: dict[str, str | None] = {}
    for r in reqs:
        if _status(signals[r.skill.slug]) != CONFIRMED:
            wanted.setdefault(r.skill.slug, None)
            for anc in graph.ancestors(r.skill.slug):
                if _status(signals[anc]) != CONFIRMED and anc not in wanted:
                    wanted[anc] = r.skill.name
    depth = {s: len(graph.ancestors(s)) for s in wanted}
    ordered = sorted(wanted, key=lambda s: (depth[s], -importance.get(s, 0.3), graph.names[s]))[:MAX_ITEMS]
    skills = {s.slug: s for s in Skill.objects.filter(slug__in=ordered)}
    resources = {}
    for res in LearningResource.objects.filter(skill__slug__in=ordered).order_by("id"):
        resources.setdefault(res.skill.slug, res)

    old = Roadmap.objects.filter(user=user, role=role, is_active=True)
    carried = {i.skill.slug: i for r in old for i in r.items.select_related("skill") if i.status != RoadmapItem.TODO}
    old.update(is_active=False)
    roadmap = Roadmap.objects.create(user=user, role=role)
    for pos, slug in enumerate(ordered, start=1):
        res, prev = resources.get(slug), carried.get(slug)
        name = graph.names[slug]
        RoadmapItem.objects.create(
            roadmap=roadmap, skill=skills[slug], position=pos, resource=res,
            reason=_reason(name, _status(signals[slug]), signals[slug], role.title, wanted[slug]),
            practice_task=res.practice_task if res else f"Write a small, self-contained exercise that uses {name} and keep it in your own repository.",
            completion_criteria=res.completion_criteria if res else "It runs, it is documented, and you can explain every line.",
            status=prev.status if prev else RoadmapItem.TODO, evidence_note=prev.evidence_note if prev else "",
            completed_at=prev.completed_at if prev else None)
    return roadmap


def active_roadmap(user, role: Role) -> Roadmap | None:
    return Roadmap.objects.filter(user=user, role=role, is_active=True).prefetch_related("items__skill", "items__resource").first()


@transaction.atomic
def complete_item(user, item: RoadmapItem, note: str = "") -> None:
    if item.roadmap.user_id != user.id:
        raise PermissionError("Not your roadmap item.")
    if item.status == RoadmapItem.DONE:
        return
    item.status, item.completed_at, item.evidence_note = RoadmapItem.DONE, timezone.now(), note.strip()[:1000]
    item.save(update_fields=["status", "completed_at", "evidence_note"])
    Evidence.objects.create(user=user, skill=item.skill, source=Evidence.PRACTICE, roadmap_item=item)


def set_status(user, item: RoadmapItem, status: str) -> None:
    if item.roadmap.user_id != user.id:
        raise PermissionError("Not your roadmap item.")
    if status in (RoadmapItem.TODO, RoadmapItem.DOING) and item.status != RoadmapItem.DONE:
        item.status = status
        item.save(update_fields=["status"])


def next_action(user, role: Role) -> dict | None:
    """The engine's single best next step, translated for the UI. Never points at a skill with no usable question."""
    graph = load_graph()
    _, profile = build_signals(user, graph)
    spec = RoleSpec(role.title, {r.skill.slug: r.importance for r in role.requirements.select_related("skill")})
    blocked = set(graph.skills()) - assessable_skills(user)
    action = recommend_next(profile, spec, exclude_assess=blocked)
    if action is None:
        return None
    out = {"kind": action.kind, "skill": action.skill, "skill_name": graph.names[action.skill], "reason": action.reason}
    if action.kind in ("assess", "reassess"):
        q = eligible_question(user, action.skill, action.difficulty)
        out["assessment_slug"] = q.assessment.slug if q else None
    return out
