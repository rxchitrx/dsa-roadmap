from django.urls import include, path


urlpatterns = [
    path("reviews/", include("reviews.urls")),
    path("practice/", include("practice.urls")),
    path("", include("planner.urls")),
]
