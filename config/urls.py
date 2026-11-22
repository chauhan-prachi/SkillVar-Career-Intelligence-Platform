from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

handler404 = "apps.web.views.not_found"
handler500 = "apps.web.views.server_error"

urlpatterns = [
    path("", include("apps.web.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("resumes/", include("apps.resumes.urls")),
    path("jobs/", include("apps.jobs.urls")),
    path("assessments/", include("apps.assessments.urls")),
    path("roadmap/", include("apps.roadmaps.urls")),
    path("data/", include("apps.dataops.urls")),
    path("", include("apps.matching.urls")),
    # allauth is only used for Google sign-in: its own login/signup pages redirect to SkillVar's pages.
    path("auth/login/", RedirectView.as_view(pattern_name="login")),
    path("auth/signup/", RedirectView.as_view(pattern_name="register")),
    path("auth/", include("allauth.urls")),
    path("admin/", admin.site.urls),
]
