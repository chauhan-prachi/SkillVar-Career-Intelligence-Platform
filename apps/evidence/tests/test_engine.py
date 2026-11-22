import pytest

from apps.evidence.engine import LearnerProfile, RoleSpec, SkillGraph, recommend_next


def graph():
    g = SkillGraph()
    g.add("sql", "SQL"); g.add("joins", "Joins", ["sql"]); g.add("agg", "Aggregation", ["sql"])
    g.add("window", "Window functions", ["joins", "agg"]); g.add("py", "Python"); g.add("etl", "ETL", ["py", "joins"])
    g.validate()
    return g


ROLE = RoleSpec("DE", {"sql": 1.0, "joins": 0.8, "window": 0.7, "py": 1.0, "etl": 0.9})


def fresh():
    return LearnerProfile(graph())


def test_cycle_is_rejected():
    g = SkillGraph(); g.add("a", "A", ["b"]); g.add("b", "B", ["a"])
    with pytest.raises(ValueError):
        g.validate()


def test_ancestors_distance():
    anc = graph().ancestors("window")
    assert anc["joins"] == 1 and anc["sql"] == 2


def test_claim_is_not_demonstrated():
    p = fresh(); p.claim("sql", 1.0)
    st = p.state("sql")
    assert st.status == "unverified_claim" and st.evidence_weight == 0


def test_claims_never_override_evidence():
    p = fresh()
    for _ in range(3): p.record_assessment("sql", 0.0, 0.5)
    before = p.state("sql").mean
    p.claim("sql", 1.0)
    assert p.state("sql").mean == before


def test_difficulty_weighting_both_directions():
    a, b = fresh(), fresh()
    a.record_assessment("sql", 1.0, 0.9); b.record_assessment("sql", 1.0, 0.1)
    assert a.state("sql").mean > b.state("sql").mean
    c, d = fresh(), fresh()
    c.record_assessment("sql", 0.0, 0.1); d.record_assessment("sql", 0.0, 0.9)
    assert c.state("sql").mean < d.state("sql").mean


def test_weight_scales_evidence_and_zero_weight_changes_nothing():
    a, b = fresh(), fresh()
    a.record_assessment("sql", 1.0, 0.5, weight=1.0); b.record_assessment("sql", 1.0, 0.5, weight=0.5)
    assert a.state("sql").mean > b.state("sql").mean
    c = fresh(); before = c.state("sql").mean
    c.record_assessment("sql", 1.0, 0.5, weight=0.0)
    assert c.state("sql").mean == before


def test_uncertainty_shrinks_with_evidence():
    p = fresh(); w0 = p.state("agg").width
    for _ in range(6): p.record_assessment("agg", 1.0, 0.6)
    assert p.state("agg").width < w0 and p.state("agg").status == "demonstrated"


def test_passing_a_hard_skill_lifts_prerequisites_without_verifying_them():
    p = fresh()
    for _ in range(3): p.record_assessment("window", 1.0, 0.8)
    assert p.state("joins").mean > 0.55 and p.state("joins").evidence_weight == 0


def test_recommender_assesses_unverified_claim():
    p = fresh(); p.claim("etl", 0.9)
    assert recommend_next(p, ROLE).kind in ("assess", "reassess")


def test_recommender_finds_root_cause():
    p = fresh()
    for _ in range(4): p.record_assessment("joins", 0.0, 0.4)
    for _ in range(4): p.record_assessment("window", 0.0, 0.5)
    a = recommend_next(p, ROLE)
    assert a.kind == "practice" and a.skill in ("joins", "sql", "agg")


def test_reassess_after_practice():
    p = fresh()
    for _ in range(4): p.record_assessment("etl", 0.0, 0.5)
    p.note_practice("etl")
    a = recommend_next(p, ROLE)
    assert a.kind == "reassess" and a.skill == "etl"


def test_practised_upstream_root_cause_is_reassessed_not_practised_again():
    p = fresh()
    for _ in range(4): p.record_assessment("joins", 0.0, 0.4)
    for _ in range(4): p.record_assessment("etl", 0.0, 0.5)
    p.note_practice("joins")
    a = recommend_next(p, ROLE)
    assert a.kind == "reassess" and a.skill == "joins"


def test_excluded_skills_are_never_offered_for_assessment():
    p = fresh(); p.claim("etl", 0.9)
    a = recommend_next(p, ROLE, exclude_assess={"etl", "py", "sql", "joins", "window", "agg"})
    assert a is None or a.kind == "practice"
