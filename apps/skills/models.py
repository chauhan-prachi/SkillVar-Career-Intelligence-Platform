"""Skill taxonomy: one canonical definition of every skill, reused by resumes, jobs, assessments and roadmaps."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from .normalize import normalize_term


class SkillCategory(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "skill categories"

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120, unique=True)
    category = models.ForeignKey(SkillCategory, on_delete=models.PROTECT, related_name="skills")
    description = models.CharField(max_length=300, blank=True)
    related = models.ManyToManyField("self", blank=True)   # symmetrical "see also" links
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SkillAlias(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=120)
    normalized = models.CharField(max_length=120, unique=True, editable=False)  # one alias -> one skill, globally

    def save(self, *args, **kwargs):
        self.normalized = normalize_term(self.alias)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.alias} -> {self.skill.slug}"


class SkillPrerequisite(models.Model):
    """`skill` should be learned after `prerequisite`."""
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="prerequisite_links")
    prerequisite = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="unlocks_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["skill", "prerequisite"], name="unique_skill_prerequisite"),
            models.CheckConstraint(condition=~Q(skill=F("prerequisite")), name="skill_not_own_prerequisite"),
        ]


class Role(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class RoleRequirement(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="requirements")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="role_requirements")
    importance = models.FloatField(validators=[MinValueValidator(0.05), MaxValueValidator(1.0)])
    is_required = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "skill"], name="unique_role_skill"),
            models.CheckConstraint(condition=Q(importance__gt=0) & Q(importance__lte=1), name="role_importance_range"),
        ]
