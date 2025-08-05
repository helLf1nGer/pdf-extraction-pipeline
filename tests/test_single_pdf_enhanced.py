#!/usr/bin/env python
"""
Test the enhanced routing on a single PDF.
"""

import asyncio
import logging
import sys
from pathlib import Path
from src.extractors.pipeline import create_validation_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_single_pdf(pdf_path: str):
    """Test enhanced routing on a single PDF."""
    
    # Create pipeline with enhanced routing
    pipeline = create_validation_pipeline(
        mock_mode=False,
        enable_claude_fallback=True,
        confidence_threshold=70.0
    )
    
    try:
        # Validate setup
        print(f"Testing PDF: {pdf_path}")
        print("=" * 60)
        
        # Process PDF
        result = await pipeline.extract_from_pdf(
            pdf_path,
            output_dir="outputs/single_pdf_test",
            save_intermediate=True
        )
        
        # Print results
        print(f"\nResults for {Path(pdf_path).name}:")
        print(f"Success: {result.success}")
        
        if result.success:
            if result.report:
                print(f"Report Name: {result.report.report_name}")
                print(f"Issues found: {len(result.report.issues)}")
                print(f"Model used: {result.model_used}")
                
                # Show first 3 issues
                for i, issue in enumerate(result.report.issues[:3]):
                    print(f"\nIssue {i+1}:")
                    print(f"  Name: {issue.issue_name}")
                    print(f"  Type: {issue.issue_type}")
                    print(f"  Severity: {getattr(issue, 'severity', 'N/A')}")
                    print(f"  Summary: {issue.issue_summary[:100]}...")
                
                if len(result.report.issues) > 3:
                    print(f"\n... and {len(result.report.issues) - 3} more issues")
            
            if result.validation_metadata:
                vm = result.validation_metadata
                print(f"\nValidation Metadata:")
                print(f"  Confidence: {vm.confidence_score:.1f}%")
                print(f"  Pipeline: {vm.pipeline_used}")
                print(f"  Agreement: {vm.agreement_percentage}%")
                print(f"  Decision: {vm.validation_decision}")
        else:
            print(f"Error: {result.error_message}")
        
        print(f"\nProcessing time: {result.processing_time:.2f}s")
        
    finally:
        await pipeline.cleanup()

if __name__ == "__main__":
    # Get PDF path from command line or default
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "data/1.pdf"
    
    asyncio.run(test_single_pdf(pdf_path))