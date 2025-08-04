"""
Enhanced validation router for PDF extraction pipeline.

This module implements the new model routing strategy that replaces the Qwen-based
validation approach with a Gemini primary/Claude backup architecture:

- Easy PDFs: Gemini 2.5 Flash (primary) → Claude Sonnet 4 (backup)
- Medium PDFs: Gemini 2.5 Pro (primary) → Claude Sonnet 4 (backup)
- Complex PDFs: Gemini 2.5 Pro (primary) → Claude Opus 4 (backup)
"""

import os
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from enum import Enum

from .schemas import ExtractionResult
from .gemini_extractor import GeminiExtractor, GeminiExtractionError
from .claude_extractor import ClaudeExtractor, ClaudeExtractionError
from .validation_metrics import ValidationMetrics, ValidationResult, ValidationDecision

logger = logging.getLogger(__name__)


class ComplexityLevel(Enum):
    """PDF complexity levels for routing decisions."""
    EASY = "easy"
    MEDIUM = "medium"
    COMPLEX = "complex"


class ModelType(Enum):
    """Available AI models for extraction."""
    GEMINI_FLASH = "gemini-2.5-flash"
    GEMINI_PRO = "gemini-2.5-pro"
    CLAUDE_SONNET_4 = "claude-3-5-sonnet-20241022"  # Updated Sonnet model
    CLAUDE_OPUS_4 = "claude-opus-4-20250514"


class EnhancedValidationRouterError(Exception):
    """Custom exception for enhanced validation router errors."""
    pass


class EnhancedValidationRouter:
    """
    Enhanced validation router with Gemini primary/Claude backup architecture.
    
    Routes PDFs through a primary/backup pipeline:
    1. Determine PDF complexity level
    2. Primary extraction with appropriate Gemini model
    3. Validation and confidence scoring
    4. Claude backup if primary fails or confidence is low
    """
    
    # Model configuration mapping
    MODEL_CONFIG = {
        ComplexityLevel.EASY: {
            'primary': ModelType.GEMINI_FLASH,
            'backup': ModelType.CLAUDE_SONNET_4
        },
        ComplexityLevel.MEDIUM: {
            'primary': ModelType.GEMINI_PRO,
            'backup': ModelType.CLAUDE_SONNET_4
        },
        ComplexityLevel.COMPLEX: {
            'primary': ModelType.GEMINI_PRO,
            'backup': ModelType.CLAUDE_OPUS_4
        }
    }
    
    def __init__(self, 
                 api_keys: Optional[Dict[str, str]] = None,
                 confidence_threshold: float = 70.0,
                 enable_backup: bool = True):
        """
        Initialize enhanced validation router.
        
        Args:
            api_keys: Dictionary of API keys for different services
            confidence_threshold: Minimum confidence to accept without backup
            enable_backup: Whether to use Claude backup for low-confidence results
        """
        self.api_keys = api_keys or {}
        self.confidence_threshold = confidence_threshold
        self.enable_backup = enable_backup
        
        # Initialize extractors (will be created as needed)
        self.gemini_flash_extractor = None
        self.gemini_pro_extractor = None
        self.claude_sonnet_extractor = None
        self.claude_opus_extractor = None
        
        # Initialize validation metrics
        self.validation_metrics = ValidationMetrics()
        
        # Router statistics
        self.stats = {
            'total_processed': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'primary_successes': 0,
            'primary_failures': 0,
            'backup_used': 0,
            'backup_successes': 0,
            'backup_failures': 0,
            'high_confidence_results': 0,
            'medium_confidence_results': 0,
            'low_confidence_results': 0,
            'complexity_distribution': {level.value: 0 for level in ComplexityLevel},
            'model_usage': {model.value: 0 for model in ModelType},
            'processing_times': [],
            'confidence_scores': [],
            'routing_decisions': {}
        }
        
        logger.info("EnhancedValidationRouter initialized")
    
    async def initialize_extractors(self) -> Dict[str, bool]:
        """
        Initialize all extractors and return status.
        
        Returns:
            Dictionary indicating which extractors initialized successfully
        """
        status = {}
        
        # Get API keys
        gemini_key = (self.api_keys.get('GOOGLE_API_KEY') or 
                     self.api_keys.get('GEMINI_API_KEY') or 
                     os.getenv('GOOGLE_API_KEY') or 
                     os.getenv('GEMINI_API_KEY'))
        
        claude_key = self.api_keys.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        
        # Initialize Gemini Flash
        try:
            self.gemini_flash_extractor = GeminiExtractor(api_key=gemini_key, model_name='gemini-2.5-flash')
            status['gemini_flash'] = self.gemini_flash_extractor.validate_api_connection()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Flash extractor: {str(e)}")
            status['gemini_flash'] = False
        
        # Initialize Gemini Pro
        try:
            self.gemini_pro_extractor = GeminiExtractor(api_key=gemini_key, model_name='gemini-2.5-pro')
            status['gemini_pro'] = self.gemini_pro_extractor.validate_api_connection()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Pro extractor: {str(e)}")
            status['gemini_pro'] = False
        
        # Initialize Claude Sonnet 4
        if self.enable_backup:
            try:
                self.claude_sonnet_extractor = ClaudeExtractor(api_key=claude_key, model_name='claude-3-5-sonnet-20241022')
                status['claude_sonnet'] = self.claude_sonnet_extractor.validate_api_connection()
            except Exception as e:
                logger.error(f"Failed to initialize Claude Sonnet extractor: {str(e)}")
                status['claude_sonnet'] = False
            
            # Initialize Claude Opus 4
            try:
                self.claude_opus_extractor = ClaudeExtractor(api_key=claude_key, model_name='claude-opus-4-20250514')
                status['claude_opus'] = self.claude_opus_extractor.validate_api_connection()
            except Exception as e:
                logger.error(f"Failed to initialize Claude Opus extractor: {str(e)}")
                status['claude_opus'] = False
        else:
            status['claude_sonnet'] = False
            status['claude_opus'] = False
        
        logger.info(f"Extractor initialization status: {status}")
        return status
    
    def determine_complexity(self, 
                           markdown_content: str, 
                           image_references: Optional[List[str]] = None,
                           source_filename: Optional[str] = None) -> ComplexityLevel:
        """
        Determine PDF complexity level based on content analysis.
        
        Args:
            markdown_content: Parsed markdown content from PDF
            image_references: List of image filenames/references
            source_filename: Original PDF filename
            
        Returns:
            ComplexityLevel enum value
        """
        content_length = len(markdown_content)
        image_count = len(image_references) if image_references else 0
        
        # Count structural elements
        sections = markdown_content.count('#')
        lists = markdown_content.count('- ')
        tables = markdown_content.count('|')
        
        # Simple heuristics for complexity
        complexity_score = 0
        
        # Length factor
        if content_length > 10000:
            complexity_score += 2
        elif content_length > 5000:
            complexity_score += 1
        
        # Image factor
        if image_count > 10:
            complexity_score += 2
        elif image_count > 5:
            complexity_score += 1
        
        # Structure factor
        if sections > 20 or lists > 50 or tables > 10:
            complexity_score += 2
        elif sections > 10 or lists > 20 or tables > 5:
            complexity_score += 1
        
        # Technical content indicators
        technical_keywords = ['electrical', 'hvac', 'structural', 'foundation', 'roofing', 'plumbing']
        technical_count = sum(1 for keyword in technical_keywords if keyword.lower() in markdown_content.lower())
        
        if technical_count > 4:
            complexity_score += 1
        
        # Determine final complexity
        if complexity_score >= 4:
            level = ComplexityLevel.COMPLEX
        elif complexity_score >= 2:
            level = ComplexityLevel.MEDIUM
        else:
            level = ComplexityLevel.EASY
        
        logger.info(f"Determined complexity for {source_filename or 'unknown'}: {level.value} (score: {complexity_score})")
        return level
    
    def get_extractors_for_complexity(self, complexity: ComplexityLevel) -> Tuple[Any, Any]:
        """
        Get primary and backup extractors for a given complexity level.
        
        Returns:
            Tuple of (primary_extractor, backup_extractor)
        """
        config = self.MODEL_CONFIG[complexity]
        
        # Get primary extractor
        if config['primary'] == ModelType.GEMINI_FLASH:
            primary = self.gemini_flash_extractor
        elif config['primary'] == ModelType.GEMINI_PRO:
            primary = self.gemini_pro_extractor
        else:
            primary = None
        
        # Get backup extractor
        if config['backup'] == ModelType.CLAUDE_SONNET_4:
            backup = self.claude_sonnet_extractor
        elif config['backup'] == ModelType.CLAUDE_OPUS_4:
            backup = self.claude_opus_extractor
        else:
            backup = None
        
        return primary, backup
    
    async def extract_with_enhanced_validation(
        self,
        markdown_content: str,
        image_references: Optional[List[str]] = None,
        source_filename: Optional[str] = None,
        force_complexity: Optional[ComplexityLevel] = None
    ) -> Dict[str, Any]:
        """
        Extract data using enhanced validation pipeline.
        
        Args:
            markdown_content: Parsed markdown content from PDF
            image_references: List of image filenames/references
            source_filename: Original PDF filename
            force_complexity: Override complexity determination for testing
            
        Returns:
            Dictionary with extraction results and validation metadata
        """
        start_time = time.time()
        self.stats['total_processed'] += 1
        
        logger.info(f"Starting enhanced validation extraction for {source_filename or 'unknown'}")
        
        # Ensure extractors are initialized
        if not self.gemini_flash_extractor:
            await self.initialize_extractors()
        
        # Step 1: Determine complexity
        complexity = force_complexity or self.determine_complexity(
            markdown_content, image_references, source_filename
        )
        self.stats['complexity_distribution'][complexity.value] += 1
        
        # Step 2: Get appropriate extractors
        primary_extractor, backup_extractor = self.get_extractors_for_complexity(complexity)
        
        if not primary_extractor:
            return self._create_error_result(
                f"Primary extractor not available for complexity: {complexity.value}",
                time.time() - start_time
            )
        
        primary_model = self.MODEL_CONFIG[complexity]['primary'].value
        backup_model = self.MODEL_CONFIG[complexity]['backup'].value if backup_extractor else None
        
        logger.info(f"Using routing: {complexity.value} → {primary_model} (primary), {backup_model} (backup)")
        
        # Step 3: Primary extraction
        logger.info("Step 3: Primary extraction...")
        primary_result = await self._extract_with_extractor(
            primary_extractor, primary_model, markdown_content, image_references, source_filename
        )
        
        # Update model usage stats
        self.stats['model_usage'][primary_model] += 1
        
        if primary_result.success:
            self.stats['primary_successes'] += 1
        else:
            self.stats['primary_failures'] += 1
        
        # Step 4: Calculate confidence score for primary result
        confidence_score = self._calculate_confidence_score(primary_result, complexity)
        
        # Step 5: Determine if backup is needed
        use_backup = (
            self.enable_backup and 
            backup_extractor and 
            (not primary_result.success or confidence_score < self.confidence_threshold)
        )
        
        final_result = primary_result
        pipeline_used = "primary_only"
        backup_result = None
        
        if use_backup:
            logger.info(f"Step 5: Using backup extraction (confidence: {confidence_score:.1f}%)...")
            backup_result = await self._extract_with_extractor(
                backup_extractor, backup_model, markdown_content, image_references, source_filename
            )
            
            self.stats['backup_used'] += 1
            self.stats['model_usage'][backup_model] += 1
            
            if backup_result.success:
                self.stats['backup_successes'] += 1
                
                # If primary failed, use backup
                if not primary_result.success:
                    final_result = backup_result
                    pipeline_used = "backup_only"
                    confidence_score = self._calculate_confidence_score(backup_result, complexity)
                else:
                    # Both succeeded - use validation logic to choose best
                    validation_result = self.validation_metrics.compare_extractions(
                        primary_result, backup_result, source_filename
                    )
                    
                    final_result = validation_result.recommended_result
                    confidence_score = validation_result.confidence_score
                    
                    if validation_result.decision == ValidationDecision.USE_PRIMARY:
                        pipeline_used = "validated_primary"
                    elif validation_result.decision == ValidationDecision.USE_VALIDATOR:
                        pipeline_used = "backup_preferred"
                    elif validation_result.decision == ValidationDecision.USE_CONSENSUS:
                        pipeline_used = "consensus"
                    else:
                        pipeline_used = "manual_review_required"
            else:
                self.stats['backup_failures'] += 1
                # Keep primary result even if backup failed
                pipeline_used = "backup_failed"
        
        # Update confidence statistics
        self._update_confidence_stats(confidence_score)
        
        # Update extraction success stats
        if final_result.success:
            self.stats['successful_extractions'] += 1
        else:
            self.stats['failed_extractions'] += 1
        
        total_time = time.time() - start_time
        self.stats['processing_times'].append(total_time)
        self.stats['confidence_scores'].append(confidence_score)
        
        # Track routing decision
        routing_key = f"{complexity.value}_{pipeline_used}"
        self.stats['routing_decisions'][routing_key] = self.stats['routing_decisions'].get(routing_key, 0) + 1
        
        logger.info(f"Enhanced validation completed for {source_filename or 'unknown'}: "
                   f"complexity={complexity.value}, pipeline={pipeline_used}, "
                   f"confidence={confidence_score:.1f}%, time={total_time:.2f}s")
        
        return self._create_router_result(
            final_result=final_result,
            primary_result=primary_result,
            backup_result=backup_result,
            complexity=complexity,
            confidence_score=confidence_score,
            processing_time=total_time,
            pipeline_used=pipeline_used
        )
    
    async def _extract_with_extractor(
        self,
        extractor: Any,
        model_name: str,
        markdown_content: str,
        image_references: Optional[List[str]],
        source_filename: Optional[str]
    ) -> ExtractionResult:
        """Extract with a specific extractor."""
        try:
            return await extractor.extract_async(
                markdown_content, image_references, source_filename
            )
        except Exception as e:
            logger.error(f"Extraction failed with {model_name}: {str(e)}")
            return ExtractionResult(
                success=False,
                error_message=f"{model_name} extraction error: {str(e)}",
                model_used=model_name
            )
    
    def _calculate_confidence_score(self, result: ExtractionResult, complexity: ComplexityLevel) -> float:
        """
        Calculate confidence score for an extraction result.
        
        Args:
            result: Extraction result to evaluate
            complexity: PDF complexity level
            
        Returns:
            Confidence score (0-100)
        """
        if not result.success:
            return 0.0
        
        confidence = 100.0
        
        # Reduce confidence based on missing data
        if not result.report:
            return 20.0
        
        report = result.report
        
        # Check for empty or minimal issues
        if not report.issues or len(report.issues) == 0:
            confidence -= 30.0
        elif len(report.issues) < 3:
            confidence -= 15.0
        
        # Check for missing critical fields
        critical_fields = ['property_address', 'inspection_date', 'inspector_name']
        missing_fields = 0
        
        for field in critical_fields:
            if not getattr(report, field, None):
                missing_fields += 1
        
        confidence -= missing_fields * 10
        
        # Check issue quality
        if report.issues:
            issue_quality_score = 0
            for issue in report.issues:
                # Check if issue has required fields
                if issue.issue_name and issue.issue_type and issue.severity:
                    issue_quality_score += 1
                if issue.description and len(issue.description) > 20:
                    issue_quality_score += 0.5
                if issue.location:
                    issue_quality_score += 0.5
            
            # Normalize issue quality (max 2 points per issue)
            max_possible = len(report.issues) * 2
            issue_quality_ratio = issue_quality_score / max_possible if max_possible > 0 else 0
            confidence = confidence * (0.7 + 0.3 * issue_quality_ratio)
        
        # Adjust based on complexity expectations
        if complexity == ComplexityLevel.COMPLEX and len(report.issues) < 5:
            confidence -= 10.0
        elif complexity == ComplexityLevel.EASY and len(report.issues) > 20:
            confidence -= 5.0  # Might be over-extraction
        
        return max(0.0, min(100.0, confidence))
    
    def _update_confidence_stats(self, confidence_score: float):
        """Update confidence-related statistics."""
        if confidence_score >= 85:
            self.stats['high_confidence_results'] += 1
        elif confidence_score >= 70:
            self.stats['medium_confidence_results'] += 1
        else:
            self.stats['low_confidence_results'] += 1
    
    def _create_error_result(self, error_message: str, processing_time: float) -> Dict[str, Any]:
        """Create an error result dictionary."""
        error_result = ExtractionResult(
            success=False,
            error_message=error_message,
            model_used='router-error',
            processing_time=processing_time
        )
        
        return self._create_router_result(
            final_result=error_result,
            primary_result=None,
            backup_result=None,
            complexity=ComplexityLevel.EASY,
            confidence_score=0.0,
            processing_time=processing_time,
            pipeline_used="error"
        )
    
    def _create_router_result(
        self,
        final_result: ExtractionResult,
        primary_result: Optional[ExtractionResult],
        backup_result: Optional[ExtractionResult],
        complexity: ComplexityLevel,
        confidence_score: float,
        processing_time: float,
        pipeline_used: str
    ) -> Dict[str, Any]:
        """Create comprehensive router result with metadata."""
        
        result = {
            # Final extraction result
            'extraction_result': final_result,
            
            # Pipeline metadata
            'pipeline_used': pipeline_used,
            'total_processing_time': processing_time,
            'complexity_level': complexity.value,
            
            # Confidence and validation metadata
            'confidence_score': confidence_score,
            'primary_model': self.MODEL_CONFIG[complexity]['primary'].value,
            'backup_model': self.MODEL_CONFIG[complexity]['backup'].value if self.enable_backup else None,
            
            # Quality metrics
            'quality_metrics': {
                'issues_found': len(final_result.report.issues) if final_result.success and final_result.report else 0,
                'extraction_time': final_result.processing_time or 0,
                'model_used': final_result.model_used,
                'primary_success': primary_result.success if primary_result else False,
                'backup_success': backup_result.success if backup_result else None,
            }
        }
        
        # Add comparison details if both primary and backup were used
        if primary_result and backup_result and primary_result.success and backup_result.success:
            validation_result = self.validation_metrics.compare_extractions(
                primary_result, backup_result, None
            )
            
            result['comparison_details'] = {
                'agreement_percentage': validation_result.agreement_percentage,
                'issue_count_difference': validation_result.issue_count_difference,
                'matched_issues': len(validation_result.issue_matches),
                'unmatched_primary': len(validation_result.unmatched_primary),
                'unmatched_backup': len(validation_result.unmatched_validator),
                'validation_decision': validation_result.decision.value
            }
        
        return result
    
    async def batch_extract_with_enhanced_validation(
        self,
        pdf_data: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Process multiple PDFs through enhanced validation pipeline.
        
        Args:
            pdf_data: List of dicts with 'markdown_content', 'images', 'filename'
            max_concurrent: Maximum concurrent extractions
            
        Returns:
            List of router results
        """
        logger.info(f"Starting batch enhanced validation extraction of {len(pdf_data)} PDFs")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(pdf_info: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.extract_with_enhanced_validation(
                    markdown_content=pdf_info['markdown_content'],
                    image_references=pdf_info.get('images', []),
                    source_filename=pdf_info.get('filename')
                )
        
        # Process PDFs concurrently
        tasks = [extract_with_semaphore(pdf_info) for pdf_info in pdf_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = self._create_error_result(
                    f"Batch processing error: {str(result)}",
                    0
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        # Summary statistics
        successful = sum(1 for r in processed_results if r['extraction_result'].success)
        logger.info(f"Batch enhanced validation extraction completed: {successful}/{len(pdf_data)} successful")
        
        return processed_results
    
    def get_router_stats(self) -> Dict[str, Any]:
        """Get comprehensive router statistics."""
        stats = self.stats.copy()
        
        # Calculate additional metrics
        if stats['processing_times']:
            times = stats['processing_times']
            stats['avg_processing_time'] = sum(times) / len(times)
            stats['min_processing_time'] = min(times)
            stats['max_processing_time'] = max(times)
        
        if stats['confidence_scores']:
            scores = stats['confidence_scores']
            stats['avg_confidence_score'] = sum(scores) / len(scores)
            stats['min_confidence_score'] = min(scores)
            stats['max_confidence_score'] = max(scores)
        
        if stats['total_processed'] > 0:
            stats['success_rate'] = stats['successful_extractions'] / stats['total_processed']
            stats['primary_success_rate'] = stats['primary_successes'] / stats['total_processed']
            stats['backup_usage_rate'] = stats['backup_used'] / stats['total_processed']
            stats['high_confidence_rate'] = stats['high_confidence_results'] / stats['total_processed']
        
        if stats['backup_used'] > 0:
            stats['backup_success_rate'] = stats['backup_successes'] / stats['backup_used']
        
        stats['timestamp'] = datetime.now().isoformat()
        stats['router_type'] = 'enhanced_validation'
        
        return stats
    
    async def cleanup(self):
        """Clean up resources."""
        # Cleanup extractors if they have cleanup methods
        extractors = [
            self.gemini_flash_extractor,
            self.gemini_pro_extractor,
            self.claude_sonnet_extractor,
            self.claude_opus_extractor
        ]
        
        for extractor in extractors:
            if extractor and hasattr(extractor, 'close'):
                try:
                    await extractor.close()
                except Exception as e:
                    logger.warning(f"Error closing extractor: {str(e)}")


# Utility functions
async def create_enhanced_validation_router(
    api_keys: Optional[Dict[str, str]] = None,
    enable_backup: bool = True,
    confidence_threshold: float = 70.0
) -> EnhancedValidationRouter:
    """Create and initialize an enhanced validation router."""
    router = EnhancedValidationRouter(
        api_keys=api_keys, 
        enable_backup=enable_backup,
        confidence_threshold=confidence_threshold
    )
    await router.initialize_extractors()
    return router


async def extract_with_enhanced_validation_pipeline(
    markdown_content: str,
    image_references: Optional[List[str]] = None,
    source_filename: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Quick utility to extract using enhanced validation pipeline.
    
    Args:
        markdown_content: Parsed markdown content from PDF
        image_references: List of image filenames/references
        source_filename: Original PDF filename
        api_keys: Optional API keys
        
    Returns:
        Router result dictionary
    """
    router = await create_enhanced_validation_router(api_keys=api_keys)
    try:
        return await router.extract_with_enhanced_validation(
            markdown_content, image_references, source_filename
        )
    finally:
        await router.cleanup()


if __name__ == "__main__":
    # Test the enhanced validation router
    import os
    
    async def test_enhanced_validation_router():
        # Check for required API keys
        required_keys = ['GOOGLE_API_KEY', 'ANTHROPIC_API_KEY']
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        
        if missing_keys:
            print(f"Missing required API keys: {missing_keys}")
            print("Please set them in your environment or .env file")
            return
        
        print("Testing EnhancedValidationRouter...")
        print("=" * 50)
        
        router = await create_enhanced_validation_router()
        
        # Test with sample content of different complexities
        test_cases = [
            {
                'name': 'Easy PDF',
                'content': """
                # Home Inspection Report - Simple Property
                
                ## Electrical System
                - Minor outlet issue in bedroom
                - All other systems working properly
                
                ## Plumbing
                - Good water pressure throughout
                """,
                'images': ["electrical_01.jpg"],
                'expected_complexity': ComplexityLevel.EASY
            },
            {
                'name': 'Medium PDF',
                'content': """
                # Home Inspection Report - Standard Property
                
                ## Electrical System
                - Knob and tube wiring found in basement requiring replacement
                - GFCI outlets missing in bathrooms
                - Panel has outdated breakers
                - Junction box improperly covered
                - Ceiling fan installation needs professional review
                
                ## Plumbing
                - Minor leak under kitchen sink
                - Low water pressure in master bathroom 
                - Hot water heater nearing end of life
                - Bathroom exhaust fan not working
                
                ## HVAC
                - Ductwork inspection reveals loose connections
                - Filter needs replacement
                """,
                'images': ["electrical_01.jpg", "plumbing_kitchen.jpg", "hvac_01.jpg", "foundation_crack.jpg"],
                'expected_complexity': ComplexityLevel.MEDIUM
            },
            {
                'name': 'Complex PDF',
                'content': """
                # Comprehensive Home Inspection Report - Large Commercial Property
                
                ## Executive Summary
                This 50-page inspection report covers a 5,000 sq ft commercial building with complex systems.
                
                ## Electrical System - Critical Issues Found
                - Main electrical panel requires immediate replacement (safety hazard)
                - Knob and tube wiring throughout entire basement level
                - GFCI protection missing in all wet areas
                - Multiple junction boxes improperly installed
                - Emergency lighting system not functional
                - Fire alarm system needs complete overhaul
                
                ## Plumbing System - Multiple Concerns
                - Main water line shows signs of significant deterioration
                - Sewer backup risk due to root intrusion
                - Hot water heater beyond service life (12 years old)
                - Multiple fixture leaks requiring immediate attention
                - Backflow prevention device missing
                
                ## HVAC System - Major Repairs Needed
                - Boiler system requires professional inspection
                - Ductwork has significant damage and inefficiencies
                - Multiple zone controls not functioning
                - Air quality concerns due to mold in ventilation system
                
                ## Structural Issues
                - Foundation settlement in northeast corner
                - Load-bearing beam shows stress fractures
                - Roof structure has compromised trusses
                - Multiple areas of water damage
                
                ## Roofing System
                - Membrane roofing has multiple punctures
                - Flashing around penetrations failing
                - Drainage system completely blocked
                """ + "\\n".join([f"- Additional technical issue {i}" for i in range(1, 51)]),
                'images': [f"image_{i:02d}.jpg" for i in range(1, 16)],
                'expected_complexity': ComplexityLevel.COMPLEX
            }
        ]
        
        for test_case in test_cases:
            print(f"\\nTesting {test_case['name']}:")
            
            result = await router.extract_with_enhanced_validation(
                markdown_content=test_case['content'],
                image_references=test_case['images'],
                source_filename=f"{test_case['name'].lower().replace(' ', '_')}.pdf"
            )
            
            print(f"  Expected Complexity: {test_case['expected_complexity'].value}")
            print(f"  Actual Complexity: {result['complexity_level']}")
            print(f"  Success: {result['extraction_result'].success}")
            print(f"  Pipeline Used: {result['pipeline_used']}")
            print(f"  Primary Model: {result['primary_model']}")
            print(f"  Backup Model: {result['backup_model']}")
            print(f"  Confidence Score: {result['confidence_score']:.1f}%")
            print(f"  Processing Time: {result['total_processing_time']:.2f}s")
            
            if result['extraction_result'].success and result['extraction_result'].report:
                issues_count = len(result['extraction_result'].report.issues)
                print(f"  Issues Found: {issues_count}")
                
                # Show a few sample issues
                for i, issue in enumerate(result['extraction_result'].report.issues[:3]):
                    print(f"    {i+1}. {issue.issue_name} ({issue.issue_type})")
                if issues_count > 3:
                    print(f"    ... and {issues_count - 3} more issues")
            else:
                print(f"  Error: {result['extraction_result'].error_message}")
        
        # Show router statistics
        stats = router.get_router_stats()
        print(f"\\nEnhanced Router Statistics:")
        print(f"  Total processed: {stats['total_processed']}")
        print(f"  Success rate: {stats.get('success_rate', 0):.2%}")
        print(f"  Primary success rate: {stats.get('primary_success_rate', 0):.2%}")
        print(f"  Backup usage rate: {stats.get('backup_usage_rate', 0):.2%}")
        print(f"  High confidence rate: {stats.get('high_confidence_rate', 0):.2%}")
        print(f"  Average confidence: {stats.get('avg_confidence_score', 0):.1f}%")
        print(f"  Complexity distribution: {stats['complexity_distribution']}")
        print(f"  Model usage: {stats['model_usage']}")
        print(f"  Routing decisions: {stats['routing_decisions']}")
        
        await router.cleanup()
    
    # Run test
    asyncio.run(test_enhanced_validation_router())