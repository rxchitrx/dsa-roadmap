from django.urls import path

from . import views


app_name = "progress"

urlpatterns = [
    path(
        "concepts/<slug:concept_slug>/",
        views.concept_progress,
        name="concept_progress",
    ),
]
