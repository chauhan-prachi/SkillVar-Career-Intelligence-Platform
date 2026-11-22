from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.skills.models import RoleRequirement, Skill
from apps.web.ratelimit import rate_limit

from .forms import ProfileForm, RegisterForm, SelfAssessmentForm
from .services import complete_onboarding, current_claims, save_self_assessment


@rate_limit("register", limit=10, window_seconds=3600)
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(request, "Welcome to SkillVar. Let's set up your profile.")
        return redirect("onboarding")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def onboarding(request):
    form = ProfileForm(request.POST or None, instance=request.user.profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("onboarding_skills")
    return render(request, "accounts/onboarding.html", {"form": form, "editing": request.user.profile.onboarding_completed})


def _goal_skills(profile):
    if not profile.career_goal_id:
        return Skill.objects.none()
    ids = RoleRequirement.objects.filter(role=profile.career_goal).order_by("-importance").values_list("skill_id", flat=True)
    by_id = {s.id: s for s in Skill.objects.filter(id__in=ids)}
    return [by_id[i] for i in ids if i in by_id]


@login_required
def onboarding_skills(request):
    profile = request.user.profile
    if not profile.career_goal_id:
        messages.info(request, "Choose a career goal first.")
        return redirect("onboarding")
    form = SelfAssessmentForm(request.POST or None, skills=_goal_skills(profile), current=_nearest(current_claims(request.user)))
    if request.method == "POST" and form.is_valid():
        save_self_assessment(request.user, form.levels())
        complete_onboarding(request.user)
        messages.success(request, "Saved. These are your own claims; they become evidence only after assessments.")
        return redirect("dashboard")
    return render(request, "accounts/onboarding_skills.html", {"form": form, "goal": profile.career_goal})


def _nearest(claims: dict[str, float]) -> dict[str, str]:
    return {s: min(("0.3", "0.6", "0.85"), key=lambda c: abs(float(c) - v)) for s, v in claims.items()}


@login_required
def account(request):
    return render(request, "accounts/account.html", {"profile": request.user.profile})
