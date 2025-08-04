"""
Validation-based router for PDF extraction pipeline.

This module implements the new validation approach that replaces complexity-based
routing. All PDFs are processed by Qwen (primary) and validated by Gemini,
with confidence scoring determining final results.
"""

import os
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from .schemas import ExtractionResult
from .qwen_extractor import QwenExtractor, QwenExtractionError
from .gemini_extractor import GeminiExtractor, GeminiExtractionError
from .claude_extractor import ClaudeExtractor, ClaudeExtractionError
from .validation_metrics import ValidationMetrics, ValidationResult, ValidationDecision

logger = logging.getLogger(__name__)


class ValidationRouterError(Exception):
    """Custom exception for validation router errors."""
    pass


class ValidationRouter:
    """
    Validation-based extraction router.
    
    Routes all PDFs through a validation pipeline:
    1. Primary extraction with Qwen 3-32B (via Groq)
    2. Validation extraction with Gemini 2.5 Pro
    3. Comparison and confidence scoring
    4. Optional Claude fallback for low-confidence results
    """
    
    def __init__(self, 
                 api_keys: Optional[Dict[str, str]] = None,
                 enable_claude_fallback: bool = True,
                 confidence_threshold: float = 70.0):
        """
        Initialize validation router.
        
        Args:
            api_keys: Dictionary of API keys for different services
            enable_claude_fallback: Whether to use Claude for low-confidence results
            confidence_threshold: Minimum confidence to accept without fallback
        """
        self.api_keys = api_keys or {}
        self.enable_claude_fallback = enable_claude_fallback
        self.confidence_threshold = confidence_threshold
        
        # Initialize extractors
        self.qwen_extractor = None
        self.gemini_extractor = None
        self.claude_extractor = None
        
        # Initialize validation metrics
        self.validation_metrics = ValidationMetrics()
        
        # Router statistics
        self.stats = {
            'total_processed': 0,
            'qwen_successes': 0,
            'qwen_failures': 0,
            'gemini_successes': 0,
            'gemini_failures': 0,
            'claude_used': 0,
            'high_confidence_results': 0,
            'medium_confidence_results': 0,
            'low_confidence_results': 0,
            'manual_review_required': 0,
            'consensus_results': 0,
            'validation_decisions': {},
            'processing_times': [],
            'confidence_scores': []
        }
        
        logger.info("ValidationRouter initialized")
    
    async def initialize_extractors(self) -> Dict[str, bool]:
        """
        Initialize all extractors and return status.
        
        Returns:
            Dictionary indicating which extractors initialized successfully
        """
        status = {}
        
        # Initialize Qwen (primary)
        try:
            groq_key = self.api_keys.get('GROQ_API_KEY') or os.getenv('GROQ_API_KEY')
            self.qwen_extractor = QwenExtractor(api_key=groq_key)
            status['qwen'] = await self.qwen_extractor.validate_api_connection()
        except Exception as e:
            logger.error(f"Failed to initialize Qwen extractor: {str(e)}")
            status['qwen'] = False
        
        # Initialize Gemini (validator)
        try:
            gemini_key = (self.api_keys.get('GOOGLE_API_KEY') or 
                         self.api_keys.get('GEMINI_API_KEY') or 
                         os.getenv('GOOGLE_API_KEY') or 
                         os.getenv('GEMINI_API_KEY'))
            self.gemini_extractor = GeminiExtractor(api_key=gemini_key)
            status['gemini'] = self.gemini_extractor.validate_api_connection()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini extractor: {str(e)}")
            status['gemini'] = False
        
        # Initialize Claude (fallback)
        if self.enable_claude_fallback:
            try:
                claude_key = self.api_keys.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
                self.claude_extractor = ClaudeExtractor(api_key=claude_key)
                status['claude'] = self.claude_extractor.validate_api_connection()
            except Exception as e:
                logger.error(f"Failed to initialize Claude extractor: {str(e)}")
                status['claude'] = False
        else:
            status['claude'] = False
        
        logger.info(f"Extractor initialization status: {status}")
        return status
    
    async def extract_with_validation(
        self,
        markdown_content: str,
        image_references: Optional[List[str]] = None,
        source_filename: Optional[str] = None,
        require_validation: bool = True
    ) -> Dict[str, Any]:
        """
        Extract data using validation pipeline.
        
        Args:
            markdown_content: Parsed markdown content from PDF
            image_references: List of image filenames/references
            source_filename: Original PDF filename
            require_validation: Whether validation is required (vs. primary-only)
            
        Returns:
            Dictionary with extraction results and validation metadata
        """
        start_time = time.time()
        self.stats['total_processed'] += 1
        
        logger.info(f"Starting validation extraction for {source_filename or 'unknown'}")
        
        # Ensure extractors are initialized
        if not self.qwen_extractor:
            await self.initialize_extractors()
        
        # Step 1: Primary extraction with Qwen
        logger.info("Step 1: Primary extraction with Qwen...")
        primary_result = await self._extract_with_qwen(
            markdown_content, image_references, source_filename
        )
        
        # Update stats
        if primary_result.success:
            self.stats['qwen_successes'] += 1
        else:
            self.stats['qwen_failures'] += 1
        
        # If primary failed and validation not required, return early
        if not primary_result.success and not require_validation:
            return self._create_router_result(
                final_result=primary_result,
                validation_result=None,
                processing_time=time.time() - start_time,
                pipeline_used="primary_only_failed"
            )
        
        # Step 2: Validation extraction with Gemini (if required and available)
        validator_result = None
        if require_validation and self.gemini_extractor:
            logger.info("Step 2: Validation extraction with Gemini...")
            validator_result = await self._extract_with_gemini(
                markdown_content, image_references, source_filename
            )
            
            # Update stats
            if validator_result.success:
                self.stats['gemini_successes'] += 1
            else:
                self.stats['gemini_failures'] += 1
        
        # Step 3: Compare results and determine confidence
        validation_result = None
        if validator_result:
            logger.info("Step 3: Comparing extraction results...")
            validation_result = self.validation_metrics.compare_extractions(
                primary_result, validator_result, source_filename
            )
            
            # Update validation decision stats
            decision = validation_result.decision.value
            self.stats['validation_decisions'][decision] = self.stats['validation_decisions'].get(decision, 0) + 1
            
            # Update confidence stats
            confidence = validation_result.confidence_score
            self.stats['confidence_scores'].append(confidence)
            
            if confidence >= 85:
                self.stats['high_confidence_results'] += 1
            elif confidence >= 70:
                self.stats['medium_confidence_results'] += 1
            else:
                self.stats['low_confidence_results'] += 1
        
        # Step 4: Apply fallback logic if needed
        final_result = primary_result
        pipeline_used = "primary_only"
        
        if validation_result:
            final_result = validation_result.recommended_result
            confidence = validation_result.confidence_score
            
            # Determine pipeline used based on decision
            if validation_result.decision == ValidationDecision.USE_PRIMARY:
                pipeline_used = "validated_primary"
            elif validation_result.decision == ValidationDecision.USE_VALIDATOR:
                pipeline_used = "validator_preferred"
            elif validation_result.decision == ValidationDecision.USE_CONSENSUS:
                pipeline_used = "consensus"
                self.stats['consensus_results'] += 1
            elif validation_result.decision == ValidationDecision.REQUIRE_MANUAL_REVIEW:
                pipeline_used = "manual_review_required"
                self.stats['manual_review_required'] += 1
            
            # Claude fallback for low confidence
            if (self.enable_claude_fallback and 
                self.claude_extractor and 
                confidence < self.confidence_threshold and
                validation_result.decision != ValidationDecision.REQUIRE_MANUAL_REVIEW):
                
                logger.info(f"Step 4: Low confidence ({confidence:.1f}%), trying Claude fallback...")
                claude_result = await self._extract_with_claude(
                    markdown_content, image_references, source_filename
                )
                
                if claude_result.success:
                    self.stats['claude_used'] += 1
                    final_result = claude_result
                    pipeline_used = "claude_fallback"
                    logger.info("Claude fallback successful, using Claude results")
        
        total_time = time.time() - start_time
        self.stats['processing_times'].append(total_time)
        
        logger.info(f"Validation extraction completed for {source_filename or 'unknown'}: "
                   f"pipeline={pipeline_used}, time={total_time:.2f}s")
        
        return self._create_router_result(
            final_result=final_result,
            validation_result=validation_result,
            processing_time=total_time,
            pipeline_used=pipeline_used
        )
    
    async def _extract_with_qwen(
        self,
        markdown_content: str,
        image_references: Optional[List[str]],
        source_filename: Optional[str]
    ) -> ExtractionResult:
        """Extract with Qwen extractor."""
        if not self.qwen_extractor:
            return ExtractionResult(
                success=False,
                error_message="Qwen extractor not initialized",
                model_used="qwen-not-available"
            )
        
        try:
            return await self.qwen_extractor.extract_async(
                markdown_content, image_references, source_filename
            )
        except Exception as e:
            logger.error(f"Qwen extraction failed: {str(e)}")
            return ExtractionResult(
                success=False,
                error_message=f"Qwen extraction error: {str(e)}",
                model_used="qwen-3-32b-groq"
            )
    
    async def _extract_with_gemini(
        self,
        markdown_content: str,
        image_references: Optional[List[str]],
        source_filename: Optional[str]
    ) -> ExtractionResult:
        """Extract with Gemini extractor."""
        if not self.gemini_extractor:
            return ExtractionResult(
                success=False,
                error_message="Gemini extractor not initialized",
                model_used="gemini-not-available"
            )
        
        try:
            return await self.gemini_extractor.extract_async(
                markdown_content, image_references, source_filename
            )
        except Exception as e:
            logger.error(f"Gemini extraction failed: {str(e)}")
            return ExtractionResult(
                success=False,
                error_message=f"Gemini extraction error: {str(e)}",
                model_used="gemini-2.5-pro"
            )
    
    async def _extract_with_claude(
        self,
        markdown_content: str,
        image_references: Optional[List[str]],
        source_filename: Optional[str]
    ) -> ExtractionResult:
        """Extract with Claude extractor."""
        if not self.claude_extractor:
            return ExtractionResult(
                success=False,
                error_message="Claude extractor not initialized",
                model_used="claude-not-available"
            )
        
        try:
            return await self.claude_extractor.extract_async(
                markdown_content, image_references, source_filename
            )
        except Exception as e:
            logger.error(f"Claude extraction failed: {str(e)}")
            return ExtractionResult(
                success=False,
                error_message=f"Claude extraction error: {str(e)}",
                model_used="claude-3.5-sonnet"
            )
    
    def _create_router_result(
        self,
        final_result: ExtractionResult,
        validation_result: Optional[ValidationResult],
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
            
            # Validation metadata (if available)
            'validation_available': validation_result is not None,
            'confidence_score': validation_result.confidence_score if validation_result else None,
            'validation_decision': validation_result.decision.value if validation_result else None,
            'agreement_percentage': validation_result.agreement_percentage if validation_result else None,
            
            # Quality metrics
            'quality_metrics': {
                'issues_found': len(final_result.report.issues) if final_result.success and final_result.report else 0,
                'extraction_time': final_result.processing_time or 0,
                'model_used': final_result.model_used,
            }
        }
        
        # Add detailed validation results if available
        if validation_result:
            result['validation_details'] = {
                'issue_count_difference': validation_result.issue_count_difference,
                'matched_issues': len(validation_result.issue_matches),
                'unmatched_primary': len(validation_result.unmatched_primary),
                'unmatched_validator': len(validation_result.unmatched_validator),
                'discrepancies': validation_result.discrepancy_summary,
                'processing_notes': validation_result.processing_notes
            }
        
        return result
    
    async def batch_extract_with_validation(
        self,
        pdf_data: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Process multiple PDFs through validation pipeline.
        
        Args:
            pdf_data: List of dicts with 'markdown_content', 'images', 'filename'
            max_concurrent: Maximum concurrent extractions
            
        Returns:
            List of router results
        """
        logger.info(f"Starting batch validation extraction of {len(pdf_data)} PDFs")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(pdf_info: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.extract_with_validation(
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
                error_result = ExtractionResult(
                    success=False,
                    error_message=f"Batch processing error: {str(result)}",
                    model_used='batch-error'
                )
                processed_results.append(self._create_router_result(
                    final_result=error_result,
                    validation_result=None,
                    processing_time=0,
                    pipeline_used="error"
                ))
            else:
                processed_results.append(result)
        
        # Summary statistics
        successful = sum(1 for r in processed_results if r['extraction_result'].success)
        logger.info(f"Batch validation extraction completed: {successful}/{len(pdf_data)} successful")
        
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
            stats['qwen_success_rate'] = stats['qwen_successes'] / stats['total_processed']
            stats['gemini_success_rate'] = stats['gemini_successes'] / max(stats['gemini_successes'] + stats['gemini_failures'], 1)
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
    
    async def cleanup(self):
        """Clean up resources."""
        if self.qwen_extractor:
            await self.qwen_extractor.close()


# Utility functions
async def create_validation_router(
    api_keys: Optional[Dict[str, str]] = None,
    enable_claude_fallback: bool = True
) -> ValidationRouter:
    """Create and initialize a validation router."""
    router = ValidationRouter(api_keys=api_keys, enable_claude_fallback=enable_claude_fallback)
    await router.initialize_extractors()
    return router


async def extract_with_validation_pipeline(
    markdown_content: str,
    image_references: Optional[List[str]] = None,
    source_filename: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Quick utility to extract using validation pipeline.
    
    Args:
        markdown_content: Parsed markdown content from PDF
        image_references: List of image filenames/references
        source_filename: Original PDF filename
        api_keys: Optional API keys
        
    Returns:
        Router result dictionary
    """
    router = await create_validation_router(api_keys=api_keys)
    try:
        return await router.extract_with_validation(
            markdown_content, image_references, source_filename
        )
    finally:
        await router.cleanup()


if __name__ == "__main__":
    # Test the validation router
    import os
    
    async def test_validation_router():
        # Check for required API keys
        required_keys = ['GROQ_API_KEY', 'GOOGLE_API_KEY']
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        
        if missing_keys:
            print(f"Missing required API keys: {missing_keys}")
            print("Please set them in your environment or .env file")
            return
        
        print("Testing ValidationRouter...")
        print("=" * 50)
        
        router = await create_validation_router()
        
        # Test with sample content
        sample_content = """
        # Home Inspection Report - Test Property
        
        ## Electrical System
        - Knob and tube wiring found in basement requiring replacement
        - GFCI outlets missing in bathrooms
        - Panel has outdated breakers
        
        ## Plumbing
        - Minor leak under kitchen sink
        - Low water pressure in master bathroom 
        - Hot water heater nearing end of life
        
        ## Structural
        - Foundation crack in east wall
        - Roof shingles missing in several areas
        """
        
        sample_images = ["electrical_01.jpg", "plumbing_kitchen.jpg", "foundation_crack.jpg"]
        
        result = await router.extract_with_validation(
            markdown_content=sample_content,
            image_references=sample_images,
            source_filename="test.pdf"
        )
        
        print("Validation Results:")
        print(f"Success: {result['extraction_result'].success}")
        print(f"Pipeline Used: {result['pipeline_used']}")
        print(f"Confidence Score: {result.get('confidence_score', 'N/A')}")
        print(f"Agreement: {result.get('agreement_percentage', 'N/A')}%")
        print(f"Processing Time: {result['total_processing_time']:.2f}s")
        
        if result['extraction_result'].success:
            report = result['extraction_result'].report
            print(f"Issues Found: {len(report.issues)}")
            for issue in report.issues:
                print(f"  - {issue.issue_name} ({issue.issue_type})")
        
        # Show router statistics
        stats = router.get_router_stats()
        print(f"\nRouter Statistics:")
        print(f"Total Processed: {stats['total_processed']}")
        print(f"Qwen Success Rate: {stats.get('qwen_success_rate', 0):.2%}")
        print(f"Validation Decisions: {stats['validation_decisions']}")
        
        await router.cleanup()
    
    # Run test
    asyncio.run(test_validation_router())