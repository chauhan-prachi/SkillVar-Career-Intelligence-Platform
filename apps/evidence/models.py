"""Append-only evidence log. A learner's skill profile is *rebuilt by replaying* these rows (plus the user's
reviewed resume skills), so every estimate can be explained from recorded facts. Rows are never edited."""
from django.conf import settings
from django.db import models
from django.db.models import Q


class Evidence(models.Model):
    SELF_REPORT, ASSESSMENT, PRACTICE = "self_report", "assessment", "practice"
    SOURCES = [(SELF_REPORT, "Self-reported"), (ASSESSMENT, "Assessment"), (PRACTICE, "Practical evidence")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="evidence")
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="evidence")
    source = models.CharField(max_length=12, choices=SOURCES)
    score = models.FloatField(null=True, blank=True)        # self-report level, or assessment score, in [0, 1]
    difficulty = models.FloatField(null=True, blank=True)
    weight = models.FloatField(default=1.0)                  # 0 = recorded for audit but not counted
    answer = models.OneToOneField("assessments.AnswerRecord", null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="evidence")
    roadmap_item = models.ForeignKey("roadmaps.RoadmapItem", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["user", "created_at"]), models.Index(fields=["user", "skill"])]
        constraints = [
            models.CheckConstraint(condition=Q(score__isnull=True) | (Q(score__gte=0) & Q(score__lte=1)),
                                   name="evidence_score_range"),
            models.CheckConstraint(condition=Q(weight__gte=0), name="evidence_weight_nonneg"),
            models.CheckConstraint(condition=~Q(source="assessment") | (Q(answer__isnull=False) & Q(score__isnull=False)
                                                                        & Q(difficulty__isnull=False)),
                                   name="assessment_evidence_complete"),
            models.CheckConstraint(condition=~Q(source="self_report") | Q(score__isnull=False),
                                   name="self_report_has_level"),
        ]
