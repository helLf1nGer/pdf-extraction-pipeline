#!/usr/bin/env python3
"""Advanced test for LlamaParse to understand why it's not extracting full content."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from llama_parse import LlamaParse

load_dotenv()

async def test_llamaparse_configurations():
    """Test different LlamaParse configurations."""
    
    pdf_path = "data/1.pdf"
    api_key = os.getenv('LLAMA_PARSE_API_KEY')
    
    if not api_key:
        print("ERROR: LLAMA_PARSE_API_KEY not found")
        return
    
    print(f"Testing LlamaParse with: {pdf_path}")
    print("=" * 60)
    
    # Test 1: Default configuration
    print("\nTEST 1: Default LlamaParse configuration")
    print("-" * 40)
    
    try:
        parser1 = LlamaParse(api_key=api_key)
        documents1 = await parser1.aload_data([pdf_path])
        
        if documents1:
            content1 = documents1[0].text
            print(f"Content length: {len(content1)} characters")
            print(f"Number of pages detected: {len(documents1)}")
            
            # Save full content
            with open("debug_output/llamaparse_default.txt", "w", encoding='utf-8') as f:
                f.write(content1)
            print("Saved to: debug_output/llamaparse_default.txt")
            
            # Check for key content
            if "knob and tube" in content1.lower():
                print("[OK] Found 'knob and tube' in content")
            else:
                print("[WARNING] 'knob and tube' NOT found in content")
                
            if "$8,000" in content1 or "8000" in content1:
                print("[OK] Found cost estimate in content")
            else:
                print("[WARNING] Cost estimate NOT found in content")
    except Exception as e:
        print(f"ERROR in test 1: {e}")
    
    # Test 2: With explicit markdown and parsing instructions
    print("\n\nTEST 2: LlamaParse with explicit settings")
    print("-" * 40)
    
    try:
        parser2 = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            parsing_instruction="Extract ALL content from the PDF including tables, forms, and all pages. Do not skip any content.",
            skip_diagonal_text=False,
            page_separator="\n\n--- PAGE BREAK ---\n\n"
        )
        
        documents2 = await parser2.aload_data([pdf_path])
        
        if documents2:
            content2 = documents2[0].text
            print(f"Content length: {len(content2)} characters")
            
            # Count page breaks
            page_count = content2.count("PAGE BREAK") + 1
            print(f"Detected pages: {page_count}")
            
            # Save full content
            with open("debug_output/llamaparse_explicit.txt", "w", encoding='utf-8') as f:
                f.write(content2)
            print("Saved to: debug_output/llamaparse_explicit.txt")
            
            # Look for content from different pages
            if "PRE-LIST SUMMARY" in content2:
                print("[OK] Found 'PRE-LIST SUMMARY' section")
            else:
                print("[WARNING] 'PRE-LIST SUMMARY' NOT found")
                
            if "REQUIRED REPAIRS" in content2:
                print("[OK] Found 'REQUIRED REPAIRS' section")
            else:
                print("[WARNING] 'REQUIRED REPAIRS' NOT found")
                
            # Extract a sample around key terms
            if "knob" in content2.lower():
                idx = content2.lower().find("knob")
                sample = content2[max(0, idx-100):min(len(content2), idx+200)]
                print(f"\nSample around 'knob':\n{sample}")
                
    except Exception as e:
        print(f"ERROR in test 2: {e}")
    
    # Test 3: Check metadata
    print("\n\nTEST 3: Checking document metadata")
    print("-" * 40)
    
    try:
        parser3 = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            verbose=True
        )
        
        documents3 = await parser3.aload_data([pdf_path])
        
        if documents3:
            doc = documents3[0]
            print(f"Document type: {type(doc)}")
            
            if hasattr(doc, 'metadata'):
                print(f"Metadata: {doc.metadata}")
            
            if hasattr(doc, 'pages'):
                print(f"Pages attribute: {doc.pages}")
                
            # Try different access methods
            if hasattr(doc, 'get_content'):
                print("Has get_content method")
                
            # Check all attributes
            print("\nDocument attributes:")
            for attr in dir(doc):
                if not attr.startswith('_'):
                    print(f"  - {attr}")
                    
    except Exception as e:
        print(f"ERROR in test 3: {e}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    

async def main():
    """Run the tests."""
    # Create debug directory
    Path("debug_output").mkdir(exist_ok=True)
    
    await test_llamaparse_configurations()


if __name__ == "__main__":
    asyncio.run(main())