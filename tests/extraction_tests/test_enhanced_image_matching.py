#!/usr/bin/env python3
"""
Test script for enhanced image matching functionality.

This script tests the new model-guided image matching system by running
extraction on a sample PDF and comparing results with the legacy approach.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extractors.pipeline import create_validation_pipeline
from src.extractors.image_matcher import ImageMatcher
from src.extractors.schemas import ImageLocation, InspectionIssue

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_enhanced_image_matching():
    """Test the enhanced image matching system."""
    print("Testing Enhanced Image Matching System")
    print("=" * 50)
    
    # Test PDF path
    test_pdf = Path("data/2.pdf")
    if not test_pdf.exists():
        # Try alternative paths
        alt_paths = [
            Path("./data/2.pdf"),
            Path("../data/2.pdf"),
            Path("data/1.pdf"),
            Path("./data/1.pdf")
        ]
        for alt_path in alt_paths:
            if alt_path.exists():
                test_pdf = alt_path
                break
    if not test_pdf.exists():
        print(f"Test PDF not found: {test_pdf}")
        return
    
    # Create pipeline with enhanced image matching
    pipeline = create_validation_pipeline(
        mock_mode=False,  # Use real extraction to test image matching
        enable_claude_fallback=False,  # Keep it simple for testing
        confidence_threshold=70.0
    )
    
    try:
        # Validate setup
        print("1. Validating pipeline setup...")
        validation = await pipeline.validate_setup()
        if not validation['overall_status']:
            print(f"Pipeline validation failed: {validation['errors']}")
            return
        print("   Pipeline setup valid!")
        
        # Extract with enhanced image matching
        print(f"2. Extracting from {test_pdf.name} with enhanced image matching...")
        result = await pipeline.extract_from_pdf(
            str(test_pdf),
            output_dir="outputs/enhanced_test_results",
            save_intermediate=True
        )
        
        if not result.success:
            print(f"   Extraction failed: {result.error_message}")
            return
        
        print(f"   Extraction successful! Found {len(result.report.issues)} issues")
        
        # Analyze enhanced image associations
        print("3. Analyzing enhanced image associations...")
        
        total_enhanced_images = 0
        high_confidence_images = 0
        location_based_matches = 0
        legacy_matches = 0
        
        for i, issue in enumerate(result.report.issues):
            print(f"\n   Issue {i+1}: {issue.issue_name}")
            print(f"     Type: {issue.issue_type}")
            print(f"     Legacy images: {len(issue.issue_images)}")
            print(f"     Expected locations: {len(issue.expected_image_locations)}")
            print(f"     Enhanced images: {len(issue.enhanced_images)}")
            
            # Show expected locations
            for j, loc in enumerate(issue.expected_image_locations):
                print(f"       Expected Location {j+1}:")
                print(f"         Page: {loc.page_number}")
                print(f"         Description: {loc.location_description}")
                print(f"         Context: {loc.section_context}")
            
            # Show enhanced image matches
            for j, img_meta in enumerate(issue.enhanced_images):
                total_enhanced_images += 1
                print(f"       Enhanced Image {j+1}:")
                print(f"         Path: {img_meta.image_path}")
                print(f"         Confidence: {img_meta.confidence_score}")
                print(f"         Method: {img_meta.matching_method}")
                print(f"         Page Match: {img_meta.location_match}")
                
                if img_meta.confidence_score and img_meta.confidence_score >= 70:
                    high_confidence_images += 1
                
                if img_meta.matching_method == 'location_based':
                    location_based_matches += 1
                elif img_meta.matching_method == 'legacy_proximity':
                    legacy_matches += 1
        
        # Generate statistics
        print("\n4. Enhanced Image Matching Statistics:")
        print(f"   Total issues: {len(result.report.issues)}")
        print(f"   Issues with expected locations: {sum(1 for issue in result.report.issues if issue.expected_image_locations)}")
        print(f"   Total enhanced image matches: {total_enhanced_images}")
        print(f"   High confidence matches (≥70%): {high_confidence_images}")
        print(f"   Location-based matches: {location_based_matches}")
        print(f"   Legacy proximity matches: {legacy_matches}")
        
        if total_enhanced_images > 0:
            print(f"   High confidence rate: {high_confidence_images/total_enhanced_images:.1%}")
            print(f"   Location-based matching rate: {location_based_matches/total_enhanced_images:.1%}")
        
        # Get detailed statistics from image matcher
        if result.report.issues:
            matcher = ImageMatcher()
            detailed_stats = matcher.get_matching_statistics(result.report.issues)
            print(f"   Average confidence score: {detailed_stats['average_confidence']:.1f}")
            print(f"   Matching methods breakdown: {detailed_stats['matching_methods']}")
        
        # Save enhanced results
        output_file = Path("outputs/enhanced_test_results/enhanced_results.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create serializable data
        enhanced_data = {
            "report_name": result.report.report_name,
            "extraction_model": result.report.extraction_model,
            "processing_time": result.processing_time,
            "total_issues": len(result.report.issues),
            "enhanced_matching_stats": {
                "total_enhanced_images": total_enhanced_images,
                "high_confidence_images": high_confidence_images,
                "location_based_matches": location_based_matches,
                "legacy_matches": legacy_matches
            },
            "issues": []
        }
        
        for issue in result.report.issues:
            issue_data = {
                "issue_name": issue.issue_name,
                "issue_type": issue.issue_type,
                "issue_description": issue.issue_description,
                "issue_summary": issue.issue_summary,
                "severity": issue.severity,
                "location": issue.location,
                "legacy_images": issue.issue_images,
                "expected_image_locations": [
                    {
                        "page_number": loc.page_number,
                        "location_description": loc.location_description,
                        "section_context": loc.section_context
                    }
                    for loc in issue.expected_image_locations
                ],
                "enhanced_images": [
                    {
                        "image_path": img.image_path,
                        "confidence_score": img.confidence_score,
                        "matching_method": img.matching_method,
                        "actual_page": img.actual_page,
                        "location_match": img.location_match,
                        "expected_location": {
                            "page_number": img.expected_location.page_number,
                            "location_description": img.expected_location.location_description,
                            "section_context": img.expected_location.section_context
                        } if img.expected_location else None
                    }
                    for img in issue.enhanced_images
                ]
            }
            enhanced_data["issues"].append(issue_data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n5. Enhanced results saved to: {output_file}")
        print("\nEnhanced image matching test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        print(f"Test failed: {str(e)}")
    
    finally:
        await pipeline.cleanup()


async def test_image_matcher_directly():
    """Test the ImageMatcher class directly with mock data."""
    print("\nTesting ImageMatcher Class Directly")
    print("=" * 40)
    
    # Create test data
    test_locations = [
        ImageLocation(
            page_number=9,
            location_description="center section",
            section_context="electrical panel area"
        ),
        ImageLocation(
            page_number=11,
            location_description="top area",
            section_context="gas fireplace installation"
        )
    ]
    
    test_issue = InspectionIssue(
        issue_name="Test Electrical and HVAC Issues",
        issue_type="Mixed",
        issue_description="Test description with multiple expected images",
        issue_summary="Test summary",
        expected_image_locations=test_locations
    )
    
    # Use actual extracted images from our test data
    test_images = [
        "outputs/images/2/page_09_image_001.png",
        "outputs/images/2/page_09_image_002.png",
        "outputs/images/2/page_11_image_001.png",
        "outputs/images/2/page_11_image_002.png",
        "outputs/images/2/page_10_image_001.png"  # Should get lower confidence
    ]
    
    # Test the matcher
    matcher = ImageMatcher()
    enhanced_issues = matcher.enhance_image_associations([test_issue], test_images)
    
    print(f"Enhanced {len(enhanced_issues)} issues")
    for issue in enhanced_issues:
        print(f"  Issue: {issue.issue_name}")
        print(f"  Expected locations: {len(issue.expected_image_locations)}")
        print(f"  Enhanced images: {len(issue.enhanced_images)}")
        
        for img in issue.enhanced_images:
            print(f"    - {Path(img.image_path).name}")
            print(f"      Confidence: {img.confidence_score:.1f}")
            print(f"      Method: {img.matching_method}")
            print(f"      Page match: {img.location_match}")
    
    # Get statistics
    stats = matcher.get_matching_statistics(enhanced_issues)
    print(f"  Statistics: {stats}")


if __name__ == "__main__":
    # Set environment variable for testing
    os.environ['PYTHONPATH'] = str(Path(__file__).parent / "src")
    
    print("Enhanced Image Matching Test Suite")
    print("=" * 60)
    
    # Test ImageMatcher directly first
    asyncio.run(test_image_matcher_directly())
    
    # Test full pipeline
    asyncio.run(test_enhanced_image_matching())