from django.urls import path

from . import views


app_name = "problems"

urlpatterns = [
    path("", views.problems_index, name="index"),
    path("<slug:slug>/", views.problem_detail, name="detail"),
]
