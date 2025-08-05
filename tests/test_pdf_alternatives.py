#!/usr/bin/env python3
"""Test alternative PDF parsing methods to extract full content."""

import os
from pathlib import Path

# Try PyPDF2
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    print("PyPDF2 not available")

# Try pdfplumber
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    print("pdfplumber not available")

# Try pymupdf/fitz
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("PyMuPDF not available")


def test_pypdf2(pdf_path):
    """Test extraction with PyPDF2."""
    print("\nTesting PyPDF2...")
    print("-" * 40)
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            print(f"Number of pages: {num_pages}")
            
            all_text = []
            
            # Extract text from each page
            for i, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                all_text.append(f"\n--- PAGE {i+1} ---\n{text}")
                
                # Check page 3 specifically (where the issues are)
                if i == 2:  # Page 3 (0-indexed)
                    print(f"\nPage 3 content length: {len(text)} chars")
                    if "knob and tube" in text.lower():
                        print("[OK] Found 'knob and tube' on page 3")
                    else:
                        print("[WARNING] 'knob and tube' NOT found on page 3")
                    
                    # Save page 3 for inspection
                    with open("debug_output/pypdf2_page3.txt", "w", encoding='utf-8') as f:
                        f.write(text)
            
            # Combine all text
            full_text = "\n".join(all_text)
            print(f"\nTotal extracted text: {len(full_text)} chars")
            
            # Save full text
            with open("debug_output/pypdf2_full.txt", "w", encoding='utf-8') as f:
                f.write(full_text)
            
            return full_text
            
    except Exception as e:
        print(f"ERROR with PyPDF2: {e}")
        return None


def test_pdfplumber(pdf_path):
    """Test extraction with pdfplumber."""
    print("\nTesting pdfplumber...")
    print("-" * 40)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            num_pages = len(pdf.pages)
            print(f"Number of pages: {num_pages}")
            
            all_text = []
            
            # Extract text from each page
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                all_text.append(f"\n--- PAGE {i+1} ---\n{text}")
                
                # Check page 3 specifically
                if i == 2:  # Page 3 (0-indexed)
                    print(f"\nPage 3 content length: {len(text) if text else 0} chars")
                    
                    # Also try extracting tables
                    tables = page.extract_tables()
                    if tables:
                        print(f"Found {len(tables)} tables on page 3")
                        
                    if text and "knob and tube" in text.lower():
                        print("[OK] Found 'knob and tube' on page 3")
                    else:
                        print("[WARNING] 'knob and tube' NOT found on page 3")
                    
                    # Save page 3
                    if text:
                        with open("debug_output/pdfplumber_page3.txt", "w", encoding='utf-8') as f:
                            f.write(text)
            
            # Combine all text
            full_text = "\n".join(filter(None, all_text))
            print(f"\nTotal extracted text: {len(full_text)} chars")
            
            # Save full text
            with open("debug_output/pdfplumber_full.txt", "w", encoding='utf-8') as f:
                f.write(full_text)
            
            return full_text
            
    except Exception as e:
        print(f"ERROR with pdfplumber: {e}")
        return None


def test_pymupdf(pdf_path):
    """Test extraction with PyMuPDF."""
    print("\nTesting PyMuPDF...")
    print("-" * 40)
    
    try:
        pdf_document = fitz.open(pdf_path)
        num_pages = pdf_document.page_count
        print(f"Number of pages: {num_pages}")
        
        all_text = []
        
        # Extract text from each page
        for i in range(num_pages):
            page = pdf_document[i]
            text = page.get_text()
            all_text.append(f"\n--- PAGE {i+1} ---\n{text}")
            
            # Check page 3 specifically
            if i == 2:  # Page 3 (0-indexed)
                print(f"\nPage 3 content length: {len(text)} chars")
                
                # Check if page contains images
                image_list = page.get_images()
                if image_list:
                    print(f"Page 3 contains {len(image_list)} images")
                
                if "knob and tube" in text.lower():
                    print("[OK] Found 'knob and tube' on page 3")
                else:
                    print("[WARNING] 'knob and tube' NOT found on page 3")
                    
                    # Check if it's an image-based PDF
                    if len(text.strip()) < 100 and image_list:
                        print("This appears to be a scanned/image-based PDF!")
                
                # Save page 3
                with open("debug_output/pymupdf_page3.txt", "w", encoding='utf-8') as f:
                    f.write(text)
        
        # Combine all text
        full_text = "\n".join(all_text)
        print(f"\nTotal extracted text: {len(full_text)} chars")
        
        # Save full text
        with open("debug_output/pymupdf_full.txt", "w", encoding='utf-8') as f:
            f.write(full_text)
        
        pdf_document.close()
        return full_text
        
    except Exception as e:
        print(f"ERROR with PyMuPDF: {e}")
        return None


def main():
    """Test all available PDF parsing methods."""
    pdf_path = "data/1.pdf"
    
    # Create debug directory
    Path("debug_output").mkdir(exist_ok=True)
    
    print(f"Testing PDF extraction methods on: {pdf_path}")
    print("=" * 60)
    
    # Test each available method
    if HAS_PYPDF2:
        test_pypdf2(pdf_path)
    
    if HAS_PDFPLUMBER:
        test_pdfplumber(pdf_path)
    
    if HAS_PYMUPDF:
        test_pymupdf(pdf_path)
    
    if not any([HAS_PYPDF2, HAS_PDFPLUMBER, HAS_PYMUPDF]):
        print("\nNo PDF parsing libraries available!")
        print("Install one of: PyPDF2, pdfplumber, or PyMuPDF")


if __name__ == "__main__":
    main()