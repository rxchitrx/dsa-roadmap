from django.urls import include, path


urlpatterns = [
    path("problems/", include("problems.urls")),
]
