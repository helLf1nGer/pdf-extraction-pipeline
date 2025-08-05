"""
Pydantic schemas for home inspection report extraction.

This module defines the data structures for extracting structured data
from home inspection PDFs using LlamaParse and AI models.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class ImageLocation(BaseModel):
    """Location information for where an image appears in the document."""
    
    page_number: int = Field(
        ...,
        description="Page number where the image appears",
        ge=1
    )
    
    location_description: Optional[str] = Field(
        None,
        description="Description of where on the page the image appears (e.g., 'top-right', 'center', 'bottom section')",
        max_length=200
    )
    
    section_context: Optional[str] = Field(
        None,
        description="Context about what section or part of the report this image relates to",
        max_length=300
    )


class ImageMetadata(BaseModel):
    """Enhanced metadata for image associations with confidence scoring."""
    
    image_path: str = Field(
        ..., 
        description="Path to the image file"
    )
    
    expected_location: Optional[ImageLocation] = Field(
        None,
        description="Expected location information provided by the model"
    )
    
    actual_page: Optional[int] = Field(
        None,
        description="Actual page number where this image was extracted",
        ge=1
    )
    
    confidence_score: Optional[float] = Field(
        None,
        description="Confidence score (0-100) for this image association",
        ge=0,
        le=100
    )
    
    matching_method: Optional[str] = Field(
        None,
        description="Method used to match this image (location_based, proximity, context, etc.)"
    )
    
    location_match: Optional[bool] = Field(
        None,
        description="Whether the expected location matches the actual extracted image location"
    )


class InspectionIssue(BaseModel):
    """Individual issue or finding from a home inspection report."""
    
    issue_name: str = Field(
        ..., 
        description="Name or title of the issue",
        min_length=1,
        max_length=200
    )
    
    issue_type: str = Field(
        ...,
        description="Category or type of issue (e.g., 'Electrical', 'Plumbing', 'Structural')",
        min_length=1,
        max_length=100
    )
    
    issue_description: str = Field(
        ...,
        description="Detailed description of the issue",
        min_length=1,
        max_length=2000
    )
    
    issue_summary: str = Field(
        ...,
        description="Brief summary of the issue",
        min_length=1,
        max_length=500
    )
    
    severity: str = Field(
        default="medium",
        description="Issue severity level (low, medium, high)",
        pattern="^(low|medium|high)$"
    )
    
    location: Optional[str] = Field(
        None,
        description="Location of the issue within the property",
        max_length=200
    )
    
    issue_images: List[str] = Field(
        default_factory=list,
        description="List of image references/filenames associated with this issue (legacy format)"
    )
    
    enhanced_images: List[ImageMetadata] = Field(
        default_factory=list,
        description="Enhanced image metadata with confidence scores and location matching"
    )
    
    expected_image_locations: List[ImageLocation] = Field(
        default_factory=list,
        description="Model-provided locations where images for this issue should appear"
    )
    
    # Aliases for backward compatibility with enhanced validation router
    @property
    def description(self) -> str:
        """Alias for issue_description for router compatibility."""
        return self.issue_description
    
    @property
    def all_image_paths(self) -> List[str]:
        """Get all image paths from both legacy and enhanced formats."""
        paths = list(self.issue_images)  # Legacy format
        paths.extend([img.image_path for img in self.enhanced_images])  # Enhanced format
        return list(set(paths))  # Remove duplicates
    
    def get_high_confidence_images(self, min_confidence: float = 70.0) -> List[ImageMetadata]:
        """Get images with confidence scores above threshold."""
        return [img for img in self.enhanced_images 
                if img.confidence_score is not None and img.confidence_score >= min_confidence]
    
    @validator('issue_name', 'issue_type', 'issue_description', 'issue_summary', 'location')
    def strip_whitespace(cls, v):
        """Strip leading/trailing whitespace from string fields."""
        return v.strip() if isinstance(v, str) and v else v
    
    @validator('issue_type')
    def normalize_issue_type(cls, v):
        """Normalize issue type capitalization."""
        return v.title() if isinstance(v, str) else v
    
    @validator('severity')
    def normalize_severity(cls, v):
        """Normalize severity to lowercase."""
        return v.lower() if isinstance(v, str) else v


class HomeInspectionReport(BaseModel):
    """Complete home inspection report with extracted data."""
    
    report_name: str = Field(
        ...,
        description="Name or title of the inspection report",
        min_length=1,
        max_length=300
    )
    
    issues: List[InspectionIssue] = Field(
        default_factory=list,
        description="List of all issues/findings extracted from the report"
    )
    
    # Optional metadata fields for enhanced tracking
    source_pdf: Optional[str] = Field(
        None,
        description="Original PDF filename"
    )
    
    extraction_model: Optional[str] = Field(
        None,
        description="AI model used for extraction (e.g., 'gemini-2.5-pro', 'claude-3.5-sonnet')"
    )
    
    total_pages: Optional[int] = Field(
        None,
        description="Total number of pages in the source PDF",
        ge=1
    )
    
    @validator('report_name')
    def strip_report_name(cls, v):
        """Strip leading/trailing whitespace from report name."""
        return v.strip() if isinstance(v, str) else v
    
    @property
    def issue_count(self) -> int:
        """Return the total number of issues in this report."""
        return len(self.issues)
    
    @property
    def issue_types(self) -> List[str]:
        """Return unique list of issue types in this report."""
        return list(set(issue.issue_type for issue in self.issues))
    
    def get_issues_by_type(self, issue_type: str) -> List[InspectionIssue]:
        """Get all issues of a specific type."""
        return [issue for issue in self.issues if issue.issue_type.lower() == issue_type.lower()]


class ValidationMetadata(BaseModel):
    """Metadata from validation process between models."""
    
    validation_performed: bool = Field(
        ...,
        description="Whether validation comparison was performed"
    )
    
    confidence_score: Optional[float] = Field(
        None,
        description="Overall confidence score (0-100) from validation",
        ge=0,
        le=100
    )
    
    validation_decision: Optional[str] = Field(
        None,
        description="Validation decision (use_primary, use_validator, manual_review, use_consensus)"
    )
    
    agreement_percentage: Optional[float] = Field(
        None,
        description="Percentage of issues that matched between models",
        ge=0,
        le=100
    )
    
    issue_count_difference: Optional[int] = Field(
        None,
        description="Absolute difference in issue counts between models",
        ge=0
    )
    
    pipeline_used: Optional[str] = Field(
        None,
        description="Which pipeline was ultimately used (primary_only, consensus, claude_fallback, etc.)"
    )
    
    discrepancies_found: List[str] = Field(
        default_factory=list,
        description="List of discrepancies identified during validation"
    )
    
    processing_notes: List[str] = Field(
        default_factory=list,
        description="Additional processing notes from validation"
    )


class ExtractionResult(BaseModel):
    """Result of the extraction process including metadata."""
    
    success: bool = Field(..., description="Whether extraction was successful")
    
    report: Optional[HomeInspectionReport] = Field(
        None,
        description="Extracted report data if successful"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error message if extraction failed"
    )
    
    processing_time: Optional[float] = Field(
        None,
        description="Time taken for extraction in seconds",
        ge=0
    )
    
    model_used: Optional[str] = Field(
        None,
        description="AI model that was used for extraction"
    )
    
    pdf_complexity: Optional[str] = Field(
        None,
        description="Classified complexity level or processing approach"
    )
    
    # Enhanced validation metadata
    validation_metadata: Optional[ValidationMetadata] = Field(
        None,
        description="Detailed validation metadata if validation was performed"
    )


# Example usage and validation
if __name__ == "__main__":
    # Test schema with sample data
    sample_issue = InspectionIssue(
        issue_name="Knob and Tube Wiring",
        issue_type="Electrical",
        issue_description="Old knob and tube wiring found in basement requiring replacement for safety compliance.",
        issue_summary="Replace old knob and tube wiring",
        issue_images=["electrical_01.jpg", "basement_wiring.jpg"]
    )
    
    sample_report = HomeInspectionReport(
        report_name="123 Main Street Home Inspection",
        issues=[sample_issue],
        source_pdf="1.pdf",
        extraction_model="gemini-2.5-pro",
        total_pages=24
    )
    
    print("Schema validation successful!")
    print(f"Report: {sample_report.report_name}")
    print(f"Issues: {sample_report.issue_count}")
    print(f"Issue types: {sample_report.issue_types}")