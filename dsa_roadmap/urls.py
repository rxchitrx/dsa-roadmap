from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


def home(request):
    return HttpResponse(
        "<h1>DSA Roadmap</h1><p>The learning workspace is being built.</p>"
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
]
