"""Next-best-action: assess when unsure, diagnose prerequisites when failing,
practice when the gap is clear, re-assess after practice."""
from __future__ import annotations

from dataclasses import dataclass

from .model import DEMONSTRATED_MEAN, LearnerProfile
from .types import RoleSpec as Role


@dataclass
class Action:
    kind: str          # assess | reassess | practice
    skill: str
    reason: str
    priority: float
    difficulty: float = 0.5


def _difficulty_for(mean: float) -> float:
    return min(max(mean, 0.25), 0.85)   # probe near current belief = most informative


def _root_cause(profile: LearnerProfile, skill: str) -> str:
    """Deepest prerequisite that is not yet demonstrated (weakest first)."""
    g = profile.graph
    pending = [p for p in g.prerequisites(skill) if profile.state(p).status != "demonstrated"]
    if not pending:
        return skill
    return _root_cause(profile, min(pending, key=lambda p: profile.state(p).mean))


def recommend_next(profile: LearnerProfile, role: Role,
                   exclude_assess: frozenset[str] | set[str] = frozenset()) -> Action | None:
    """Pick the single most valuable next action.

    ``exclude_assess`` lists skills with no available assessment item, so the
    recommender never points the learner at a dead end."""
    g = profile.graph
    candidates: list[Action] = []
    for skill, imp in role.requirements.items():
        st = profile.state(skill)
        name = g.names[skill]
        if st.practiced_since_assessment:
            candidates.append(Action("reassess", skill,
                f"You practiced {name}; re-test to measure whether it helped.", imp * 1.2,
                _difficulty_for(st.mean)))
            continue
        status = st.status
        if status == "demonstrated":
            continue
        # Prerequisite-aware: a confirmed upstream gap blocks everything downstream.
        blockers = [p for p in g.ancestors(skill) if profile.state(p).status == "gap"]
        if blockers:
            root = min(blockers, key=lambda p: profile.state(p).mean)
            if profile.state(root).practiced_since_assessment:
                candidates.append(Action("reassess", root,
                    f"You practiced {g.names[root]}, a prerequisite of {name}; re-test it.",
                    imp * 1.2, _difficulty_for(profile.state(root).mean)))
                continue
            candidates.append(Action("practice", root,
                f"{name} depends on {g.names[root]}, which is a confirmed gap "
                f"(est. {profile.state(root).mean:.0%}); fix the root cause first.",
                imp * (0.3 + DEMONSTRATED_MEAN - profile.state(root).mean) * 1.1))
            continue
        if status in ("unknown", "unverified_claim", "insufficient_evidence"):
            why = ("Claimed but unverified" if status == "unverified_claim"
                   else "Not enough evidence yet")
            candidates.append(Action("assess", skill,
                f"{why} for {name}; a short assessment will settle it.",
                imp * (0.2 + 0.5 * st.width) / (1 + 0.3 * st.n_assessments), _difficulty_for(st.mean)))
            continue
        # No confirmed upstream gap. Work from the deepest non-demonstrated prerequisite.
        root = _root_cause(profile, skill)
        rst = profile.state(root)
        rname = g.names[root]
        # priority reflects the loss on the *required* skill, even when we act on an upstream cause
        pri = imp * ((0.3 if status == "gap" else 0.0) + max(DEMONSTRATED_MEAN - st.mean, 0.05))
        if rst.practiced_since_assessment:
            candidates.append(Action("reassess", root,
                f"You practiced {rname}; re-test it to measure whether it helped.",
                imp * 1.2, _difficulty_for(rst.mean)))
        elif rst.status in ("gap", "developing"):
            label = "Clear gap" if rst.status == "gap" else "Still developing"
            why = (f"{label} in {rname} (est. {rst.mean:.0%})." if root == skill else
                   f"{name} builds on {rname}, which is not yet solid (est. {rst.mean:.0%}).")
            candidates.append(Action("practice", root, why + " Targeted practice.", pri))
        else:
            candidates.append(Action("assess", root,
                f"Need more evidence on {rname}"
                + ("" if root == skill else f" (prerequisite of {name})") + ".",
                pri, _difficulty_for(rst.mean)))
    candidates = [c for c in candidates
                  if c.kind == "practice" or c.skill not in exclude_assess]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a.priority)
