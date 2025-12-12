"""Job management tools for MCP platform.

Provides tools for managing jobs on worker nodes:
- submit_job: Submit a command to run on a worker node
- list_jobs: List recent jobs with filtering
- get_job: Get full details of a specific job
"""

import logging
import time
from typing import Optional, List

from asgiref.sync import sync_to_async
from pydantic import BaseModel, Field

from .executor import WorkerSSHExecutor

logger = logging.getLogger(__name__)


# =============================================================================
# Submit Job Tool
# =============================================================================

class SubmitJobInput(BaseModel):
    """Input schema for submit_job."""

    node_name: str = Field(
        description="Name of the worker node to run the job on"
    )
    command: str = Field(
        description="Shell command to execute on the worker node"
    )
    description: str = Field(
        default="",
        description="Optional human-readable description of what this job does"
    )
    timeout: int = Field(
        default=300,
        description="Command timeout in seconds (default: 5 minutes)"
    )


class JobInfo(BaseModel):
    """Information about a job."""

    id: str = Field(description="Unique job identifier (UUID)")
    node_name: str = Field(description="Target worker node name")
    command: str = Field(description="Command that was/will be executed")
    description: str = Field(default="", description="Human-readable description of what this job does")
    status: str = Field(description="Job status: queued, running, succeeded, failed")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    exit_code: Optional[int] = Field(default=None, description="Exit code")
    duration_ms: Optional[int] = Field(default=None, description="Duration in milliseconds")
    created_at: str = Field(description="When the job was created")
    updated_at: str = Field(description="When the job was last updated")


class SubmitJobOutput(BaseModel):
    """Output schema for submit_job."""

    success: bool = Field(description="Whether the job completed successfully")
    job: Optional[JobInfo] = Field(default=None, description="Job details")
    error: str = Field(default="", description="Error message if failed to submit")


async def submit_job(params: SubmitJobInput) -> SubmitJobOutput:
    """Submit and execute a job on a worker node.

    This tool:
    1. Creates a job record with status 'queued'
    2. Resolves the target worker node
    3. Executes the command via SSH
    4. Updates the job with results (stdout, stderr, exit_code)
    5. Sets final status to 'succeeded' or 'failed'

    Jobs are executed synchronously - this call blocks until complete.

    Args:
        params: Job submission parameters

    Returns:
        Job execution results
    """
    logger.info(f"Submitting job to {params.node_name}: {params.command[:100]}...")

    try:
        from mcp_tools_core.models import WorkerNode, Job
        from django.utils import timezone

        # Get the target node
        @sync_to_async
        def get_node():
            try:
                return WorkerNode.objects.get(name=params.node_name, is_active=True)
            except WorkerNode.DoesNotExist:
                return None

        @sync_to_async
        def create_job(node):
            return Job.objects.create(
                target_node=node,
                command=params.command,
                description=params.description,
                status=Job.STATUS_QUEUED,
            )

        @sync_to_async
        def update_job(job, status, stdout, stderr, exit_code, duration_ms):
            job.status = status
            job.stdout = stdout
            job.stderr = stderr
            job.exit_code = exit_code
            job.duration_ms = duration_ms
            job.save()
            return job

        @sync_to_async
        def update_node_last_seen(node):
            node.last_seen = timezone.now()
            node.save(update_fields=["last_seen"])

        @sync_to_async
        def job_to_info(job):
            return JobInfo(
                id=str(job.id),
                node_name=job.target_node.name,
                command=job.command,
                description=job.description or "",
                status=job.status,
                stdout=job.stdout,
                stderr=job.stderr,
                exit_code=job.exit_code,
                duration_ms=job.duration_ms,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
            )

        node = await get_node()

        if node is None:
            return SubmitJobOutput(
                success=False,
                error=f"Worker node '{params.node_name}' not found or not active"
            )

        # Create job record
        job = await create_job(node)
        logger.info(f"Created job {job.id} for node {node.name}")

        # Update status to running
        await update_job(job, Job.STATUS_RUNNING, "", "", None, None)

        # Execute the command
        executor = WorkerSSHExecutor(timeout=params.timeout)
        result = executor.run_command(node, params.command)

        # Determine final status
        if result.success:
            final_status = Job.STATUS_SUCCEEDED
            await update_node_last_seen(node)
        else:
            final_status = Job.STATUS_FAILED

        # Update job with results
        job = await update_job(
            job,
            final_status,
            result.stdout,
            result.stderr,
            result.exit_code,
            result.duration_ms,
        )

        job_info = await job_to_info(job)

        logger.info(f"Job {job.id} completed with status {final_status}")

        return SubmitJobOutput(
            success=result.success,
            job=job_info,
            error="" if result.success else result.stderr[:500],
        )

    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        return SubmitJobOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# List Jobs Tool
# =============================================================================

class ListJobsInput(BaseModel):
    """Input schema for list_jobs."""

    node_name: Optional[str] = Field(
        default=None,
        description="Filter by worker node name"
    )
    status: Optional[str] = Field(
        default=None,
        description="Filter by status: queued, running, succeeded, failed"
    )
    limit: int = Field(
        default=20,
        description="Maximum number of jobs to return (default: 20)"
    )


class ListJobsOutput(BaseModel):
    """Output schema for list_jobs."""

    success: bool = Field(description="Whether the query succeeded")
    jobs: List[JobInfo] = Field(default_factory=list, description="List of jobs")
    count: int = Field(default=0, description="Number of jobs returned")
    error: str = Field(default="", description="Error message if failed")


async def list_jobs(params: ListJobsInput) -> ListJobsOutput:
    """List recent jobs with optional filtering.

    Jobs are returned in reverse chronological order (newest first).

    Args:
        params: Filter parameters

    Returns:
        List of jobs matching the filter
    """
    logger.info(f"Listing jobs: node={params.node_name}, status={params.status}, limit={params.limit}")

    try:
        from mcp_tools_core.models import Job

        @sync_to_async
        def query_jobs():
            queryset = Job.objects.select_related("target_node").order_by("-created_at")

            if params.node_name:
                queryset = queryset.filter(target_node__name=params.node_name)

            if params.status:
                queryset = queryset.filter(status=params.status)

            jobs = []
            for job in queryset[:params.limit]:
                # Truncate stdout/stderr for list view
                stdout_preview = job.stdout[:200] + "..." if len(job.stdout) > 200 else job.stdout
                stderr_preview = job.stderr[:200] + "..." if len(job.stderr) > 200 else job.stderr

                jobs.append(JobInfo(
                    id=str(job.id),
                    node_name=job.target_node.name,
                    command=job.command[:100] + "..." if len(job.command) > 100 else job.command,
                    description=job.description or "",
                    status=job.status,
                    stdout=stdout_preview,
                    stderr=stderr_preview,
                    exit_code=job.exit_code,
                    duration_ms=job.duration_ms,
                    created_at=job.created_at.isoformat(),
                    updated_at=job.updated_at.isoformat(),
                ))

            return jobs

        jobs = await query_jobs()

        return ListJobsOutput(
            success=True,
            jobs=jobs,
            count=len(jobs)
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return ListJobsOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# Get Job Tool
# =============================================================================

class GetJobInput(BaseModel):
    """Input schema for get_job."""

    job_id: str = Field(
        description="UUID of the job to retrieve"
    )


class GetJobOutput(BaseModel):
    """Output schema for get_job."""

    success: bool = Field(description="Whether the query succeeded")
    job: Optional[JobInfo] = Field(default=None, description="Full job details")
    error: str = Field(default="", description="Error message if failed")


async def get_job(params: GetJobInput) -> GetJobOutput:
    """Get full details of a specific job.

    Returns complete job information including full stdout/stderr.

    Args:
        params: Job ID to retrieve

    Returns:
        Complete job details
    """
    logger.info(f"Getting job: {params.job_id}")

    try:
        from mcp_tools_core.models import Job
        import uuid

        # Validate UUID format
        try:
            job_uuid = uuid.UUID(params.job_id)
        except ValueError:
            return GetJobOutput(
                success=False,
                error=f"Invalid job ID format: {params.job_id}"
            )

        @sync_to_async
        def get_job_by_id():
            try:
                job = Job.objects.select_related("target_node").get(id=job_uuid)
                return JobInfo(
                    id=str(job.id),
                    node_name=job.target_node.name,
                    command=job.command,
                    description=job.description or "",
                    status=job.status,
                    stdout=job.stdout,
                    stderr=job.stderr,
                    exit_code=job.exit_code,
                    duration_ms=job.duration_ms,
                    created_at=job.created_at.isoformat(),
                    updated_at=job.updated_at.isoformat(),
                )
            except Job.DoesNotExist:
                return None

        job_info = await get_job_by_id()

        if job_info is None:
            return GetJobOutput(
                success=False,
                error=f"Job '{params.job_id}' not found"
            )

        return GetJobOutput(
            success=True,
            job=job_info
        )

    except Exception as e:
        logger.error(f"Failed to get job: {e}")
        return GetJobOutput(
            success=False,
            error=str(e)
        )

