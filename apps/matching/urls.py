from django.urls import path

from . import views

urlpatterns = [
    path("matches/", views.match_list, name="match_list"),
    path("matches/<int:pk>/", views.match_detail, name="match_detail"),
    path("readiness/", views.readiness, name="readiness"),
    path("skills/", views.my_skills, name="my_skills"),
]
