from django.urls import path

from . import views

urlpatterns = [path("", views.runs, name="dataops_runs"), path("runs/<int:pk>/", views.run_detail, name="dataops_run")]
