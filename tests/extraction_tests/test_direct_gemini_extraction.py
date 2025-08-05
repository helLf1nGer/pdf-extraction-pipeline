#!/usr/bin/env python3
"""
Test direct Gemini extraction without validation to see if we can get all issues.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractors.gemini_extractor import GeminiExtractor
from extractors.pdf_parser import LlamaParseIntegration


async def test_direct():
    """Test direct extraction without validation."""
    
    print("="*60)
    print("TESTING DIRECT GEMINI EXTRACTION")
    print("="*60)
    
    # Parse PDF first
    api_key = os.getenv('LLAMA_PARSE_API_KEY')
    parser = LlamaParseIntegration(api_key=api_key)
    
    print("Parsing PDF...")
    result = await parser.parse_pdf_async("data/2.pdf")
    
    if not result['success']:
        print(f"Parse failed: {result.get('error_message')}")
        return
        
    markdown_content = result['markdown_content']
    images = result.get('images', [])
    
    print(f"Parsed successfully: {len(markdown_content)} chars, {len(images)} images")
    
    # Direct extraction with Gemini
    gemini_key = os.getenv('GOOGLE_API_KEY')
    extractor = GeminiExtractor(api_key=gemini_key, model_name="gemini-2.5-pro")
    
    print("\nExtracting with Gemini Pro directly...")
    
    extraction_result = await extractor.extract_async(
        markdown_content=markdown_content,
        image_references=images,
        source_filename="2.pdf"
    )
    
    if extraction_result.success and extraction_result.report:
        print(f"\nExtraction successful!")
        print(f"Issues found: {len(extraction_result.report.issues)}")
        
        # Check for all expected issues
        print("\nISSUES EXTRACTED:")
        print("-"*40)
        for i, issue in enumerate(extraction_result.report.issues, 1):
            print(f"{i}. {issue.issue_name} ({issue.issue_type})")
        
        # Save results
        with open("outputs/2_direct_gemini_test.json", 'w') as f:
            json.dump(extraction_result.report.dict(), f, indent=2, ensure_ascii=False)
            
        print(f"\nExtraction rate: {len(extraction_result.report.issues)}/13 = {len(extraction_result.report.issues)/13*100:.1f}%")
        
        # Check what we might be missing
        issue_names = [issue.issue_name.lower() for issue in extraction_result.report.issues]
        
        print("\nCHECKING FOR KEY ISSUES:")
        checks = {
            "Electrical breaker": any("breaker" in name or "electrical" in name for name in issue_names),
            "Gas fireplace": any("fireplace" in name or "gas" in name for name in issue_names),
            "Floor joist": any("joist" in name or "notch" in name for name in issue_names),
            "Plumbing trap": any("plumbing" in name or "trap" in name for name in issue_names),
            "Roof shingles": any("shingle" in name or "roof" in name for name in issue_names),
            "Window well": any("window" in name and "well" in name for name in issue_names),
            "Water stains": any("water" in name and "stain" in name for name in issue_names),
            "Insulation": any("insulation" in name for name in issue_names),
            "HVAC maintenance": any("hvac" in name or "maintenance" in name for name in issue_names),
            "WETT inspection": any("wett" in name for name in issue_names),
            "Specialist evaluation": any("specialist" in name for name in issue_names),
            "Permits": any("permit" in name for name in issue_names)
        }
        
        for check, found in checks.items():
            print(f"  {check}: {'FOUND' if found else 'MISSING'}")
            
    else:
        print(f"\nExtraction failed: {extraction_result.error_message}")


if __name__ == "__main__":
    asyncio.run(test_direct())