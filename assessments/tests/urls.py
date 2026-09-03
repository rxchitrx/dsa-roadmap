from django.urls import include, path


urlpatterns = [
    path("assessments/", include("assessments.urls")),
]
