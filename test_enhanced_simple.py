#!/usr/bin/env python3
"""
Simple test script for enhanced validation routing.
"""

import os
import sys
import asyncio
import logging
import time
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extractors.enhanced_validation_router import (
    EnhancedValidationRouter, 
    ComplexityLevel,
    create_enhanced_validation_router
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_enhanced_routing():
    """Simple test of enhanced routing system."""
    print("Enhanced Validation Routing Test")
    print("=" * 40)
    
    try:
        # Initialize router
        print("1. Initializing enhanced router...")
        router = await create_enhanced_validation_router()
        
        # Test with sample content
        sample_content = """
        # Home Inspection Report - Test Property
        
        Property Address: 123 Test Street, Test City, TS 12345
        Inspection Date: 2024-01-15
        Inspector: John Smith
        
        ## Electrical System
        - Knob and tube wiring found in basement requiring replacement
        - GFCI outlets missing in bathrooms
        - Main panel has outdated breakers that should be updated
        
        ## Plumbing System
        - Minor leak detected under kitchen sink
        - Low water pressure in master bathroom shower
        """
        
        print("2. Testing extraction...")
        start_time = time.time()
        result = await router.extract_with_enhanced_validation(
            markdown_content=sample_content,
            image_references=["electrical_panel.jpg", "plumbing_leak.jpg"],
            source_filename="test_sample.pdf"
        )
        end_time = time.time()
        
        # Print results
        print(f"3. Results:")
        print(f"   Success: {result['extraction_result'].success}")
        print(f"   Complexity: {result.get('complexity_level')}")
        print(f"   Pipeline: {result.get('pipeline_used')}")
        print(f"   Confidence: {result.get('confidence_score', 0):.1f}%")
        print(f"   Time: {end_time - start_time:.2f}s")
        
        if result['extraction_result'].success and result['extraction_result'].report:
            issues = result['extraction_result'].report.issues
            print(f"   Issues found: {len(issues)}")
            for i, issue in enumerate(issues[:3]):
                print(f"     {i+1}. {issue.issue_name} ({issue.issue_type}) - {issue.severity}")
        
        # Get stats
        stats = router.get_router_stats()
        print(f"4. Router Stats:")
        print(f"   Total processed: {stats['total_processed']}")
        print(f"   Success rate: {stats.get('success_rate', 0):.2%}")
        print(f"   Model usage: {stats['model_usage']}")
        
        await router.cleanup()
        print("\nTest completed successfully!")
        return True
        
    except Exception as e:
        print(f"Test failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_enhanced_routing())
    sys.exit(0 if success else 1)