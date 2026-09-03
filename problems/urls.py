from django.urls import path

from . import views


app_name = "problems"

urlpatterns = [
    path("", views.problems_index, name="index"),
    path("sync/", views.sync_catalog, name="sync"),
    path("sync/status/", views.catalog_sync_status, name="sync_status"),
    path(
        "<slug:slug>/classifications/add/",
        views.add_problem_classification,
        name="classification_add",
    ),
    path(
        "<slug:slug>/classifications/<int:classification_id>/remove/",
        views.remove_problem_classification,
        name="classification_remove",
    ),
    path("<slug:slug>/", views.problem_detail, name="detail"),
]
