from django.urls import path

from . import views


app_name = "practice"

urlpatterns = [
    path("<slug:slug>/draft/", views.save_problem_draft, name="save_draft"),
    path("<slug:slug>/", views.editor, name="editor"),
    # The explicit form reads well in copied links and keeps a stable alias
    # available if the app later adds more practice modes.
    path("problems/<slug:slug>/draft/", views.save_problem_draft, name="problem_save_draft"),
    path("problems/<slug:slug>/", views.editor, name="problem_editor"),
]
