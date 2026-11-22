"""Explainable match / readiness scoring. PURE functions: no Django, no database, fully unit-testable.

Per-skill credit (what a requirement is worth given the evidence behind it):
  assessment-tested  -> the engine's posterior mean (conservative: the interval's lower bound)
  resume, contextual -> MATCH_CREDITS["contextual"]   (skill shown in experience/projects; not proof)
  claimed / resume-stated -> MATCH_CREDITS["claimed"] (a claim; not proof)
  nothing            -> 0
Unverified evidence contributes nothing to the *conservative* score.

Overall = sum(weight_i * component_i) over the components that apply, weights renormalised so a missing
component can never silently inflate the score. This is a product heuristic, NOT a hiring probability."""
from __future__ import annotations

from dataclasses import dataclass, field

# evidence classes
CONFIRMED, POSSIBLE, INSUFFICIENT, NOT_DEMONSTRATED, MISSING = (
    "confirmed", "possible", "insufficient", "not_demonstrated", "missing")
CLASS_LABELS = {CONFIRMED: "Confirmed match", POSSIBLE: "Possible match", INSUFFICIENT: "Insufficient evidence",
                NOT_DEMONSTRATED: "Not demonstrated", MISSING: "Missing"}
LABELS = {
    "assessment_tested": "Assessment",
    "evidence_supported": "Projects / experience",
    "insufficient_evidence": "Limited evidence",
    "self_reported": "Self-reported",
    "resume_stated": "Resume",
    "self_and_resume": "Resume + self-reported",
    "none": "No evidence",
}


@dataclass
class SkillSignals:
    """Everything known about one skill for one person (built from the database by evidence.profile)."""
    claimed: float | None = None
    resume: str | None = None          # None | "stated" | "contextual"
    assessed: bool = False             # any counted assessment evidence
    performance: str = "unknown"       # engine status: demonstrated | developing | gap | insufficient_evidence | ...
    mean: float = 0.5
    lower: float = 0.0
    n_assessments: int = 0


@dataclass
class Requirement:
    slug: str
    name: str
    kind: str                          # "required" | "preferred"
    importance: float = 1.0
    origin: str = "explicit"


@dataclass
class SkillScore:
    slug: str
    name: str
    kind: str
    importance: float
    status: str
    label_code: str
    expected: float
    conservative: float

    @property
    def status_label(self) -> str:
        return CLASS_LABELS[self.status]

    @property
    def label(self) -> str:
        return LABELS[self.label_code]


def skill_credit(sig: SkillSignals, credits: dict[str, float], cap: float) -> tuple[str, str, float, float]:
    """-> (status, label_code, expected, conservative)"""
    resume_credit = credits["contextual"] if sig.resume == "contextual" else (credits["claimed"] if sig.resume else 0.0)
    claim_credit = credits["claimed"] if sig.claimed is not None else 0.0
    unverified = max(resume_credit, claim_credit)
    if sig.assessed:
        if sig.performance == "demonstrated":
            return CONFIRMED, "assessment_tested", sig.mean, sig.lower
        if sig.performance == "gap":
            return NOT_DEMONSTRATED, "assessment_tested", sig.mean, sig.lower
        if sig.performance == "developing":
            return POSSIBLE, "assessment_tested", sig.mean, sig.lower
        return POSSIBLE, "insufficient_evidence", min(max(sig.mean, unverified), cap), min(sig.lower, cap)
    if sig.resume == "contextual":
        return POSSIBLE, "evidence_supported", credits["contextual"], 0.0
    if sig.resume and sig.claimed is not None:
        return INSUFFICIENT, "self_and_resume", unverified, 0.0
    if sig.resume:
        return INSUFFICIENT, "resume_stated", unverified, 0.0
    if sig.claimed is not None:
        return INSUFFICIENT, "self_reported", unverified, 0.0
    return MISSING, "none", 0.0, 0.0


@dataclass
class MatchResult:
    score: float | None
    conservative: float | None
    evidence_coverage: float
    confidence: str
    components: dict = field(default_factory=dict)
    skills: list[SkillScore] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    experience_note: str = ""

    def by_status(self, status: str, kind: str | None = None) -> list[SkillScore]:
        return [s for s in self.skills if s.status == status and (kind is None or s.kind == kind)]

    def to_dict(self) -> dict:
        return {"score": self.score, "conservative": self.conservative, "evidence_coverage": self.evidence_coverage,
                "confidence": self.confidence, "components": self.components, "explanation": self.explanation,
                "experience_note": self.experience_note,
                "skills": [{"slug": s.slug, "name": s.name, "kind": s.kind, "importance": s.importance,
                            "status": s.status, "label_code": s.label_code, "expected": round(s.expected, 4),
                            "conservative": round(s.conservative, 4)} for s in self.skills]}


def _coverage(items: list[SkillScore], attr: str) -> float | None:
    total = sum(i.importance for i in items)
    return None if total == 0 else sum(i.importance * getattr(i, attr) for i in items) / total


def score_requirements(requirements: list[Requirement], signals: dict[str, SkillSignals], *, weights: dict[str, float],
                       credits: dict[str, float], undecided_cap: float, years_required: float | None = None,
                       user_years: float | None = None) -> MatchResult:
    scored = []
    for r in requirements:
        status, code, exp, cons = skill_credit(signals.get(r.slug, SkillSignals()), credits, undecided_cap)
        scored.append(SkillScore(r.slug, r.name, r.kind, r.importance, status, code, exp, cons))
    required = [s for s in scored if s.kind == "required"]
    preferred = [s for s in scored if s.kind == "preferred"]

    exp_fit, exp_note = None, ""
    if years_required is not None:
        if user_years is None:
            exp_note = f"The posting asks for {years_required:g}+ years, but you have not stated your years of experience, so experience was left out of the score."
        else:
            exp_fit = min(1.0, user_years / years_required) if years_required > 0 else 1.0
            exp_note = f"You stated {user_years:g} years against {years_required:g}+ requested (self-stated, not verified)."

    comps = {"required": {"value": _coverage(required, "expected"), "cons": _coverage(required, "conservative")},
             "preferred": {"value": _coverage(preferred, "expected"), "cons": _coverage(preferred, "conservative")},
             "experience": {"value": exp_fit, "cons": 0.0 if exp_fit is not None else None}}
    applicable = [k for k, c in comps.items() if c["value"] is not None]
    nominal = sum(weights[k] for k in applicable)
    for k, c in comps.items():
        c["nominal_weight"] = weights[k]
        c["applied_weight"] = round(weights[k] / nominal, 4) if k in applicable and nominal else 0.0
    if not applicable:
        return MatchResult(None, None, 0.0, "No requirements to score", comps, scored,
                           ["There were no requirements to compare, so no score was produced."], exp_note)

    score = sum(comps[k]["applied_weight"] * comps[k]["value"] for k in applicable)
    cons = sum(comps[k]["applied_weight"] * comps[k]["cons"] for k in applicable)
    total_imp = sum(s.importance for s in scored)
    backed = sum(s.importance for s in scored if s.label_code in ("assessment_tested", "evidence_supported", "insufficient_evidence"))
    coverage = backed / total_imp if total_imp else 0.0
    confidence = ("Higher evidence" if coverage >= 0.6 else "Moderate evidence" if coverage >= 0.3
                  else "Low evidence (mostly unverified)")
    lines = []
    for k, label in (("required", "Required skills"), ("preferred", "Preferred skills"), ("experience", "Experience")):
        c = comps[k]
        if c["value"] is None:
            lines.append(f"{label}: not applicable, so its {c['nominal_weight']:.0%} weight was redistributed.")
        else:
            lines.append(f"{label}: {c['value']:.2f} x weight {c['applied_weight']:.2f} = {c['value'] * c['applied_weight']:.3f}")
    lines.append(f"Overall = {score:.3f}. Conservative (verified evidence only) = {cons:.3f}.")
    return MatchResult(round(score, 4), round(cons, 4), round(coverage, 4), confidence, comps, scored, lines, exp_note)
