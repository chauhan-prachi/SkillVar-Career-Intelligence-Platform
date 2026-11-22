import pytest
from django.db import IntegrityError, transaction

from apps.evidence.profile import load_graph
from apps.skills.models import Role, RoleRequirement, Skill, SkillAlias, SkillCategory, SkillPrerequisite


@pytest.mark.django_db
def test_seed_is_idempotent(seeded):
    from django.core.management import call_command
    before = (Skill.objects.count(), SkillAlias.objects.count(), SkillPrerequisite.objects.count(), RoleRequirement.objects.count())
    call_command("seed_data", verbosity=0)
    assert before == (Skill.objects.count(), SkillAlias.objects.count(), SkillPrerequisite.objects.count(), RoleRequirement.objects.count())
    assert before[0] >= 60


def test_taxonomy_graph_is_acyclic_and_complete(seeded):
    graph = load_graph()
    graph.validate()          # raises on a cycle or an undefined prerequisite
    assert "sql" in graph.ancestors("sql-window-functions")


def test_every_role_requirement_points_at_an_existing_active_skill(seeded):
    for r in RoleRequirement.objects.select_related("skill"):
        assert r.skill.is_active and 0 < r.importance <= 1


def test_every_assessed_skill_exists_in_the_taxonomy(seeded):
    from apps.assessments.models import Question
    assert Question.objects.filter(skill__isnull=True).count() == 0 and Question.objects.count() >= 40


def test_alias_is_globally_unique_after_normalisation(seeded):
    sql = Skill.objects.get(slug="sql")
    with pytest.raises(IntegrityError), transaction.atomic():
        SkillAlias.objects.create(skill=sql, alias="Postgres")        # already an alias of PostgreSQL
    with pytest.raises(IntegrityError), transaction.atomic():
        SkillAlias.objects.create(skill=sql, alias="POSTGRES!")      # differs only by case/punctuation


def test_alias_normalisation_is_stored(seeded):
    assert SkillAlias.objects.get(alias="postgres").normalized == "postgres"


def test_skill_cannot_be_its_own_prerequisite(seeded):
    sql = Skill.objects.get(slug="sql")
    with pytest.raises(IntegrityError), transaction.atomic():
        SkillPrerequisite.objects.create(skill=sql, prerequisite=sql)


def test_duplicate_prerequisite_rejected(seeded):
    link = SkillPrerequisite.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        SkillPrerequisite.objects.create(skill=link.skill, prerequisite=link.prerequisite)


@pytest.mark.parametrize("importance", [0, -0.1, 1.5])
def test_role_importance_range_enforced(seeded, importance):
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleRequirement.objects.create(role=Role.objects.first(), skill=Skill.objects.get(slug="docker"), importance=importance)


def test_role_skill_pair_is_unique(seeded):
    r = RoleRequirement.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleRequirement.objects.create(role=r.role, skill=r.skill, importance=0.5)


def test_skill_in_use_cannot_be_deleted_silently(seeded):
    with pytest.raises(Exception):  # noqa: B017 - ProtectedError
        Skill.objects.get(slug="python").delete()


def test_category_with_skills_is_protected(seeded):
    with pytest.raises(Exception):  # noqa: B017
        SkillCategory.objects.get(slug="databases").delete()


def test_migrations_are_consistent(db):
    from django.core.management import call_command
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)    # raises SystemExit if a migration is missing
