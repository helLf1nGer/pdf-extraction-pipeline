"""
PDF extraction endpoints.

This module handles PDF file uploads and extraction job submission
with comprehensive validation and error handling.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import (
    ExtractResponse, APIError, ErrorCode, ExampleModels, 
    JobStatus, FileUpload
)
from ..core.config import get_settings
from ..services.job_manager import JobManager

# Get router dependencies
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def get_job_manager(request: Request) -> JobManager:
    """Dependency to get the job manager from the app."""
    return request.app.state.job_manager


@router.post(
    "/extract",
    response_model=ExtractResponse,
    status_code=202,
    summary="Extract data from PDF inspection report",
    description="""
    Upload a PDF inspection report for async extraction processing.
    
    The API will:
    1. Validate the uploaded PDF file
    2. Create an async processing job
    3. Return a job ID for tracking progress
    4. Process the PDF using AI models (Gemini 2.5 Pro/Flash with Claude backup)
    5. Extract structured inspection data with 92.3% accuracy
    
    **File Requirements:**
    - Must be a valid PDF file
    - Maximum size: 50MB
    - Supported content: Home inspection reports
    
    **Processing Features:**
    - Async processing with job tracking
    - Enhanced validation with confidence scoring
    - Automatic model routing based on complexity
    - Image extraction and association
    - Backup model fallback for low-confidence results
    
    **Response:**
    Returns immediately with a job ID. Use the `/status/{job_id}` endpoint 
    to track processing progress and retrieve results.
    """,
    responses={
        202: {
            "description": "PDF accepted for processing",
            "content": {
                "application/json": {
                    "example": ExampleModels.get_extract_response_example()
                }
            }
        },
        400: {
            "description": "Invalid request or file validation failed",
            "content": {
                "application/json": {
                    "example": ExampleModels.get_error_response_example()
                }
            }
        },
        413: {
            "description": "File too large",
            "content": {
                "application/json": {
                    "example": {
                        "error": "File too large",
                        "message": "File size exceeds maximum allowed size of 50MB",
                        "code": "file_too_large"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                        "code": "quota_exceeded"
                    }
                }
            }
        }
    }
)
@limiter.limit("30/minute")  # Default rate limit
async def extract_pdf(
    request: Request,
    file: UploadFile = File(
        ...,
        description="PDF file to process",
        media_type="application/pdf"
    ),
    enable_claude_fallback: bool = Form(
        True,
        description="Enable Claude backup models for low-confidence results"
    ),
    confidence_threshold: float = Form(
        70.0,
        ge=0.0,
        le=100.0,
        description="Minimum confidence threshold before using backup models"
    ),
    save_intermediate: bool = Form(
        False,
        description="Save intermediate processing results (markdown, images)"
    ),
    mock_mode: bool = Form(
        False,
        description="Use mock extraction for testing (no API calls)"
    ),
    job_manager: JobManager = Depends(get_job_manager)
):
    """Extract structured data from a PDF inspection report."""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        # Validate file upload
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File validation failed",
                    "message": "No filename provided",
                    "code": ErrorCode.VALIDATION_ERROR,
                    "request_id": request_id
                }
            )
        
        # Check file size
        file_content = await file.read()
        file_size = len(file_content)
        
        settings = get_settings()
        if file_size > settings.max_upload_size:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": "File too large",
                    "message": f"File size ({file_size} bytes) exceeds maximum allowed size of {settings.max_upload_size} bytes",
                    "code": ErrorCode.FILE_TOO_LARGE,
                    "details": {
                        "file_size": file_size,
                        "max_size": settings.max_upload_size,
                        "filename": file.filename
                    },
                    "request_id": request_id
                }
            )
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid file type",
                    "message": "Only PDF files are allowed",
                    "code": ErrorCode.INVALID_FILE_TYPE,
                    "details": {
                        "filename": file.filename,
                        "allowed_types": [".pdf"]
                    },
                    "request_id": request_id
                }
            )
        
        # Additional file validation
        try:
            file_upload = FileUpload(
                filename=file.filename,
                content_type=file.content_type or "application/pdf",
                size=file_size
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File validation failed",
                    "message": str(e),
                    "code": ErrorCode.VALIDATION_ERROR,
                    "request_id": request_id
                }
            )
        
        # Save uploaded file to temporary location
        try:
            # Create temporary file with proper extension
            settings = get_settings()
            temp_dir = Path(settings.upload_dir)
            temp_dir.mkdir(exist_ok=True, parents=True)
            
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.pdf',
                dir=temp_dir
            )
            
            temp_file.write(file_content)
            temp_file.close()
            temp_file_path = temp_file.name
            
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "File processing error",
                    "message": "Failed to save uploaded file",
                    "code": ErrorCode.INTERNAL_ERROR,
                    "request_id": request_id
                }
            )
        
        # Submit job for processing
        try:
            job_options = {
                'enable_claude_fallback': enable_claude_fallback,
                'confidence_threshold': confidence_threshold,
                'save_intermediate': save_intermediate,
                'mock_mode': mock_mode,
                'output_dir': get_settings().output_dir
            }
            
            job_id = await job_manager.submit_job(
                filename=file.filename,
                file_path=temp_file_path,
                options=job_options
            )
            
            logger.info(
                f"Job {job_id} submitted successfully",
                extra={
                    "request_id": request_id,
                    "pdf_filename": file.filename,
                    "file_size": file_size,
                    "options": job_options
                }
            )
            
            # Estimate processing time based on file size and settings
            estimated_time = min(60, max(30, file_size // (1024 * 1024) * 15))  # ~15s per MB
            
            return ExtractResponse(
                job_id=job_id,
                status=JobStatus.PENDING,
                message="PDF upload successful. Processing started.",
                estimated_time=estimated_time,
                status_url=f"/status/{job_id}"
            )
            
        except Exception as e:
            # Cleanup temp file if job submission failed
            try:
                os.unlink(temp_file_path)
            except:
                pass
            
            logger.error(f"Failed to submit job: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Job submission failed",
                    "message": "Failed to start processing job",
                    "code": ErrorCode.INTERNAL_ERROR,
                    "request_id": request_id
                }
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in extract_pdf: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred during file processing",
                "code": ErrorCode.INTERNAL_ERROR,
                "request_id": request_id
            }
        )


@router.get(
    "/extract/limits",
    summary="Get extraction service limits",
    description="Get current service limits and quotas for PDF extraction",
    response_model=dict
)
async def get_extraction_limits():
    """Get current service limits and quotas."""
    settings = get_settings()
    return {
        "max_file_size": settings.max_upload_size,
        "max_file_size_mb": settings.max_upload_size // (1024 * 1024),
        "allowed_file_types": settings.allowed_file_types,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "job_timeout_seconds": settings.job_timeout,
        "supported_features": {
            "async_processing": True,
            "job_tracking": True,
            "enhanced_validation": True,
            "claude_fallback": True,
            "image_extraction": True,
            "confidence_scoring": True
        }
    }