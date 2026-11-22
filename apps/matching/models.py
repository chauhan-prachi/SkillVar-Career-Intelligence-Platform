from django.conf import settings
from django.db import models
from django.db.models import Q


class JobMatch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_matches")
    job = models.ForeignKey("jobs.JobDescription", on_delete=models.CASCADE, related_name="matches")
    score = models.FloatField()
    result = models.JSONField(default=dict)          # full breakdown so the stored number is always explainable
    formula_version = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [models.CheckConstraint(condition=Q(score__gte=0) & Q(score__lte=1), name="match_score_range")]


class ReadinessSnapshot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="readiness_snapshots")
    role = models.ForeignKey("skills.Role", on_delete=models.CASCADE, related_name="+")
    score = models.FloatField()
    conservative = models.FloatField()
    evidence_coverage = models.FloatField()
    result = models.JSONField(default=dict)
    formula_version = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["user", "role", "created_at"])]
        constraints = [models.CheckConstraint(condition=Q(score__gte=0) & Q(score__lte=1), name="readiness_score_range")]
