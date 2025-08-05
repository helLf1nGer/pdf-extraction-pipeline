"""
JSON output cleaner for integrating enhanced images into issue_images.

This module takes the extraction results with enhanced_images and integrates
the highest confidence images into the issue_images array for cleaner output.
"""

import json
import logging
from typing import Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class JSONCleaner:
    """Clean and integrate enhanced images into final JSON output."""
    
    def __init__(self, confidence_threshold: float = 50.0, max_images_per_issue: int = 3):
        """
        Initialize the JSON cleaner.
        
        Args:
            confidence_threshold: Minimum confidence score to include an image
            max_images_per_issue: Maximum number of images to include per issue
        """
        self.confidence_threshold = confidence_threshold
        self.max_images_per_issue = max_images_per_issue
    
    def clean_extraction_output(self, extraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean the extraction output by integrating enhanced images.
        
        Args:
            extraction_data: Raw extraction data with enhanced_images
            
        Returns:
            Cleaned extraction data with integrated images
        """
        cleaned_data = extraction_data.copy()
        
        if 'issues' not in cleaned_data:
            return cleaned_data
        
        cleaned_issues = []
        stats = {
            'total_issues': len(cleaned_data['issues']),
            'issues_with_images': 0,
            'total_images_integrated': 0,
            'high_confidence_images': 0
        }
        
        for issue in cleaned_data['issues']:
            cleaned_issue = self._clean_single_issue(issue, stats)
            cleaned_issues.append(cleaned_issue)
        
        cleaned_data['issues'] = cleaned_issues
        
        # Add statistics as metadata
        if 'metadata' not in cleaned_data:
            cleaned_data['metadata'] = {}
        cleaned_data['metadata']['image_integration_stats'] = stats
        
        logger.info(f"JSON cleaning complete: {stats['issues_with_images']}/{stats['total_issues']} issues have images, "
                   f"{stats['total_images_integrated']} total images integrated")
        
        return cleaned_data
    
    def _clean_single_issue(self, issue: Dict[str, Any], stats: Dict[str, int]) -> Dict[str, Any]:
        """
        Clean a single issue by integrating enhanced images.
        
        Args:
            issue: Single issue data
            stats: Statistics dictionary to update
            
        Returns:
            Cleaned issue with integrated images
        """
        cleaned_issue = issue.copy()
        
        # Get enhanced images if available
        enhanced_images = issue.get('enhanced_images', [])
        
        if enhanced_images:
            # Sort by confidence score (highest first)
            sorted_images = sorted(
                enhanced_images, 
                key=lambda x: x.get('confidence_score', 0), 
                reverse=True
            )
            
            # Select best images above threshold
            selected_images = []
            for img in sorted_images:
                if img.get('confidence_score', 0) >= self.confidence_threshold:
                    # Convert to simple image path for issue_images array
                    image_path = img.get('image_path', '')
                    if image_path and image_path not in selected_images:
                        selected_images.append(image_path)
                        
                        # Update statistics
                        stats['total_images_integrated'] += 1
                        if img.get('confidence_score', 0) >= 70.0:
                            stats['high_confidence_images'] += 1
                        
                        # Stop if we've reached max images per issue
                        if len(selected_images) >= self.max_images_per_issue:
                            break
            
            # Update issue_images with selected images
            cleaned_issue['issue_images'] = selected_images
            
            if selected_images:
                stats['issues_with_images'] += 1
            
            # Keep enhanced_images for detailed info but mark which were selected
            for img in enhanced_images:
                img['selected'] = img.get('image_path', '') in selected_images
            
            # Optionally remove enhanced_images from final output for cleaner JSON
            # Uncomment the line below to remove enhanced_images completely:
            # del cleaned_issue['enhanced_images']
            
            # Remove expected_image_locations from final output (internal use only)
            if 'expected_image_locations' in cleaned_issue:
                del cleaned_issue['expected_image_locations']
        
        return cleaned_issue
    
    def clean_and_save(self, input_path: str, output_path: str = None) -> str:
        """
        Clean a JSON file and save the result.
        
        Args:
            input_path: Path to input JSON file
            output_path: Path to save cleaned JSON (if None, overwrites input)
            
        Returns:
            Path to the saved file
        """
        input_file = Path(input_path)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Load the JSON data
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Clean the data
        cleaned_data = self.clean_extraction_output(data)
        
        # Determine output path
        if output_path is None:
            output_file = input_file
        else:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save cleaned data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Cleaned JSON saved to: {output_file}")
        return str(output_file)


def clean_extraction_json(
    input_path: str, 
    output_path: str = None,
    confidence_threshold: float = 50.0,
    max_images_per_issue: int = 3
) -> str:
    """
    Convenience function to clean extraction JSON output.
    
    Args:
        input_path: Path to input JSON file
        output_path: Path to save cleaned JSON (if None, overwrites input)
        confidence_threshold: Minimum confidence score for images
        max_images_per_issue: Maximum images per issue
        
    Returns:
        Path to the saved file
    """
    cleaner = JSONCleaner(
        confidence_threshold=confidence_threshold,
        max_images_per_issue=max_images_per_issue
    )
    return cleaner.clean_and_save(input_path, output_path)