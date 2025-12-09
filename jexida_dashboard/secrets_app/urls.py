"""URL patterns for secrets app."""

from django.urls import path
from . import views

app_name = "secrets"

urlpatterns = [
    path("", views.secret_list, name="list"),
    path("new/", views.secret_create, name="create"),
    path("<int:secret_id>/edit/", views.secret_edit, name="edit"),
    path("<int:secret_id>/delete/", views.secret_delete, name="delete"),
]

