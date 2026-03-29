"""Django app URLs for testing."""

from django.urls import path

from . import views

app_name = "myapp"

urlpatterns = [
    path("test/", views.test_view, name="test_view"),
    path("api/", views.api_view, name="api_view"),
    path("complex/", views.complex_view, name="complex_view"),
]
