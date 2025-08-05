"""
Evaluation pipeline for home inspection PDF extraction accuracy.

This module implements the LLM-as-judge pattern to evaluate extraction accuracy
by comparing extracted JSON data against source PDFs. Provides comprehensive
metrics for completeness, content accuracy, and image association.
"""

import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image

from .evaluation_schemas import (
    PDFEvaluationResult,
    BatchEvaluationResult,
    ExtractionCompletenessResult,
    ImageEvaluationResult,
    IssueEvaluationResult,
    EvaluationError,
    AccuracyLevel,
    calculate_accuracy_level,
    calculate_f1_score,
    create_empty_image_result
)

# Import the extractors for LLM evaluation  
from extractors.gemini_extractor import GeminiExtractor
from extractors.claude_extractor import ClaudeExtractor

logger = logging.getLogger(__name__)


class EvaluationPipelineError(Exception):
    """Custom exception for evaluation pipeline errors."""
    pass


class HomeInspectionEvaluationPipeline:
    """
    Comprehensive evaluation pipeline for home inspection extraction accuracy.
    
    Uses LLM-as-judge pattern with structured evaluation prompts to assess:
    - Extraction completeness (expected vs extracted issue count)
    - Content accuracy (field-by-field verification)
    - Image association correctness (image-to-content mappings)
    """
    
    def __init__(self, 
                 primary_evaluator: str = "gemini-2.5-pro",
                 backup_evaluator: str = "claude-sonnet-4",
                 api_keys: Optional[Dict[str, str]] = None,
                 confidence_threshold: float = 80.0):
        """
        Initialize the evaluation pipeline.
        
        Args:
            primary_evaluator: Primary LLM model for evaluation
            backup_evaluator: Backup LLM model if primary fails
            api_keys: Dictionary of API keys
            confidence_threshold: Minimum confidence to accept evaluation
        """
        self.primary_evaluator = primary_evaluator
        self.backup_evaluator = backup_evaluator
        self.api_keys = api_keys or {}
        self.confidence_threshold = confidence_threshold
        
        # Initialize extractors for LLM evaluation
        self.gemini_extractor = None
        self.claude_extractor = None
        
        # Statistics tracking
        self.stats = {
            'total_evaluations': 0,
            'successful_evaluations': 0,
            'failed_evaluations': 0,
            'primary_model_usage': 0,
            'backup_model_usage': 0,
            'evaluation_times': [],
            'accuracy_scores': []
        }
        
    async def initialize_extractors(self) -> Dict[str, bool]:
        """Initialize LLM extractors for evaluation."""
        results = {}
        
        try:
            # Initialize Gemini extractor
            gemini_key = self.api_keys.get('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
            if gemini_key:
                self.gemini_extractor = GeminiExtractor(api_key=gemini_key, model_name='gemini-2.5-pro')
                # Test connection
                if self.gemini_extractor.validate_api_connection():
                    results['gemini'] = True
                    logger.info("Gemini evaluator initialized successfully")
                else:
                    results['gemini'] = False
                    logger.warning("Gemini API connection test failed")
            else:
                results['gemini'] = False
                logger.warning("Gemini API key not found")
                
        except Exception as e:
            logger.error(f"Failed to initialize Gemini evaluator: {str(e)}")
            results['gemini'] = False
        
        try:
            # Initialize Claude extractor
            claude_key = self.api_keys.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
            if claude_key:
                self.claude_extractor = ClaudeExtractor(api_key=claude_key, model_name='claude-3-5-sonnet-20241022')
                # Test connection  
                if self.claude_extractor.validate_api_connection():
                    results['claude'] = True
                    logger.info("Claude evaluator initialized successfully")
                else:
                    results['claude'] = False
                    logger.warning("Claude API connection test failed")
            else:
                results['claude'] = False
                logger.warning("Claude API key not found")
                
        except Exception as e:
            logger.error(f"Failed to initialize Claude evaluator: {str(e)}")
            results['claude'] = False
        
        return results
    
    async def evaluate_pdf_extraction(
        self,
        pdf_path: str,
        json_path: str,
        output_dir: Optional[str] = None
    ) -> PDFEvaluationResult:
        """
        Evaluate extraction accuracy for a single PDF.
        
        Args:
            pdf_path: Path to the original PDF file
            json_path: Path to the extracted JSON file
            output_dir: Optional directory to save evaluation results
            
        Returns:
            PDFEvaluationResult with comprehensive accuracy metrics
        """
        start_time = time.time()
        pdf_path = Path(pdf_path)
        json_path = Path(json_path)
        
        logger.info(f"Starting evaluation: {pdf_path.name} -> {json_path.name}")
        
        try:
            # Validate input files
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            if not json_path.exists():
                raise FileNotFoundError(f"JSON file not found: {json_path}")
            
            # Step 1: Parse ground truth from PDF
            logger.info("Step 1: Parsing ground truth from PDF...")
            ground_truth_start = time.time()
            ground_truth = await self._parse_ground_truth_from_pdf(str(pdf_path))
            ground_truth_time = time.time() - ground_truth_start
            
            # Step 2: Load extracted data
            logger.info("Step 2: Loading extracted JSON data...")
            with open(json_path, 'r', encoding='utf-8') as f:
                extracted_data = json.load(f)
            
            # Step 3: Perform LLM evaluation
            logger.info("Step 3: Performing LLM-as-judge evaluation...")
            llm_eval_start = time.time()
            evaluation_result = await self._perform_llm_evaluation(
                ground_truth, extracted_data, pdf_path.name, json_path.name
            )
            llm_eval_time = time.time() - llm_eval_start
            
            # Step 4: Calculate comprehensive metrics
            logger.info("Step 4: Calculating comprehensive metrics...")
            final_result = await self._calculate_comprehensive_metrics(
                evaluation_result, ground_truth, extracted_data,
                pdf_path.name, json_path.name
            )
            
            # Add timing information
            total_time = time.time() - start_time
            final_result.evaluation_time_seconds = total_time
            final_result.ground_truth_parsing_time = ground_truth_time
            final_result.llm_evaluation_time = llm_eval_time
            
            # Update statistics
            self._update_evaluation_stats(final_result, total_time)
            
            # Save results if requested
            if output_dir:
                await self._save_evaluation_results(final_result, output_dir)
            
            logger.info(f"Evaluation completed: {pdf_path.name} - "
                       f"Overall: {final_result.overall_accuracy_score:.1f}%, "
                       f"Pass: {final_result.passes_threshold}, "
                       f"Time: {total_time:.2f}s")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Evaluation failed for {pdf_path.name}: {str(e)}")
            self.stats['failed_evaluations'] += 1
            raise EvaluationPipelineError(f"Evaluation failed: {str(e)}")
    
    async def _parse_ground_truth_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Parse ground truth data from PDF using LLM."""
        
        # Extract text and images from PDF
        doc = fitz.open(pdf_path)
        
        # Extract text
        full_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            full_text += f"\n--- Page {page_num + 1} ---\n"
            full_text += page.get_text()
        
        # Extract image information
        image_info = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            image_list = page.get_images()
            for img_index, img in enumerate(image_list):
                image_info.append({
                    'page': page_num + 1,
                    'index': img_index,
                    'xref': img[0],
                    'location': f"page_{page_num + 1:02d}_image_{img_index + 1:03d}"
                })
        
        doc.close()
        
        # Create ground truth extraction prompt
        ground_truth_prompt = self._create_ground_truth_prompt(full_text, image_info)
        
        # Use LLM to extract ground truth
        if "gemini" in self.primary_evaluator.lower() and self.gemini_extractor:
            try:
                result = await self.gemini_extractor.extract_async(ground_truth_prompt, "ground_truth")
                response = result.report.dict() if result.success and result.report else {}
                self.stats['primary_model_usage'] += 1
            except Exception as e:
                logger.warning(f"Primary evaluator failed for ground truth: {str(e)}")
                if self.claude_extractor:
                    result = await self.claude_extractor.extract_async(ground_truth_prompt, "ground_truth")
                    response = result.report.dict() if result.success and result.report else {}
                    self.stats['backup_model_usage'] += 1
                else:
                    raise
        elif "claude" in self.primary_evaluator.lower() and self.claude_extractor:
            try:
                result = await self.claude_extractor.extract_async(ground_truth_prompt, "ground_truth")
                response = result.report.dict() if result.success and result.report else {}
                self.stats['primary_model_usage'] += 1
            except Exception as e:
                logger.warning(f"Primary evaluator failed for ground truth: {str(e)}")
                if self.gemini_extractor:
                    result = await self.gemini_extractor.extract_async(ground_truth_prompt, "ground_truth")
                    response = result.report.dict() if result.success and result.report else {}
                    self.stats['backup_model_usage'] += 1
                else:
                    raise
        else:
            raise EvaluationPipelineError("No suitable evaluator available for ground truth parsing")
        
        # Parse the response
        try:
            ground_truth_data = response
            
            # Add image information
            ground_truth_data['pdf_images'] = image_info
            ground_truth_data['total_pdf_images'] = len(image_info)
            
            return ground_truth_data
            
        except Exception as e:
            logger.error(f"Failed to parse ground truth response: {str(e)}")
            raise EvaluationPipelineError(f"Ground truth parsing failed: {str(e)}")
    
    def _create_ground_truth_prompt(self, pdf_text: str, image_info: List[Dict]) -> str:
        """Create a structured prompt for ground truth extraction."""
        
        return f"""
<evaluation_context>
<original_pdf_text>
{pdf_text}
</original_pdf_text>

<pdf_image_locations>
{json.dumps(image_info, indent=2)}
</pdf_image_locations>
</evaluation_context>

<evaluation_task>
You are evaluating a home inspection PDF to establish ground truth for accuracy testing.

Your task is to carefully analyze the PDF content and extract all issues/findings mentioned in the inspection report. This will serve as the ground truth for evaluating an AI extraction system.

CRITICAL REQUIREMENTS:
1. Extract ALL issues mentioned in the document - don't miss any
2. Use the exact names/titles as they appear in the PDF
3. Capture complete descriptions without summarizing
4. Note which images (by their location identifiers) are associated with each issue
5. Be extremely thorough - this is ground truth data

For each issue you find, extract:
- issue_name: Exact name/title as written in the PDF
- issue_type: Category (Electrical, Plumbing, Safety, etc.)
- issue_description: Complete description as written
- issue_summary: Brief summary if provided separately in PDF
- location: Specific location if mentioned
- associated_images: List of image location identifiers that relate to this issue

Output your response as a JSON object with this structure:
{{
  "report_name": "Full report name/title from PDF",
  "issues": [
    {{
      "issue_name": "Exact issue name from PDF",
      "issue_type": "Category",
      "issue_description": "Complete description from PDF",
      "issue_summary": "Summary if available",
      "location": "Location if specified",
      "associated_images": ["page_01_image_001", "page_02_image_003"]
    }}
  ],
  "total_issues_found": 0,
  "confidence_score": 95.0
}}

Be extremely careful to not miss any issues. This ground truth will be used to evaluate extraction accuracy.
</evaluation_task>
"""
    
    async def _perform_llm_evaluation(
        self,
        ground_truth: Dict[str, Any],
        extracted_data: Dict[str, Any],
        pdf_filename: str,
        json_filename: str
    ) -> Dict[str, Any]:
        """Perform LLM-as-judge evaluation comparing ground truth vs extracted data."""
        
        evaluation_prompt = self._create_evaluation_prompt(
            ground_truth, extracted_data, pdf_filename, json_filename
        )
        
        # Use primary evaluator
        if "gemini" in self.primary_evaluator.lower() and self.gemini_extractor:
            try:
                result = await self.gemini_extractor.extract_async(evaluation_prompt, "evaluation")
                response = result.report.dict() if result.success and result.report else {}
                self.stats['primary_model_usage'] += 1
            except Exception as e:
                logger.warning(f"Primary evaluator failed for comparison: {str(e)}")
                if self.claude_extractor:
                    result = await self.claude_extractor.extract_async(evaluation_prompt, "evaluation")
                    response = result.report.dict() if result.success and result.report else {}
                    self.stats['backup_model_usage'] += 1
                else:
                    raise
        elif "claude" in self.primary_evaluator.lower() and self.claude_extractor:
            try:
                result = await self.claude_extractor.extract_async(evaluation_prompt, "evaluation")
                response = result.report.dict() if result.success and result.report else {}
                self.stats['primary_model_usage'] += 1
            except Exception as e:
                logger.warning(f"Primary evaluator failed for comparison: {str(e)}")
                if self.gemini_extractor:
                    result = await self.gemini_extractor.extract_async(evaluation_prompt, "evaluation")
                    response = result.report.dict() if result.success and result.report else {}
                    self.stats['backup_model_usage'] += 1
                else:
                    raise
        else:
            raise EvaluationPipelineError("No suitable evaluator available for comparison")
        
        return response
    
    def _create_evaluation_prompt(
        self,
        ground_truth: Dict[str, Any],
        extracted_data: Dict[str, Any],
        pdf_filename: str,
        json_filename: str
    ) -> str:
        """Create structured evaluation prompt for LLM-as-judge comparison."""
        
        return f"""
<evaluation_context>
<ground_truth_data>
{json.dumps(ground_truth, indent=2)}
</ground_truth_data>

<extracted_data>
{json.dumps(extracted_data, indent=2)}
</extracted_data>

<file_info>
PDF: {pdf_filename}
JSON: {json_filename}
</file_info>
</evaluation_context>

<evaluation_tasks>
You are an expert evaluator assessing the accuracy of an AI extraction system for home inspection reports.

Compare the extracted data against the ground truth and evaluate on these criteria:

1. ISSUE COUNT ACCURACY:
   - Did the extraction find the correct number of issues?
   - Are there missing issues (false negatives)?
   - Are there extra issues that don't exist (false positives)?

2. ISSUE NAME ACCURACY:
   - For each extracted issue, does the name match the ground truth?
   - Rate name accuracy from 0-100 for each issue

3. DESCRIPTION COMPLETENESS AND ACCURACY:
   - Is the description complete compared to ground truth?
   - Is the information accurate?
   - What key information is missing or incorrect?

4. IMAGE ASSOCIATION ACCURACY:
   - Were images correctly associated with issues?
   - Are there missing image associations?
   - Are there incorrect image associations?

5. OVERALL ASSESSMENT:
   - What are the extraction's strengths?
   - What are the key weaknesses?
   - What specific improvements are needed?
</evaluation_tasks>

<required_output_format>
Provide your evaluation as a JSON object with this exact structure:

{{
  "issue_count_evaluation": {{
    "ground_truth_count": 0,
    "extracted_count": 0,
    "correctly_identified": 0,
    "false_positives": 0,
    "false_negatives": 0,
    "missing_issues": ["list of missing issue names"],
    "extra_issues": ["list of incorrectly added issue names"]
  }},
  "issue_evaluations": [
    {{
      "extracted_issue_index": 0,
      "extracted_issue_name": "Name from extraction",
      "ground_truth_match": "Matching ground truth name or null if no match",
      "name_accuracy_score": 95.0,
      "description_accuracy_score": 88.0,
      "description_completeness_score": 92.0,
      "image_association_score": 75.0,
      "overall_issue_score": 87.5,
      "evaluation_notes": ["specific observations"],
      "missing_information": ["what was missed"],
      "incorrect_information": ["what was wrong"]
    }}
  ],
  "image_evaluation": {{
    "total_ground_truth_images": 0,
    "total_extracted_images": 0,
    "correctly_associated_images": 0,
    "extraction_completeness_score": 85.0,
    "association_accuracy_score": 70.0,
    "missing_images": ["list of missing images"],
    "incorrect_associations": ["list of incorrect associations"]
  }},
  "overall_assessment": {{
    "content_accuracy_score": 89.0,
    "completeness_score": 85.0,
    "image_accuracy_score": 72.0,
    "overall_accuracy_score": 82.0,
    "strengths": ["list of strengths"],
    "weaknesses": ["list of weaknesses"],
    "recommendations": ["list of specific improvements needed"]
  }},
  "confidence_score": 92.0
}}

Be thorough, objective, and provide specific examples in your evaluation notes.
</required_output_format>
"""
    
    async def _calculate_comprehensive_metrics(
        self,
        llm_evaluation: Dict[str, Any],
        ground_truth: Dict[str, Any],
        extracted_data: Dict[str, Any],
        pdf_filename: str,
        json_filename: str
    ) -> PDFEvaluationResult:
        """Calculate comprehensive metrics and create final evaluation result."""
        
        # Extract LLM evaluation results
        issue_count_eval = llm_evaluation.get('issue_count_evaluation', {})
        issue_evals = llm_evaluation.get('issue_evaluations', [])
        image_eval = llm_evaluation.get('image_evaluation', {})
        overall_assessment = llm_evaluation.get('overall_assessment', {})
        
        # Create completeness result
        gt_count = issue_count_eval.get('ground_truth_count', 0)
        ext_count = issue_count_eval.get('extracted_count', 0)
        correct_count = issue_count_eval.get('correctly_identified', 0)
        false_pos = issue_count_eval.get('false_positives', 0)
        false_neg = issue_count_eval.get('false_negatives', 0)
        
        # Calculate precision, recall, F1
        precision = (correct_count / ext_count * 100) if ext_count > 0 else 0.0
        recall = (correct_count / gt_count * 100) if gt_count > 0 else 0.0
        f1 = calculate_f1_score(precision, recall)
        
        completeness_result = ExtractionCompletenessResult(
            ground_truth_issue_count=gt_count,
            extracted_issue_count=ext_count,
            correctly_identified_issues=correct_count,
            false_positives=false_pos,
            false_negatives=false_neg,
            precision=precision,
            recall=recall,
            f1_score=f1,
            missed_issues=issue_count_eval.get('missing_issues', []),
            extra_issues=issue_count_eval.get('extra_issues', [])
        )
        
        # Create image evaluation result
        image_result = ImageEvaluationResult(
            total_images_in_pdf=image_eval.get('total_ground_truth_images', 0),
            total_images_extracted=image_eval.get('total_extracted_images', 0),
            correctly_associated_images=image_eval.get('correctly_associated_images', 0),
            extraction_completeness=image_eval.get('extraction_completeness_score', 0.0),
            association_accuracy=image_eval.get('association_accuracy_score', 0.0),
            image_quality_score=100.0,  # Assume good quality for extracted images
            missing_images=image_eval.get('missing_images', []),
            incorrect_associations=[]
        )
        
        # Create individual issue evaluations
        issue_evaluations = []
        for eval_data in issue_evals:
            issue_eval = IssueEvaluationResult(
                issue_index=eval_data.get('extracted_issue_index', 0),
                extracted_issue_name=eval_data.get('extracted_issue_name', ''),
                name_accuracy_score=eval_data.get('name_accuracy_score', 0.0),
                description_accuracy_score=eval_data.get('description_accuracy_score', 0.0),
                description_completeness_score=eval_data.get('description_completeness_score', 0.0),
                image_association_score=eval_data.get('image_association_score', 0.0),
                overall_issue_score=eval_data.get('overall_issue_score', 0.0),
                matched_ground_truth=eval_data.get('ground_truth_match') is not None,
                ground_truth_issue_name=eval_data.get('ground_truth_match'),
                evaluation_notes=eval_data.get('evaluation_notes', []),
                missing_information=eval_data.get('missing_information', []),
                incorrect_information=eval_data.get('incorrect_information', []),
                image_extraction_issues=[]
            )
            issue_evaluations.append(issue_eval)
        
        # Calculate overall scores
        overall_accuracy = overall_assessment.get('overall_accuracy_score', 0.0)
        content_accuracy = overall_assessment.get('content_accuracy_score', 0.0)
        image_accuracy = overall_assessment.get('image_accuracy_score', 0.0)
        completeness_score = overall_assessment.get('completeness_score', 0.0)
        
        # Determine accuracy level and threshold pass
        accuracy_level = calculate_accuracy_level(overall_accuracy)
        passes_threshold = overall_accuracy >= 85.0
        
        # Create evaluation summary
        strengths = overall_assessment.get('strengths', [])
        weaknesses = overall_assessment.get('weaknesses', [])
        recommendations = overall_assessment.get('recommendations', [])
        
        summary_parts = []
        summary_parts.append(f"Overall accuracy: {overall_accuracy:.1f}%")
        summary_parts.append(f"Content accuracy: {content_accuracy:.1f}%")
        summary_parts.append(f"Completeness: {completeness_score:.1f}%")
        summary_parts.append(f"Image accuracy: {image_accuracy:.1f}%")
        summary_parts.append(f"Issues found: {ext_count}/{gt_count} ({precision:.1f}% precision)")
        
        if passes_threshold:
            summary_parts.append("✓ PASSES 85% threshold")
        else:
            summary_parts.append("✗ FAILS 85% threshold")
        
        evaluation_summary = ". ".join(summary_parts) + "."
        
        # Determine evaluator model used
        evaluator_model = self.primary_evaluator
        if self.stats['backup_model_usage'] > self.stats['primary_model_usage']:
            evaluator_model = self.backup_evaluator
        
        # Create final result
        result = PDFEvaluationResult(
            pdf_filename=pdf_filename,
            json_filename=json_filename,
            evaluation_timestamp=datetime.now(),
            evaluator_model=evaluator_model,
            completeness_result=completeness_result,
            image_result=image_result,
            issue_evaluations=issue_evaluations,
            overall_accuracy_score=overall_accuracy,
            content_accuracy_score=content_accuracy,
            image_accuracy_score=image_accuracy,
            completeness_score=completeness_score,
            accuracy_level=accuracy_level,
            passes_threshold=passes_threshold,
            evaluation_summary=evaluation_summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
        
        return result
    
    def _update_evaluation_stats(self, result: PDFEvaluationResult, evaluation_time: float):
        """Update evaluation pipeline statistics."""
        self.stats['total_evaluations'] += 1
        self.stats['successful_evaluations'] += 1
        self.stats['evaluation_times'].append(evaluation_time)
        self.stats['accuracy_scores'].append(result.overall_accuracy_score)
    
    async def _save_evaluation_results(self, result: PDFEvaluationResult, output_dir: str):
        """Save evaluation results to disk."""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Create filename based on PDF name
            pdf_stem = Path(result.pdf_filename).stem
            results_file = output_path / f"{pdf_stem}_evaluation.json"
            
            # Save evaluation results
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(result.dict(), f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Saved evaluation results to {results_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save evaluation results: {str(e)}")
    
    async def batch_evaluate(
        self,
        pdf_json_pairs: List[Tuple[str, str]],
        output_dir: Optional[str] = None,
        max_concurrent: int = 2
    ) -> BatchEvaluationResult:
        """
        Evaluate multiple PDF extractions in batch.
        
        Args:
            pdf_json_pairs: List of (pdf_path, json_path) tuples
            output_dir: Optional directory to save results
            max_concurrent: Maximum concurrent evaluations
            
        Returns:
            BatchEvaluationResult with aggregate statistics
        """
        start_time = time.time()
        logger.info(f"Starting batch evaluation of {len(pdf_json_pairs)} PDF-JSON pairs")
        
        # Initialize extractors if not done already
        if not self.gemini_extractor and not self.claude_extractor:
            await self.initialize_extractors()
        
        # Create output directory for individual results
        individual_results_dir = None
        if output_dir:
            individual_results_dir = Path(output_dir) / "individual_results"
            individual_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Process evaluations with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def evaluate_with_semaphore(pdf_path: str, json_path: str) -> Optional[PDFEvaluationResult]:
            async with semaphore:
                try:
                    return await self.evaluate_pdf_extraction(
                        pdf_path, json_path, str(individual_results_dir) if individual_results_dir else None
                    )
                except Exception as e:
                    logger.error(f"Failed to evaluate {Path(pdf_path).name}: {str(e)}")
                    return None
        
        # Execute evaluations
        tasks = [evaluate_with_semaphore(pdf_path, json_path) for pdf_path, json_path in pdf_json_pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and separate successful from failed
        successful_results: List[PDFEvaluationResult] = []
        failed_evaluations: List[Dict[str, str]] = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_evaluations.append({
                    'pdf_path': pdf_json_pairs[i][0],
                    'json_path': pdf_json_pairs[i][1],
                    'error': str(result)
                })
            elif result is not None:
                successful_results.append(result)
            else:
                failed_evaluations.append({
                    'pdf_path': pdf_json_pairs[i][0],
                    'json_path': pdf_json_pairs[i][1],
                    'error': 'Unknown evaluation failure'
                })
        
        # Calculate aggregate statistics
        total_evaluations = len(pdf_json_pairs)
        successful_count = len(successful_results)
        failed_count = len(failed_evaluations)
        
        if successful_results:
            avg_overall = sum(r.overall_accuracy_score for r in successful_results) / successful_count
            avg_content = sum(r.content_accuracy_score for r in successful_results) / successful_count
            avg_image = sum(r.image_accuracy_score for r in successful_results) / successful_count
            avg_completeness = sum(r.completeness_score for r in successful_results) / successful_count
            
            passing_count = sum(1 for r in successful_results if r.passes_threshold)
            pass_rate = (passing_count / successful_count) * 100
            
            # Count accuracy level distribution
            accuracy_distribution = {}
            for level in AccuracyLevel:
                count = sum(1 for r in successful_results if r.accuracy_level == level)
                accuracy_distribution[level.value] = count
        else:
            avg_overall = avg_content = avg_image = avg_completeness = 0.0
            passing_count = 0
            pass_rate = 0.0
            accuracy_distribution = {}
        
        # Determine system requirements compliance
        meets_requirements = avg_overall >= 85.0
        
        # Create summary
        summary_parts = [
            f"Evaluated {total_evaluations} PDF extractions with {successful_count} successful evaluations.",
            f"Average overall accuracy: {avg_overall:.1f}%",
            f"Pass rate (≥85%): {pass_rate:.1f}% ({passing_count}/{successful_count})",
        ]
        
        if meets_requirements:
            summary_parts.append("✓ SYSTEM MEETS >85% ACCURACY REQUIREMENT")
        else:
            summary_parts.append("✗ SYSTEM FAILS >85% ACCURACY REQUIREMENT")
        
        if failed_count > 0:
            summary_parts.append(f"⚠ {failed_count} evaluations failed")
        
        summary = " ".join(summary_parts)
        
        # Analyze common patterns
        common_strengths = []
        common_weaknesses = []
        system_recommendations = []
        
        if successful_results:
            # Find most common strengths
            all_strengths = []
            for result in successful_results:
                all_strengths.extend(result.strengths)
            
            strength_counts = {}
            for strength in all_strengths:
                strength_counts[strength] = strength_counts.get(strength, 0) + 1
            
            common_strengths = [s for s, count in sorted(strength_counts.items(), key=lambda x: x[1], reverse=True)[:5]]
            
            # Find most common weaknesses
            all_weaknesses = []
            for result in successful_results:
                all_weaknesses.extend(result.weaknesses)
            
            weakness_counts = {}
            for weakness in all_weaknesses:
                weakness_counts[weakness] = weakness_counts.get(weakness, 0) + 1
            
            common_weaknesses = [w for w, count in sorted(weakness_counts.items(), key=lambda x: x[1], reverse=True)[:5]]
            
            # Generate system recommendations
            if avg_image < 50:
                system_recommendations.append("Critical: Fix image extraction pipeline - severely underperforming")
            if avg_completeness < 85:
                system_recommendations.append("Improve issue detection completeness to reduce false negatives")
            if avg_content < 90:
                system_recommendations.append("Enhance content accuracy, particularly for issue descriptions")
            if pass_rate < 85:
                system_recommendations.append(f"Overall system accuracy needs improvement: {pass_rate:.1f}% pass rate is below target")
        
        # Determine evaluator model used
        evaluator_model = self.primary_evaluator
        if self.stats['backup_model_usage'] > self.stats['primary_model_usage']:
            evaluator_model = self.backup_evaluator
        
        # Create batch result
        batch_result = BatchEvaluationResult(
            evaluation_timestamp=datetime.now(),
            evaluator_model=evaluator_model,
            total_pdfs_evaluated=total_evaluations,
            successful_evaluations=successful_count,
            failed_evaluations=failed_count,
            pdf_results=successful_results,
            average_overall_accuracy=avg_overall,
            average_content_accuracy=avg_content,
            average_image_accuracy=avg_image,
            average_completeness=avg_completeness,
            pdfs_passing_threshold=passing_count,
            overall_pass_rate=pass_rate,
            meets_system_requirements=meets_requirements,
            accuracy_distribution=accuracy_distribution,
            total_evaluation_time=time.time() - start_time,
            average_evaluation_time=sum(self.stats['evaluation_times']) / len(self.stats['evaluation_times']) if self.stats['evaluation_times'] else 0,
            summary=summary,
            common_strengths=common_strengths,
            common_weaknesses=common_weaknesses,
            system_recommendations=system_recommendations,
            failed_evaluations_details=failed_evaluations
        )
        
        # Save batch results
        if output_dir:
            await self._save_batch_results(batch_result, output_dir)
        
        logger.info(f"Batch evaluation completed: {successful_count}/{total_evaluations} successful, "
                   f"avg accuracy: {avg_overall:.1f}%, pass rate: {pass_rate:.1f}%")
        
        return batch_result
    
    async def _save_batch_results(self, batch_result: BatchEvaluationResult, output_dir: str):
        """Save batch evaluation results."""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Save comprehensive batch results
            batch_file = output_path / f"batch_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(batch_file, 'w', encoding='utf-8') as f:
                json.dump(batch_result.dict(), f, indent=2, ensure_ascii=False, default=str)
            
            # Save summary report
            summary_file = output_path / "evaluation_summary.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("HOME INSPECTION EXTRACTION EVALUATION SUMMARY\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Evaluation Date: {batch_result.evaluation_timestamp}\n")
                f.write(f"Evaluator Model: {batch_result.evaluator_model}\n")
                f.write(f"Total PDFs: {batch_result.total_pdfs_evaluated}\n")
                f.write(f"Successful Evaluations: {batch_result.successful_evaluations}\n")
                f.write(f"Failed Evaluations: {batch_result.failed_evaluations}\n\n")
                
                f.write("ACCURACY METRICS:\n")
                f.write(f"  Average Overall Accuracy: {batch_result.average_overall_accuracy:.1f}%\n")
                f.write(f"  Average Content Accuracy: {batch_result.average_content_accuracy:.1f}%\n")
                f.write(f"  Average Image Accuracy: {batch_result.average_image_accuracy:.1f}%\n")
                f.write(f"  Average Completeness: {batch_result.average_completeness:.1f}%\n\n")
                
                f.write("THRESHOLD ANALYSIS:\n")
                f.write(f"  PDFs Passing 85% Threshold: {batch_result.pdfs_passing_threshold}/{batch_result.successful_evaluations}\n")
                f.write(f"  Overall Pass Rate: {batch_result.overall_pass_rate:.1f}%\n")
                f.write(f"  Meets System Requirements (>85%): {'YES' if batch_result.meets_system_requirements else 'NO'}\n\n")
                
                if batch_result.common_strengths:
                    f.write("COMMON STRENGTHS:\n")
                    for strength in batch_result.common_strengths:
                        f.write(f"  • {strength}\n")
                    f.write("\n")
                
                if batch_result.common_weaknesses:
                    f.write("COMMON WEAKNESSES:\n")
                    for weakness in batch_result.common_weaknesses:
                        f.write(f"  • {weakness}\n")
                    f.write("\n")
                
                if batch_result.system_recommendations:
                    f.write("SYSTEM RECOMMENDATIONS:\n")
                    for rec in batch_result.system_recommendations:
                        f.write(f"  • {rec}\n")
                    f.write("\n")
                
                f.write(f"SUMMARY:\n{batch_result.summary}\n")
            
            logger.info(f"Saved batch evaluation results to {batch_file}")
            logger.info(f"Saved evaluation summary to {summary_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save batch results: {str(e)}")
    
    def get_evaluation_stats(self) -> Dict[str, Any]:
        """Get evaluation pipeline statistics."""
        stats = self.stats.copy()
        
        if stats['evaluation_times']:
            times = stats['evaluation_times']
            stats['avg_evaluation_time'] = sum(times) / len(times)
            stats['min_evaluation_time'] = min(times)
            stats['max_evaluation_time'] = max(times)
        
        if stats['accuracy_scores']:
            scores = stats['accuracy_scores']
            stats['avg_accuracy_score'] = sum(scores) / len(scores)
            stats['min_accuracy_score'] = min(scores)
            stats['max_accuracy_score'] = max(scores)
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
    
    async def cleanup(self):
        """Clean up pipeline resources."""
        # Extractors don't have cleanup methods, just clear references
        self.gemini_extractor = None
        self.claude_extractor = None


# Utility functions
def create_evaluation_pipeline(
    primary_evaluator: str = "gemini-2.5-pro",
    backup_evaluator: str = "claude-sonnet-4",
    api_keys: Optional[Dict[str, str]] = None
) -> HomeInspectionEvaluationPipeline:
    """Create an evaluation pipeline instance."""
    return HomeInspectionEvaluationPipeline(
        primary_evaluator=primary_evaluator,
        backup_evaluator=backup_evaluator,
        api_keys=api_keys
    )


async def evaluate_single_pdf(
    pdf_path: str,
    json_path: str,
    output_dir: Optional[str] = None,
    evaluator_model: str = "gemini-2.5-pro"
) -> PDFEvaluationResult:
    """Quick utility to evaluate a single PDF extraction."""
    pipeline = create_evaluation_pipeline(primary_evaluator=evaluator_model)
    try:
        await pipeline.initialize_extractors()
        return await pipeline.evaluate_pdf_extraction(pdf_path, json_path, output_dir)
    finally:
        await pipeline.cleanup()


if __name__ == "__main__":
    # Test the evaluation pipeline
    async def test_evaluation_pipeline():
        print("Testing Home Inspection Evaluation Pipeline")
        print("=" * 50)
        
        pipeline = create_evaluation_pipeline()
        
        try:
            # Initialize extractors
            extractor_status = await pipeline.initialize_extractors()
            print(f"Extractor initialization: {extractor_status}")
            
            # Test with sample data
            test_pdf = "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/1.pdf"
            test_json = "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/outputs/1_extracted.json"
            
            if Path(test_pdf).exists() and Path(test_json).exists():
                print(f"\nEvaluating: {Path(test_pdf).name} -> {Path(test_json).name}")
                
                result = await pipeline.evaluate_pdf_extraction(
                    test_pdf, test_json, "outputs/evaluations"
                )
                
                print(f"\nEvaluation Results:")
                print(f"  Overall Accuracy: {result.overall_accuracy_score:.1f}%")
                print(f"  Content Accuracy: {result.content_accuracy_score:.1f}%")
                print(f"  Image Accuracy: {result.image_accuracy_score:.1f}%")
                print(f"  Completeness: {result.completeness_score:.1f}%")
                print(f"  Accuracy Level: {result.accuracy_level}")
                print(f"  Passes Threshold: {result.passes_threshold}")
                print(f"  Evaluation Time: {result.evaluation_time_seconds:.2f}s")
                
                print(f"\nSummary: {result.evaluation_summary}")
                
                if result.strengths:
                    print(f"\nStrengths:")
                    for strength in result.strengths[:3]:
                        print(f"  • {strength}")
                
                if result.weaknesses:
                    print(f"\nWeaknesses:")
                    for weakness in result.weaknesses[:3]:
                        print(f"  • {weakness}")
            else:
                print("Test files not found!")
                
        finally:
            await pipeline.cleanup()
    
    # Run test
    asyncio.run(test_evaluation_pipeline())