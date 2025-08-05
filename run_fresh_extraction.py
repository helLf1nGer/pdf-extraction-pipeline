#!/usr/bin/env python
"""
Run fresh extraction on PDFs to demonstrate the complete pipeline with image extraction.
"""

import asyncio
import os
import sys
from pathlib import Path
import json
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.extractors.pipeline import HomeInspectionExtractionPipeline


async def run_extraction(pdf_path: str):
    """Run extraction on a single PDF."""
    print(f"\nExtracting: {pdf_path}")
    print("=" * 60)
    
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
            print(f"✓ Success! Extracted {len(result.report.issues)} issues")
            
            # Count images
            total_images = sum(len(issue.issue_images) for issue in result.report.issues)
            print(f"✓ Total image references: {total_images}")
            
            # Check actual image files
            pdf_name = Path(pdf_path).stem
            image_dir = Path(f"outputs/images/{pdf_name}")
            if image_dir.exists():
                image_files = list(image_dir.glob("*.png"))
                print(f"✓ Image files extracted: {len(image_files)}")
            
            return True
        else:
            print(f"✗ Failed: {result.error_message}")
            return False
            
    finally:
        await pipeline.cleanup()


async def main():
    """Run fresh extractions on multiple PDFs."""
    print("Running Fresh Extractions with Image Support")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Select PDFs to test
    test_pdfs = ["data/1.pdf", "data/2.pdf", "data/3.pdf"]
    
    # Check which exist
    existing_pdfs = [pdf for pdf in test_pdfs if Path(pdf).exists()]
    print(f"\nFound {len(existing_pdfs)} PDFs to process")
    
    # Process each PDF
    results = []
    for pdf_path in existing_pdfs:
        success = await run_extraction(pdf_path)
        results.append((pdf_path, success))
    
    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    successful = sum(1 for _, success in results if success)
    print(f"Successful: {successful}/{len(results)}")
    
    for pdf_path, success in results:
        status = "✓" if success else "✗"
        print(f"{status} {Path(pdf_path).name}")


if __name__ == "__main__":
    asyncio.run(main())