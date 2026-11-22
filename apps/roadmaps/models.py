from django.conf import settings
from django.db import models


class LearningResource(models.Model):
    """Curated, self-authored learning activities. `url` stays blank unless a real, checked link is supplied."""
    skill = models.ForeignKey("skills.Skill", on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=160)
    description = models.TextField()
    kind = models.CharField(max_length=20, default="exercise")
    url = models.URLField(blank=True)
    practice_task = models.TextField()
    completion_criteria = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["skill", "title"], name="unique_resource_title_per_skill")]


class Roadmap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roadmaps")
    role = models.ForeignKey("skills.Role", on_delete=models.CASCADE, related_name="+")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_active"])]


class RoadmapItem(models.Model):
    TODO, DOING, DONE = "todo", "doing", "done"
    roadmap = models.ForeignKey(Roadmap, on_delete=models.CASCADE, related_name="items")
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    position = models.PositiveSmallIntegerField()
    reason = models.TextField()
    resource = models.ForeignKey(LearningResource, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    practice_task = models.TextField()
    completion_criteria = models.TextField()
    status = models.CharField(max_length=5, choices=[(TODO, "To do"), (DOING, "In progress"), (DONE, "Done")], default=TODO)
    evidence_note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["roadmap", "skill"], name="unique_roadmap_skill")]
