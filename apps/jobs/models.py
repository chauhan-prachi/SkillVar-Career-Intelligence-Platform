from django.conf import settings
from django.db import models
from django.db.models import Q


class JobDescription(models.Model):
    PASTED, DATASET = "pasted", "dataset"
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                             related_name="job_descriptions")   # NULL = shared reference data (dataset)
    source = models.CharField(max_length=10, choices=[(PASTED, "Pasted by user"), (DATASET, "Dataset")], default=PASTED)
    is_synthetic = models.BooleanField(default=False)
    title = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    raw_text = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True)
    years_required = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    education_required = models.CharField(max_length=120, blank=True)
    responsibilities = models.JSONField(default=list, blank=True)
    ingestion_run = models.ForeignKey("dataops.IngestionRun", null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="jobs")
    analysis_version = models.CharField(max_length=10, default="1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"]), models.Index(fields=["source", "-created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["content_hash"], condition=Q(user__isnull=True), name="unique_shared_job_content"),
            models.CheckConstraint(condition=Q(user__isnull=False) | Q(source="dataset"), name="ownerless_job_is_dataset"),
        ]

    def __str__(self) -> str:
        return self.title or f"Job {self.pk}"


class JobRequirement(models.Model):
    REQUIRED, PREFERRED = "required", "preferred"
    EXPLICIT, INFERRED = "explicit", "inferred"
    job = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name="requirements")
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=10, choices=[(REQUIRED, "Required"), (PREFERRED, "Preferred")])
    origin = models.CharField(max_length=10, choices=[(EXPLICIT, "Stated in the text"), (INFERRED, "Implied (prerequisite)")],
                              default=EXPLICIT)
    snippet = models.CharField(max_length=300, blank=True)
    edited_by_user = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "skill"], name="unique_job_skill")]
        indexes = [models.Index(fields=["skill", "kind"])]
