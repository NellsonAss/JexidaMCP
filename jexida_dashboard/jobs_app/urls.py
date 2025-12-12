"""URL patterns for jobs app."""

from django.urls import path
from . import views

app_name = "jobs"

urlpatterns = [
    # Jobs
    path("", views.job_list, name="list"),
    path("<uuid:job_id>/", views.job_detail, name="detail"),
    path("<uuid:job_id>/check/", views.job_check_status, name="check_status"),
    path("<uuid:job_id>/description/", views.job_update_description, name="update_description"),
    path("submit/", views.job_submit, name="submit"),
    # Worker Nodes
    path("nodes/", views.node_list, name="nodes"),
    path("nodes/<str:node_name>/", views.node_detail, name="node_detail"),
    path("nodes/<str:node_name>/check/", views.node_check, name="node_check"),
    # Partials for HTMX
    path("partials/job-row/<uuid:job_id>/", views.job_row_partial, name="job_row_partial"),
    path("partials/jobs-table/", views.jobs_table_partial, name="jobs_table_partial"),
]

