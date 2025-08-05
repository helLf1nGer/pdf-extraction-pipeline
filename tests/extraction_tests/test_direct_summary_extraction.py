#!/usr/bin/env python3
"""
Directly test if we can extract the missing summary items.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractors.gemini_extractor import GeminiExtractor


async def test_direct_extraction():
    """Test extraction with modified prompts that prioritize summary content."""
    
    print("="*60)
    print("TESTING DIRECT SUMMARY EXTRACTION")
    print("="*60)
    
    # Read the parsed content
    with open("outputs/2_markdown_check.md", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract just the summary section for focused testing
    summary_start = content.find("Key Points:")
    summary_end = content.find("Issues Identified:")
    
    if summary_start > 0 and summary_end > summary_start:
        summary_section = content[summary_start:summary_end]
        print("\nSUMMARY SECTION:")
        print("-"*40)
        print(summary_section[:500] + "...")
        print("-"*40)
    
    # Create a focused prompt that explicitly asks for summary items
    test_prompt = f"""Extract ALL issues and recommendations from this home inspection report.

IMPORTANT: Include EVERY recommendation, especially:
1. All recommendations should be addressed by qualified specialists
2. Homeowners should obtain required permits before starting renovations  
3. Wood-burning appliances should be inspected by a WETT-certified technician before use
4. Annual maintenance programs for HVAC systems
5. Any other recommendations in the summary or overview sections

For items from the summary that don't have detailed descriptions, create appropriate entries with:
- issue_type: "General" or "Safety" as appropriate
- severity: "medium"
- Clear descriptions even if brief

<markdown_content>
{content}
</markdown_content>

Return a JSON with all issues found, including those from the summary section."""
    
    # Initialize extractor
    api_key = os.getenv('GOOGLE_API_KEY')
    extractor = GeminiExtractor(api_key=api_key, model_name="gemini-2.5-pro")
    
    print("\nExtracting with focused prompt...")
    
    # Use the extractor's method with our custom content
    result = await extractor.extract_async(
        markdown_content=test_prompt,
        image_references=[],
        source_filename="2.pdf"
    )
    
    if result.success and result.report:
        print(f"\nExtraction successful!")
        print(f"Total issues found: {len(result.report.issues)}")
        
        # Check for summary items
        print("\nCHECKING FOR SUMMARY ITEMS:")
        print("-"*40)
        
        found_wett = False
        found_specialist = False
        found_permit = False
        
        for i, issue in enumerate(result.report.issues, 1):
            print(f"{i}. {issue.issue_name} ({issue.issue_type})")
            
            name_lower = issue.issue_name.lower()
            desc_lower = (issue.issue_description or "").lower()
            
            if "wett" in name_lower or "wett" in desc_lower:
                found_wett = True
                print("   >>> WETT inspection found!")
            if "specialist" in name_lower or "specialist" in desc_lower:
                found_specialist = True
                print("   >>> Specialist evaluation found!")
            if "permit" in name_lower or "permit" in desc_lower:
                found_permit = True
                print("   >>> Permit requirement found!")
        
        print("\nRESULTS:")
        print(f"WETT inspection: {'FOUND' if found_wett else 'MISSING'}")
        print(f"Specialist evaluation: {'FOUND' if found_specialist else 'MISSING'}")
        print(f"Permit requirement: {'FOUND' if found_permit else 'MISSING'}")
        
        print(f"\nExtraction rate: {len(result.report.issues)}/13 = {len(result.report.issues)/13*100:.1f}%")
        
        # Save results
        with open("outputs/2_direct_summary_test.json", 'w') as f:
            json.dump(result.report.dict(), f, indent=2, ensure_ascii=False)
            
    else:
        print(f"\nExtraction failed: {result.error_message}")


if __name__ == "__main__":
    asyncio.run(test_direct_extraction())