"""URL patterns for mcp_tools_core app.

Provides both web UI routes (HTMX) and REST API routes.
"""

from django.urls import path

from . import views

app_name = "mcp_tools"

urlpatterns = [
    # Web UI Routes (HTMX)
    path("", views.tool_list, name="list"),
    path("<int:tool_id>/run/", views.tool_run, name="run"),
    path("<int:tool_id>/detail/", views.tool_detail, name="detail"),
    path("requests/", views.tool_request_list, name="requests"),
    path("requests/create/", views.tool_request_create, name="request_create"),
    path("requests/<int:request_id>/resolve/", views.tool_request_resolve, name="request_resolve"),
    path("facts/", views.fact_list, name="facts"),
    path("facts/create/", views.fact_create, name="fact_create"),
    path("logs/", views.execution_log_list, name="logs"),
    
    # REST API Routes
    path("api/", views.api_root, name="api_root"),
    path("api/tools/", views.api_tool_list, name="api_list"),
    path("api/tools/<str:name>/", views.api_tool_detail, name="api_detail"),
    path("api/tools/<str:name>/run/", views.api_tool_run, name="api_run"),
    path("api/request/", views.api_tool_request, name="api_request"),
    path("api/facts/", views.api_fact_list, name="api_facts"),
    path("api/facts/<str:key>/", views.api_fact_detail, name="api_fact_detail"),
]

