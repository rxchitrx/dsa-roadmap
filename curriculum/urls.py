from django.urls import path

from . import views


app_name = "curriculum"

urlpatterns = [
    path("", views.curriculum_index, name="index"),
    path("recommendation/", views.concept_recommendation, name="recommendation"),
    path("graph/", views.prerequisite_graph, name="prerequisite_graph"),
    path(
        "graph/add/",
        views.add_prerequisite_edge,
        name="graph_add",
    ),
    path(
        "graph/remove/",
        views.remove_prerequisite_edge,
        name="graph_remove",
    ),
    path("concepts/<slug:concept_slug>/", views.concept_detail, name="concept_detail"),
]
