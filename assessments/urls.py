from django.urls import path

from . import views


app_name = "assessments"


urlpatterns = [
    path("saturday/", views.saturday_pool, name="saturday_pool"),
    path("saturday/start/", views.start_assessment, name="start_assessment"),
    path(
        "saturday/assessment/<int:session_id>/",
        views.assessment_session,
        name="assessment_session",
    ),
    path(
        "saturday/assessment/<int:session_id>/mistakes/",
        views.assessment_mistakes,
        name="assessment_mistakes",
    ),
]
