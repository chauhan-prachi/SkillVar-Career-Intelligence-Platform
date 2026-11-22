from django.conf import settings
from django.db import models
from django.db.models import Q


class Assessment(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=140)
    description = models.CharField(max_length=300, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "title"]

    def __str__(self) -> str:
        return self.title


class Question(models.Model):
    MCQ, SQL = "mcq", "sql"
    slug = models.SlugField(unique=True)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions")
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="questions")
    kind = models.CharField(max_length=3, choices=[(MCQ, "Multiple choice"), (SQL, "SQL (executed in a sandbox)")])
    prompt = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_index = models.PositiveSmallIntegerField(null=True, blank=True)
    explanation = models.TextField(blank=True)
    sql_config = models.JSONField(default=dict, blank=True)   # fixture, reference, order_matters, schema (never shown)
    difficulty = models.FloatField(default=0.5)
    weight = models.FloatField(default=1.0)                    # guessable items carry less evidence
    version = models.PositiveSmallIntegerField(default=1)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["assessment", "position", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(difficulty__gte=0) & Q(difficulty__lte=1), name="question_difficulty_range"),
            models.CheckConstraint(condition=~Q(kind="mcq") | Q(correct_index__isnull=False), name="mcq_has_correct_index"),
        ]


class Attempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="attempts")
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"])]


class AnswerRecord(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="answers")
    question_version = models.PositiveSmallIntegerField()      # keeps old results interpretable if a question changes
    answer_text = models.TextField(blank=True)
    score = models.FloatField()
    feedback = models.TextField(blank=True)
    weight_applied = models.FloatField(default=1.0)            # 0 when a repeat did not count
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="one_answer_per_question_attempt")]

    @property
    def counted(self) -> bool:
        return self.weight_applied > 0
