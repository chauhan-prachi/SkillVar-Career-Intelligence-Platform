import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from .storage import private_storage


def resume_path(instance, filename: str) -> str:
    ext = "pdf" if filename.lower().endswith(".pdf") else "docx"
    return f"resumes/{instance.user_id}/{uuid.uuid4().hex}.{ext}"      # server-chosen name, never the user's


class Resume(models.Model):
    PDF, DOCX = "pdf", "docx"
    PROCESSED, EMPTY = "processed", "empty"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    original_filename = models.CharField(max_length=255)         # display only
    file = models.FileField(upload_to=resume_path, storage=private_storage)
    file_format = models.CharField(max_length=4, choices=[(PDF, "PDF"), (DOCX, "DOCX")])
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=[(PROCESSED, "Processed"), (EMPTY, "Little or no text")])
    page_count = models.PositiveSmallIntegerField(null=True, blank=True)
    extracted_text = models.TextField(blank=True)
    analysis = models.JSONField(default=dict, blank=True)         # contact/section/quality indicators + warnings
    years_experience_stated = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    education_stated = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "sha256"], name="unique_resume_per_user")]

    def __str__(self) -> str:
        return f"{self.original_filename} (user {self.user_id})"


class ResumeSkill(models.Model):
    DETECTED, CONFIRMED, REJECTED, MANUAL = "detected", "confirmed", "rejected", "manual"
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    section = models.CharField(max_length=20, blank=True)
    contextual = models.BooleanField(default=False)
    matched_text = models.CharField(max_length=120, blank=True)
    snippet = models.CharField(max_length=300, blank=True)
    review = models.CharField(max_length=10, default=DETECTED,
                              choices=[(DETECTED, "Detected"), (CONFIRMED, "Confirmed by you"),
                                       (REJECTED, "Rejected by you"), (MANUAL, "Added by you")])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["resume", "skill"], name="unique_resume_skill"),
                       models.CheckConstraint(condition=Q(review__in=["detected", "confirmed", "rejected", "manual"]),
                                              name="resume_skill_review_valid")]
