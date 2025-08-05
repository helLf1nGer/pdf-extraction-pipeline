#!/usr/bin/env python3
"""
Test the summary-first extraction approach.
"""

import re
from pathlib import Path


def analyze_markdown_structure():
    """Analyze the structure of the parsed markdown to understand summary location."""
    
    markdown_path = Path("outputs/2_markdown_check.md")
    if not markdown_path.exists():
        print("Error: Run check_pdf_content.py first!")
        return
    
    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("="*60)
    print("MARKDOWN STRUCTURE ANALYSIS")
    print("="*60)
    
    # Find summary section
    summary_match = re.search(r'SUMMARY.*?Key Points:(.*?)Issues Identified:', content, re.DOTALL | re.IGNORECASE)
    
    if summary_match:
        summary_text = summary_match.group(1)
        print("\nSUMMARY SECTION FOUND:")
        print("-"*40)
        print(summary_text.strip())
        print("-"*40)
        
        # Extract key recommendations
        print("\nKEY RECOMMENDATIONS FROM SUMMARY:")
        lines = summary_text.strip().split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['recommendation', 'should', 'require', 'must', 'inspection']):
                print(f"  - {line.strip()}")
    
    # Find issues section
    issues_match = re.search(r'Issues Identified:(.*?)(?:---|$)', content, re.DOTALL)
    
    if issues_match:
        print("\n\nISSUES SECTION STRUCTURE:")
        print("-"*40)
        issues_text = issues_match.group(1)
        # Count issue categories
        categories = re.findall(r'\d+\.\s+(\w+):', issues_text)
        print(f"Categories found: {', '.join(set(categories))}")
        print(f"Total issue entries: {len(categories)}")
    
    # Check for overview sections
    overview_matches = re.findall(r'Overview:.*?(?=\n\d+\.|\n---|$)', content, re.DOTALL | re.IGNORECASE)
    print(f"\n\nOVERVIEW SECTIONS FOUND: {len(overview_matches)}")
    for i, overview in enumerate(overview_matches[:3], 1):
        print(f"\nOverview {i}:")
        print(overview[:200] + "..." if len(overview) > 200 else overview)
    
    print("\n\nIMPLEMENTATION APPROACH:")
    print("-"*40)
    print("1. PHASE 1: Extract summary recommendations first")
    print("   - Look for 'Key Points' or 'SUMMARY' section")
    print("   - Extract all numbered recommendations")
    print("   - These often contain the general/administrative items we're missing")
    print("\n2. PHASE 2: Extract detailed issues")
    print("   - Process the main body as usual")
    print("   - Look for condition/implication/task patterns")
    print("\n3. MERGE: Combine and deduplicate")
    print("   - Summary items might not have images or detailed descriptions")
    print("   - Mark them with appropriate categories (General, Safety, etc.)")


if __name__ == "__main__":
    analyze_markdown_structure()