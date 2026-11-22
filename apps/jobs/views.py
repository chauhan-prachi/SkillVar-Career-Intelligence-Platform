from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.matching.services import job_requirements, match_job
from apps.skills.models import Skill
from apps.web.ratelimit import rate_limit

from . import services
from .models import JobDescription, JobRequirement


class JobForm(forms.Form):
    title = forms.CharField(required=False, max_length=200, label="Job title (optional)", widget=forms.TextInput(attrs={"class": "form-control"}))
    text = forms.CharField(label="Job description", widget=forms.Textarea(attrs={"class": "form-control", "rows": 14,
                           "placeholder": "Paste the full job description here"}))


def _own(request, pk) -> JobDescription:
    return get_object_or_404(JobDescription, pk=pk, user=request.user)


@login_required
@rate_limit("job-analyze", limit=30, window_seconds=3600)
def analyze(request):
    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            job = services.create_job(request.user, form.cleaned_data["text"], title=form.cleaned_data["title"])
        except ValidationError as exc:
            form.add_error("text", exc)
        else:
            return redirect("job_detail", pk=job.pk)
    return render(request, "jobs/analyze.html", {"form": form})


@login_required
def job_list(request):
    page = Paginator(request.user.job_descriptions.annotate(n=Count("requirements")).order_by("-created_at", "-id"), 10).get_page(request.GET.get("page"))
    return render(request, "jobs/list.html", {"page": page})


@login_required
def sample_jobs(request):
    q = request.GET.get("q", "").strip()[:80]
    qs = JobDescription.objects.filter(user__isnull=True).annotate(n=Count("requirements"))
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(company__icontains=q))
    page = Paginator(qs.order_by("title", "id"), 20).get_page(request.GET.get("page"))
    return render(request, "jobs/samples.html", {"page": page, "q": q})


@login_required
def detail(request, pk):
    # users may open their own analyses, and the shared dataset postings
    job = get_object_or_404(JobDescription, Q(user=request.user) | Q(user__isnull=True), pk=pk)
    reqs = job.requirements.select_related("skill__category").order_by("kind", "origin", "skill__name")
    explicit = [r for r in reqs if r.origin == JobRequirement.EXPLICIT]
    return render(request, "jobs/detail.html", {
        "job": job, "owned": job.user_id == request.user.id,
        "required": [r for r in explicit if r.kind == "required"], "preferred": [r for r in explicit if r.kind == "preferred"],
        "inferred": [r for r in reqs if r.origin == JobRequirement.INFERRED],
        "tools": sorted({r.skill.name for r in explicit if r.skill.category.slug not in ("cs-fundamentals", "analytics-ml")}),
        "all_skills": Skill.objects.filter(is_active=True).exclude(id__in=job.requirements.values("skill_id")).order_by("name")})


@login_required
@require_POST
def edit_requirements(request, pk):
    job = _own(request, pk)
    action, sid = request.POST.get("action"), request.POST.get("skill_id", "")
    if action == "add" and request.POST.get("new_skill", "").isdigit() and request.POST.get("kind") in ("required", "preferred"):
        services.set_requirement(job, get_object_or_404(Skill, pk=request.POST["new_skill"]), request.POST["kind"])
    elif action == "remove" and sid.isdigit():
        services.remove_requirement(job, int(sid))
    elif action == "toggle" and sid.isdigit():
        r = get_object_or_404(job.requirements, skill_id=int(sid))
        services.set_requirement(job, r.skill, "preferred" if r.kind == "required" else "required")
    elif action == "promote" and sid.isdigit():
        services.promote_inferred(job, int(sid))
    return redirect("job_detail", pk=pk)


@login_required
@require_POST
def delete(request, pk):
    _own(request, pk).delete()
    messages.success(request, "Job analysis deleted.")
    return redirect("job_list")


@login_required
@require_POST
@rate_limit("job-match", limit=60, window_seconds=3600)
def match(request, pk):
    job = get_object_or_404(JobDescription, Q(user=request.user) | Q(user__isnull=True), pk=pk)
    if not job_requirements(job):
        messages.error(request, "This job has no recognized requirements to compare against.")
        return redirect("job_detail", pk=pk)
    _, record = match_job(request.user, job)
    return redirect("match_detail", pk=record.pk)
