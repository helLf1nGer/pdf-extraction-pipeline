#!/usr/bin/env python3
"""
Test script for image extraction functionality.

This script tests the enhanced PDF parser with image extraction
using LlamaParse's get_image_documents() method.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extractors.pdf_parser import LlamaParseIntegration

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_image_extraction():
    """Test image extraction from PDF 2 which should have 18+ images."""
    
    print("Testing Enhanced Image Extraction with LlamaParse")
    print("=" * 60)
    
    # Test PDF - we'll use PDF 2 which should have many images
    test_pdf = Path("./data/2.pdf")
    
    if not test_pdf.exists():
        print(f"ERROR: Test PDF not found: {test_pdf}")
        return
    
    try:
        # Initialize parser
        parser = LlamaParseIntegration()
        
        # Validate API key
        if not parser.validate_api_key():
            print("ERROR: Invalid LlamaParse API key")
            return
        
        print(f"Testing image extraction with: {test_pdf.name}")
        print(f"Expected: 18+ images based on user confirmation")
        print()
        
        # Parse PDF with image extraction
        result = await parser.parse_pdf_async(str(test_pdf))
        
        print("PARSING RESULTS:")
        print("-" * 40)
        print(f"Success: {result['success']}")
        print(f"Processing time: {result.get('processing_time', 0):.2f}s")
        print(f"Content length: {result.get('content_length', 0):,} characters")
        print(f"Images extracted: {result.get('image_count', 0)}")
        print()
        
        if result['success']:
            images = result.get('images', [])
            
            if images:
                print("EXTRACTED IMAGES:")
                print("-" * 40)
                for i, image_path in enumerate(images, 1):
                    print(f"{i:2d}. {image_path}")
                    
                    # Verify file exists
                    full_path = Path(image_path)
                    if full_path.exists():
                        file_size = full_path.stat().st_size
                        print(f"     ✓ Exists ({file_size:,} bytes)")
                    else:
                        print(f"     ✗ File not found!")
                print()
                
                # Check image directory
                image_dir = Path("./outputs/images/2")
                if image_dir.exists():
                    all_files = list(image_dir.glob("*.*"))
                    print(f"Total files in {image_dir}: {len(all_files)}")
                    
                    image_files = [f for f in all_files 
                                 if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']]
                    print(f"Image files found: {len(image_files)}")
                    
                    if len(image_files) != len(images):
                        print("⚠️  WARNING: Mismatch between reported and actual image files!")
                else:
                    print("ERROR: Image directory not created!")
                
            else:
                print("No images extracted from PDF")
                print("This might indicate:")
                print("1. PDF has no embedded images")
                print("2. LlamaParse API issue")
                print("3. Image extraction method needs adjustment")
            
            # Show first 500 characters of extracted text
            if result.get('markdown_content'):
                print("SAMPLE EXTRACTED TEXT:")
                print("-" * 40)
                sample_text = result['markdown_content'][:500]
                print(sample_text)
                if len(result['markdown_content']) > 500:
                    print("... (truncated)")
                print()
        
        else:
            print(f"ERROR: {result.get('error_message', 'Unknown error')}")
    
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_image_extraction())