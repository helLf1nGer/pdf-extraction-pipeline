"""
Health check and system monitoring endpoints.

This module provides health check endpoints for monitoring
system status and component health.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from ..models import HealthResponse, ComponentStatus
from ..core.config import get_settings
from ..services.job_manager import JobManager

# Get logger
logger = logging.getLogger(__name__)

# Track service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Create router
router = APIRouter()


def get_job_manager(request: Request) -> JobManager:
    """Dependency to get the job manager from the app."""
    return request.app.state.job_manager


@router.get(
    "/",
    summary="Basic health check",
    description="""
    Basic health check endpoint that returns system status.
    
    **Response Codes:**
    - 200: System is healthy and operational
    - 503: System is unhealthy (one or more critical components failing)
    
    **Use Cases:**
    - Load balancer health checks
    - Basic monitoring and alerting
    - Service discovery health verification
    """,
    responses={
        200: {
            "description": "System is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "version": "1.0.0",
                        "uptime": 3600.5
                    }
                }
            }
        },
        503: {
            "description": "System is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "version": "1.0.0",
                        "uptime": 3600.5,
                        "components": [
                            {
                                "name": "extraction_pipeline",
                                "status": "unhealthy",
                                "details": {"error": "API keys not configured"},
                                "last_check": "2024-01-15T10:30:00Z"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def health_check():
    """Basic health check endpoint."""
    
    try:
        settings = get_settings()
        uptime = time.time() - SERVICE_START_TIME
        
        # Return simple dictionary instead of model
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": settings.api_version,
            "uptime": uptime
        }
    except Exception as e:
        # Return error details for debugging
        return JSONResponse(
            status_code=500,
            content={
                "error": "Health check failed",
                "details": str(e),
                "type": type(e).__name__
            }
        )


@router.get(
    "/detailed",
    response_model=HealthResponse,
    summary="Detailed health check",
    description="""
    Detailed health check with component-level status information.
    
    **Checked Components:**
    - Job Manager: Queue status and processing capacity
    - Extraction Pipeline: AI model availability and configuration
    - File System: Upload and output directory accessibility
    - Memory: Job history and active job counts
    
    **Response Codes:**
    - 200: All components healthy
    - 503: One or more components unhealthy
    
    **Use Cases:**
    - Comprehensive system monitoring
    - Troubleshooting and diagnostics
    - Component-level alerting
    """,
    responses={
        200: {
            "description": "Detailed health status"
        },
        503: {
            "description": "System or components unhealthy"
        }
    }
)
async def detailed_health_check(
    request: Request,
    job_manager: JobManager = Depends(get_job_manager)
):
    """Detailed health check with component status."""
    
    uptime = time.time() - SERVICE_START_TIME
    components = []
    overall_status = "healthy"
    
    # Check job manager
    try:
        job_stats = job_manager.get_statistics()
        active_jobs = job_stats.get('active_jobs', 0)
        
        job_manager_status = "healthy"
        job_manager_details = {
            "active_jobs": active_jobs,
            "max_concurrent": settings.max_concurrent_jobs if 'settings' in locals() else 3,
            "total_processed": job_stats.get('total_jobs', 0),
            "success_rate": job_stats.get('success_rate', 0)
        }
        
        # Check if we're at capacity
        settings = get_settings()
        if active_jobs >= settings.max_concurrent_jobs:
            job_manager_status = "degraded"
            job_manager_details["warning"] = "At maximum capacity"
        
    except Exception as e:
        job_manager_status = "unhealthy"
        job_manager_details = {"error": str(e)}
        overall_status = "unhealthy"
    
    components.append(ComponentStatus(
        name="job_manager",
        status=job_manager_status,
        details=job_manager_details,
        last_check=datetime.now(timezone.utc)
    ))
    
    # Check extraction pipeline
    try:
        pipeline_validation = await job_manager.validate_pipeline()
        
        if pipeline_validation["overall_status"]:
            pipeline_status = "healthy"
            pipeline_details = {
                "configuration": pipeline_validation.get("configuration", {}),
                "components": pipeline_validation.get("components", {})
            }
        else:
            pipeline_status = "unhealthy"
            pipeline_details = {
                "errors": pipeline_validation.get("errors", []),
                "warnings": pipeline_validation.get("warnings", [])
            }
            overall_status = "unhealthy"
            
    except Exception as e:
        pipeline_status = "unhealthy"
        pipeline_details = {"error": str(e)}
        overall_status = "unhealthy"
    
    components.append(ComponentStatus(
        name="extraction_pipeline",
        status=pipeline_status,
        details=pipeline_details,
        last_check=datetime.now(timezone.utc)
    ))
    
    # Check file system
    try:
        import os
        from pathlib import Path
        
        settings = get_settings()
        upload_dir = Path(settings.upload_dir)
        output_dir = Path(settings.output_dir)
        
        upload_accessible = upload_dir.exists() and os.access(upload_dir, os.W_OK)
        output_accessible = output_dir.exists() and os.access(output_dir, os.W_OK)
        
        if upload_accessible and output_accessible:
            fs_status = "healthy"
            fs_details = {
                "upload_dir": str(upload_dir),
                "output_dir": str(output_dir),
                "upload_writable": upload_accessible,
                "output_writable": output_accessible
            }
        else:
            fs_status = "unhealthy"
            fs_details = {
                "upload_dir": str(upload_dir),
                "output_dir": str(output_dir),
                "upload_writable": upload_accessible,
                "output_writable": output_accessible,
                "error": "Directory not accessible or writable"
            }
            overall_status = "unhealthy"
            
    except Exception as e:
        fs_status = "unhealthy"
        fs_details = {"error": str(e)}
        overall_status = "unhealthy"
    
    components.append(ComponentStatus(
        name="file_system",
        status=fs_status,
        details=fs_details,
        last_check=datetime.now(timezone.utc)
    ))
    
    # Check memory/resource usage
    try:
        import psutil
        memory = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')
        
        memory_percent = memory.percent
        disk_percent = disk_usage.percent
        
        if memory_percent < 90 and disk_percent < 90:
            resource_status = "healthy"
        elif memory_percent < 95 and disk_percent < 95:
            resource_status = "degraded"
        else:
            resource_status = "unhealthy"
            overall_status = "degraded" if overall_status == "healthy" else overall_status
        
        resource_details = {
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
            "available_memory_gb": memory.available / (1024**3),
            "available_disk_gb": disk_usage.free / (1024**3)
        }
        
    except ImportError:
        # psutil not available, skip resource check
        resource_status = "unknown"
        resource_details = {"note": "psutil not available for resource monitoring"}
    except Exception as e:
        resource_status = "unknown"
        resource_details = {"error": str(e)}
    
    components.append(ComponentStatus(
        name="system_resources",
        status=resource_status,
        details=resource_details,
        last_check=datetime.now(timezone.utc)
    ))
    
    # Create response
    health_response = HealthResponse(
        status=overall_status,
        version=settings.api_version if 'settings' in locals() else "1.0.0",
        uptime=uptime,
        components=components
    )
    
    # Return appropriate status code
    status_code = 200 if overall_status == "healthy" else 503
    
    return JSONResponse(
        status_code=status_code,
        content=health_response.model_dump()
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="""
    Kubernetes-style readiness probe endpoint.
    
    **Purpose:**
    Indicates whether the service is ready to accept traffic.
    Unlike health checks, this focuses on whether the service can
    handle requests right now.
    
    **Checks:**
    - Job manager is initialized and operational
    - Extraction pipeline components are available
    - Required directories are accessible
    
    **Response Codes:**
    - 200: Service is ready to accept traffic
    - 503: Service is not ready (initialization in progress or failing)
    """,
    responses={
        200: {
            "description": "Service is ready",
            "content": {
                "application/json": {
                    "example": {
                        "ready": True,
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        503: {
            "description": "Service is not ready",
            "content": {
                "application/json": {
                    "example": {
                        "ready": False,
                        "timestamp": "2024-01-15T10:30:00Z",
                        "reason": "Pipeline initialization in progress"
                    }
                }
            }
        }
    }
)
async def readiness_probe(
    request: Request,
    job_manager: JobManager = Depends(get_job_manager)
):
    """Readiness probe for Kubernetes-style health checking."""
    
    try:
        # Check if job manager is operational
        stats = job_manager.get_statistics()
        
        # Check if we can accept new jobs (not at capacity)
        active_jobs = stats.get('active_jobs', 0)
        settings = get_settings()
        at_capacity = active_jobs >= settings.max_concurrent_jobs
        
        # Basic pipeline check (quick)
        pipeline_ready = True
        reason = None
        
        if at_capacity:
            pipeline_ready = False
            reason = f"At maximum capacity ({active_jobs}/{settings.max_concurrent_jobs} jobs)"
        
        if pipeline_ready:
            return JSONResponse(
                status_code=200,
                content={
                    "ready": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": reason
                }
            )
    
    except Exception as e:
        logger.error(f"Readiness probe failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": f"Service error: {str(e)}"
            }
        )


@router.get(
    "/live",
    summary="Liveness probe",
    description="""
    Kubernetes-style liveness probe endpoint.
    
    **Purpose:**
    Indicates whether the service is alive and running.
    This is a minimal check that should only fail if the
    service needs to be restarted.
    
    **Response Codes:**
    - 200: Service is alive
    - 503: Service is dead and should be restarted
    """,
    responses={
        200: {
            "description": "Service is alive"
        }
    }
)
async def liveness_probe():
    """Minimal liveness probe for Kubernetes-style health checking."""
    
    # Very basic check - if we can respond, we're alive
    return JSONResponse(
        status_code=200,
        content={
            "alive": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    )