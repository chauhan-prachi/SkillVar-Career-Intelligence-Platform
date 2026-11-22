from django.urls import path

from . import views

urlpatterns = [
    path("", views.roadmap, name="roadmap"),
    path("generate/", views.generate, name="roadmap_generate"),
    path("items/<int:pk>/", views.item_action, name="roadmap_item"),
]
