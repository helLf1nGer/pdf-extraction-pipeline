"""
Job status tracking endpoints.

This module handles job status queries, result retrieval,
and job management operations.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import JSONResponse

from ..models import (
    StatusResponse, JobInfo, ExtractionData, APIError, ErrorCode, 
    JobStatus, ExampleModels, SystemStats
)
from ..core.config import get_settings
from ..services.job_manager import JobManager

# Get dependencies
settings = get_settings()
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def get_job_manager(request: Request) -> JobManager:
    """Dependency to get the job manager from the app."""
    return request.app.state.job_manager


@router.get(
    "/status/{job_id}",
    response_model=StatusResponse,
    summary="Get job status and results",
    description="""
    Get the current status and results of a PDF extraction job.
    
    **Job Statuses:**
    - `pending`: Job is queued and waiting to start
    - `processing`: Job is currently being processed
    - `completed`: Job finished successfully with results available
    - `failed`: Job failed with error details available
    - `timeout`: Job exceeded maximum processing time
    
    **Response Content:**
    - For `completed` jobs: Full extraction results with inspection data
    - For `failed` jobs: Error details and diagnostic information
    - For active jobs: Progress information and estimated completion
    
    **Polling Recommendations:**
    - Poll every 5-10 seconds for active jobs
    - Results are cached and can be retrieved multiple times
    - Jobs are automatically cleaned up after 24 hours
    """,
    responses={
        200: {
            "description": "Job status retrieved successfully",
            "content": {
                "application/json": {
                    "example": ExampleModels.get_status_response_example()
                }
            }
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Job not found",
                        "message": "No job found with the specified ID",
                        "code": "job_not_found"
                    }
                }
            }
        }
    }
)
async def get_job_status(
    job_id: str,
    request: Request,
    job_manager: JobManager = Depends(get_job_manager)
):
    """Get the status and results of a processing job."""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        # Get job from manager
        job = await job_manager.get_job_status(job_id)
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Job not found",
                    "message": f"No job found with ID: {job_id}",
                    "code": ErrorCode.JOB_NOT_FOUND,
                    "request_id": request_id
                }
            )
        
        # Build response based on job status
        response_data = {
            "job_info": job.to_job_info()
        }
        
        # Add results for completed jobs
        if job.status == JobStatus.COMPLETED:
            extraction_data = job.to_extraction_data()
            if extraction_data:
                response_data["data"] = extraction_data
            else:
                # This shouldn't happen, but handle gracefully
                logger.warning(f"Completed job {job_id} has no extraction data")
        
        # Add error details for failed jobs
        elif job.status in [JobStatus.FAILED, JobStatus.TIMEOUT]:
            if job.error:
                response_data["error"] = job.error
            else:
                # Create generic error if none exists
                response_data["error"] = APIError(
                    error="Processing failed",
                    message="Job failed without specific error details",
                    code=ErrorCode.PROCESSING_ERROR
                )
        
        return StatusResponse(**response_data)
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except Exception as e:
        logger.error(f"Error retrieving job status for {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Status retrieval error",
                "message": "Failed to retrieve job status",
                "code": ErrorCode.INTERNAL_ERROR,
                "request_id": request_id
            }
        )


@router.delete(
    "/status/{job_id}",
    summary="Cancel a job",
    description="""
    Cancel a pending or running extraction job.
    
    **Behavior:**
    - `pending` jobs: Removed from queue immediately
    - `processing` jobs: Stopped as soon as possible
    - `completed`/`failed` jobs: Cannot be cancelled
    
    **Note:** Cancellation may take a few seconds for running jobs.
    """,
    responses={
        200: {
            "description": "Job cancelled successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Job cancelled successfully",
                        "job_id": "job_12345678-1234-5678-9abc-123456789012"
                    }
                }
            }
        },
        404: {
            "description": "Job not found"
        },
        409: {
            "description": "Job cannot be cancelled (already completed/failed)"
        }
    }
)
async def cancel_job(
    job_id: str,
    request: Request,
    job_manager: JobManager = Depends(get_job_manager)
):
    """Cancel a pending or running job."""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        # Check if job exists
        job = await job_manager.get_job_status(job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Job not found",
                    "message": f"No job found with ID: {job_id}",
                    "code": ErrorCode.JOB_NOT_FOUND,
                    "request_id": request_id
                }
            )
        
        # Check if job can be cancelled
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMEOUT]:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Cannot cancel job",
                    "message": f"Job is already {job.status.value} and cannot be cancelled",
                    "code": ErrorCode.VALIDATION_ERROR,
                    "request_id": request_id
                }
            )
        
        # Attempt cancellation
        cancelled = await job_manager.cancel_job(job_id)
        
        if cancelled:
            return {
                "success": True,
                "message": "Job cancelled successfully",
                "job_id": job_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Cancellation failed",
                    "message": "Failed to cancel the job",
                    "code": ErrorCode.INTERNAL_ERROR,
                    "request_id": request_id
                }
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Cancellation error",
                "message": "Failed to cancel job",
                "code": ErrorCode.INTERNAL_ERROR,
                "request_id": request_id
            }
        )


@router.get(
    "/jobs",
    response_model=List[JobInfo],
    summary="List recent jobs",
    description="""
    Get a list of recent extraction jobs with optional filtering.
    
    **Filtering:**
    - Filter by job status (pending, processing, completed, failed, timeout)
    - Pagination with limit and offset
    - Jobs are sorted by creation time (newest first)
    
    **Use Cases:**
    - Monitor job queue status
    - Review recent processing history
    - Debug failed jobs
    """,
    responses={
        200: {
            "description": "Job list retrieved successfully"
        }
    }
)
async def list_jobs(
    request: Request,
    status: Optional[JobStatus] = Query(
        None,
        description="Filter jobs by status"
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of jobs to return"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of jobs to skip"
    ),
    job_manager: JobManager = Depends(get_job_manager)
):
    """Get a list of recent jobs with optional filtering."""
    
    try:
        jobs = await job_manager.get_job_list(
            status_filter=status,
            limit=limit,
            offset=offset
        )
        
        return jobs
    
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Job listing error",
                "message": "Failed to retrieve job list",
                "code": ErrorCode.INTERNAL_ERROR,
                "request_id": getattr(request.state, "request_id", "unknown")
            }
        )


@router.get(
    "/stats",
    response_model=SystemStats,
    summary="Get system statistics",
    description="""
    Get comprehensive system statistics and performance metrics.
    
    **Included Metrics:**
    - Job processing statistics (total, completed, failed)
    - Performance metrics (average processing time, success rate)
    - System status (active jobs, uptime)
    - Pipeline statistics (model usage, confidence scores)
    
    **Use Cases:**
    - System monitoring and alerting
    - Performance analysis and optimization
    - Capacity planning
    """,
    responses={
        200: {
            "description": "Statistics retrieved successfully"
        }
    }
)
async def get_system_stats(
    request: Request,
    job_manager: JobManager = Depends(get_job_manager)
):
    """Get comprehensive system statistics."""
    
    try:
        stats = job_manager.get_statistics()
        
        return SystemStats(
            total_jobs=stats.get('total_jobs', 0),
            active_jobs=stats.get('active_jobs', 0),
            completed_jobs=stats.get('completed_jobs', 0),
            failed_jobs=stats.get('failed_jobs', 0),
            average_processing_time=stats.get('avg_processing_time'),
            success_rate=stats.get('success_rate'),
            pipeline_stats=stats.get('pipeline_stats')
        )
    
    except Exception as e:
        logger.error(f"Error retrieving system stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Statistics error",
                "message": "Failed to retrieve system statistics",
                "code": ErrorCode.INTERNAL_ERROR,
                "request_id": getattr(request.state, "request_id", "unknown")
            }
        )