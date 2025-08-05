#!/usr/bin/env python
"""Quick test to verify image extraction is working."""

import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from src.extractors.pdf_parser import LlamaParseIntegration


async def test_image_extraction():
    """Test image extraction on PDF 2."""
    parser = LlamaParseIntegration()
    
    # Parse PDF 2 which should have ~17 images
    pdf_path = "data/2.pdf"
    print(f"Testing image extraction on: {pdf_path}")
    
    result = await parser.parse_pdf_async(pdf_path)
    
    if result['success']:
        print(f"✓ Parsed successfully")
        print(f"✓ Text extracted: {len(result['markdown_content'])} characters")
        print(f"✓ Images extracted: {len(result['images'])}")
        
        # Check actual image files
        image_dir = Path("outputs/images/2")
        if image_dir.exists():
            image_files = list(image_dir.glob("*.png"))
            print(f"✓ Image files saved: {len(image_files)}")
            
            # Show some file names
            print("\nSample images:")
            for img in list(image_files)[:5]:
                size_kb = img.stat().st_size / 1024
                print(f"  - {img.name} ({size_kb:.1f} KB)")
    else:
        print(f"✗ Failed: {result['error_message']}")


if __name__ == "__main__":
    asyncio.run(test_image_extraction())