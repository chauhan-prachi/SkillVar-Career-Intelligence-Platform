from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("healthz/", views.health, name="health"),
    path("api/v1/skills/", api.SkillListView.as_view()),
    path("api/v1/me/skills/", api.MySkillsView.as_view()),
    path("api/v1/me/readiness/", api.MyReadinessView.as_view()),
    path("api/v1/me/matches/", api.MyMatchesView.as_view()),
]
