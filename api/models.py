"""
API models and schemas for the PDF extraction service.

These models define the request/response structures for the FastAPI endpoints,
extending the existing extraction pipeline schemas with API-specific fields.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator

# Import the existing extraction schemas
from src.extractors.schemas import HomeInspectionReport, InspectionIssue, ValidationMetadata


class JobStatus(str, Enum):
    """Enum for job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ErrorCode(str, Enum):
    """Enum for API error codes."""
    VALIDATION_ERROR = "validation_error"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_FILE_TYPE = "invalid_file_type"
    PROCESSING_ERROR = "processing_error"
    JOB_NOT_FOUND = "job_not_found"
    PIPELINE_ERROR = "pipeline_error"
    TIMEOUT_ERROR = "timeout_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    INTERNAL_ERROR = "internal_error"


# Request Models

class ExtractRequest(BaseModel):
    """Request model for PDF extraction (used for documentation)."""
    
    enable_claude_fallback: bool = Field(
        default=True,
        description="Enable Claude backup models for low-confidence results"
    )
    
    confidence_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum confidence threshold before using backup models"
    )
    
    save_intermediate: bool = Field(
        default=False,
        description="Save intermediate processing results (markdown, images)"
    )
    
    mock_mode: bool = Field(
        default=False,
        description="Use mock extraction for testing (no API calls)"
    )


# Response Models

class APIError(BaseModel):
    """Standard API error response."""
    
    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Human-readable error message")
    code: ErrorCode = Field(..., description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional error details"
    )
    request_id: Optional[str] = Field(
        None, 
        description="Unique request identifier for debugging"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )


class JobInfo(BaseModel):
    """Job information and metadata."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    filename: Optional[str] = Field(None, description="Original filename")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    processing_time: Optional[float] = Field(
        None, 
        description="Total processing time in seconds"
    )
    progress: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=100.0,
        description="Processing progress percentage"
    )
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time"
    )


class ExtractResponse(BaseModel):
    """Response for PDF extraction request."""
    
    job_id: str = Field(..., description="Unique job identifier for tracking")
    status: JobStatus = Field(..., description="Initial job status")
    message: str = Field(..., description="Status message")
    estimated_time: Optional[int] = Field(
        None,
        description="Estimated processing time in seconds"
    )
    status_url: str = Field(..., description="URL to check job status")


class ProcessingMetadata(BaseModel):
    """Metadata about the processing pipeline."""
    
    model_used: Optional[str] = Field(None, description="Primary AI model used")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    pdf_complexity: Optional[str] = Field(None, description="Classified PDF complexity")
    validation_metadata: Optional[ValidationMetadata] = Field(
        None, 
        description="Validation metadata if enhanced validation was used"
    )
    pipeline_stats: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional pipeline statistics"
    )


class ExtractionData(BaseModel):
    """Complete extraction results with metadata."""
    
    report: HomeInspectionReport = Field(..., description="Extracted inspection report")
    metadata: ProcessingMetadata = Field(..., description="Processing metadata")
    extraction_quality: Optional[Dict[str, Any]] = Field(
        None,
        description="Quality metrics and confidence scores"
    )


class JobResult(BaseModel):
    """Complete job result with data or error information."""
    
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Final job status")
    job_info: JobInfo = Field(..., description="Job metadata and timing")
    
    # Success case
    data: Optional[ExtractionData] = Field(
        None, 
        description="Extraction results (present when status is completed)"
    )
    
    # Error case
    error: Optional[APIError] = Field(
        None, 
        description="Error information (present when status is failed)"
    )


class StatusResponse(BaseModel):
    """Response for job status requests."""
    
    job_info: JobInfo = Field(..., description="Job information and metadata")
    
    # For completed jobs
    data: Optional[ExtractionData] = Field(
        None,
        description="Extraction results (only present when job is completed)"
    )
    
    # For failed jobs  
    error: Optional[APIError] = Field(
        None,
        description="Error information (only present when job failed)"
    )


# Health Check Models

class ComponentStatus(BaseModel):
    """Status of individual system components."""
    
    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Component status (healthy, unhealthy, unknown)")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional component details"
    )
    last_check: datetime = Field(..., description="Last health check timestamp")


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Health check timestamp"
    )
    version: str = Field(..., description="API version")
    uptime: float = Field(..., description="System uptime in seconds")
    components: List[ComponentStatus] = Field(
        default_factory=list,
        description="Individual component statuses"
    )


class SystemStats(BaseModel):
    """System statistics and metrics."""
    
    total_jobs: int = Field(..., description="Total jobs processed")
    active_jobs: int = Field(..., description="Currently active jobs")
    completed_jobs: int = Field(..., description="Successfully completed jobs")
    failed_jobs: int = Field(..., description="Failed jobs")
    average_processing_time: Optional[float] = Field(
        None,
        description="Average processing time in seconds"
    )
    success_rate: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Job success rate (0.0 to 1.0)"
    )
    pipeline_stats: Optional[Dict[str, Any]] = Field(
        None,
        description="Extraction pipeline statistics"
    )


# Validation Models

class FileUpload(BaseModel):
    """Model for file upload validation."""
    
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME content type")
    size: int = Field(..., ge=0, description="File size in bytes")
    
    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v):
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        
        # Check for dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Filename contains invalid character: {char}")
        
        return v.strip()
    
    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v):
        allowed_types = ["application/pdf"]
        if v not in allowed_types:
            raise ValueError(f"Content type must be one of {allowed_types}")
        return v


# Utility Models

class PaginatedResponse(BaseModel):
    """Base model for paginated responses."""
    
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")


# Example schemas for documentation
class ExampleModels:
    """Example models for API documentation."""
    
    @staticmethod
    def get_extract_response_example() -> Dict[str, Any]:
        return {
            "job_id": "job_12345678-1234-5678-9abc-123456789012",
            "status": "pending",
            "message": "PDF upload successful. Processing started.",
            "estimated_time": 45,
            "status_url": "/status/job_12345678-1234-5678-9abc-123456789012"
        }
    
    @staticmethod
    def get_status_response_example() -> Dict[str, Any]:
        return {
            "job_info": {
                "job_id": "job_12345678-1234-5678-9abc-123456789012",
                "status": "completed",
                "filename": "inspection_report.pdf",
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:05Z", 
                "completed_at": "2024-01-15T10:31:23Z",
                "processing_time": 78.5,
                "progress": 100.0
            },
            "data": {
                "report": {
                    "report_name": "123 Main Street Home Inspection",
                    "issues": [
                        {
                            "issue_name": "Electrical Panel Issues",
                            "issue_type": "Electrical",
                            "issue_description": "The main electrical panel shows signs of corrosion and several breakers appear to be loose.",
                            "issue_summary": "Main panel needs inspection and repair",
                            "severity": "high",
                            "location": "Basement utility room",
                            "issue_images": ["electrical_panel_01.jpg", "electrical_panel_02.jpg"]
                        }
                    ],
                    "source_pdf": "inspection_report.pdf"
                },
                "metadata": {
                    "model_used": "gemini-2.5-pro",
                    "processing_time": 78.5,
                    "pdf_complexity": "medium",
                    "validation_metadata": {
                        "validation_performed": True,
                        "confidence_score": 87.5,
                        "validation_decision": "use_primary",
                        "agreement_percentage": 92.0,
                        "pipeline_used": "gemini_pro_primary"
                    }
                }
            }
        }
    
    @staticmethod
    def get_error_response_example() -> Dict[str, Any]:
        return {
            "error": "File validation failed",
            "message": "The uploaded file exceeds the maximum size limit of 50MB",
            "code": "file_too_large",
            "details": {
                "file_size": 52428800,
                "max_size": 52428800,
                "filename": "large_inspection.pdf"
            },
            "request_id": "req_12345678-1234-5678-9abc-123456789012",
            "timestamp": "2024-01-15T10:30:00Z"
        }