import pytest

from apps.matching.scoring import Requirement, SkillSignals, score_requirements, skill_credit

W = {"required": 0.6, "preferred": 0.2, "experience": 0.2}
C = {"claimed": 0.2, "contextual": 0.5}
CAP = 0.5


def run(reqs, sigs, **kw):
    return score_requirements(reqs, sigs, weights=W, credits=C, undecided_cap=CAP, **kw)


def test_hand_computed_score_without_experience_component():
    reqs = [Requirement("python", "Python", "required"), Requirement("sql", "SQL", "required"),
            Requirement("docker", "Docker", "preferred")]
    sigs = {"python": SkillSignals(assessed=True, performance="demonstrated", mean=0.8, lower=0.6, n_assessments=4),
            "sql": SkillSignals(claimed=0.85)}
    r = run(reqs, sigs)
    # required = (0.8 + 0.2) / 2 = 0.5 ; preferred = 0 ; experience n/a -> weights 0.75 / 0.25
    assert r.score == pytest.approx(0.75 * 0.5 + 0.25 * 0.0)
    assert r.conservative == pytest.approx(0.75 * 0.3)            # (0.6 + 0) / 2 = 0.3
    assert r.components["experience"]["applied_weight"] == 0
    assert r.components["required"]["applied_weight"] == pytest.approx(0.75)
    assert r.evidence_coverage == pytest.approx(1 / 3, abs=1e-3) and r.confidence == "Moderate evidence"
    assert [s.slug for s in r.by_status("confirmed")] == ["python"]
    assert [s.slug for s in r.by_status("insufficient")] == ["sql"]
    assert [s.slug for s in r.by_status("missing", "preferred")] == ["docker"]


def test_experience_component_applies_when_both_sides_known():
    reqs = [Requirement("python", "Python", "required"), Requirement("docker", "Docker", "preferred")]
    r = run(reqs, {"python": SkillSignals(assessed=True, performance="demonstrated", mean=1.0, lower=1.0)},
            years_required=4, user_years=2)
    assert r.components["experience"]["value"] == 0.5
    assert r.score == pytest.approx(0.6 * 1.0 + 0.2 * 0.0 + 0.2 * 0.5)
    assert r.conservative == pytest.approx(0.6)                    # self-stated years are never verified evidence
    assert "self-stated" in r.experience_note


def test_unknown_user_years_excludes_experience_and_says_so():
    r = run([Requirement("python", "Python", "required")], {}, years_required=3, user_years=None)
    assert r.components["experience"]["applied_weight"] == 0 and "not stated" in r.experience_note or "have not stated" in r.experience_note


def test_no_requirements_never_becomes_a_perfect_score():
    r = run([], {})
    assert r.score is None and "no score was produced" in r.explanation[0]


def test_nothing_known_scores_zero_not_neutral():
    r = run([Requirement("python", "Python", "required")], {})
    assert r.score == 0 and r.evidence_coverage == 0 and r.confidence.startswith("Low")


def test_a_claim_is_worth_far_less_than_assessment_evidence():
    claimed = skill_credit(SkillSignals(claimed=1.0), C, CAP)
    tested = skill_credit(SkillSignals(assessed=True, performance="demonstrated", mean=0.85, lower=0.6), C, CAP)
    assert claimed[0] == "insufficient" and claimed[2] == 0.2 and claimed[3] == 0.0
    assert tested[0] == "confirmed" and tested[2] > claimed[2] * 3


def test_resume_context_counts_as_possible_not_confirmed():
    status, code, exp, cons = skill_credit(SkillSignals(resume="contextual"), C, CAP)
    assert (status, code, exp, cons) == ("possible", "evidence_supported", 0.5, 0.0)


def test_resume_listing_alone_is_a_claim():
    assert skill_credit(SkillSignals(resume="stated"), C, CAP)[:2] == ("insufficient", "resume_stated")
    assert skill_credit(SkillSignals(resume="stated", claimed=0.6), C, CAP)[1] == "self_and_resume"


def test_thin_assessment_evidence_is_capped():
    status, code, exp, _ = skill_credit(SkillSignals(assessed=True, performance="insufficient_evidence", mean=0.9, lower=0.5), C, CAP)
    assert status == "possible" and code == "insufficient_evidence" and exp == CAP


def test_assessed_gap_is_not_rescued_by_a_resume_claim():
    status, _, exp, _ = skill_credit(SkillSignals(assessed=True, performance="gap", mean=0.2, lower=0.05, resume="contextual"), C, CAP)
    assert status == "not_demonstrated" and exp == 0.2


def test_importance_weights_skills_unequally():
    reqs = [Requirement("a", "A", "required", importance=1.0), Requirement("b", "B", "required", importance=0.2)]
    sigs = {"a": SkillSignals(assessed=True, performance="demonstrated", mean=1.0, lower=1.0)}
    equal = run([Requirement("a", "A", "required"), Requirement("b", "B", "required")], sigs).score
    weighted = run(reqs, sigs).score
    assert weighted > equal


def test_explanation_matches_the_numbers():
    r = run([Requirement("python", "Python", "required")], {"python": SkillSignals(claimed=0.5)})
    assert any(f"{r.score:.3f}" in line for line in r.explanation)
    d = r.to_dict()
    assert d["score"] == r.score and d["skills"][0]["status"] == "insufficient"
