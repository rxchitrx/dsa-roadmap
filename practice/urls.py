from django.urls import path

from . import views


app_name = "practice"

urlpatterns = [
    path("<slug:slug>/run/", views.run_problem_tests, name="run_tests"),
    path(
        "<slug:slug>/custom-tests/save/",
        views.save_problem_custom_tests,
        name="save_custom_tests",
    ),
    path(
        "<slug:slug>/custom-tests/<int:case_id>/delete/",
        views.delete_problem_custom_test,
        name="delete_custom_test",
    ),
    path("<slug:slug>/draft/", views.save_problem_draft, name="save_draft"),
    path("<slug:slug>/", views.editor, name="editor"),
    # The explicit form reads well in copied links and keeps a stable alias
    # available if the app later adds more practice modes.
    path("problems/<slug:slug>/draft/", views.save_problem_draft, name="problem_save_draft"),
    path("problems/<slug:slug>/", views.editor, name="problem_editor"),
]
