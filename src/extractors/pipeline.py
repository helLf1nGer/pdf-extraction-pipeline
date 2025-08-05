"""
Main extraction pipeline for home inspection PDF processing.

This module orchestrates the complete extraction workflow:
PDF → LlamaParse → Model Router → Gemini/Claude → Structured JSON

The pipeline automatically routes PDFs to appropriate models based on complexity
and provides comprehensive error handling and retry logic.
"""

import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime

from .schemas import HomeInspectionReport, ExtractionResult, ValidationMetadata
from .pdf_parser import LlamaParseIntegration, PDFParsingError
from .enhanced_validation_router import EnhancedValidationRouter, EnhancedValidationRouterError
from .gemini_extractor import GeminiExtractor, GeminiExtractionError
from .claude_extractor import ClaudeExtractor, ClaudeExtractionError
from .mock_services import MockExtractionPipeline

logger = logging.getLogger(__name__)


class ExtractionPipelineError(Exception):
    """Custom exception for pipeline errors."""
    pass


class HomeInspectionExtractionPipeline:
    """
    Complete extraction pipeline for home inspection reports.
    
    Uses enhanced validation approach with Gemini primary extraction,
    Claude backup models, and confidence scoring for optimal results.
    """
    
    def __init__(self, 
                 mock_mode: bool = False, 
                 api_keys: Optional[Dict[str, str]] = None,
                 enable_claude_fallback: bool = True,
                 confidence_threshold: float = 70.0):
        """
        Initialize the extraction pipeline.
        
        Args:
            mock_mode: If True, use mock services for testing without API keys
            api_keys: Optional dictionary of API keys
            enable_claude_fallback: Whether to use Claude for low-confidence results
            confidence_threshold: Minimum confidence to accept without fallback
        """
        self.mock_mode = mock_mode
        self.api_keys = api_keys or {}
        self.enable_claude_fallback = enable_claude_fallback
        self.confidence_threshold = confidence_threshold
        
        # Initialize enhanced validation router
        self.enhanced_router = None
        
        if mock_mode:
            logger.info("Initializing pipeline in MOCK MODE")
            self.mock_pipeline = MockExtractionPipeline()
            self.pdf_parser = None
        else:
            logger.info("Initializing pipeline in PRODUCTION MODE with Enhanced Validation")
            self.mock_pipeline = None
            
            # Initialize PDF parser
            try:
                llamaparse_key = self.api_keys.get('LLAMA_PARSE_API_KEY') or os.getenv('LLAMA_PARSE_API_KEY')
                self.pdf_parser = LlamaParseIntegration(api_key=llamaparse_key)
            except Exception as e:
                logger.error(f"Failed to initialize LlamaParse: {str(e)}")
                self.pdf_parser = None
            
            # Initialize enhanced validation router (will be done async)
            # This contains Gemini Flash/Pro and Claude Sonnet/Opus extractors
        
        # Enhanced pipeline statistics for validation approach
        self.stats = {
            'total_processed': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'processing_times': [],
            'confidence_scores': [],
            'validation_decisions': {},
            'pipeline_usage': {},
            'high_confidence_results': 0,
            'medium_confidence_results': 0,
            'low_confidence_results': 0,
            'manual_review_required': 0,
            'model_agreement_rates': []
        }
        
        logger.info(f"EnhancedValidationPipeline initialized (mock_mode={mock_mode}, claude_backup={enable_claude_fallback})")
    
    async def extract_from_pdf(
        self, 
        pdf_path: str, 
        output_dir: Optional[str] = None,
        save_intermediate: bool = False
    ) -> ExtractionResult:
        """
        Extract structured data from a PDF inspection report using validation approach.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Optional directory to save outputs
            save_intermediate: Whether to save intermediate results (markdown, etc.)
            
        Returns:
            ExtractionResult with success status, extracted data, and validation metadata
        """
        start_time = time.time()
        pdf_path = Path(pdf_path)
        
        logger.info(f"Starting enhanced validation extraction pipeline for: {pdf_path.name}")
        
        try:
            # Validate input
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            if not pdf_path.suffix.lower() == '.pdf':
                raise ValueError(f"File is not a PDF: {pdf_path}")
            
            # Step 1: Parse PDF to markdown
            logger.info("Step 1: Parsing PDF with LlamaParse...")
            parse_result = await self._parse_pdf(str(pdf_path))
            
            if not parse_result['success']:
                return ExtractionResult(
                    success=False,
                    error_message=f"PDF parsing failed: {parse_result.get('error_message', 'Unknown error')}",
                    processing_time=time.time() - start_time,
                    model_used='pipeline-parser-failed'
                )
            
            markdown_content = parse_result['markdown_content']
            images = parse_result.get('images', [])
            
            # Save intermediate results if requested
            if save_intermediate and output_dir:
                await self._save_intermediate_results(
                    pdf_path.name, markdown_content, images, output_dir
                )
            
            # Step 2: Initialize enhanced validation router if needed
            if not self.enhanced_router and not self.mock_mode:
                logger.info("Step 2: Initializing enhanced validation router...")
                self.enhanced_router = EnhancedValidationRouter(
                    api_keys=self.api_keys,
                    enable_backup=self.enable_claude_fallback,
                    confidence_threshold=self.confidence_threshold
                )
                await self.enhanced_router.initialize_extractors()
            
            # Step 3: Extract with enhanced validation pipeline
            logger.info("Step 3: Extracting with enhanced validation pipeline...")
            if self.mock_mode:
                # Use mock extraction for testing
                extraction_result = await self.mock_pipeline.extract_from_pdf(
                    str(pdf_path), "dynamic"
                )
                # Add mock validation metadata
                validation_metadata = ValidationMetadata(
                    validation_performed=True,
                    confidence_score=85.0,
                    validation_decision="use_primary",
                    agreement_percentage=90.0,
                    pipeline_used="mock_enhanced_validation"
                )
                extraction_result.validation_metadata = validation_metadata
            else:
                # Use real enhanced validation extraction
                enhanced_result = await self.enhanced_router.extract_with_enhanced_validation(
                    markdown_content=markdown_content,
                    image_references=images,
                    source_filename=pdf_path.name
                )
                
                # Extract the final result and create validation metadata
                extraction_result = enhanced_result['extraction_result']
                
                validation_metadata = ValidationMetadata(
                    validation_performed=True,  # Always performed in enhanced mode
                    confidence_score=enhanced_result.get('confidence_score'),
                    validation_decision=enhanced_result.get('pipeline_used'),
                    agreement_percentage=enhanced_result.get('comparison_details', {}).get('agreement_percentage'),
                    pipeline_used=enhanced_result['pipeline_used'],
                    discrepancies_found=[],  # Enhanced router handles this differently
                    processing_notes=[f"Complexity: {enhanced_result['complexity_level']}", 
                                     f"Primary model: {enhanced_result['primary_model']}",
                                     f"Backup model: {enhanced_result['backup_model']}"]
                )
                
                extraction_result.validation_metadata = validation_metadata
            
            # Update enhanced statistics
            self._update_validation_stats(extraction_result, validation_metadata)
            
            # Save final results if requested
            if extraction_result.success and output_dir:
                await self._save_final_results(extraction_result, output_dir)
            
            total_time = time.time() - start_time
            extraction_result.processing_time = total_time
            
            logger.info(f"Enhanced validation pipeline completed for {pdf_path.name}: "
                       f"success={extraction_result.success}, confidence={validation_metadata.confidence_score}, "
                       f"pipeline={validation_metadata.pipeline_used}, time={total_time:.2f}s")
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Enhanced validation pipeline failed for {pdf_path.name}: {str(e)}")
            return ExtractionResult(
                success=False,
                error_message=f"Enhanced pipeline error: {str(e)}",
                processing_time=time.time() - start_time,
                model_used='enhanced-validation-pipeline-error'
            )
    
    async def _parse_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Parse PDF using appropriate service."""
        if self.mock_mode:
            return await self.mock_pipeline.llamaparse.parse_pdf_async(pdf_path)
        else:
            if not self.pdf_parser:
                return {
                    'success': False,
                    'error_message': 'LlamaParse not initialized (check API key)'
                }
            return await self.pdf_parser.parse_pdf_async(pdf_path)
    
    def _update_validation_stats(self, result: ExtractionResult, validation_metadata: ValidationMetadata):
        """Update enhanced pipeline statistics for validation approach."""
        self.stats['total_processed'] += 1
        
        if result.success:
            self.stats['successful_extractions'] += 1
        else:
            self.stats['failed_extractions'] += 1
        
        if result.processing_time:
            self.stats['processing_times'].append(result.processing_time)
        
        # Validation-specific statistics
        if validation_metadata.validation_performed and validation_metadata.confidence_score is not None:
            confidence = validation_metadata.confidence_score
            self.stats['confidence_scores'].append(confidence)
            
            if confidence >= 85:
                self.stats['high_confidence_results'] += 1
            elif confidence >= 70:
                self.stats['medium_confidence_results'] += 1
            else:
                self.stats['low_confidence_results'] += 1
        
        # Track validation decisions
        if validation_metadata.validation_decision:
            decision = validation_metadata.validation_decision
            self.stats['validation_decisions'][decision] = self.stats['validation_decisions'].get(decision, 0) + 1
        
        # Track pipeline usage
        if validation_metadata.pipeline_used:
            pipeline = validation_metadata.pipeline_used
            self.stats['pipeline_usage'][pipeline] = self.stats['pipeline_usage'].get(pipeline, 0) + 1
        
        # Track manual review requirements
        if validation_metadata.validation_decision == "manual_review":
            self.stats['manual_review_required'] += 1
        
        # Track agreement rates
        if validation_metadata.agreement_percentage is not None:
            self.stats['model_agreement_rates'].append(validation_metadata.agreement_percentage)
    
    async def cleanup(self):
        """Clean up pipeline resources."""
        if self.enhanced_router:
            await self.enhanced_router.cleanup()
            self.enhanced_router = None
    
    async def _save_intermediate_results(
        self, 
        filename: str, 
        markdown_content: str, 
        images: List[str], 
        output_dir: str
    ):
        """Save intermediate processing results."""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Save markdown content
            markdown_file = output_path / f"{Path(filename).stem}_markdown.md"
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Save image references
            if images:
                images_file = output_path / f"{Path(filename).stem}_images.json"
                with open(images_file, 'w') as f:
                    json.dump(images, f, indent=2)
            
            logger.debug(f"Saved intermediate results for {filename}")
            
        except Exception as e:
            logger.warning(f"Failed to save intermediate results: {str(e)}")
    
    async def _save_final_results(self, result: ExtractionResult, output_dir: str):
        """Save final extraction results."""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            if result.report:
                filename = result.report.source_pdf or "unknown"
                base_name = Path(filename).stem
                
                # Save as JSON
                json_file = output_path / f"{base_name}_extracted.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(result.report.dict(), f, indent=2, ensure_ascii=False)
                
                logger.info(f"Saved extraction results to {json_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save final results: {str(e)}")
    
    
    async def batch_extract(
        self, 
        pdf_paths: List[str], 
        output_dir: Optional[str] = None,
        max_concurrent: int = 3,
        save_intermediate: bool = False
    ) -> List[ExtractionResult]:
        """
        Extract data from multiple PDFs concurrently.
        
        Args:
            pdf_paths: List of PDF file paths
            output_dir: Optional directory to save outputs
            max_concurrent: Maximum number of concurrent extractions
            save_intermediate: Whether to save intermediate results
            
        Returns:
            List of ExtractionResults
        """
        logger.info(f"Starting batch extraction of {len(pdf_paths)} PDFs")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(pdf_path: str) -> ExtractionResult:
            async with semaphore:
                return await self.extract_from_pdf(pdf_path, output_dir, save_intermediate)
        
        # Process PDFs concurrently
        tasks = [extract_with_semaphore(pdf_path) for pdf_path in pdf_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results  
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ExtractionResult(
                    success=False,
                    error_message=f"Batch processing error: {str(result)}",
                    model_used='batch-error'
                ))
            else:
                processed_results.append(result)
        
        # Summary statistics
        successful = sum(1 for r in processed_results if r.success)
        logger.info(f"Batch extraction completed: {successful}/{len(pdf_paths)} successful")
        
        return processed_results
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get comprehensive validation pipeline statistics."""
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
        
        if stats['model_agreement_rates']:
            rates = stats['model_agreement_rates']
            stats['avg_agreement_rate'] = sum(rates) / len(rates)
            stats['min_agreement_rate'] = min(rates)
            stats['max_agreement_rate'] = max(rates)
        
        if stats['total_processed'] > 0:
            stats['success_rate'] = stats['successful_extractions'] / stats['total_processed']
            stats['high_confidence_rate'] = stats['high_confidence_results'] / stats['total_processed']
            stats['manual_review_rate'] = stats['manual_review_required'] / stats['total_processed']
        
        # Add enhanced router stats if available
        if self.enhanced_router:
            router_stats = self.enhanced_router.get_router_stats()
            stats['enhanced_router_stats'] = router_stats
        
        stats['timestamp'] = datetime.now().isoformat()
        stats['pipeline_type'] = 'enhanced_validation_based'
        
        return stats
    
    async def validate_setup(self) -> Dict[str, Any]:
        """
        Validate that all required components are properly configured.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'overall_status': True,
            'components': {},
            'errors': [],
            'warnings': []
        }
        
        if self.mock_mode:
            results['components']['mock_services'] = True
            results['warnings'].append("Running in mock mode - no real API calls will be made")
        else:
            # Validate PDF parser
            if self.pdf_parser:
                try:
                    if hasattr(self.pdf_parser, 'validate_api_key'):
                        results['components']['pdf_parser'] = self.pdf_parser.validate_api_key()
                    else:
                        results['components']['pdf_parser'] = True
                except Exception as e:
                    results['components']['pdf_parser'] = False
                    results['errors'].append(f"PDF parser validation failed: {str(e)}")
            else:
                results['components']['pdf_parser'] = False
                results['errors'].append("PDF parser not initialized")
            
            # Initialize and validate enhanced validation router
            if not self.enhanced_router:
                try:
                    self.enhanced_router = EnhancedValidationRouter(
                        api_keys=self.api_keys,
                        enable_backup=self.enable_claude_fallback,
                        confidence_threshold=self.confidence_threshold
                    )
                    extractor_status = await self.enhanced_router.initialize_extractors()
                    results['components'].update(extractor_status)
                    
                    # Check critical components
                    if not extractor_status.get('gemini_flash') and not extractor_status.get('gemini_pro'):
                        results['errors'].append("Gemini (primary) extractors failed to initialize")
                    if not extractor_status.get('gemini_flash'):
                        results['warnings'].append("Gemini Flash extractor failed - easy PDFs will use Pro")
                    if not extractor_status.get('gemini_pro'):
                        results['warnings'].append("Gemini Pro extractor failed - medium/complex PDFs will use Flash")
                    if self.enable_claude_fallback and not extractor_status.get('claude_sonnet'):
                        results['warnings'].append("Claude Sonnet (backup) extractor failed - limited fallback available")
                    if self.enable_claude_fallback and not extractor_status.get('claude_opus'):
                        results['warnings'].append("Claude Opus (backup) extractor failed - complex PDFs have no backup")
                        
                except Exception as e:
                    results['components']['enhanced_router'] = False
                    results['errors'].append(f"Enhanced validation router initialization failed: {str(e)}")
            else:
                results['components']['enhanced_router'] = True
        
        # Check if any critical components failed
        critical_failures = []
        if not self.mock_mode:
            if not results['components'].get('pdf_parser'):
                critical_failures.append('pdf_parser')
            if not results['components'].get('gemini_flash') and not results['components'].get('gemini_pro'):
                critical_failures.append('gemini_primary_extractors')
        
        if critical_failures:
            results['overall_status'] = False
            results['errors'].append(f"Critical components failed: {critical_failures}")
        
        # Add configuration summary
        results['configuration'] = {
            'mock_mode': self.mock_mode,
            'claude_backup_enabled': self.enable_claude_fallback,
            'confidence_threshold': self.confidence_threshold,
            'pipeline_type': 'enhanced_validation_based'
        }
        
        return results


# Utility functions for easy usage
def create_validation_pipeline(
    mock_mode: bool = False, 
    api_keys: Optional[Dict[str, str]] = None,
    enable_claude_fallback: bool = True,
    confidence_threshold: float = 70.0
) -> HomeInspectionExtractionPipeline:
    """Create a validation-based pipeline instance."""
    return HomeInspectionExtractionPipeline(
        mock_mode=mock_mode, 
        api_keys=api_keys,
        enable_claude_fallback=enable_claude_fallback,
        confidence_threshold=confidence_threshold
    )


async def extract_single_pdf_with_validation(
    pdf_path: str, 
    output_dir: Optional[str] = None,
    mock_mode: bool = False,
    enable_claude_fallback: bool = True
) -> ExtractionResult:
    """Quick utility to extract a single PDF with validation."""
    pipeline = create_validation_pipeline(
        mock_mode=mock_mode,
        enable_claude_fallback=enable_claude_fallback
    )
    try:
        return await pipeline.extract_from_pdf(pdf_path, output_dir)
    finally:
        await pipeline.cleanup()


# Backward compatibility
def create_pipeline(mock_mode: bool = False, api_keys: Optional[Dict[str, str]] = None) -> HomeInspectionExtractionPipeline:
    """Create a pipeline instance (backward compatibility)."""
    return create_validation_pipeline(mock_mode=mock_mode, api_keys=api_keys)


async def extract_single_pdf(
    pdf_path: str, 
    output_dir: Optional[str] = None,
    mock_mode: bool = False
) -> ExtractionResult:
    """Quick utility to extract a single PDF (backward compatibility)."""
    return await extract_single_pdf_with_validation(pdf_path, output_dir, mock_mode)


if __name__ == "__main__":
    # Test the enhanced validation pipeline
    async def test_enhanced_validation_pipeline():
        # Check for mock mode environment variable
        mock_mode = os.getenv('MOCK_MODE', 'false').lower() == 'true'
        
        print(f"Testing enhanced validation extraction pipeline (mock_mode={mock_mode})")
        print("=" * 60)
        
        pipeline = create_validation_pipeline(mock_mode=mock_mode)
        
        try:
            # Validate setup
            validation = await pipeline.validate_setup()
            print(f"Pipeline validation: {validation['overall_status']}")
            if validation['errors']:
                print("Errors:", validation['errors'])
            if validation['warnings']:
                print("Warnings:", validation['warnings'])
            print(f"Configuration: {validation['configuration']}")
            
            # Test with first 3 PDFs (validation is more expensive)
            test_pdfs = [
                "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/1.pdf",
                "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/2.pdf",
                "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/3.pdf",
            ]
            
            existing_pdfs = [pdf for pdf in test_pdfs if Path(pdf).exists()]
            
            if not existing_pdfs:
                print("No test PDFs found!")
                return
            
            print(f"\nTesting with {len(existing_pdfs)} PDFs:")
            
            # Test single extraction
            result = await pipeline.extract_from_pdf(
                existing_pdfs[0], 
                output_dir="outputs/validation_test_results"
            )
            
            print(f"\nEnhanced validation extraction test:")
            print(f"  PDF: {Path(existing_pdfs[0]).name}")
            print(f"  Success: {result.success}")
            print(f"  Model: {result.model_used}")
            print(f"  Time: {result.processing_time:.2f}s")
            
            # Show validation metadata
            if result.validation_metadata:
                vm = result.validation_metadata
                print(f"  Validation performed: {vm.validation_performed}")
                print(f"  Confidence score: {vm.confidence_score}")
                print(f"  Agreement rate: {vm.agreement_percentage}%")
                print(f"  Pipeline used: {vm.pipeline_used}")
                print(f"  Validation decision: {vm.validation_decision}")
            
            if result.success and result.report:
                print(f"  Issues found: {len(result.report.issues)}")
                for i, issue in enumerate(result.report.issues[:3]):  # Show first 3 issues
                    print(f"    {i+1}. {issue.issue_name} ({issue.issue_type})")
                if len(result.report.issues) > 3:
                    print(f"    ... and {len(result.report.issues) - 3} more issues")
            else:
                print(f"  Error: {result.error_message}")
            
            # Show enhanced pipeline stats
            stats = pipeline.get_pipeline_stats()
            print(f"\nEnhanced Validation Pipeline Statistics:")
            print(f"  Total processed: {stats['total_processed']}")
            print(f"  Success rate: {stats.get('success_rate', 0):.2%}")
            print(f"  High confidence rate: {stats.get('high_confidence_rate', 0):.2%}")
            print(f"  Average confidence: {stats.get('avg_confidence_score', 0):.1f}")
            print(f"  Manual review rate: {stats.get('manual_review_rate', 0):.2%}")
            print(f"  Pipeline usage: {stats['pipeline_usage']}")
            print(f"  Validation decisions: {stats['validation_decisions']}")
            
        finally:
            # Always cleanup resources
            await pipeline.cleanup()
    
    # Run test
    asyncio.run(test_enhanced_validation_pipeline())