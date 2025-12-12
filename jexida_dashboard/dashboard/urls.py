"""URL patterns for dashboard app."""

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("monitoring/", views.monitoring, name="monitoring"),
    path("health/", views.health, name="health"),
    # Models and orchestration
    path("models/", views.models_view, name="models"),
    path("models/set/", views.models_set, name="models_set"),
    # Network hardening
    path("network-hardening/", views.network_hardening, name="network_hardening"),
    path("network-hardening/run/<str:evaluation>/", views.run_evaluation, name="run_evaluation"),
    # Azure flows
    path("azure/", views.azure_dashboard, name="azure"),
    path("azure/create-env/", views.azure_create_env, name="azure_create_env"),
    path("azure/add-data/", views.azure_add_data, name="azure_add_data"),
    path("azure/deploy/", views.azure_deploy, name="azure_deploy"),
    # Discord
    path("discord/", views.discord_dashboard, name="discord"),
    path("discord/test/", views.discord_test, name="discord_test"),
    path("discord/bootstrap/", views.discord_bootstrap, name="discord_bootstrap"),
    path("discord/send-message/", views.discord_send_message, name="discord_send_message"),
    # Patreon
    path("patreon/", views.patreon_dashboard, name="patreon"),
    path("patreon/patrons/", views.patreon_get_patrons, name="patreon_patrons"),
    path("patreon/export/", views.patreon_export, name="patreon_export"),
]

