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
]
