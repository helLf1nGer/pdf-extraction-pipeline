#!/usr/bin/env python3
"""
Command Line Interface for Home Inspection PDF Extraction

This script provides an easy-to-use CLI for testing the extraction pipeline
with both mock and production modes.
"""

import os
import sys
import asyncio
import argparse
import json
from pathlib import Path
from typing import List, Optional

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / 'src'))

from src.extractors.pipeline import HomeInspectionExtractionPipeline, create_pipeline
from src.extractors.schemas import ExtractionResult


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    import logging
    
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce noise from external libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('anthropic').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)


def print_result(result: ExtractionResult, verbose: bool = False):
    """Print extraction result in a formatted way."""
    print(f"\n{'='*60}")
    print(f"EXTRACTION RESULT")
    print(f"{'='*60}")
    print(f"Success: {'YES' if result.success else 'NO'}")
    print(f"Model: {result.model_used or 'Unknown'}")
    print(f"Complexity: {result.pdf_complexity or 'Unknown'}")
    print(f"Processing Time: {result.processing_time:.2f}s" if result.processing_time else "Unknown")
    
    if result.success and result.report:
        print(f"Report Name: {result.report.report_name}")
        print(f"Issues Found: {len(result.report.issues)}")
        
        if verbose and result.report.issues:
            print(f"\nISSUES DETAIL:")
            for i, issue in enumerate(result.report.issues[:5]):  # Show first 5
                print(f"  {i+1}. {issue.issue_name} ({issue.issue_type})")
                if verbose:
                    print(f"     Summary: {issue.issue_summary}")
            
            if len(result.report.issues) > 5:
                print(f"  ... and {len(result.report.issues) - 5} more issues")
    
    if not result.success:
        print(f"Error: {result.error_message}")
    
    print(f"{'='*60}")


async def extract_single(args):
    """Extract data from a single PDF."""
    pdf_path = Path(args.pdf)
    
    if not pdf_path.exists():
        print(f"[ERROR] Error: PDF file not found: {pdf_path}")
        return False
    
    print(f"[SEARCH] Extracting from: {pdf_path.name}")
    print(f"[DIR] Output directory: {args.output or 'outputs/'}")
    print(f"[TEST] Mock mode: {'ON' if args.mock else 'OFF'}")
    
    # Create pipeline
    pipeline = create_pipeline(mock_mode=args.mock)
    
    # Validate setup if not in mock mode
    if not args.mock:
        validation = pipeline.validate_setup()
        if not validation['overall_status']:
            print("[ERROR] Pipeline validation failed!")
            for error in validation['errors']:
                print(f"   - {error}")
            print("\n[TIP] Try using --mock for testing without API keys")
            return False
        else:
            print("[OK] Pipeline validation passed")
    
    # Run extraction
    try:
        result = await pipeline.extract_from_pdf(
            str(pdf_path),
            output_dir=args.output,
            save_intermediate=args.save_intermediate
        )
        
        print_result(result, args.verbose)
        
        # Save result as JSON if successful
        if result.success and result.report and args.output:
            output_path = Path(args.output)
            output_path.mkdir(parents=True, exist_ok=True)
            
            json_file = output_path / f"{pdf_path.stem}_result.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(result.report.dict(), f, indent=2, ensure_ascii=False)
            
            print(f"[SAVE] Results saved to: {json_file}")
        
        return result.success
        
    except Exception as e:
        print(f"[ERROR] Extraction failed: {str(e)}")
        return False


async def extract_batch(args):
    """Extract data from multiple PDFs."""
    pdf_dir = Path(args.directory)
    
    if not pdf_dir.exists():
        print(f"[ERROR] Error: Directory not found: {pdf_dir}")
        return False
    
    # Find PDF files
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"[ERROR] No PDF files found in: {pdf_dir}")
        return False
    
    # Limit to specified count
    if args.limit:
        pdf_files = pdf_files[:args.limit]
    
    print(f"[SEARCH] Found {len(pdf_files)} PDF files to process")
    print(f"[DIR] Output directory: {args.output or 'outputs/'}")
    print(f"[TEST] Mock mode: {'ON' if args.mock else 'OFF'}")
    print(f"[SPEED] Max concurrent: {args.concurrent}")
    
    # Create pipeline
    pipeline = create_pipeline(mock_mode=args.mock)
    
    # Validate setup if not in mock mode
    if not args.mock:
        validation = pipeline.validate_setup()
        if not validation['overall_status']:
            print("[ERROR] Pipeline validation failed!")
            for error in validation['errors']:
                print(f"   - {error}")
            return False
    
    # Run batch extraction
    try:
        pdf_paths = [str(pdf) for pdf in pdf_files]
        results = await pipeline.batch_extract(
            pdf_paths,
            output_dir=args.output,
            max_concurrent=args.concurrent,
            save_intermediate=args.save_intermediate
        )
        
        # Summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        print(f"\n{'='*60}")
        print(f"BATCH EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total PDFs: {len(results)}")
        print(f"Successful: {successful} ({successful/len(results)*100:.1f}%)")
        print(f"Failed: {failed}")
        
        # Show individual results
        if args.verbose:
            print(f"\nINDIVIDUAL RESULTS:")
            for i, (pdf_path, result) in enumerate(zip(pdf_paths, results)):
                status = "[OK]" if result.success else "[ERROR]"
                pdf_name = Path(pdf_path).name
                issues = len(result.report.issues) if result.success and result.report else 0
                print(f"  {i+1:2d}. {status} {pdf_name:<30} ({issues:2d} issues)")
        
        # Pipeline statistics
        stats = pipeline.get_pipeline_stats()
        if stats['processing_times']:
            avg_time = stats['avg_processing_time']
            print(f"\nPERFORMANCE:")
            print(f"Average processing time: {avg_time:.2f}s")
            print(f"Model usage: {stats['model_usage']}")
        
        return successful > 0
        
    except Exception as e:
        print(f"[ERROR] Batch extraction failed: {str(e)}")
        return False


async def validate_setup(args):
    """Validate pipeline setup and API keys."""
    print("[CONFIG] Validating pipeline setup...")
    
    pipeline = create_pipeline(mock_mode=args.mock)
    validation = pipeline.validate_setup()
    
    print(f"\n{'='*60}")
    print(f"PIPELINE VALIDATION")
    print(f"{'='*60}")
    print(f"Overall Status: {'PASS' if validation['overall_status'] else 'FAIL'}")
    
    print(f"\nCOMPONENTS:")
    for component, status in validation['components'].items():
        status_icon = "[OK]" if status else "[ERROR]"
        print(f"  {component:<15}: {status_icon}")
    
    if validation['errors']:
        print(f"\nERRORS:")
        for error in validation['errors']:
            print(f"  [ERROR] {error}")
    
    if validation['warnings']:
        print(f"\nWARNINGS:")
        for warning in validation['warnings']:
            print(f"  [WARNING]  {warning}")
    
    if not validation['overall_status']:
        print(f"\n[TIP] SUGGESTIONS:")
        print(f"  - Check API_SETUP.md for API key setup instructions")
        print(f"  - Run 'python src/extractors/test_api_keys.py' to test individual APIs")
        print(f"  - Use --mock flag for testing without API keys")
    
    return validation['overall_status']


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Home Inspection PDF Extraction CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract single PDF (mock mode)
  python extract_cli.py single data/1.pdf --mock --verbose
  
  # Extract single PDF (production)
  python extract_cli.py single data/1.pdf --output results/
  
  # Batch extract first 5 PDFs
  python extract_cli.py batch data/ --limit 5 --mock
  
  # Validate setup
  python extract_cli.py validate
        """
    )
    
    parser.add_argument(
        '--mock', 
        action='store_true', 
        help='Use mock services (no API keys required)'
    )
    
    parser.add_argument(
        '--verbose', '-v', 
        action='store_true', 
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--output', '-o', 
        help='Output directory for results (default: outputs/)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Single PDF extraction
    single_parser = subparsers.add_parser('single', help='Extract single PDF')
    single_parser.add_argument('pdf', help='Path to PDF file')
    single_parser.add_argument(
        '--save-intermediate', 
        action='store_true', 
        help='Save intermediate results (markdown, images)'
    )
    
    # Batch extraction
    batch_parser = subparsers.add_parser('batch', help='Extract multiple PDFs')
    batch_parser.add_argument('directory', help='Directory containing PDF files')
    batch_parser.add_argument(
        '--limit', 
        type=int, 
        help='Limit number of PDFs to process'
    )
    batch_parser.add_argument(
        '--concurrent', 
        type=int, 
        default=2, 
        help='Max concurrent extractions (default: 2)'
    )
    batch_parser.add_argument(
        '--save-intermediate', 
        action='store_true', 
        help='Save intermediate results'
    )
    
    # Validation
    validate_parser = subparsers.add_parser('validate', help='Validate setup')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Set default output directory
    if not args.output:
        args.output = "outputs"
    
    # Handle commands
    if args.command == 'single':
        success = asyncio.run(extract_single(args))
        sys.exit(0 if success else 1)
    
    elif args.command == 'batch':
        success = asyncio.run(extract_batch(args))
        sys.exit(0 if success else 1)
    
    elif args.command == 'validate':
        success = asyncio.run(validate_setup(args))
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()