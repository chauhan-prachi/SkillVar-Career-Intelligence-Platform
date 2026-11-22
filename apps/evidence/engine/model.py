"""Evidence model: each skill is a Beta(alpha, beta) belief about mastery.

Design principles
* Self-claims are a *weak prior* and never count as demonstrated evidence.
* Assessments are evidence, weighted by item difficulty: passing a hard item
  says more than passing an easy one; failing an easy item says more than
  failing a hard one.
* Passing a skill gives small *inferred* support to its prerequisites
  (you probably know joins if you can write window functions), tracked
  separately from direct evidence.
* Uncertainty is first-class: every estimate carries a credible interval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

from .graph import SkillGraph

PRIOR_STRENGTH = 2.0      # pseudo-observations for an uninformed Beta(1,1)
CLAIM_STRENGTH = 1.0      # extra pseudo-observations a self-claim may add
INFER_DECAY = 0.35        # per-hop weight for prerequisite inference
Z90 = 1.645

# Thresholds for status classification
MIN_EVIDENCE = 2.0        # direct evidence weight needed to "verify" anything
MAX_INTERVAL = 0.50       # undecided AND wider than this = need more evidence
CONFIDENT_LOWER = 0.50    # lower bound needed to call a skill demonstrated
GAP_UPPER = 0.65          # upper bound below this = confident it is a gap
DEMONSTRATED_MEAN = 0.70
GAP_MEAN = 0.50


@dataclass
class SkillState:
    alpha: float = 1.0
    beta: float = 1.0
    claimed: float | None = None
    evidence_weight: float = 0.0     # direct assessment evidence only
    n_assessments: int = 0
    practiced_since_assessment: bool = False

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def std(self) -> float:
        n = self.alpha + self.beta
        return sqrt(self.alpha * self.beta / (n * n * (n + 1)))

    @property
    def interval(self) -> tuple[float, float]:
        m, s = self.mean, self.std
        return max(0.0, m - Z90 * s), min(1.0, m + Z90 * s)

    @property
    def lower(self) -> float:
        return self.interval[0]

    @property
    def width(self) -> float:
        lo, hi = self.interval
        return hi - lo

    @property
    def status(self) -> str:
        """Decision-based: is the interval confidently above/below mastery?"""
        if self.evidence_weight < MIN_EVIDENCE:
            if self.evidence_weight == 0:
                return "unverified_claim" if self.claimed is not None else "unknown"
            return "insufficient_evidence"
        lo, hi = self.interval
        if self.mean >= DEMONSTRATED_MEAN and lo >= CONFIDENT_LOWER:
            return "demonstrated"
        if hi < GAP_UPPER:
            return "gap"
        if self.width > MAX_INTERVAL:
            return "insufficient_evidence"
        return "developing"


@dataclass
class LearnerProfile:
    graph: SkillGraph
    states: dict[str, SkillState] = field(default_factory=dict)
    log: list[dict] = field(default_factory=list)

    def state(self, skill: str) -> SkillState:
        if skill not in self.graph:
            raise KeyError(skill)
        return self.states.setdefault(skill, SkillState())

    def claim(self, skill: str, level: float) -> None:
        """Record a self-reported level in [0,1]. Weak prior only."""
        st = self.state(skill)
        level = min(max(level, 0.0), 1.0)
        if st.claimed is not None or st.n_assessments:
            return  # claims never override evidence
        st.claimed = level
        st.alpha = 1.0 + CLAIM_STRENGTH * level
        st.beta = 1.0 + CLAIM_STRENGTH * (1 - level)

    def record_assessment(self, skill: str, score: float, difficulty: float,
                          weight: float = 1.0) -> None:
        """score in [0,1] (partial credit allowed); difficulty in [0,1].

        ``weight`` scales how much this item counts (e.g. guessable multiple
        choice < auto-graded code; repeated items < fresh items)."""
        score = min(max(score, 0.0), 1.0)
        d = min(max(difficulty, 0.0), 1.0)
        w_pass, w_fail = (0.5 + d) * weight, (1.5 - d) * weight
        st = self.state(skill)
        st.alpha += score * w_pass
        st.beta += (1 - score) * w_fail
        st.evidence_weight += score * w_pass + (1 - score) * w_fail
        st.n_assessments += 1
        st.practiced_since_assessment = False
        # inferred support for prerequisites (passes only)
        if score > 0.5:
            for anc, hops in self.graph.ancestors(skill).items():
                a = self.state(anc)
                a.alpha += (score - 0.5) * 2 * w_pass * (INFER_DECAY ** hops)
        self.log.append({"type": "assessment", "skill": skill, "score": score,
                         "difficulty": d, "weight": weight, "mean_after": round(st.mean, 3)})

    def note_practice(self, skill: str) -> None:
        self.state(skill).practiced_since_assessment = True
        self.log.append({"type": "practice", "skill": skill})

    def summary(self) -> dict[str, dict]:
        out = {}
        for s in self.graph.skills():
            st = self.states.get(s)
            if st is None:
                continue
            lo, hi = st.interval
            out[s] = {"mean": round(st.mean, 2), "low": round(lo, 2), "high": round(hi, 2),
                      "status": st.status, "evidence": round(st.evidence_weight, 1)}
        return out
