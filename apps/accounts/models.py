from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """Custom user from day one (Django best practice). Email is required and unique, case-insensitively."""
    email = models.EmailField("email address")
    REQUIRED_FIELDS = ["email"]

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_user_email_ci")]


class Profile(models.Model):
    EDUCATION = [("", "Prefer not to say"), ("high_school", "High school"), ("diploma", "Diploma / associate"),
                 ("bachelor", "Bachelor's degree"), ("master", "Master's degree"), ("doctorate", "Doctorate"),
                 ("self_taught", "Self-taught / bootcamp")]
    EXPERIENCE = [("student", "Student"), ("entry", "Entry level (0–1 years)"), ("junior", "Junior (1–3 years)"),
                  ("mid", "Mid-level (3–6 years)"), ("senior", "Senior (6+ years)")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    career_goal = models.ForeignKey("skills.Role", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="aspirants")
    preferred_roles = models.ManyToManyField("skills.Role", blank=True, related_name="interested_profiles")
    education_level = models.CharField(max_length=20, choices=EDUCATION, blank=True)
    field_of_study = models.CharField(max_length=120, blank=True)
    experience_level = models.CharField(max_length=10, choices=EXPERIENCE, blank=True)
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(60)])
    preferred_location = models.CharField(max_length=120, blank=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def onboarding_completed(self) -> bool:
        return self.onboarding_completed_at is not None

    def __str__(self) -> str:
        return f"Profile<{self.user_id}>"
