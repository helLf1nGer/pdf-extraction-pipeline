#!/usr/bin/env python3
"""
Simple test to demonstrate enhanced image matching functionality.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extractors.schemas import ImageLocation, InspectionIssue
from src.extractors.image_matcher import ImageMatcher
import json

def test_enhanced_matching():
    """Demonstrate enhanced image matching with real data."""
    print("Enhanced Image Matching Demonstration")
    print("=" * 50)
    
    # Create sample issues with expected image locations (as model would provide)
    issue1 = InspectionIssue(
        issue_name="Oversized Breaker and Double-Tapped Wire",
        issue_type="Electrical",
        issue_description="A 40-amp breaker is powering a 10-gauge wire, and is also double-tapped with an 8-gauge stranded wire.",
        issue_summary="An oversized 40-amp breaker is connected to a 10-gauge wire and is also double-tapped, creating a fire hazard.",
        expected_image_locations=[
            ImageLocation(
                page_number=9,
                location_description="center section",
                section_context="electrical panel showing breaker issue"
            )
        ]
    )
    
    issue2 = InspectionIssue(
        issue_name="Inoperative Gas Fireplace with Incomplete Venting",
        issue_type="HVAC",
        issue_description="The exhaust vent installation for the gas fireplace is incomplete.",
        issue_summary="The gas fireplace has an incomplete exhaust vent, which is a life safety issue.",
        expected_image_locations=[
            ImageLocation(
                page_number=11,
                location_description="top area",
                section_context="gas fireplace vent installation"
            ),
            ImageLocation(
                page_number=11,
                location_description="bottom area", 
                section_context="fireplace interior showing incomplete vent"
            )
        ]
    )
    
    # Available extracted images (from our PDF 2 example)
    extracted_images = [
        "outputs/images/2/page_09_image_001.png",
        "outputs/images/2/page_09_image_002.png",
        "outputs/images/2/page_11_image_001.png", 
        "outputs/images/2/page_11_image_002.png",
        "outputs/images/2/page_07_image_001.png",
        "outputs/images/2/page_08_image_001.png"
    ]
    
    print(f"Input: {len([issue1, issue2])} issues with expected image locations")
    print(f"Input: {len(extracted_images)} extracted images")
    print()
    
    # Apply enhanced image matching
    matcher = ImageMatcher() 
    enhanced_issues = matcher.enhance_image_associations([issue1, issue2], extracted_images)
    
    print("Enhanced Image Matching Results:")
    print("-" * 40)
    
    for i, issue in enumerate(enhanced_issues, 1):
        print(f"\n{i}. {issue.issue_name}")
        print(f"   Type: {issue.issue_type}")
        print(f"   Expected locations: {len(issue.expected_image_locations)}")
        
        for j, loc in enumerate(issue.expected_image_locations, 1):
            print(f"     Expected {j}: Page {loc.page_number}, {loc.location_description}")
            print(f"                 Context: {loc.section_context}")
        
        print(f"   Enhanced matches: {len(issue.enhanced_images)}")
        for j, img in enumerate(issue.enhanced_images, 1):
            filename = Path(img.image_path).name
            print(f"     Match {j}: {filename}")
            print(f"               Confidence: {img.confidence_score:.1f}%")
            print(f"               Method: {img.matching_method}")
            print(f"               Page match: {img.location_match}")
    
    # Generate statistics
    stats = matcher.get_matching_statistics(enhanced_issues)
    print(f"\nOverall Statistics:")
    print(f"  Total enhanced matches: {stats['total_enhanced_matches']}")
    print(f"  High confidence (>=85%): {stats['high_confidence_matches']}")
    print(f"  Medium confidence (>=70%): {stats['medium_confidence_matches']}")
    print(f"  Low confidence (<70%): {stats['low_confidence_matches']}")
    print(f"  Average confidence: {stats['average_confidence']:.1f}%")
    print(f"  Location-based matches: {stats['location_based_matches']}")
    print(f"  Legacy matches: {stats['legacy_matches']}")
    
    # Show accuracy improvement over legacy approach
    print(f"\nAccuracy Improvement Analysis:")
    
    exact_page_matches = sum(1 for issue in enhanced_issues 
                           for img in issue.enhanced_images 
                           if img.location_match)
    total_matches = sum(len(issue.enhanced_images) for issue in enhanced_issues)
    
    if total_matches > 0:
        page_accuracy = exact_page_matches / total_matches
        print(f"  Exact page matching accuracy: {page_accuracy:.1%}")
        
        high_conf_rate = stats['high_confidence_matches'] / total_matches
        print(f"  High confidence rate: {high_conf_rate:.1%}")
        
        location_based_rate = stats['location_based_matches'] / total_matches
        print(f"  Location-based matching rate: {location_based_rate:.1%}")
    
    # Export results for further analysis
    results = {
        "enhancement_type": "model_guided_location_based",
        "total_issues": len(enhanced_issues),
        "total_images_available": len(extracted_images),
        "matching_statistics": stats,
        "issues": []
    }
    
    for issue in enhanced_issues:
        issue_result = {
            "issue_name": issue.issue_name,
            "issue_type": issue.issue_type,
            "expected_locations_count": len(issue.expected_image_locations),
            "enhanced_matches_count": len(issue.enhanced_images),
            "expected_locations": [
                {
                    "page_number": loc.page_number,
                    "location_description": loc.location_description,
                    "section_context": loc.section_context
                }
                for loc in issue.expected_image_locations
            ],
            "enhanced_matches": [
                {
                    "image_path": img.image_path,
                    "confidence_score": img.confidence_score,
                    "matching_method": img.matching_method,
                    "page_match": img.location_match,
                    "actual_page": img.actual_page
                }
                for img in issue.enhanced_images
            ]
        }
        results["issues"].append(issue_result)
    
    # Save results
    output_file = Path("outputs/enhanced_matching_demo.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed results saved to: {output_file}")
    print("\n✓ Enhanced image matching demonstration completed successfully!")

if __name__ == "__main__":
    test_enhanced_matching()