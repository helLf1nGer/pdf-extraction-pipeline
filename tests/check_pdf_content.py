#!/usr/bin/env python3
"""
Check PDF content to see if missing issues are in the source.
"""

import asyncio
import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractors.pdf_parser import LlamaParseIntegration


async def check_pdf_content():
    """Parse PDF and search for missing issues."""
    
    # Initialize parser
    api_key = os.getenv('LLAMA_PARSE_API_KEY')
    parser = LlamaParseIntegration(api_key=api_key)
    
    print("Parsing PDF 2...")
    result = await parser.parse_pdf_async("data/2.pdf")
    
    if result['success']:
        content = result['markdown_content']
        print(f"Parsed {len(content)} characters")
        
        # Search for missing issues
        keywords = [
            "WETT",
            "wood burning",
            "wood-burning", 
            "specialist",
            "evaluation required",
            "obtain permit",
            "permits",
            "overview",
            "OVERVIEW",
            "Summary of",
            "SUMMARY"
        ]
        
        print("\nSearching for missing issues...")
        for keyword in keywords:
            if keyword.lower() in content.lower():
                print(f"\nFOUND '{keyword}':")
                # Find context around keyword
                idx = content.lower().find(keyword.lower())
                start = max(0, idx - 200)
                end = min(len(content), idx + 200)
                context = content[start:end]
                print(f"...{context}...")
        
        # Save markdown for inspection
        with open("outputs/2_markdown_check.md", "w", encoding="utf-8") as f:
            f.write(content)
        print("\n\nFull markdown saved to outputs/2_markdown_check.md")
    else:
        print(f"Parse failed: {result.get('error_message')}")


if __name__ == "__main__":
    asyncio.run(check_pdf_content())