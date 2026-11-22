import pytest

from apps.assessments import services as assess
from apps.assessments.models import Assessment, Question
from apps.evidence.models import Evidence
from apps.evidence.tests.test_profile import answer
from apps.roadmaps import services
from apps.roadmaps.models import Roadmap, RoadmapItem
from apps.skills.models import Skill


def order(rm):
    return [i.skill.slug for i in rm.items.all()]


def test_roadmap_lists_unproven_role_skills_prerequisites_first(goal_user):
    rm = services.generate_roadmap(goal_user, goal_user.profile.career_goal)
    slugs = order(rm)
    assert "sql" in slugs and "python" in slugs and len(slugs) == 12                     # capped
    assert "sql-joins" in slugs and slugs.index("sql") < slugs.index("sql-joins")      # prerequisites come first
    positions = [i.position for i in rm.items.all()]
    assert positions == sorted(positions) == list(range(1, len(positions) + 1))
    first = rm.items.first()
    assert first.reason and first.practice_task and first.completion_criteria


def test_every_item_explains_why(goal_user):
    for i in services.generate_roadmap(goal_user, goal_user.profile.career_goal).items.all():
        assert len(i.reason) > 30 and i.skill.name in i.reason


def test_confirmed_skills_are_left_out(goal_user):
    for _ in range(4):
        answer(goal_user, "sql", 1.0)
    assert "sql" not in order(services.generate_roadmap(goal_user, goal_user.profile.career_goal))


def test_prerequisite_only_items_say_what_they_unlock(goal_user, monkeypatch):
    monkeypatch.setattr(services, "MAX_ITEMS", 60)           # database-design is not a role skill; it is only a prerequisite
    rm = services.generate_roadmap(goal_user, goal_user.profile.career_goal)
    item = rm.items.get(skill__slug="database-design")
    assert "prerequisite of Data modeling" in item.reason
    assert [i.skill.slug for i in rm.items.all()].index("database-design") < [i.skill.slug for i in rm.items.all()].index("data-modeling")


def test_curated_resource_is_used_and_generic_fallback_is_labelled(goal_user):
    rm = services.generate_roadmap(goal_user, goal_user.profile.career_goal)
    sql = rm.items.get(skill__slug="sql")
    assert sql.resource is not None and sql.resource.title == "Filter and sort drill"
    RoadmapItem.objects.filter(pk=sql.pk).update(resource=None)
    from apps.roadmaps.models import LearningResource
    LearningResource.objects.all().delete()
    rm2 = services.generate_roadmap(goal_user, goal_user.profile.career_goal)
    assert "self-contained exercise" in rm2.items.first().practice_task and all(i.resource is None for i in rm2.items.all())


def test_regeneration_keeps_one_active_roadmap_and_carries_progress(goal_user):
    role = goal_user.profile.career_goal
    first = services.generate_roadmap(goal_user, role)
    item = first.items.get(skill__slug="python")
    services.complete_item(goal_user, item, "built the exercise")
    second = services.generate_roadmap(goal_user, role)
    assert Roadmap.objects.filter(user=goal_user, is_active=True).count() == 1 and not Roadmap.objects.get(pk=first.pk).is_active
    carried = second.items.get(skill__slug="python")
    assert carried.status == "done" and carried.evidence_note == "built the exercise"


def test_completing_an_item_records_practical_evidence_and_unlocks_a_retest(goal_user):
    q = Question.objects.get(slug="py-listcomp")
    a = Assessment.objects.get(slug="python-fundamentals")
    assess.submit_attempt(goal_user, a, {q.id: "0"})
    assert not assess.is_eligible(goal_user, q)
    rm = services.generate_roadmap(goal_user, goal_user.profile.career_goal)
    services.complete_item(goal_user, rm.items.get(skill__slug="python"), "done")
    assert Evidence.objects.filter(user=goal_user, source="practice", skill__slug="python").count() == 1
    assert assess.is_eligible(goal_user, q)


def test_completing_twice_does_not_duplicate_evidence(goal_user):
    item = services.generate_roadmap(goal_user, goal_user.profile.career_goal).items.first()
    services.complete_item(goal_user, item); services.complete_item(goal_user, item)
    assert Evidence.objects.filter(source="practice").count() == 1


def test_users_cannot_complete_each_others_items(goal_user, other_user):
    item = services.generate_roadmap(goal_user, goal_user.profile.career_goal).items.first()
    with pytest.raises(PermissionError):
        services.complete_item(other_user, item)
    with pytest.raises(PermissionError):
        services.set_status(other_user, item, "doing")


def test_status_can_move_between_todo_and_doing_but_not_away_from_done(goal_user):
    item = services.generate_roadmap(goal_user, goal_user.profile.career_goal).items.first()
    services.set_status(goal_user, item, "doing"); item.refresh_from_db(); assert item.status == "doing"
    services.complete_item(goal_user, item)
    services.set_status(goal_user, item, "todo"); item.refresh_from_db(); assert item.status == "done"


def test_roadmap_for_a_fully_confirmed_role_is_empty(goal_user):
    role = goal_user.profile.career_goal
    for r in role.requirements.select_related("skill"):
        for _ in range(4):
            answer(goal_user, r.skill.slug, 1.0)
    assert list(services.generate_roadmap(goal_user, role).items.all()) == []


# ---------- next action (engine) ----------
def test_next_action_for_a_new_learner_is_an_assessment_with_a_real_question(goal_user):
    action = services.next_action(goal_user, goal_user.profile.career_goal)
    assert action["kind"] == "assess" and action["assessment_slug"] and Assessment.objects.filter(slug=action["assessment_slug"]).exists()


def test_next_action_never_points_at_an_exhausted_skill(goal_user):
    role = goal_user.profile.career_goal
    seen = set()
    for _ in range(60):
        a = services.next_action(goal_user, role)
        if a is None or a["kind"] != "assess":
            break
        q = assess.eligible_question(goal_user, a["skill"])
        assert q is not None and q.id not in seen, "the recommender offered an item that cannot produce evidence"
        seen.add(q.id)
        assess.submit_attempt(goal_user, q.assessment, {q.id: "0" if q.kind == "mcq" else "SELECT 1"})


def test_next_action_recommends_practice_then_a_retest_after_failures(goal_user):
    role = goal_user.profile.career_goal
    practice = None
    for _ in range(80):
        a = services.next_action(goal_user, role)
        if a is None:
            break
        if a["kind"] == "practice":
            practice = a
            break
        q = assess.eligible_question(goal_user, a["skill"])
        assess.submit_attempt(goal_user, q.assessment, {q.id: "0" if q.kind == "mcq" else "SELECT 1"})
    assert practice is not None and practice["reason"]
    Evidence.objects.create(user=goal_user, skill=Skill.objects.get(slug=practice["skill"]), source="practice")
    again = services.next_action(goal_user, role)
    assert again is not None and again["kind"] == "reassess" and again["skill"] == practice["skill"]   # re-test after practice


# ---------- views ----------
def test_roadmap_page_flow(goal_client, goal_user):
    assert "Generate my roadmap" in goal_client.get("/roadmap/").content.decode()
    assert goal_client.post("/roadmap/generate/").status_code == 302
    page = goal_client.get("/roadmap/").content.decode()
    assert "Practice task" in page and "You are done when" in page and "Mark done" in page
    item = RoadmapItem.objects.first()
    assert goal_client.post(f"/roadmap/items/{item.pk}/", {"action": "complete", "note": "link"}).status_code == 302
    assert RoadmapItem.objects.get(pk=item.pk).status == "done"


def test_roadmap_item_actions_are_private(goal_client, goal_user, client, other_user):
    item = services.generate_roadmap(goal_user, goal_user.profile.career_goal).items.first()
    client.force_login(other_user)
    assert client.post(f"/roadmap/items/{item.pk}/", {"action": "complete"}).status_code == 404
    assert RoadmapItem.objects.get(pk=item.pk).status == "todo"


def test_roadmap_requires_a_goal(client, user):
    client.force_login(user)
    assert client.get("/roadmap/").url == "/accounts/onboarding/"
