"""Django URL configuration."""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("myapp/", include("myapp.urls")),
    path("", lambda r: HttpResponse("Welcome to Django!")),
]
