from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("curriculum/", include("curriculum.urls")),
    path("progress/", include("progress.urls")),
    path("problems/", include("problems.urls")),
    path("practice/", include("practice.urls")),
    path("history/", include("history.urls")),
    path("", include("planner.urls")),
]
