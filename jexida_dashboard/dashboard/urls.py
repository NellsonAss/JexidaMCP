"""URL patterns for dashboard app."""

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("monitoring/", views.monitoring, name="monitoring"),
    path("health/", views.health, name="health"),
]

