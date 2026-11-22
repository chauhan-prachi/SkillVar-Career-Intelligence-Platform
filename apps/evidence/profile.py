"""Build a learner's skill signals by replaying their evidence (and reviewed resume skills) through the engine."""
from __future__ import annotations

from collections import defaultdict

from apps.matching.scoring import SkillSignals
from apps.resumes.models import ResumeSkill
from apps.skills.models import Skill, SkillPrerequisite

from .engine import LearnerProfile, SkillGraph
from .models import Evidence


def load_graph() -> SkillGraph:
    graph = SkillGraph()
    prereqs: dict[str, list[str]] = defaultdict(list)
    for slug, pre in SkillPrerequisite.objects.values_list("skill__slug", "prerequisite__slug"):
        prereqs[slug].append(pre)
    for slug, name in Skill.objects.values_list("slug", "name"):
        graph.add(slug, name, prereqs[slug])
    graph.validate()
    return graph


def replay(user, graph: SkillGraph | None = None) -> LearnerProfile:
    """Rules: only the latest self-report made before a skill's first counted assessment is used (claims can be
    revised, never override evidence); weight-0 assessment rows are audit-only; practice marks 'practised'."""
    profile = LearnerProfile(graph or load_graph())
    events = list(Evidence.objects.filter(user=user).select_related("skill"))
    first_assessment: dict[int, int] = {}
    for ev in events:
        if ev.source == Evidence.ASSESSMENT and ev.weight > 0:
            first_assessment.setdefault(ev.skill_id, ev.id)
    effective_claim: dict[int, int] = {}
    for ev in events:
        if ev.source == Evidence.SELF_REPORT and ev.id < first_assessment.get(ev.skill_id, float("inf")):
            effective_claim[ev.skill_id] = ev.id
    for ev in events:
        slug = ev.skill.slug
        if ev.source == Evidence.SELF_REPORT:
            if effective_claim.get(ev.skill_id) == ev.id:
                profile.claim(slug, ev.score)
        elif ev.source == Evidence.ASSESSMENT:
            if ev.weight > 0:
                profile.record_assessment(slug, ev.score, ev.difficulty, ev.weight)
        elif ev.source == Evidence.PRACTICE:
            profile.note_practice(slug)
    return profile


def resume_tiers(user) -> dict[str, str]:
    """slug -> 'contextual' | 'stated' from the user's non-rejected resume skills (contextual wins)."""
    tiers: dict[str, str] = {}
    qs = ResumeSkill.objects.filter(resume__user=user).exclude(review=ResumeSkill.REJECTED).select_related("skill")
    for rs in qs:
        tier = "contextual" if rs.contextual else "stated"
        if tiers.get(rs.skill.slug) != "contextual":
            tiers[rs.skill.slug] = tier
    return tiers


def build_signals(user, graph: SkillGraph | None = None) -> tuple[dict[str, SkillSignals], LearnerProfile]:
    profile = replay(user, graph)
    tiers = resume_tiers(user)
    signals: dict[str, SkillSignals] = {}
    for slug in profile.graph.skills():
        st = profile.states.get(slug)
        assessed = bool(st and st.evidence_weight > 0)
        signals[slug] = SkillSignals(
            claimed=st.claimed if st else None, resume=tiers.get(slug), assessed=assessed,
            performance=st.status if st else "unknown", mean=st.mean if st else 0.5,
            lower=st.lower if st else 0.0, n_assessments=st.n_assessments if st else 0)
    return signals, profile
