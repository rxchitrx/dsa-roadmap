from django.urls import path

from . import views


app_name = "planner"

urlpatterns = [
    path("", views.today, name="today"),
    path("today/", views.today, name="today_page"),
    path(
        "routine/generate/",
        views.generate_weekly_routine_view,
        name="generate_weekly_routine",
    ),
    path("routine/", views.weekly_plan, name="weekly_plan"),
    path(
        "routine/days/<str:day_date>/rest/",
        views.toggle_rest_day_view,
        name="toggle_rest_day",
    ),
    path(
        "routine/blocks/<int:block_id>/edit/",
        views.edit_study_block,
        name="edit_study_block",
    ),
    path(
        "routine/blocks/<int:block_id>/move/",
        views.reorder_study_block,
        name="reorder_study_block",
    ),
    path(
        "routine/blocks/<int:block_id>/timer/start/",
        views.start_timer,
        name="start_timer",
    ),
    path(
        "routine/blocks/<int:block_id>/timer/pause/",
        views.pause_timer,
        name="pause_timer",
    ),
    path(
        "routine/blocks/<int:block_id>/timer/resume/",
        views.resume_timer,
        name="resume_timer",
    ),
    path(
        "routine/blocks/<int:block_id>/timer/stop/",
        views.stop_timer,
        name="stop_timer",
    ),
]
