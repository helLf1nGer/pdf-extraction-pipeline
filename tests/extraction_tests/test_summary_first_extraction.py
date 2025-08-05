#!/usr/bin/env python3
"""
Test the summary-first extraction approach.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractors.gemini_extractor import GeminiExtractor
from extractors.summary_first_prompts import get_summary_first_prompt


async def test_summary_first():
    """Test the summary-first extraction approach."""
    
    print("="*60)
    print("TESTING SUMMARY-FIRST EXTRACTION APPROACH")
    print("="*60)
    
    # Read the markdown content
    markdown_path = Path("outputs/2_markdown.md")
    if not markdown_path.exists():
        # Try the check file
        markdown_path = Path("outputs/2_markdown_check.md")
        if not markdown_path.exists():
            print("ERROR: No markdown file found. Run extraction first.")
            return
    
    with open(markdown_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Get image references
    images_dir = Path("outputs/images/2")
    image_refs = []
    if images_dir.exists():
        image_refs = [f"outputs/images/2/{img.name}" for img in images_dir.glob("*.png")]
    
    print(f"Markdown content: {len(markdown_content)} characters")
    print(f"Available images: {len(image_refs)}")
    
    # Initialize Gemini extractor
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found")
        return
    
    extractor = GeminiExtractor(api_key=api_key, model_name="gemini-2.5-pro")
    
    # Create prompt with summary-first approach
    prompt = get_summary_first_prompt(markdown_content, image_refs)
    
    print("\nExtracting with summary-first approach...")
    
    try:
        # Extract using the new prompt
        # Note: We need to modify the extractor to use our custom prompt
        # For now, let's test with the standard extraction method
        result = await extractor.extract_async(
            markdown_content=prompt,  # Pass our prompt as the content
            image_references=image_refs,
            source_filename="2.pdf"
        )
        
        if result.success and result.report:
            print(f"\nExtraction successful!")
            print(f"Issues found: {len(result.report.issues)}")
            
            # Save the results
            output_path = Path("outputs/2_summary_first_test.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.report.dict(), f, indent=2, ensure_ascii=False)
            
            print(f"\nResults saved to: {output_path}")
            
            # Display the issues
            print("\nEXTRACTED ISSUES:")
            print("-"*40)
            for i, issue in enumerate(result.report.issues, 1):
                print(f"{i}. {issue.issue_name} ({issue.issue_type})")
                if "specialist" in issue.issue_name.lower():
                    print("   [CHECK] Found specialist evaluation!")
                if "permit" in issue.issue_name.lower():
                    print("   [CHECK] Found permit requirement!")
                if "wett" in issue.issue_name.lower():
                    print("   [CHECK] Found WETT inspection!")
            
            # Check if we found the missing issues
            issue_names = [issue.issue_name.lower() for issue in result.report.issues]
            print("\n\nMISSING ISSUES CHECK:")
            print("-"*40)
            
            missing = []
            if not any("wett" in name for name in issue_names):
                missing.append("WETT inspection")
            if not any("specialist" in name for name in issue_names):
                missing.append("Specialist evaluation")  
            if not any("permit" in name for name in issue_names):
                missing.append("Permit requirement")
            
            if missing:
                print(f"Still missing: {', '.join(missing)}")
            else:
                print("ALL KEY ISSUES FOUND!")
            
            print(f"\nExtraction rate: {len(result.report.issues)}/13 = {len(result.report.issues)/13*100:.1f}%")
            
        else:
            print(f"\nExtraction failed: {result.error_message}")
            
    except Exception as e:
        print(f"\nError: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_summary_first())