from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("analyze/", views.analyze, name="job_analyze"),
    path("samples/", views.sample_jobs, name="job_samples"),
    path("<int:pk>/", views.detail, name="job_detail"),
    path("<int:pk>/requirements/", views.edit_requirements, name="job_requirements"),
    path("<int:pk>/delete/", views.delete, name="job_delete"),
    path("<int:pk>/match/", views.match, name="job_match"),
]
