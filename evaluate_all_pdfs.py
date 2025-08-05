#!/usr/bin/env python3
"""
Batch evaluation script for all home inspection PDFs.

This script evaluates the accuracy of extraction for all PDFs in the data directory
using the LLM-as-judge evaluation pipeline. Generates comprehensive reports showing
which extractions meet the >85% accuracy threshold.

Usage:
    python evaluate_all_pdfs.py [--data-dir data] [--output-dir outputs] [--evaluator gemini-2.5-pro]
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Optional
import json

# Add src to path
script_dir = Path(__file__).parent
src_dir = script_dir / "src"
sys.path.insert(0, str(src_dir))

from evaluators.evaluation_pipeline import (
    HomeInspectionEvaluationPipeline,
    create_evaluation_pipeline
)
from evaluators.evaluation_schemas import BatchEvaluationResult

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_pdf_json_pairs(data_dir: str, outputs_dir: str) -> List[Tuple[str, str]]:
    """
    Find matching PDF and JSON file pairs.
    
    Args:
        data_dir: Directory containing PDF files
        outputs_dir: Directory containing extracted JSON files
        
    Returns:
        List of (pdf_path, json_path) tuples for files that exist
    """
    data_path = Path(data_dir)
    outputs_path = Path(outputs_dir)
    
    pairs = []
    
    # Find all PDF files
    pdf_files = list(data_path.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files in {data_dir}")
    
    for pdf_file in sorted(pdf_files):
        # Look for corresponding JSON file
        pdf_stem = pdf_file.stem
        json_file = outputs_path / f"{pdf_stem}_extracted.json"
        
        if json_file.exists():
            pairs.append((str(pdf_file), str(json_file)))
            logger.debug(f"Found pair: {pdf_file.name} -> {json_file.name}")
        else:
            logger.warning(f"No JSON file found for {pdf_file.name} (expected: {json_file.name})")
    
    logger.info(f"Found {len(pairs)} PDF-JSON pairs ready for evaluation")
    return pairs


def load_api_keys() -> dict:
    """Load API keys from environment variables."""
    api_keys = {}
    
    # Load all possible API keys
    key_names = [
        'GEMINI_API_KEY', 'GOOGLE_API_KEY',
        'ANTHROPIC_API_KEY', 'CLAUDE_API_KEY',
        'OPENAI_API_KEY',
        'LLAMA_PARSE_API_KEY'
    ]
    
    for key_name in key_names:
        value = os.getenv(key_name)
        if value:
            api_keys[key_name] = value
    
    logger.info(f"Loaded {len(api_keys)} API keys from environment")
    return api_keys


async def run_batch_evaluation(
    pdf_json_pairs: List[Tuple[str, str]],
    output_dir: str,
    evaluator_model: str = "gemini-2.5-pro",
    max_concurrent: int = 2
) -> BatchEvaluationResult:
    """
    Run batch evaluation on all PDF-JSON pairs.
    
    Args:
        pdf_json_pairs: List of (pdf_path, json_path) tuples
        output_dir: Directory to save evaluation results
        evaluator_model: Primary evaluator model to use
        max_concurrent: Maximum concurrent evaluations
        
    Returns:
        BatchEvaluationResult with comprehensive statistics
    """
    logger.info(f"Starting batch evaluation with {evaluator_model}")
    logger.info(f"Evaluating {len(pdf_json_pairs)} PDF-JSON pairs")
    logger.info(f"Max concurrent evaluations: {max_concurrent}")
    logger.info(f"Output directory: {output_dir}")
    
    # Load API keys
    api_keys = load_api_keys()
    
    if not api_keys:
        logger.error("No API keys found! Please set GEMINI_API_KEY and/or ANTHROPIC_API_KEY")
        raise ValueError("No API keys available for evaluation")
    
    # Create evaluation pipeline
    backup_model = "claude-sonnet-4" if "gemini" in evaluator_model.lower() else "gemini-2.5-pro"
    pipeline = create_evaluation_pipeline(
        primary_evaluator=evaluator_model,
        backup_evaluator=backup_model,
        api_keys=api_keys
    )
    
    try:
        # Initialize extractors
        logger.info("Initializing LLM extractors for evaluation...")
        extractor_status = await pipeline.initialize_extractors()
        logger.info(f"Extractor initialization status: {extractor_status}")
        
        # Check if we have at least one working extractor
        if not any(extractor_status.values()):
            raise ValueError("No LLM extractors could be initialized - check API keys")
        
        # Run batch evaluation
        batch_result = await pipeline.batch_evaluate(
            pdf_json_pairs=pdf_json_pairs,
            output_dir=output_dir,
            max_concurrent=max_concurrent
        )
        
        return batch_result
        
    finally:
        await pipeline.cleanup()


def print_evaluation_summary(batch_result: BatchEvaluationResult):
    """Print a comprehensive evaluation summary to console."""
    print("\n" + "=" * 80)
    print("HOME INSPECTION EXTRACTION EVALUATION RESULTS")
    print("=" * 80)
    
    print(f"\nEVALUATION OVERVIEW:")
    print(f"  Date: {batch_result.evaluation_timestamp}")
    print(f"  Evaluator Model: {batch_result.evaluator_model}")
    print(f"  Total PDFs: {batch_result.total_pdfs_evaluated}")
    print(f"  Successful Evaluations: {batch_result.successful_evaluations}")
    print(f"  Failed Evaluations: {batch_result.failed_evaluations}")
    print(f"  Total Evaluation Time: {batch_result.total_evaluation_time:.1f} seconds")
    print(f"  Average Time per PDF: {batch_result.average_evaluation_time:.1f} seconds")
    
    print(f"\nACCURACY METRICS:")
    print(f"  Average Overall Accuracy: {batch_result.average_overall_accuracy:.1f}%")
    print(f"  Average Content Accuracy: {batch_result.average_content_accuracy:.1f}%")
    print(f"  Average Image Accuracy: {batch_result.average_image_accuracy:.1f}%")
    print(f"  Average Completeness: {batch_result.average_completeness:.1f}%")
    
    print(f"\nTHRESHOLD ANALYSIS:")
    print(f"  PDFs Passing 85% Threshold: {batch_result.pdfs_passing_threshold}/{batch_result.successful_evaluations}")
    print(f"  Overall Pass Rate: {batch_result.overall_pass_rate:.1f}%")
    
    # System requirements status
    if batch_result.meets_system_requirements:
        print(f"  🎉 SYSTEM MEETS >85% ACCURACY REQUIREMENT!")
    else:
        print(f"  ❌ SYSTEM FAILS >85% ACCURACY REQUIREMENT")
    
    # Accuracy distribution
    if batch_result.accuracy_distribution:
        print(f"\nACCURACY DISTRIBUTION:")
        for level, count in batch_result.accuracy_distribution.items():
            percentage = (count / batch_result.successful_evaluations) * 100 if batch_result.successful_evaluations > 0 else 0
            print(f"  {level.title()}: {count} PDFs ({percentage:.1f}%)")
    
    # Individual results summary
    if batch_result.pdf_results:
        print(f"\nINDIVIDUAL RESULTS SUMMARY:")
        print(f"{'PDF':<20} {'Overall':<8} {'Content':<8} {'Images':<8} {'Complete':<9} {'Pass':<5}")
        print("-" * 60)
        
        for result in sorted(batch_result.pdf_results, key=lambda x: x.overall_accuracy_score, reverse=True):
            pdf_name = Path(result.pdf_filename).stem
            pass_mark = "✓" if result.passes_threshold else "✗"
            print(f"{pdf_name:<20} {result.overall_accuracy_score:>6.1f}% "
                  f"{result.content_accuracy_score:>6.1f}% {result.image_accuracy_score:>6.1f}% "
                  f"{result.completeness_score:>7.1f}% {pass_mark:>3}")
    
    # Top performing PDFs
    if batch_result.pdf_results:
        top_performers = [r for r in batch_result.pdf_results if r.passes_threshold]
        if top_performers:
            print(f"\nTOP PERFORMING EXTRACTIONS (≥85%):")
            for result in sorted(top_performers, key=lambda x: x.overall_accuracy_score, reverse=True)[:5]:
                print(f"  {Path(result.pdf_filename).stem}: {result.overall_accuracy_score:.1f}%")
        
        # Poor performing PDFs
        poor_performers = [r for r in batch_result.pdf_results if not r.passes_threshold]
        if poor_performers:
            print(f"\nPOOR PERFORMING EXTRACTIONS (<85%):")
            for result in sorted(poor_performers, key=lambda x: x.overall_accuracy_score)[:5]:
                print(f"  {Path(result.pdf_filename).stem}: {result.overall_accuracy_score:.1f}%")
    
    # Common patterns
    if batch_result.common_strengths:
        print(f"\nCOMMON STRENGTHS:")
        for strength in batch_result.common_strengths[:5]:
            print(f"  • {strength}")
    
    if batch_result.common_weaknesses:
        print(f"\nCOMMON WEAKNESSES:")
        for weakness in batch_result.common_weaknesses[:5]:
            print(f"  • {weakness}")
    
    if batch_result.system_recommendations:
        print(f"\nSYSTEM RECOMMENDATIONS:")
        for rec in batch_result.system_recommendations:
            print(f"  • {rec}")
    
    # Failed evaluations
    if batch_result.failed_evaluations_details:
        print(f"\nFAILED EVALUATIONS:")
        for failure in batch_result.failed_evaluations_details:
            pdf_name = Path(failure['pdf_path']).name
            print(f"  {pdf_name}: {failure['error']}")
    
    print(f"\nSUMMARY:")
    print(f"{batch_result.summary}")
    
    print("\n" + "=" * 80)


async def main():
    """Main entry point for batch evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate extraction accuracy for all home inspection PDFs"
    )
    parser.add_argument(
        "--data-dir", 
        default="data",
        help="Directory containing PDF files (default: data)"
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs", 
        help="Directory containing extracted JSON files (default: outputs)"
    )
    parser.add_argument(
        "--evaluation-dir",
        default="outputs/evaluations",
        help="Directory to save evaluation results (default: outputs/evaluations)"
    )
    parser.add_argument(
        "--evaluator",
        default="gemini-2.5-pro",
        choices=["gemini-2.5-pro", "gemini-2.5-flash", "claude-sonnet-4", "claude-opus-4"],
        help="Primary evaluator model (default: gemini-2.5-pro)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="Maximum concurrent evaluations (default: 2)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Find PDF-JSON pairs
        pairs = find_pdf_json_pairs(args.data_dir, args.outputs_dir)
        
        if not pairs:
            logger.error("No PDF-JSON pairs found for evaluation!")
            logger.error(f"Check that {args.data_dir} contains PDFs and {args.outputs_dir} contains extracted JSONs")
            return 1
        
        # Run batch evaluation
        batch_result = await run_batch_evaluation(
            pdf_json_pairs=pairs,
            output_dir=args.evaluation_dir,
            evaluator_model=args.evaluator,
            max_concurrent=args.max_concurrent
        )
        
        # Print summary to console
        print_evaluation_summary(batch_result)
        
        # Print file locations
        print(f"\nDETAILED RESULTS SAVED TO:")
        print(f"  Evaluation Directory: {args.evaluation_dir}")
        print(f"  Individual Results: {args.evaluation_dir}/individual_results/")
        print(f"  Summary Report: {args.evaluation_dir}/evaluation_summary.txt")
        
        # Return exit code based on system requirements
        if batch_result.meets_system_requirements:
            logger.info("✅ SUCCESS: System meets >85% accuracy requirement")
            return 0
        else:
            logger.warning("⚠️  WARNING: System does not meet >85% accuracy requirement")
            return 2
            
    except KeyboardInterrupt:
        logger.info("Evaluation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Evaluation failed: {str(e)}")
        return 1


if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)