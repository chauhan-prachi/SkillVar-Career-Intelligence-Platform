from django.urls import path

from . import views

urlpatterns = [
    path("", views.assessment_list, name="assessment_list"),
    path("history/", views.history, name="assessment_history"),
    path("attempts/<int:pk>/", views.result, name="attempt_result"),
    path("<slug:slug>/", views.take, name="assessment_take"),
]
