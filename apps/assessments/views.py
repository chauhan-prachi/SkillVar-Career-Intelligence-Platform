from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from apps.web.ratelimit import hit

from . import services
from .models import Assessment, Attempt


@login_required
def assessment_list(request):
    last = {a.assessment_id: a for a in Attempt.objects.filter(user=request.user).order_by("created_at")}
    items = [{"a": a, "n": a.n, "last": last.get(a.id)} for a in
             Assessment.objects.filter(is_active=True).annotate(n=Count("questions"))]
    return render(request, "assessments/list.html", {"items": items})


@login_required
def take(request, slug):
    assessment = get_object_or_404(Assessment, slug=slug, is_active=True)
    questions = list(assessment.questions.filter(is_active=True).select_related("skill"))
    for q in questions:
        q.eligible = services.is_eligible(request.user, q)
        q.posted = request.POST.get(f"q{q.id}", "")
    error = None
    if request.method == "POST":
        answers = {q.id: request.POST.get(f"q{q.id}", "") for q in questions}
        try:
            return redirect("attempt_result", pk=_submit(request, assessment, answers).pk)
        except ValidationError as exc:
            error = " ".join(exc.messages)
    return render(request, "assessments/take.html", {"assessment": assessment, "questions": questions, "error": error})


def _submit(request, assessment, answers):
    if hit(request, "assessment-submit", 60, 3600):
        raise ValidationError("You are submitting too quickly. Please wait a few minutes.")
    return services.submit_attempt(request.user, assessment, answers)


@login_required
def result(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("assessment"), pk=pk, user=request.user)
    answers = attempt.answers.select_related("question__skill").order_by("question__position")
    return render(request, "assessments/result.html", {"attempt": attempt, "answers": answers,
                                                       "any_uncounted": any(not a.counted for a in answers)})


@login_required
def history(request):
    page = Paginator(Attempt.objects.filter(user=request.user).select_related("assessment"), 15).get_page(request.GET.get("page"))
    return render(request, "assessments/history.html", {"page": page})
