from django.urls import path

from . import views


app_name = "assessments"


urlpatterns = [
    path("saturday/", views.saturday_pool, name="saturday_pool"),
]
