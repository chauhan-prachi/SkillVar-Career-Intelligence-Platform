from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assessments.models import Assessment, Question
from apps.assessments.seed_bank import ASSESSMENTS, QUESTIONS
from apps.roadmaps.models import LearningResource
from apps.roadmaps.seed_resources import R
from apps.skills.models import Role, RoleRequirement, Skill, SkillAlias, SkillCategory, SkillPrerequisite
from apps.skills.normalize import normalize_term
from apps.skills.seed_data import CATEGORIES, ROLES, S


class Command(BaseCommand):
    help = "Load the curated taxonomy, roles, assessments and learning resources. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **opts):
        cats = {slug: SkillCategory.objects.update_or_create(slug=slug, defaults={"name": name, "position": i})[0]
                for i, (slug, name) in enumerate(CATEGORIES)}
        skills = {}
        for slug, (name, cat, aliases, _pre, _rel) in S.items():
            skill, _ = Skill.objects.update_or_create(slug=slug, defaults={"name": name, "category": cats[cat]})
            skills[slug] = skill
            for alias in aliases:
                SkillAlias.objects.update_or_create(normalized=normalize_term(alias), defaults={"alias": alias, "skill": skill})
        for slug, (_n, _c, _a, pre, rel) in S.items():
            for p in pre:
                SkillPrerequisite.objects.get_or_create(skill=skills[slug], prerequisite=skills[p])
            for r in rel:
                skills[slug].related.add(skills[r])
        for slug, (title, desc, reqs) in ROLES.items():
            role, _ = Role.objects.update_or_create(slug=slug, defaults={"title": title, "description": desc})
            for skill, importance, required in reqs:
                RoleRequirement.objects.update_or_create(role=role, skill=skills[skill],
                                                         defaults={"importance": importance, "is_required": required})
        assessments = {slug: Assessment.objects.update_or_create(
            slug=slug, defaults={"title": t, "description": d, "position": p})[0] for slug, t, d, p in ASSESSMENTS}
        for pos, q in enumerate(QUESTIONS):
            fields = {k: q[k] for k in ("kind", "prompt", "options", "correct_index", "explanation", "difficulty", "weight", "sql_config")}
            Question.objects.update_or_create(slug=q["slug"], defaults={
                **fields, "assessment": assessments[q["assessment"]], "skill": skills[q["skill"]], "position": pos})
        for skill, title, kind, desc, task, criteria in R:
            LearningResource.objects.update_or_create(skill=skills[skill], title=title, defaults={
                "description": desc, "kind": kind, "practice_task": task, "completion_criteria": criteria})
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(skills)} skills, {len(ROLES)} roles, {len(QUESTIONS)} questions, {len(R)} resources."))

