"""Django app configuration for jobs_app."""

from django.apps import AppConfig


class JobsAppConfig(AppConfig):
    """Configuration for the jobs app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "jobs_app"
    verbose_name = "Jobs"

