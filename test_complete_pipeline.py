#!/usr/bin/env python3
"""
Test complete extraction pipeline with image extraction.

This script tests the full pipeline from PDF to JSON with actual image files.
"""

import os
import sys
import asyncio
import json
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extractors.pipeline import HomeInspectionExtractionPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_complete_pipeline():
    """Test the complete extraction pipeline with image extraction."""
    
    print("TESTING COMPLETE EXTRACTION PIPELINE WITH IMAGES")
    print("=" * 60)
    
    # Test PDF - we'll use PDF 2 which should have many images
    test_pdf = Path("./data/2.pdf")
    output_dir = Path("./outputs/pipeline_test")
    
    if not test_pdf.exists():
        print(f"ERROR: Test PDF not found: {test_pdf}")
        return
    
    try:
        # Initialize pipeline
        pipeline = HomeInspectionExtractionPipeline(
            mock_mode=False,
            enable_claude_fallback=True,
            confidence_threshold=70.0
        )
        
        # Validate setup
        validation = await pipeline.validate_setup()
        print(f"Pipeline validation: {validation['overall_status']}")
        if validation['errors']:
            print("Errors:", validation['errors'])
        if validation['warnings']:
            print("Warnings:", validation['warnings'])
        print()
        
        # Extract with image processing
        print(f"Extracting from: {test_pdf.name}")
        print(f"Output directory: {output_dir}")
        print()
        
        result = await pipeline.extract_from_pdf(
            str(test_pdf), 
            output_dir=str(output_dir),
            save_intermediate=True
        )
        
        print("EXTRACTION RESULTS:")
        print("-" * 40)
        print(f"Success: {result.success}")
        print(f"Processing time: {result.processing_time:.2f}s")
        print(f"Model used: {result.model_used}")
        
        if result.validation_metadata:
            vm = result.validation_metadata
            print(f"Confidence score: {vm.confidence_score}")
            print(f"Pipeline used: {vm.pipeline_used}")
        print()
        
        if result.success and result.report:
            print("REPORT DETAILS:")
            print("-" * 40)
            print(f"Report name: {result.report.report_name}")
            print(f"Source PDF: {result.report.source_pdf}")
            print(f"Issues found: {len(result.report.issues)}")
            print()
            
            # Check for images in issues
            total_issue_images = 0
            issues_with_images = 0
            
            print("ISSUES WITH IMAGES:")
            print("-" * 40)
            
            for i, issue in enumerate(result.report.issues[:5], 1):  # Show first 5 issues
                issue_image_count = len(issue.issue_images)
                total_issue_images += issue_image_count
                
                if issue_image_count > 0:
                    issues_with_images += 1
                
                print(f"{i}. {issue.issue_name}")
                print(f"   Type: {issue.issue_type}")
                print(f"   Images: {issue_image_count}")
                
                if issue.issue_images:
                    for img_path in issue.issue_images[:3]:  # Show first 3 images
                        # Check if file exists
                        if Path(img_path).exists():
                            file_size = Path(img_path).stat().st_size
                            print(f"   - {img_path} (OK - {file_size:,} bytes)")
                        else:
                            print(f"   - {img_path} (MISSING)")
                    
                    if len(issue.issue_images) > 3:
                        print(f"   ... and {len(issue.issue_images) - 3} more images")
                print()
            
            if len(result.report.issues) > 5:
                print(f"... and {len(result.report.issues) - 5} more issues")
                print()
            
            print("IMAGE SUMMARY:")
            print("-" * 40)
            print(f"Total issues: {len(result.report.issues)}")
            print(f"Issues with images: {issues_with_images}")
            print(f"Total issue images: {total_issue_images}")
            print()
            
            # Check output directory
            if output_dir.exists():
                json_files = list(output_dir.glob("*.json"))
                md_files = list(output_dir.glob("*.md"))
                
                print("OUTPUT FILES:")
                print("-" * 40)
                print(f"JSON files: {len(json_files)}")
                print(f"Markdown files: {len(md_files)}")
                
                if json_files:
                    json_file = json_files[0]
                    print(f"JSON file: {json_file.name} ({json_file.stat().st_size:,} bytes)")
                    
                    # Read and validate JSON
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                        
                        print("JSON structure validation: OK")
                        
                        # Check image references in JSON
                        issues_in_json = json_data.get('issues', [])
                        json_image_count = sum(len(issue.get('issue_images', [])) for issue in issues_in_json)
                        print(f"Image references in JSON: {json_image_count}")
                        
                    except Exception as e:
                        print(f"JSON validation failed: {e}")
                print()
            
            # Check actual image directory
            image_dir = Path("./outputs/images/2")
            if image_dir.exists():
                image_files = list(image_dir.glob("*.png"))
                print(f"Actual image files extracted: {len(image_files)}")
                
                if image_files:
                    total_size = sum(f.stat().st_size for f in image_files)
                    print(f"Total image size: {total_size:,} bytes")
                    print(f"Average image size: {total_size // len(image_files):,} bytes")
            else:
                print("No image directory found")
        
        else:
            print(f"ERROR: {result.error_message}")
        
        # Cleanup
        await pipeline.cleanup()
        
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_complete_pipeline())