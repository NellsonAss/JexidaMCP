"""Views for jobs and worker nodes management."""

import asyncio
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone

from mcp_tools_core.models import WorkerNode, Job

logger = logging.getLogger(__name__)


def job_list(request):
    """List all jobs with optional filtering."""
    node_name = request.GET.get("node")
    status = request.GET.get("status")

    queryset = Job.objects.select_related("target_node").order_by("-created_at")

    if node_name:
        queryset = queryset.filter(target_node__name=node_name)

    if status:
        queryset = queryset.filter(status=status)

    jobs = queryset[:50]
    nodes = WorkerNode.objects.filter(is_active=True).order_by("name")

    return render(request, "jobs/list.html", {
        "page_title": "Jobs",
        "jobs": jobs,
        "nodes": nodes,
        "filter_node": node_name,
        "filter_status": status,
    })


def job_detail(request, job_id):
    """Show full details of a specific job."""
    job = get_object_or_404(Job.objects.select_related("target_node"), id=job_id)

    return render(request, "jobs/detail.html", {
        "page_title": f"Job {str(job.id)[:8]}...",
        "job": job,
    })


def job_update_description(request, job_id):
    """Update a job's description via HTMX."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        job.description = description
        job.save(update_fields=["description"])
        
        # Refresh from DB to get updated timestamp
        job.refresh_from_db()
        
        # Return updated description display partial for HTMX
        if request.headers.get("HX-Request"):
            return render(request, "jobs/partials/job_description.html", {
                "job": job,
            })
        
        messages.success(request, "Description updated successfully")
        return redirect("jobs:detail", job_id=job_id)
    
    # GET request - return form partial or display based on query param
    if request.headers.get("HX-Request"):
        if request.GET.get("display") == "1":
            # Return display partial (for cancel)
            return render(request, "jobs/partials/job_description.html", {
                "job": job,
            })
        else:
            # Return form partial (for edit)
            return render(request, "jobs/partials/job_description_form.html", {
                "job": job,
            })
    
    return redirect("jobs:detail", job_id=job_id)


def job_submit(request):
    """Submit a new job to a worker node."""
    nodes = WorkerNode.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        node_name = request.POST.get("node_name")
        command = request.POST.get("command")
        description = request.POST.get("description", "").strip()
        timeout = int(request.POST.get("timeout", 300))

        if not node_name or not command:
            messages.error(request, "Node and command are required")
            return render(request, "jobs/submit.html", {
                "page_title": "Submit Job",
                "nodes": nodes,
                "command": command,
            })

        # Get the node
        try:
            node = WorkerNode.objects.get(name=node_name, is_active=True)
        except WorkerNode.DoesNotExist:
            messages.error(request, f"Worker node '{node_name}' not found or not active")
            return render(request, "jobs/submit.html", {
                "page_title": "Submit Job",
                "nodes": nodes,
                "command": command,
            })

        # Import and run the submit_job tool
        from mcp_tools_core.tools.jobs.jobs import submit_job, SubmitJobInput

        params = SubmitJobInput(
            node_name=node_name,
            command=command,
            description=description,
            timeout=timeout,
        )

        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(submit_job(params))
        finally:
            loop.close()

        if result.success:
            messages.success(request, f"Job submitted successfully on {node_name}")
            return redirect("jobs:detail", job_id=result.job.id)
        else:
            messages.error(request, f"Job failed: {result.error}")
            return redirect("jobs:list")

    return render(request, "jobs/submit.html", {
        "page_title": "Submit Job",
        "nodes": nodes,
    })


def node_list(request):
    """List all worker nodes."""
    nodes = WorkerNode.objects.all().order_by("name")

    return render(request, "jobs/nodes.html", {
        "page_title": "Worker Nodes",
        "nodes": nodes,
    })


def node_detail(request, node_name):
    """Show details of a specific worker node."""
    node = get_object_or_404(WorkerNode, name=node_name)
    recent_jobs = Job.objects.filter(target_node=node).order_by("-created_at")[:10]

    return render(request, "jobs/node_detail.html", {
        "page_title": f"Node: {node.name}",
        "node": node,
        "recent_jobs": recent_jobs,
    })


def node_check(request, node_name):
    """Check connectivity to a worker node."""
    node = get_object_or_404(WorkerNode, name=node_name)

    # Import and run the check tool
    from mcp_tools_core.tools.jobs.nodes import check_worker_node, CheckWorkerNodeInput

    detailed = request.GET.get("detailed", "false").lower() == "true"
    params = CheckWorkerNodeInput(name=node_name, detailed=detailed)

    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(check_worker_node(params))
    finally:
        loop.close()

    # For HTMX requests, return a partial
    if request.headers.get("HX-Request"):
        return render(request, "jobs/partials/node_check_result.html", {
            "node": node,
            "result": result,
        })

    # Full page response
    return render(request, "jobs/node_check.html", {
        "page_title": f"Check Node: {node.name}",
        "node": node,
        "result": result,
    })


def job_row_partial(request, job_id):
    """HTMX partial for a single job row."""
    job = get_object_or_404(Job.objects.select_related("target_node"), id=job_id)

    return render(request, "jobs/partials/job_row.html", {
        "job": job,
    })


def jobs_table_partial(request):
    """HTMX partial for the jobs table body."""
    node_name = request.GET.get("node")
    status = request.GET.get("status")

    queryset = Job.objects.select_related("target_node").order_by("-created_at")

    if node_name:
        queryset = queryset.filter(target_node__name=node_name)

    if status:
        queryset = queryset.filter(status=status)

    jobs = queryset[:50]

    return render(request, "jobs/partials/jobs_table.html", {
        "jobs": jobs,
    })


def job_check_status(request, job_id):
    """Check if a job's node is reachable and optionally check for running processes."""
    job = get_object_or_404(Job.objects.select_related("target_node"), id=job_id)

    # Import and run the check tool
    from mcp_tools_core.tools.jobs.nodes import check_worker_node, CheckWorkerNodeInput
    from mcp_tools_core.tools.jobs.executor import WorkerSSHExecutor

    # Check node connectivity
    params = CheckWorkerNodeInput(name=job.target_node.name, detailed=False)
    
    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    status_updated = False
    update_message = None
    try:
        connectivity_result = loop.run_until_complete(check_worker_node(params))
        
        # If node is unreachable and job is still running, mark as lost
        if not connectivity_result.reachable and job.status == Job.STATUS_RUNNING:
            job.status = Job.STATUS_LOST
            job.stderr = (job.stderr or "") + f"\n[Status Check] Node unreachable - marked as lost at {timezone.now()}"
            job.save(update_fields=["status", "stderr"])
            status_updated = True
            update_message = "Job marked as 'Lost' - node is unreachable"
        
        # If node is reachable, try to check for processes matching the command
        process_check = None
        if connectivity_result.reachable:
            try:
                executor = WorkerSSHExecutor(timeout=10)
                # Extract the base command (first word) to search for
                cmd_parts = job.command.strip().split()
                if cmd_parts:
                    base_cmd = cmd_parts[0]
                    # Check if process is running (using pgrep, fallback to ps)
                    # Escape single quotes in base_cmd for safety
                    escaped_cmd = base_cmd.replace("'", "'\"'\"'")
                    check_cmd = f"pgrep -f '{escaped_cmd}' > /dev/null 2>&1 && echo 'Process found' || echo 'Process not found'"
                    process_result = executor.run_command(job.target_node, check_cmd)
                    process_check = {
                        "found": "Process found" in process_result.stdout,
                        "output": process_result.stdout.strip(),
                    }
                    
                    # If process not found and job is still running, mark as lost
                    if not process_check["found"] and job.status == Job.STATUS_RUNNING:
                        job.status = Job.STATUS_LOST
                        job.stderr = (job.stderr or "") + f"\n[Status Check] Process not found - marked as lost at {timezone.now()}"
                        job.save(update_fields=["status", "stderr"])
                        status_updated = True
                        update_message = "Job marked as 'Lost' - process no longer running"
            except Exception as e:
                # If process check fails, just skip it
                logger.warning(f"Failed to check process for job {job.id}: {e}")
                process_check = None
    finally:
        loop.close()

    # Refresh job from database
    job.refresh_from_db()

    # For HTMX requests, return a partial
    if request.headers.get("HX-Request"):
        return render(request, "jobs/partials/job_check_result.html", {
            "job": job,
            "connectivity_result": connectivity_result,
            "process_check": process_check,
            "status_updated": status_updated,
            "update_message": update_message,
        })

    # Full page response
    return render(request, "jobs/detail.html", {
        "page_title": f"Job {str(job.id)[:8]}...",
        "job": job,
        "connectivity_result": connectivity_result,
        "process_check": process_check,
    })