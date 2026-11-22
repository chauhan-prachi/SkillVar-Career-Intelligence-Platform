from django.urls import path

from . import views

urlpatterns = [
    path("", views.resume_list, name="resume_list"),
    path("upload/", views.upload, name="resume_upload"),
    path("<int:pk>/", views.detail, name="resume_detail"),
    path("<int:pk>/review/", views.review, name="resume_review"),
    path("<int:pk>/facts/", views.update_facts, name="resume_facts"),
    path("<int:pk>/delete/", views.delete, name="resume_delete"),
    path("<int:pk>/download/", views.download, name="resume_download"),
]
