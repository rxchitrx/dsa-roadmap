from django.urls import path

from . import views


app_name = "reviews"

urlpatterns = [
    path("<slug:slug>/", views.problem_review, name="problem_review"),
]
