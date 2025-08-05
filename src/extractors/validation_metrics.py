"""
Validation metrics and comparison logic for multi-model PDF extraction.

This module provides comprehensive comparison between primary and validation
extraction results, calculates confidence scores, and determines which
results to use based on agreement levels and quality metrics.
"""

import logging
import difflib
import re
from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

from .schemas import HomeInspectionReport, InspectionIssue, ExtractionResult

logger = logging.getLogger(__name__)


class ValidationDecision(Enum):
    """Possible validation decisions based on comparison results."""
    USE_PRIMARY = "use_primary"  # Use primary model results (high confidence)
    USE_VALIDATOR = "use_validator"  # Use validation model results (primary failed)
    REQUIRE_MANUAL_REVIEW = "manual_review"  # Significant discrepancies found
    USE_CONSENSUS = "use_consensus"  # Merge agreeable results


@dataclass
class IssueComparison:
    """Comparison between individual issues from different models."""
    primary_issue: Optional[InspectionIssue]
    validator_issue: Optional[InspectionIssue]
    similarity_score: float  # 0-1, higher = more similar
    matched: bool  # Whether issues are considered a match
    discrepancies: List[str]  # List of specific differences


@dataclass
class ValidationResult:
    """Result of validation comparison between two extraction results."""
    confidence_score: float  # Overall confidence (0-100)
    decision: ValidationDecision
    issue_count_difference: int  # Absolute difference in issue counts
    issue_matches: List[IssueComparison]
    unmatched_primary: List[InspectionIssue]  # Issues only in primary
    unmatched_validator: List[InspectionIssue]  # Issues only in validator
    agreement_percentage: float  # Percentage of issues that match
    recommended_result: ExtractionResult  # Which result to use
    discrepancy_summary: List[str]  # High-level discrepancies
    processing_notes: List[str]  # Additional processing information


class ValidationMetrics:
    """
    Comprehensive validation and comparison system for extraction results.
    
    Compares primary extractor results with validator results to calculate
    confidence scores and determine optimal output.
    """
    
    def __init__(self):
        """Initialize validation metrics with configurable thresholds."""
        # Confidence scoring thresholds
        self.high_confidence_threshold = 85.0
        self.medium_confidence_threshold = 70.0
        self.low_confidence_threshold = 50.0
        
        # Issue matching thresholds
        self.issue_similarity_threshold = 0.7  # For considering issues matched
        self.text_similarity_threshold = 0.6  # For text field comparisons
        
        # Count difference thresholds (percentage)
        self.minor_count_diff_threshold = 0.1  # 10%
        self.major_count_diff_threshold = 0.3  # 30%
        
        logger.info("ValidationMetrics initialized with default thresholds")
    
    def compare_extractions(
        self,
        primary_result: ExtractionResult,
        validator_result: ExtractionResult,
        source_filename: Optional[str] = None
    ) -> ValidationResult:
        """
        Compare two extraction results and determine validation outcome.
        
        Args:
            primary_result: Result from primary extractor (Qwen)
            validator_result: Result from validation extractor (Gemini)
            source_filename: Source PDF filename for context
            
        Returns:
            ValidationResult with comparison details and recommendation
        """
        logger.info(f"Starting validation comparison for {source_filename or 'unknown'}")
        
        processing_notes = []
        discrepancy_summary = []
        
        # Handle cases where one or both extractions failed
        if not primary_result.success and not validator_result.success:
            return self._handle_both_failed(primary_result, validator_result, source_filename)
        
        if not primary_result.success:
            processing_notes.append("Primary extraction failed, using validator results")
            return self._create_validation_result(
                confidence_score=60.0,  # Medium-low confidence when primary fails
                decision=ValidationDecision.USE_VALIDATOR,
                recommended_result=validator_result,
                processing_notes=processing_notes,
                discrepancy_summary=["Primary extraction failed"]
            )
        
        if not validator_result.success:
            processing_notes.append("Validator extraction failed, using primary results")
            return self._create_validation_result(
                confidence_score=75.0,  # Medium confidence when validator fails
                decision=ValidationDecision.USE_PRIMARY,
                recommended_result=primary_result,
                processing_notes=processing_notes,
                discrepancy_summary=["Validator extraction failed"]
            )
        
        # Both extractions succeeded - perform detailed comparison
        primary_report = primary_result.report
        validator_report = validator_result.report
        
        if not primary_report or not validator_report:
            processing_notes.append("Missing report data despite successful extraction")
            # Use whichever has report data, or primary if both missing
            if primary_report:
                recommended_result = primary_result
            elif validator_report:
                recommended_result = validator_result
            else:
                recommended_result = primary_result
            
            return self._create_validation_result(
                confidence_score=50.0,
                decision=ValidationDecision.USE_PRIMARY,
                recommended_result=recommended_result,
                processing_notes=processing_notes,
                discrepancy_summary=["Missing report data"]
            )
        
        # Compare issue counts
        primary_count = len(primary_report.issues)
        validator_count = len(validator_report.issues)
        count_difference = abs(primary_count - validator_count)
        
        processing_notes.append(f"Issue counts: Primary={primary_count}, Validator={validator_count}")
        
        # Calculate count difference percentage
        max_count = max(primary_count, validator_count, 1)  # Avoid division by zero
        count_diff_percentage = count_difference / max_count
        
        if count_diff_percentage > self.major_count_diff_threshold:
            discrepancy_summary.append(f"Major issue count difference: {count_difference} issues")
        elif count_diff_percentage > self.minor_count_diff_threshold:
            discrepancy_summary.append(f"Minor issue count difference: {count_difference} issues")
        
        # Perform detailed issue matching
        issue_matches, unmatched_primary, unmatched_validator = self._match_issues(
            primary_report.issues, validator_report.issues
        )
        
        # Calculate agreement metrics
        total_potential_matches = max(primary_count, validator_count)
        actual_matches = len([m for m in issue_matches if m.matched])
        agreement_percentage = (actual_matches / total_potential_matches * 100) if total_potential_matches > 0 else 0
        
        processing_notes.append(f"Agreement: {actual_matches}/{total_potential_matches} issues matched ({agreement_percentage:.1f}%)")
        
        # Calculate overall confidence score
        confidence_score = self._calculate_confidence_score(
            agreement_percentage=agreement_percentage,
            count_diff_percentage=count_diff_percentage,
            issue_matches=issue_matches,
            primary_count=primary_count,
            validator_count=validator_count
        )
        
        # Determine validation decision
        decision = self._determine_validation_decision(
            confidence_score=confidence_score,
            agreement_percentage=agreement_percentage,
            count_diff_percentage=count_diff_percentage,
            primary_result=primary_result,
            validator_result=validator_result
        )
        
        # Choose recommended result based on decision
        recommended_result = self._choose_recommended_result(
            decision=decision,
            primary_result=primary_result,
            validator_result=validator_result,
            issue_matches=issue_matches
        )
        
        # Add decision-specific notes
        if decision == ValidationDecision.REQUIRE_MANUAL_REVIEW:
            discrepancy_summary.append("Significant discrepancies require manual review")
        elif decision == ValidationDecision.USE_CONSENSUS:
            processing_notes.append("Using consensus of matched issues")
        
        return ValidationResult(
            confidence_score=confidence_score,
            decision=decision,
            issue_count_difference=count_difference,
            issue_matches=issue_matches,
            unmatched_primary=unmatched_primary,
            unmatched_validator=unmatched_validator,
            agreement_percentage=agreement_percentage,
            recommended_result=recommended_result,
            discrepancy_summary=discrepancy_summary,
            processing_notes=processing_notes
        )
    
    def _match_issues(
        self,
        primary_issues: List[InspectionIssue],
        validator_issues: List[InspectionIssue]
    ) -> Tuple[List[IssueComparison], List[InspectionIssue], List[InspectionIssue]]:
        """
        Match issues between primary and validator results using similarity scoring.
        
        Returns:
            Tuple of (matched_comparisons, unmatched_primary, unmatched_validator)
        """
        matches = []
        used_validator_indices = set()
        unmatched_primary = []
        
        # For each primary issue, find best match in validator issues
        for primary_issue in primary_issues:
            best_match_idx = None
            best_similarity = 0.0
            
            for i, validator_issue in enumerate(validator_issues):
                if i in used_validator_indices:
                    continue
                
                similarity = self._calculate_issue_similarity(primary_issue, validator_issue)
                
                if similarity > best_similarity and similarity >= self.issue_similarity_threshold:
                    best_similarity = similarity
                    best_match_idx = i
            
            if best_match_idx is not None:
                # Found a match
                validator_issue = validator_issues[best_match_idx]
                used_validator_indices.add(best_match_idx)
                
                # Create detailed comparison
                discrepancies = self._identify_issue_discrepancies(primary_issue, validator_issue)
                
                matches.append(IssueComparison(
                    primary_issue=primary_issue,
                    validator_issue=validator_issue,
                    similarity_score=best_similarity,
                    matched=True,
                    discrepancies=discrepancies
                ))
            else:
                # No match found
                unmatched_primary.append(primary_issue)
        
        # Identify unmatched validator issues
        unmatched_validator = [
            validator_issues[i] for i in range(len(validator_issues))
            if i not in used_validator_indices
        ]
        
        return matches, unmatched_primary, unmatched_validator
    
    def _calculate_issue_similarity(
        self,
        issue1: InspectionIssue,
        issue2: InspectionIssue
    ) -> float:
        """
        Calculate similarity score between two issues.
        
        Returns:
            Similarity score from 0.0 to 1.0
        """
        # Weight different components
        weights = {
            'type': 0.3,
            'name': 0.3,
            'description': 0.25,
            'summary': 0.15
        }
        
        # Calculate component similarities
        type_sim = self._text_similarity(issue1.issue_type, issue2.issue_type)
        name_sim = self._text_similarity(issue1.issue_name, issue2.issue_name)
        desc_sim = self._text_similarity(issue1.issue_description, issue2.issue_description)
        summary_sim = self._text_similarity(issue1.issue_summary, issue2.issue_summary)
        
        # Weighted average
        total_similarity = (
            type_sim * weights['type'] +
            name_sim * weights['name'] +
            desc_sim * weights['description'] +
            summary_sim * weights['summary']
        )
        
        return total_similarity
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two text strings.
        
        Uses a combination of exact matching, word overlap, and sequence matching.
        """
        if not text1 or not text2:
            return 0.0 if text1 != text2 else 1.0
        
        # Normalize texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        # Exact match
        if norm1 == norm2:
            return 1.0
        
        # Sequence matching for overall similarity
        seq_matcher = difflib.SequenceMatcher(None, norm1, norm2)
        sequence_similarity = seq_matcher.ratio()
        
        # Word-level overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if len(words1) == 0 and len(words2) == 0:
            word_similarity = 1.0
        elif len(words1) == 0 or len(words2) == 0:
            word_similarity = 0.0
        else:
            overlap = len(words1.intersection(words2))
            union = len(words1.union(words2))
            word_similarity = overlap / union
        
        # Combine metrics (sequence matching weighted higher)
        combined_similarity = 0.7 * sequence_similarity + 0.3 * word_similarity
        
        return combined_similarity
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison by lowercasing and removing extra whitespace."""
        return re.sub(r'\s+', ' ', text.lower().strip())
    
    def _identify_issue_discrepancies(
        self,
        primary_issue: InspectionIssue,
        validator_issue: InspectionIssue
    ) -> List[str]:
        """Identify specific discrepancies between two matched issues."""
        discrepancies = []
        
        # Check each field for differences
        if self._normalize_text(primary_issue.issue_type) != self._normalize_text(validator_issue.issue_type):
            discrepancies.append(f"Type differs: '{primary_issue.issue_type}' vs '{validator_issue.issue_type}'")
        
        if self._text_similarity(primary_issue.issue_name, validator_issue.issue_name) < self.text_similarity_threshold:
            discrepancies.append("Issue names significantly different")
        
        if self._text_similarity(primary_issue.issue_description, validator_issue.issue_description) < self.text_similarity_threshold:
            discrepancies.append("Issue descriptions significantly different")
        
        # Check image references
        primary_images = set(primary_issue.issue_images)
        validator_images = set(validator_issue.issue_images)
        
        if primary_images != validator_images:
            discrepancies.append("Different image references")
        
        return discrepancies
    
    def _calculate_confidence_score(
        self,
        agreement_percentage: float,
        count_diff_percentage: float,
        issue_matches: List[IssueComparison],
        primary_count: int,
        validator_count: int
    ) -> float:
        """
        Calculate overall confidence score based on multiple factors.
        
        Returns confidence score from 0-100.
        """
        # Base score from agreement percentage
        base_score = agreement_percentage
        
        # Penalty for count differences
        count_penalty = min(count_diff_percentage * 100, 30)  # Max 30 point penalty
        
        # Quality bonus for high-similarity matches
        quality_bonus = 0
        if issue_matches:
            avg_similarity = sum(m.similarity_score for m in issue_matches if m.matched) / len([m for m in issue_matches if m.matched])
            if avg_similarity > 0.8:
                quality_bonus = 10  # Up to 10 bonus points for high-quality matches
        
        # Completeness factor - penalize if either extractor found very few issues
        min_issues = min(primary_count, validator_count)
        if min_issues < 2:
            completeness_penalty = 15  # Significant penalty for very few issues
        elif min_issues < 5:
            completeness_penalty = 5   # Minor penalty for few issues
        else:
            completeness_penalty = 0
        
        # Calculate final score
        confidence_score = base_score - count_penalty + quality_bonus - completeness_penalty
        
        # Ensure score is within bounds
        confidence_score = max(0, min(100, confidence_score))
        
        return confidence_score
    
    def _determine_validation_decision(
        self,
        confidence_score: float,
        agreement_percentage: float,
        count_diff_percentage: float,
        primary_result: ExtractionResult,
        validator_result: ExtractionResult
    ) -> ValidationDecision:
        """Determine the appropriate validation decision based on metrics."""
        
        # High confidence - use primary
        if confidence_score >= self.high_confidence_threshold:
            return ValidationDecision.USE_PRIMARY
        
        # Very low confidence or major discrepancies - manual review
        if (confidence_score < self.low_confidence_threshold or 
            count_diff_percentage > self.major_count_diff_threshold or
            agreement_percentage < 40):
            return ValidationDecision.REQUIRE_MANUAL_REVIEW
        
        # Medium confidence with reasonable agreement - use consensus
        if confidence_score >= self.medium_confidence_threshold and agreement_percentage >= 60:
            return ValidationDecision.USE_CONSENSUS
        
        # Otherwise, default to primary (with lower confidence)
        return ValidationDecision.USE_PRIMARY
    
    def _choose_recommended_result(
        self,
        decision: ValidationDecision,
        primary_result: ExtractionResult,
        validator_result: ExtractionResult,
        issue_matches: List[IssueComparison]
    ) -> ExtractionResult:
        """Choose the recommended result based on validation decision."""
        
        if decision == ValidationDecision.USE_VALIDATOR:
            return validator_result
        elif decision == ValidationDecision.USE_CONSENSUS:
            # Create consensus result with only matched issues
            return self._create_consensus_result(primary_result, validator_result, issue_matches)
        else:
            # USE_PRIMARY or REQUIRE_MANUAL_REVIEW - default to primary
            return primary_result
    
    def _create_consensus_result(
        self,
        primary_result: ExtractionResult,
        validator_result: ExtractionResult,
        issue_matches: List[IssueComparison]
    ) -> ExtractionResult:
        """Create a consensus result using only agreed-upon issues."""
        
        consensus_issues = []
        
        # Use primary issues that have matches (they've been validated)
        for match in issue_matches:
            if match.matched and match.primary_issue:
                consensus_issues.append(match.primary_issue)
        
        # Create consensus report
        if primary_result.report:
            consensus_report = HomeInspectionReport(
                report_name=primary_result.report.report_name,
                issues=consensus_issues,
                source_pdf=primary_result.report.source_pdf,
                extraction_model=f'consensus-{primary_result.model_used}-{validator_result.model_used}'
            )
        else:
            consensus_report = None
        
        # Create consensus extraction result
        return ExtractionResult(
            success=True,
            report=consensus_report,
            processing_time=max(
                primary_result.processing_time or 0,
                validator_result.processing_time or 0
            ),
            model_used=f'consensus-{primary_result.model_used}-{validator_result.model_used}',
            pdf_complexity='validated'
        )
    
    def _handle_both_failed(
        self,
        primary_result: ExtractionResult,
        validator_result: ExtractionResult,
        source_filename: Optional[str]
    ) -> ValidationResult:
        """Handle case where both extractions failed."""
        
        # Return the primary result with very low confidence
        return ValidationResult(
            confidence_score=0.0,
            decision=ValidationDecision.REQUIRE_MANUAL_REVIEW,
            issue_count_difference=0,
            issue_matches=[],
            unmatched_primary=[],
            unmatched_validator=[],
            agreement_percentage=0.0,
            recommended_result=primary_result,  # Return primary even though it failed
            discrepancy_summary=["Both primary and validator extractions failed"],
            processing_notes=[
                f"Primary error: {primary_result.error_message}",
                f"Validator error: {validator_result.error_message}"
            ]
        )
    
    def _create_validation_result(
        self,
        confidence_score: float,
        decision: ValidationDecision,
        recommended_result: ExtractionResult,
        processing_notes: List[str],
        discrepancy_summary: List[str],
        issue_count_difference: int = 0,
        issue_matches: List[IssueComparison] = None,
        unmatched_primary: List[InspectionIssue] = None,
        unmatched_validator: List[InspectionIssue] = None,
        agreement_percentage: float = 0.0
    ) -> ValidationResult:
        """Helper to create ValidationResult with defaults."""
        
        return ValidationResult(
            confidence_score=confidence_score,
            decision=decision,
            issue_count_difference=issue_count_difference,
            issue_matches=issue_matches or [],
            unmatched_primary=unmatched_primary or [],
            unmatched_validator=unmatched_validator or [],
            agreement_percentage=agreement_percentage,
            recommended_result=recommended_result,
            discrepancy_summary=discrepancy_summary,
            processing_notes=processing_notes
        )


# Utility functions
def validate_extractions(
    primary_result: ExtractionResult,
    validator_result: ExtractionResult,
    source_filename: Optional[str] = None
) -> ValidationResult:
    """Quick utility function to validate two extraction results."""
    metrics = ValidationMetrics()
    return metrics.compare_extractions(primary_result, validator_result, source_filename)


def calculate_extraction_confidence(
    result: ExtractionResult,
    baseline_confidence: float = 75.0
) -> float:
    """
    Calculate confidence for a single extraction result.
    
    Used when validation is not available.
    """
    if not result.success:
        return 0.0
    
    if not result.report or not result.report.issues:
        return 30.0  # Low confidence for empty results
    
    # Adjust based on processing time (very fast might indicate issues)
    time_factor = 1.0
    if result.processing_time and result.processing_time < 5:
        time_factor = 0.9  # Slight penalty for very fast processing
    
    # Adjust based on issue count (very few might indicate missed issues)
    issue_count = len(result.report.issues)
    count_factor = 1.0
    if issue_count < 2:
        count_factor = 0.8  # Penalty for very few issues
    elif issue_count > 20:
        count_factor = 0.95  # Slight penalty for many issues (might be over-extraction)
    
    adjusted_confidence = baseline_confidence * time_factor * count_factor
    return min(100.0, max(0.0, adjusted_confidence))


if __name__ == "__main__":
    # Test validation metrics with sample data
    from .schemas import HomeInspectionReport, InspectionIssue, ExtractionResult
    
    # Create sample issues
    issue1_primary = InspectionIssue(
        issue_name="Knob and Tube Wiring",
        issue_type="Electrical",
        issue_description="Old knob and tube wiring found in basement",
        issue_summary="Replace old wiring",
        issue_images=["electrical_01.jpg"]
    )
    
    issue1_validator = InspectionIssue(
        issue_name="Knob & Tube Electrical Wiring",  # Similar but slightly different
        issue_type="Electrical",
        issue_description="Knob and tube wiring discovered in basement area",
        issue_summary="Old wiring needs replacement",
        issue_images=["electrical_01.jpg"]
    )
    
    issue2_primary = InspectionIssue(
        issue_name="Kitchen Sink Leak",
        issue_type="Plumbing",
        issue_description="Minor leak under kitchen sink",
        issue_summary="Fix sink leak",
        issue_images=["plumbing_01.jpg"]
    )
    
    # Create sample reports
    primary_report = HomeInspectionReport(
        report_name="Test Report",
        issues=[issue1_primary, issue2_primary],
        source_pdf="test.pdf",
        extraction_model="qwen-3-32b"
    )
    
    validator_report = HomeInspectionReport(
        report_name="Test Report",
        issues=[issue1_validator],  # Missing the plumbing issue
        source_pdf="test.pdf",
        extraction_model="gemini-2.5-pro"
    )
    
    # Create extraction results
    primary_result = ExtractionResult(
        success=True,
        report=primary_report,
        processing_time=15.5,
        model_used="qwen-3-32b"
    )
    
    validator_result = ExtractionResult(
        success=True,
        report=validator_report,
        processing_time=12.3,
        model_used="gemini-2.5-pro"
    )
    
    # Test validation
    validation_result = validate_extractions(primary_result, validator_result, "test.pdf")
    
    print("Validation Results:")
    print(f"Confidence Score: {validation_result.confidence_score:.1f}")
    print(f"Decision: {validation_result.decision.value}")
    print(f"Agreement: {validation_result.agreement_percentage:.1f}%")
    print(f"Issue Count Difference: {validation_result.issue_count_difference}")
    print(f"Matched Issues: {len(validation_result.issue_matches)}")
    print(f"Unmatched Primary: {len(validation_result.unmatched_primary)}")
    print(f"Unmatched Validator: {len(validation_result.unmatched_validator)}")
    
    if validation_result.discrepancy_summary:
        print(f"Discrepancies: {validation_result.discrepancy_summary}")
    
    if validation_result.processing_notes:
        print(f"Processing Notes: {validation_result.processing_notes}")