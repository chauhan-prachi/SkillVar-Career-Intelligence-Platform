from django.db import models


class Dataset(models.Model):
    JOBS = "jobs"
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=[(JOBS, "Job postings")])
    description = models.CharField(max_length=300, blank=True)
    source_note = models.CharField(max_length=300, blank=True, help_text="Provenance / licence of the data")

    def __str__(self) -> str:
        return self.slug


class IngestionRun(models.Model):
    RUNNING, SUCCEEDED, REJECTS, FAILED = "running", "succeeded", "succeeded_with_rejects", "failed"
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=24, default=RUNNING,
                              choices=[(RUNNING, "Running"), (SUCCEEDED, "Succeeded"),
                                       (REJECTS, "Succeeded with rejected rows"), (FAILED, "Failed")])
    source_name = models.CharField(max_length=255)
    source_sha256 = models.CharField(max_length=64, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    rows_read = models.PositiveIntegerField(default=0)
    rows_loaded = models.PositiveIntegerField(default=0)
    rows_duplicate = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]

    @property
    def duration_seconds(self):
        return (self.finished_at - self.started_at).total_seconds() if self.finished_at else None


class DataQualityResult(models.Model):
    PASS, WARN, FAIL = "pass", "warn", "fail"
    run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name="quality_results")
    check_name = models.CharField(max_length=60)
    column = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=4, choices=[(PASS, "Pass"), (WARN, "Warning"), (FAIL, "Fail")])
    detail = models.JSONField(default=dict, blank=True)


class RejectedRecord(models.Model):
    run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name="rejected")
    row_number = models.PositiveIntegerField()
    reason = models.CharField(max_length=200)
    raw = models.JSONField(default=dict)
