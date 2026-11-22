from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from apps.skills.models import Role

from .models import Profile

User = get_user_model()
LEVELS = [("", "No statement"), ("0.3", "Beginner"), ("0.6", "Intermediate"), ("0.85", "Advanced")]


def style(form):
    for f in form.fields.values():
        w = f.widget
        if isinstance(w, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
            w.attrs["class"] = "form-check-input" if isinstance(w, forms.CheckboxInput) else w.attrs.get("class", "")
        else:
            w.attrs["class"] = (w.attrs.get("class", "") + (" form-select" if isinstance(w, forms.Select) else " form-control")).strip()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Email address")

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        style(self)

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in instead.")
        return email


class ProfileForm(forms.ModelForm):
    career_goal = forms.ModelChoiceField(queryset=Role.objects.none(), label="Career goal", required=True,
                                         help_text="The role you are working toward.")
    preferred_roles = forms.ModelMultipleChoiceField(queryset=Role.objects.none(), required=False,
                                                     widget=forms.CheckboxSelectMultiple, label="Other roles you are interested in")

    class Meta:
        model = Profile
        fields = ["career_goal", "education_level", "field_of_study", "experience_level", "years_experience",
                  "preferred_location", "preferred_roles"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        roles = Role.objects.filter(is_active=True)
        self.fields["career_goal"].queryset = roles
        self.fields["preferred_roles"].queryset = roles
        self.fields["years_experience"].widget.attrs.update({"step": "0.5", "min": "0", "max": "60"})
        style(self)


class SelfAssessmentForm(forms.Form):
    """One level selector per skill that matters for the chosen career goal. Levels are claims, not proof."""

    def __init__(self, *a, skills=(), current=None, **kw):
        super().__init__(*a, **kw)
        self.skill_fields = []
        for s in skills:
            name = f"skill_{s.slug}"
            self.fields[name] = forms.ChoiceField(choices=LEVELS, required=False, label=s.name,
                                                  initial=(current or {}).get(s.slug, ""))
            self.skill_fields.append((s, name))
        style(self)

    def levels(self) -> dict[str, float]:
        return {s.slug: float(self.cleaned_data[name]) for s, name in self.skill_fields if self.cleaned_data.get(name)}
