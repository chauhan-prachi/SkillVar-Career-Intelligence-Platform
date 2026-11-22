from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.skills.models import Skill
from apps.web.ratelimit import rate_limit

from . import services
from .models import Resume


class UploadForm(forms.Form):
    file = forms.FileField(label="Resume (PDF or DOCX)", widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf,.docx"}))


class FactsForm(forms.Form):
    years_experience_stated = forms.DecimalField(required=False, min_value=0, max_value=60, decimal_places=1, label="Years of experience",
                                                 widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}))
    education_stated = forms.CharField(required=False, max_length=200, label="Highest education",
                                       widget=forms.TextInput(attrs={"class": "form-control"}))


def _own(request, pk) -> Resume:
    return get_object_or_404(Resume, pk=pk, user=request.user)     # other users' ids are a 404, not a 403


@login_required
def resume_list(request):
    page = Paginator(request.user.resumes.all(), 10).get_page(request.GET.get("page"))
    return render(request, "resumes/list.html", {"page": page})


@login_required
@rate_limit("resume-upload", limit=10, window_seconds=3600)
def upload(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            resume = services.process_upload(request.user, form.cleaned_data["file"])
        except ValidationError as exc:
            form.add_error("file", exc)
        else:
            messages.success(request, "Resume analyzed. Please review the detected skills below.")
            return redirect("resume_detail", pk=resume.pk)
    return render(request, "resumes/upload.html", {"form": form})


@login_required
def detail(request, pk):
    resume = _own(request, pk)
    skills = resume.skills.select_related("skill__category").order_by("-contextual", "skill__name")
    initial = {"years_experience_stated": resume.years_experience_stated, "education_stated": resume.education_stated}
    return render(request, "resumes/detail.html", {
        "resume": resume, "skills": skills, "facts_form": FactsForm(initial=initial), "analysis": resume.analysis,
        "all_skills": Skill.objects.filter(is_active=True).exclude(id__in=resume.skills.values("skill_id")).order_by("name")})


@login_required
@require_POST
def review(request, pk):
    resume = _own(request, pk)
    action = request.POST.get("action")
    if action in ("confirm", "reject") and request.POST.get("skill_id", "").isdigit():
        try:
            services.review_skill(resume, int(request.POST["skill_id"]), action)
        except resume.skills.model.DoesNotExist:
            raise Http404
    elif action == "add" and request.POST.get("new_skill", "").isdigit():
        services.add_manual_skill(resume, get_object_or_404(Skill, pk=request.POST["new_skill"], is_active=True))
    return redirect("resume_detail", pk=pk)


@login_required
@require_POST
def update_facts(request, pk):
    resume = _own(request, pk)
    form = FactsForm(request.POST)
    if form.is_valid():
        resume.years_experience_stated = form.cleaned_data["years_experience_stated"]
        resume.education_stated = form.cleaned_data["education_stated"]
        resume.save(update_fields=["years_experience_stated", "education_stated"])
        if resume.years_experience_stated is not None:
            profile = request.user.profile
            profile.years_experience = resume.years_experience_stated
            profile.save(update_fields=["years_experience"])
        messages.success(request, "Saved your corrections.")
    return redirect("resume_detail", pk=pk)


@login_required
@require_POST
def delete(request, pk):
    services.delete_resume(_own(request, pk))
    messages.success(request, "Resume and all data derived from it were deleted.")
    return redirect("resume_list")


@login_required
def download(request, pk):
    resume = _own(request, pk)
    return FileResponse(resume.file.open("rb"), as_attachment=True, filename=f"resume.{resume.file_format}",
                        content_type="application/octet-stream")
