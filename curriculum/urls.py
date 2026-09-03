from django.urls import path

from . import views


app_name = "curriculum"

urlpatterns = [
    path("", views.curriculum_index, name="index"),
    path("concepts/<slug:concept_slug>/", views.concept_detail, name="concept_detail"),
]
