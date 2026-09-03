from django.urls import path

from . import views


app_name = "reviews"

urlpatterns = [
    path("due/", views.due_queue, name="due_queue"),
    path("sunday/", views.sunday_batch, name="sunday_batch"),
    path("<slug:slug>/", views.problem_review, name="problem_review"),
]
