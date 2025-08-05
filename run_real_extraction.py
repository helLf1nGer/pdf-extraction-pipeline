#!/usr/bin/env python
"""
Run the ACTUAL extraction pipeline on a real PDF to show how it's working.
"""

import asyncio
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from src.extractors.pipeline import HomeInspectionExtractionPipeline


async def main():
    """Run real extraction on PDF 2."""
    pdf_path = "data/2.pdf"
    print(f"Running REAL extraction on: {pdf_path}")
    print("=" * 80)
    
    # Create pipeline
    pipeline = HomeInspectionExtractionPipeline(mock_mode=False)
    
    try:
        # Run extraction
        result = await pipeline.extract_from_pdf(
            pdf_path,
            output_dir="outputs",
            save_intermediate=True
        )
        
        if result.success:
            print(f"\nEXTRACTION SUCCESSFUL!")
            print(f"Report Name: {result.report.report_name}")
            print(f"Issues Found: {len(result.report.issues)}")
            print(f"Processing Time: {result.processing_time:.2f} seconds")
            print(f"Model Used: {result.model_used}")
            
            # Show some issues
            print("\nFirst 3 Issues:")
            print("-" * 80)
            for i, issue in enumerate(result.report.issues[:3], 1):
                print(f"\n{i}. {issue.issue_name}")
                print(f"   Type: {issue.issue_type}")
                print(f"   Summary: {issue.issue_summary}")
                print(f"   Images: {issue.issue_images}")
            
            # Check image extraction
            pdf_name = Path(pdf_path).stem
            image_dir = Path(f"outputs/images/{pdf_name}")
            if image_dir.exists():
                image_files = list(image_dir.glob("*.png"))
                print(f"\n\nIMAGE EXTRACTION:")
                print(f"Total image files extracted: {len(image_files)}")
                
                # Count image references in issues
                total_refs = sum(len(issue.issue_images) for issue in result.report.issues)
                print(f"Total image references in JSON: {total_refs}")
                
                # Show some image files
                print("\nSample image files:")
                for img in list(image_files)[:5]:
                    size_kb = img.stat().st_size / 1024
                    print(f"  - {img.name} ({size_kb:.1f} KB)")
            
            # Show JSON output location
            json_path = Path(f"outputs/{pdf_name}_extracted.json")
            if json_path.exists():
                print(f"\n\nJSON output saved to: {json_path}")
                print(f"JSON file size: {json_path.stat().st_size:,} bytes")
                
        else:
            print(f"\nEXTRACTION FAILED!")
            print(f"Error: {result.error_message}")
            
    finally:
        await pipeline.cleanup()
    
    print("\n" + "=" * 80)
    print("DONE!")


if __name__ == "__main__":
    asyncio.run(main())