"""
Pydantic schemas for home inspection report evaluation.

This module defines the data structures for evaluating extraction accuracy
using the LLM-as-judge pattern to compare extracted JSON against source PDFs.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class AccuracyLevel(str, Enum):
    """Accuracy level classifications."""
    EXCELLENT = "excellent"  # 95-100%
    GOOD = "good"           # 85-94%
    FAIR = "fair"           # 70-84%
    POOR = "poor"           # 50-69%
    FAILING = "failing"     # 0-49%


class IssueEvaluationResult(BaseModel):
    """Evaluation result for a single extracted issue."""
    
    issue_index: int = Field(
        ...,
        description="Index of the issue in the extracted data",
        ge=0
    )
    
    extracted_issue_name: str = Field(
        ...,
        description="Name of the issue as extracted",
        min_length=1,
        max_length=200
    )
    
    name_accuracy_score: float = Field(
        ...,
        description="Accuracy score for issue name (0-100)",
        ge=0,
        le=100
    )
    
    description_accuracy_score: float = Field(
        ...,
        description="Accuracy score for issue description (0-100)",
        ge=0,
        le=100
    )
    
    description_completeness_score: float = Field(
        ...,
        description="Completeness score for description (0-100)",
        ge=0,
        le=100
    )
    
    image_association_score: float = Field(
        ...,
        description="Accuracy score for image associations (0-100)",
        ge=0,
        le=100
    )
    
    overall_issue_score: float = Field(
        ...,
        description="Overall accuracy score for this issue (0-100)",
        ge=0,
        le=100
    )
    
    matched_ground_truth: bool = Field(
        ...,
        description="Whether this issue was matched to ground truth"
    )
    
    ground_truth_issue_name: Optional[str] = Field(
        None,
        description="Corresponding issue name in ground truth (if matched)"
    )
    
    evaluation_notes: List[str] = Field(
        default_factory=list,
        description="Detailed evaluation notes and observations"
    )
    
    missing_information: List[str] = Field(
        default_factory=list,
        description="Information that was missing from the extraction"
    )
    
    incorrect_information: List[str] = Field(
        default_factory=list,
        description="Information that was incorrectly extracted"
    )
    
    image_extraction_issues: List[str] = Field(
        default_factory=list,
        description="Issues with image extraction for this item"
    )


class ImageEvaluationResult(BaseModel):
    """Evaluation result for image extraction."""
    
    total_images_in_pdf: int = Field(
        ...,
        description="Total number of images found in the PDF",
        ge=0
    )
    
    total_images_extracted: int = Field(
        ...,
        description="Total number of images extracted",
        ge=0
    )
    
    correctly_associated_images: int = Field(
        ...,
        description="Number of images correctly associated with issues",
        ge=0
    )
    
    extraction_completeness: float = Field(
        ...,
        description="Percentage of images that were extracted (0-100)",
        ge=0,
        le=100
    )
    
    association_accuracy: float = Field(
        ...,
        description="Accuracy of image-to-issue associations (0-100)",
        ge=0,
        le=100
    )
    
    image_quality_score: float = Field(
        ...,
        description="Quality score for extracted images (0-100)",
        ge=0,
        le=100
    )
    
    missing_images: List[str] = Field(
        default_factory=list,
        description="List of images that should have been extracted but were not"
    )
    
    incorrect_associations: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Images that were associated with wrong issues"
    )


class ExtractionCompletenessResult(BaseModel):
    """Evaluation result for extraction completeness."""
    
    ground_truth_issue_count: int = Field(
        ...,
        description="Total number of issues identified in ground truth",
        ge=0
    )
    
    extracted_issue_count: int = Field(
        ...,
        description="Total number of issues extracted",
        ge=0
    )
    
    correctly_identified_issues: int = Field(
        ...,
        description="Number of issues correctly identified",
        ge=0
    )
    
    false_positives: int = Field(
        ...,
        description="Number of issues extracted that don't exist in ground truth",
        ge=0
    )
    
    false_negatives: int = Field(
        ...,
        description="Number of real issues that were missed",
        ge=0
    )
    
    precision: float = Field(
        ...,
        description="Precision score (correct / extracted) * 100",
        ge=0,
        le=100
    )
    
    recall: float = Field(
        ...,
        description="Recall score (correct / ground_truth) * 100",
        ge=0,
        le=100
    )
    
    f1_score: float = Field(
        ...,
        description="F1 score (harmonic mean of precision and recall)",
        ge=0,
        le=100
    )
    
    missed_issues: List[str] = Field(
        default_factory=list,
        description="Names of issues that were missed"
    )
    
    extra_issues: List[str] = Field(
        default_factory=list,
        description="Names of issues that were incorrectly identified as separate issues"
    )


class PDFEvaluationResult(BaseModel):
    """Complete evaluation result for a single PDF."""
    
    pdf_filename: str = Field(
        ...,
        description="Name of the evaluated PDF file",
        min_length=1
    )
    
    json_filename: str = Field(
        ...,
        description="Name of the extracted JSON file",
        min_length=1
    )
    
    evaluation_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this evaluation was performed"
    )
    
    evaluator_model: str = Field(
        ...,
        description="AI model used for evaluation",
        min_length=1
    )
    
    # Completeness metrics
    completeness_result: ExtractionCompletenessResult = Field(
        ...,
        description="Results of completeness evaluation"
    )
    
    # Image evaluation
    image_result: ImageEvaluationResult = Field(
        ...,
        description="Results of image extraction evaluation"
    )
    
    # Per-issue evaluations
    issue_evaluations: List[IssueEvaluationResult] = Field(
        default_factory=list,
        description="Evaluation results for each extracted issue"
    )
    
    # Overall scores
    overall_accuracy_score: float = Field(
        ...,
        description="Overall extraction accuracy score (0-100)",
        ge=0,
        le=100
    )
    
    content_accuracy_score: float = Field(
        ...,
        description="Content accuracy score (names, descriptions) (0-100)",
        ge=0,
        le=100
    )
    
    image_accuracy_score: float = Field(
        ...,
        description="Image extraction accuracy score (0-100)",
        ge=0,
        le=100
    )
    
    completeness_score: float = Field(
        ...,
        description="Extraction completeness score (0-100)",
        ge=0,
        le=100
    )
    
    # Classification
    accuracy_level: AccuracyLevel = Field(
        ...,
        description="Classification of overall accuracy level"
    )
    
    passes_threshold: bool = Field(
        ...,
        description="Whether this extraction meets the 85% threshold"
    )
    
    # Detailed analysis
    evaluation_summary: str = Field(
        ...,
        description="Summary of the evaluation findings",
        min_length=10
    )
    
    strengths: List[str] = Field(
        default_factory=list,
        description="Strengths identified in the extraction"
    )
    
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Weaknesses identified in the extraction"
    )
    
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )
    
    # Processing metadata
    evaluation_time_seconds: Optional[float] = Field(
        None,
        description="Time taken for evaluation in seconds",
        ge=0
    )
    
    ground_truth_parsing_time: Optional[float] = Field(
        None,
        description="Time taken to parse ground truth from PDF",
        ge=0
    )
    
    llm_evaluation_time: Optional[float] = Field(
        None,
        description="Time taken for LLM evaluation",
        ge=0
    )


class BatchEvaluationResult(BaseModel):
    """Results from evaluating multiple PDFs."""
    
    evaluation_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this batch evaluation was performed"
    )
    
    evaluator_model: str = Field(
        ...,
        description="AI model used for evaluation",
        min_length=1
    )
    
    total_pdfs_evaluated: int = Field(
        ...,
        description="Total number of PDFs evaluated",
        ge=0
    )
    
    successful_evaluations: int = Field(
        ...,
        description="Number of successful evaluations",
        ge=0
    )
    
    failed_evaluations: int = Field(
        ...,
        description="Number of failed evaluations",
        ge=0
    )
    
    # Individual results
    pdf_results: List[PDFEvaluationResult] = Field(
        default_factory=list,
        description="Individual evaluation results for each PDF"
    )
    
    # Aggregate statistics
    average_overall_accuracy: float = Field(
        ...,
        description="Average overall accuracy across all PDFs (0-100)",
        ge=0,
        le=100
    )
    
    average_content_accuracy: float = Field(
        ...,
        description="Average content accuracy across all PDFs (0-100)",
        ge=0,
        le=100
    )
    
    average_image_accuracy: float = Field(
        ...,
        description="Average image accuracy across all PDFs (0-100)",
        ge=0,
        le=100
    )
    
    average_completeness: float = Field(
        ...,
        description="Average completeness across all PDFs (0-100)",
        ge=0,
        le=100
    )
    
    # Threshold analysis
    pdfs_passing_threshold: int = Field(
        ...,
        description="Number of PDFs meeting the 85% threshold",
        ge=0
    )
    
    overall_pass_rate: float = Field(
        ...,
        description="Percentage of PDFs passing the 85% threshold",
        ge=0,
        le=100
    )
    
    meets_system_requirements: bool = Field(
        ...,
        description="Whether the overall system meets >85% accuracy requirement"
    )
    
    # Performance breakdown
    accuracy_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of PDFs by accuracy level"
    )
    
    # Processing statistics
    total_evaluation_time: Optional[float] = Field(
        None,
        description="Total time for batch evaluation in seconds",
        ge=0
    )
    
    average_evaluation_time: Optional[float] = Field(
        None,
        description="Average time per PDF evaluation in seconds",
        ge=0
    )
    
    # Summary and recommendations
    summary: str = Field(
        ...,
        description="Executive summary of batch evaluation results",
        min_length=50
    )
    
    common_strengths: List[str] = Field(
        default_factory=list,
        description="Common strengths across extractions"
    )
    
    common_weaknesses: List[str] = Field(
        default_factory=list,
        description="Common weaknesses across extractions"
    )
    
    system_recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improving the extraction system"
    )
    
    failed_evaluations_details: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Details about failed evaluations"
    )

    @validator('overall_pass_rate')
    def validate_pass_rate(cls, v, values):
        """Validate pass rate calculation."""
        if 'total_pdfs_evaluated' in values and values['total_pdfs_evaluated'] > 0:
            expected_rate = (values.get('pdfs_passing_threshold', 0) / values['total_pdfs_evaluated']) * 100
            if abs(v - expected_rate) > 0.1:  # Allow small floating point errors
                raise ValueError(f"Pass rate {v} doesn't match calculated rate {expected_rate}")
        return v

    @validator('meets_system_requirements')
    def validate_system_requirements(cls, v, values):
        """Validate system requirements based on average accuracy."""
        if 'average_overall_accuracy' in values:
            expected = values['average_overall_accuracy'] >= 85.0
            if v != expected:
                raise ValueError(f"System requirements flag {v} doesn't match average accuracy {values['average_overall_accuracy']}")
        return v


class EvaluationError(BaseModel):
    """Details about an evaluation error."""
    
    pdf_filename: str = Field(
        ...,
        description="Name of the PDF that failed evaluation"
    )
    
    error_type: str = Field(
        ...,
        description="Type of error that occurred"
    )
    
    error_message: str = Field(
        ...,
        description="Detailed error message"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the error occurred"
    )
    
    recovery_attempted: bool = Field(
        default=False,
        description="Whether recovery was attempted"
    )
    
    recovery_successful: bool = Field(
        default=False,
        description="Whether recovery was successful"
    )


# Utility functions for schema validation and creation
def calculate_accuracy_level(score: float) -> AccuracyLevel:
    """Calculate accuracy level from score."""
    if score >= 95:
        return AccuracyLevel.EXCELLENT
    elif score >= 85:
        return AccuracyLevel.GOOD
    elif score >= 70:
        return AccuracyLevel.FAIR
    elif score >= 50:
        return AccuracyLevel.POOR
    else:
        return AccuracyLevel.FAILING


def create_empty_image_result() -> ImageEvaluationResult:
    """Create an empty image evaluation result for cases with no images."""
    return ImageEvaluationResult(
        total_images_in_pdf=0,
        total_images_extracted=0,
        correctly_associated_images=0,
        extraction_completeness=0.0,
        association_accuracy=0.0,
        image_quality_score=0.0
    )


def calculate_f1_score(precision: float, recall: float) -> float:
    """Calculate F1 score from precision and recall."""
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


# Example usage and validation
if __name__ == "__main__":
    # Test schema with sample data
    sample_issue_eval = IssueEvaluationResult(
        issue_index=0,
        extracted_issue_name="Knob and Tube Wiring",
        name_accuracy_score=95.0,
        description_accuracy_score=88.0,
        description_completeness_score=90.0,
        image_association_score=0.0,  # No images extracted
        overall_issue_score=68.25,    # Weighted average
        matched_ground_truth=True,
        ground_truth_issue_name="Knob and Tube Electrical Wiring",
        evaluation_notes=["Name is very close to ground truth", "Description captures key points"],
        missing_information=["No images associated with this issue"],
        image_extraction_issues=["No images were extracted for this electrical issue"]
    )
    
    sample_completeness = ExtractionCompletenessResult(
        ground_truth_issue_count=25,
        extracted_issue_count=22,
        correctly_identified_issues=20,
        false_positives=2,
        false_negatives=5,
        precision=90.9,  # 20/22 * 100
        recall=80.0,     # 20/25 * 100
        f1_score=85.1,   # Calculated F1
        missed_issues=["Roof Damage", "Foundation Crack", "Window Seal Issues", "Deck Railing", "Fence Repair"],
        extra_issues=["General Budget Item", "Miscellaneous Repairs"]
    )
    
    sample_image_result = create_empty_image_result()
    
    sample_pdf_result = PDFEvaluationResult(
        pdf_filename="1.pdf",
        json_filename="1_extracted.json",
        evaluator_model="gemini-2.5-pro",
        completeness_result=sample_completeness,
        image_result=sample_image_result,
        issue_evaluations=[sample_issue_eval],
        overall_accuracy_score=75.2,
        content_accuracy_score=89.5,
        image_accuracy_score=0.0,
        completeness_score=85.1,
        accuracy_level=AccuracyLevel.FAIR,
        passes_threshold=False,
        evaluation_summary="Extraction shows good content accuracy but fails on image extraction and has some completeness issues.",
        strengths=["Accurate issue names", "Good description quality", "Proper categorization"],
        weaknesses=["No image extraction", "Missed 5 issues", "2 false positive issues"],
        recommendations=["Fix image extraction pipeline", "Improve issue detection completeness", "Reduce false positives"]
    )
    
    print("Schema validation successful!")
    print(f"PDF result accuracy: {sample_pdf_result.overall_accuracy_score}%")
    print(f"Accuracy level: {sample_pdf_result.accuracy_level}")
    print(f"Passes threshold: {sample_pdf_result.passes_threshold}")