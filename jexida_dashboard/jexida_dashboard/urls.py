"""
URL configuration for jexida_dashboard project.

Main URL routing for the Django dashboard, migrated from FastAPI.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    
    # Authentication
    path("accounts/", include("accounts.urls")),
    
    # Main dashboard
    path("", include("dashboard.urls")),
    
    # Secrets management
    path("secrets/", include("secrets_app.urls")),
    
    # AI Assistant
    path("assistant/", include("assistant_app.urls")),
    path("api/assistant/", include("assistant_app.api_urls")),
]
