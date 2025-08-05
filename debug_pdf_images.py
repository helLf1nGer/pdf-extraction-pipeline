#!/usr/bin/env python3
"""
Debug script to understand PDF 2 structure and test different LlamaParse settings.

This script investigates why image extraction isn't working and tests various approaches.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extractors.pdf_parser import LlamaParseIntegration

# Try to import additional PDF libraries for analysis
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from llama_parse import LlamaParse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_pdf_with_pypdf2(pdf_path):
    """Analyze PDF using PyPDF2 to see if it has images."""
    if not HAS_PYPDF2:
        print("PyPDF2 not available for analysis")
        return
    
    print("ANALYZING PDF WITH PyPDF2:")
    print("-" * 40)
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            print(f"Number of pages: {len(reader.pages)}")
            
            total_objects = 0
            for page_num, page in enumerate(reader.pages):
                if '/XObject' in page['/Resources']:
                    xobjects = page['/Resources']['/XObject'].get_object()
                    objects = len(xobjects)
                    total_objects += objects
                    print(f"Page {page_num + 1}: {objects} XObjects (potential images)")
            
            print(f"Total XObjects found: {total_objects}")
            
    except Exception as e:
        print(f"PyPDF2 analysis failed: {e}")


def analyze_pdf_with_pymupdf(pdf_path):
    """Analyze PDF using PyMuPDF to detect images."""
    if not HAS_PYMUPDF:
        print("PyMuPDF not available for analysis")
        return
    
    print("ANALYZING PDF WITH PyMuPDF:")
    print("-" * 40)
    
    try:
        doc = fitz.open(pdf_path)
        print(f"Number of pages: {len(doc)}")
        
        total_images = 0
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            total_images += len(image_list)
            print(f"Page {page_num + 1}: {len(image_list)} images")
            
            if image_list:
                for img_index, img in enumerate(image_list):
                    print(f"  Image {img_index + 1}: {img}")
        
        print(f"Total images found: {total_images}")
        doc.close()
        
    except Exception as e:
        print(f"PyMuPDF analysis failed: {e}")


async def test_llamaparse_configurations():
    """Test different LlamaParse configurations for image extraction."""
    pdf_path = "./data/2.pdf"
    
    if not Path(pdf_path).exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return
    
    print("TESTING DIFFERENT LLAMAPARSE CONFIGURATIONS:")
    print("=" * 60)
    
    # Configuration 1: Basic with image extraction enabled
    print("\n1. Testing basic configuration with image extraction...")
    try:
        parser1 = LlamaParse(
            api_key=os.getenv('LLAMA_PARSE_API_KEY'),
            result_type="markdown",
            disable_image_extraction=False,
            verbose=True
        )
        
        image_dir = Path("./outputs/images/2_test1")
        image_dir.mkdir(parents=True, exist_ok=True)
        
        images = await parser1.aget_images([pdf_path], download_path=str(image_dir))
        print(f"Configuration 1 result: {len(images) if images else 0} images")
        
        # Check if files were actually downloaded
        saved_files = list(image_dir.glob("*.*"))
        print(f"Files in directory: {len(saved_files)}")
        
    except Exception as e:
        print(f"Configuration 1 failed: {e}")
    
    # Configuration 2: Premium mode
    print("\n2. Testing premium mode...")
    try:
        parser2 = LlamaParse(
            api_key=os.getenv('LLAMA_PARSE_API_KEY'),
            result_type="markdown",
            disable_image_extraction=False,
            premium_mode=True,
            verbose=True
        )
        
        image_dir = Path("./outputs/images/2_test2")
        image_dir.mkdir(parents=True, exist_ok=True)
        
        images = await parser2.aget_images([pdf_path], download_path=str(image_dir))
        print(f"Configuration 2 result: {len(images) if images else 0} images")
        
        saved_files = list(image_dir.glob("*.*"))
        print(f"Files in directory: {len(saved_files)}")
        
    except Exception as e:
        print(f"Configuration 2 failed: {e}")
    
    # Configuration 3: Extract layout + images
    print("\n3. Testing with extract_layout enabled...")
    try:
        parser3 = LlamaParse(
            api_key=os.getenv('LLAMA_PARSE_API_KEY'),
            result_type="markdown",
            disable_image_extraction=False,
            extract_layout=True,
            verbose=True
        )
        
        image_dir = Path("./outputs/images/2_test3")
        image_dir.mkdir(parents=True, exist_ok=True)
        
        images = await parser3.aget_images([pdf_path], download_path=str(image_dir))
        print(f"Configuration 3 result: {len(images) if images else 0} images")
        
        saved_files = list(image_dir.glob("*.*"))
        print(f"Files in directory: {len(saved_files)}")
        
    except Exception as e:
        print(f"Configuration 3 failed: {e}")
    
    # Configuration 4: Try parsing with charts/tables (which might include images)
    print("\n4. Testing chart and table extraction...")
    try:
        parser4 = LlamaParse(
            api_key=os.getenv('LLAMA_PARSE_API_KEY'),
            result_type="markdown",
            disable_image_extraction=False,
            extract_charts=True,
            verbose=True
        )
        
        # Try charts
        chart_dir = Path("./outputs/images/2_charts")
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        charts = await parser4.aget_charts([pdf_path], download_path=str(chart_dir))
        print(f"Charts found: {len(charts) if charts else 0}")
        
        # Check chart files
        chart_files = list(chart_dir.glob("*.*"))
        print(f"Chart files saved: {len(chart_files)}")
        
    except Exception as e:
        print(f"Configuration 4 failed: {e}")


async def main():
    """Main debug function."""
    print("PDF IMAGE EXTRACTION DEBUG")
    print("=" * 60)
    
    pdf_path = "./data/2.pdf"
    
    if not Path(pdf_path).exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return
    
    # Basic file info
    file_size = Path(pdf_path).stat().st_size
    print(f"PDF file: {pdf_path}")
    print(f"File size: {file_size:,} bytes")
    print()
    
    # Analyze with different libraries
    analyze_pdf_with_pypdf2(pdf_path)
    print()
    analyze_pdf_with_pymupdf(pdf_path)
    print()
    
    # Test LlamaParse configurations
    await test_llamaparse_configurations()


if __name__ == "__main__":
    asyncio.run(main())