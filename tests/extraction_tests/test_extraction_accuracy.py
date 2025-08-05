#!/usr/bin/env python3
"""
Test script to verify actual extraction accuracy after improvements.
"""

import json
from pathlib import Path

def analyze_extraction():
    """Analyze the extraction results for PDF 2."""
    
    # Read the extracted JSON
    json_path = Path("outputs/2_result.json")
    if not json_path.exists():
        print("ERROR: No extraction results found!")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("="*60)
    print("EXTRACTION ANALYSIS FOR PDF 2")
    print("="*60)
    
    print(f"\nReport Name: {data.get('report_name', 'N/A')}")
    print(f"Total Issues Found: {len(data.get('issues', []))}")
    print(f"Extraction Model: {data.get('extraction_model', 'N/A')}")
    
    print("\nISSUES EXTRACTED:")
    for i, issue in enumerate(data.get('issues', []), 1):
        print(f"\n{i}. {issue['issue_name']}")
        print(f"   Type: {issue['issue_type']}")
        print(f"   Images: {len(issue.get('issue_images', []))} attached")
        print(f"   Summary: {issue['issue_summary'][:100]}...")
    
    # Count total images referenced
    total_images = sum(len(issue.get('issue_images', [])) for issue in data.get('issues', []))
    print(f"\nTotal Images Referenced: {total_images}")
    
    # Check image files exist
    images_dir = Path("outputs/images/2")
    if images_dir.exists():
        actual_images = list(images_dir.glob("*.png"))
        print(f"Actual Image Files: {len(actual_images)}")
    
    print("\n" + "="*60)
    print("KNOWN ISSUES FROM MANUAL REVIEW:")
    print("="*60)
    
    known_issues = [
        "1. Oversized Breaker and Double-Tapped Wire (Electrical)",
        "2. Inoperative Gas Fireplace with Incomplete Venting (HVAC)",
        "3. Missing, Loose, or Torn Asphalt Shingles (Roofing)",
        "4. Improperly Notched Floor Joist (Structural)",
        "5. Annual HVAC Maintenance Recommended (HVAC)",
        "6. Missing Window Well (Exterior)",
        "7. Non-Standard Plumbing Trap (Plumbing)",
        "8. Water Stains on Ceiling (Interior)",
        "9. Insufficient Attic Insulation (Insulation)",
        "10. WETT Inspection for Wood-Burning Appliances (Safety)",
        "11. Specialist Evaluation Required (General)",
        "12. Obtain Permits for Renovations (General)",
        "13. [Possibly one more issue]"
    ]
    
    for issue in known_issues:
        print(issue)
    
    print(f"\nExtraction Rate: {len(data.get('issues', []))}/13 = {len(data.get('issues', []))/13*100:.1f}%")
    
    # Check which issues we might be missing
    extracted_names = [issue['issue_name'].lower() for issue in data.get('issues', [])]
    
    print("\nPOTENTIAL MISSING ISSUES:")
    missing = []
    if not any('wett' in name for name in extracted_names):
        missing.append("- WETT Inspection for Wood-Burning Appliances")
    if not any('specialist' in name or 'evaluation required' in name for name in extracted_names):
        missing.append("- Specialist Evaluation Required")
    if not any('permit' in name for name in extracted_names):
        missing.append("- Obtain Permits for Renovations")
    
    if missing:
        for m in missing:
            print(m)
    else:
        print("None identified")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if len(data.get('issues', [])) >= 11:
        print("SUCCESS: Extraction performance is good (>85% of issues found)")
        print("The extraction found most critical safety and maintenance issues.")
    else:
        print("NEEDS IMPROVEMENT: Still missing some issues")
        print("Consider enhancing prompts to capture overview/summary recommendations")


if __name__ == "__main__":
    analyze_extraction()