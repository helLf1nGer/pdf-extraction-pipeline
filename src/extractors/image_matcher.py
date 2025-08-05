"""
Enhanced image matching module for model-guided image association.

This module implements improved image-to-issue association using location-based
matching from model-provided location hints combined with extracted image metadata.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .schemas import ImageLocation, ImageMetadata, InspectionIssue

logger = logging.getLogger(__name__)


class ImageMatcher:
    """
    Enhanced image matcher using model-provided location information.
    
    This matcher improves upon simple proximity-based association by using
    the model's understanding of where images should appear in relation to issues.
    """
    
    def __init__(self):
        """Initialize the image matcher."""
        self.confidence_weights = {
            'exact_page_match': 70.0,  # Increased - exact page match should be high confidence
            'location_context_match': 20.0,
            'section_context_match': 15.0,
            'proximity_fallback': 10.0
        }
    
    def enhance_image_associations(
        self, 
        issues: List[InspectionIssue], 
        extracted_images: List[str]
    ) -> List[InspectionIssue]:
        """
        Enhance image associations for all issues using model-provided location information.
        
        Args:
            issues: List of extracted issues with expected_image_locations
            extracted_images: List of extracted image file paths
            
        Returns:
            List of issues with enhanced image associations
        """
        logger.info(f"Enhancing image associations for {len(issues)} issues with {len(extracted_images)} extracted images")
        
        # Parse extracted image metadata
        image_metadata = self._parse_extracted_image_paths(extracted_images)
        
        enhanced_issues = []
        total_matches = 0
        high_confidence_matches = 0
        
        for issue in issues:
            enhanced_issue = self._enhance_single_issue(issue, image_metadata)
            enhanced_issues.append(enhanced_issue)
            
            # Count matches for statistics
            total_matches += len(enhanced_issue.enhanced_images)
            high_confidence_matches += len(enhanced_issue.get_high_confidence_images(min_confidence=70.0))
        
        logger.info(f"Enhanced image matching completed: {total_matches} total matches, "
                   f"{high_confidence_matches} high-confidence matches")
        
        return enhanced_issues
    
    def _enhance_single_issue(
        self, 
        issue: InspectionIssue, 
        image_metadata: List[Dict]
    ) -> InspectionIssue:
        """
        Enhance image associations for a single issue.
        
        Args:
            issue: The issue to enhance
            image_metadata: Parsed metadata from extracted images
            
        Returns:
            Enhanced issue with better image associations
        """
        enhanced_images = []
        
        # If model provided expected locations, use them for matching
        if issue.expected_image_locations:
            for expected_location in issue.expected_image_locations:
                best_matches = self._find_best_image_matches(expected_location, image_metadata)
                
                for image_path, confidence, match_info in best_matches:
                    image_meta = ImageMetadata(
                        image_path=image_path,
                        expected_location=expected_location,
                        actual_page=match_info.get('actual_page'),
                        confidence_score=confidence,
                        matching_method='location_based',
                        location_match=match_info.get('page_match', False)
                    )
                    enhanced_images.append(image_meta)
        
        # Fallback: if no expected locations or no matches found, use legacy approach
        if not enhanced_images and issue.issue_images:
            for image_path in issue.issue_images:
                # Try to extract page info from filename
                page_info = self._extract_page_from_filename(image_path)
                image_meta = ImageMetadata(
                    image_path=image_path,
                    actual_page=page_info.get('page_number'),
                    confidence_score=50.0,  # Medium confidence for legacy approach
                    matching_method='legacy_proximity'
                )
                enhanced_images.append(image_meta)
        
        # Create enhanced issue (copy all fields and add enhanced images)
        enhanced_issue = InspectionIssue(
            issue_name=issue.issue_name,
            issue_type=issue.issue_type,
            issue_description=issue.issue_description,
            issue_summary=issue.issue_summary,
            severity=issue.severity,
            location=issue.location,
            issue_images=issue.issue_images,  # Keep legacy format
            enhanced_images=enhanced_images,
            expected_image_locations=issue.expected_image_locations
        )
        
        return enhanced_issue
    
    def _find_best_image_matches(
        self, 
        expected_location: ImageLocation, 
        image_metadata: List[Dict]
    ) -> List[Tuple[str, float, Dict]]:
        """
        Find the best matching images for an expected location.
        
        Args:
            expected_location: Model-provided location information
            image_metadata: Available image metadata
            
        Returns:
            List of (image_path, confidence_score, match_info) tuples
        """
        matches = []
        
        for img_meta in image_metadata:
            confidence = 0.0
            match_info = {
                'actual_page': img_meta.get('page_number'),
                'page_match': False,
                'location_hints': []
            }
            
            # 1. Exact page match (highest weight)
            if img_meta.get('page_number') == expected_location.page_number:
                confidence += self.confidence_weights['exact_page_match']
                match_info['page_match'] = True
                match_info['location_hints'].append('exact_page_match')
            
            # 2. Location description matching (if available)
            if expected_location.location_description and img_meta.get('position'):
                location_match = self._match_location_description(
                    expected_location.location_description, 
                    img_meta.get('position', '')
                )
                if location_match:
                    confidence += self.confidence_weights['location_context_match']
                    match_info['location_hints'].append('location_description_match')
            
            # 3. Section context matching
            if expected_location.section_context:
                # This could be enhanced with more sophisticated context matching
                # For now, use basic keyword matching
                context_match = self._match_section_context(
                    expected_location.section_context,
                    img_meta.get('filename', '')
                )
                if context_match:
                    confidence += self.confidence_weights['section_context_match']
                    match_info['location_hints'].append('section_context_match')
            
            # 4. Proximity fallback (for images on nearby pages)
            if not match_info['page_match']:
                page_diff = abs(img_meta.get('page_number', 0) - expected_location.page_number)
                if page_diff <= 2:  # Within 2 pages
                    proximity_bonus = max(0, self.confidence_weights['proximity_fallback'] - (page_diff * 3))
                    confidence += proximity_bonus
                    match_info['location_hints'].append(f'proximity_page_diff_{page_diff}')
            
            # Only include matches with some confidence
            if confidence > 0:
                matches.append((img_meta['path'], confidence, match_info))
        
        # Sort by confidence score (highest first) and return top matches
        matches.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 3 matches to avoid over-association
        return matches[:3]
    
    def _parse_extracted_image_paths(self, image_paths: List[str]) -> List[Dict]:
        """
        Parse extracted image paths to extract metadata like page numbers.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of dictionaries with parsed metadata
        """
        parsed_images = []
        
        for image_path in image_paths:
            filename = Path(image_path).name
            metadata = {
                'path': image_path,
                'filename': filename,
                'page_number': None,
                'image_index': None,
                'position': None  # Could be enhanced with position detection
            }
            
            # Extract page number from filenames like "page_09_image_002.png"
            page_match = re.search(r'page_(\d+)', filename)
            if page_match:
                metadata['page_number'] = int(page_match.group(1))
            
            # Extract image index from filename
            img_match = re.search(r'image_(\d+)', filename)
            if img_match:
                metadata['image_index'] = int(img_match.group(1))
            
            parsed_images.append(metadata)
        
        return parsed_images
    
    def _extract_page_from_filename(self, image_path: str) -> Dict:
        """Extract page information from image filename."""
        filename = Path(image_path).name
        page_match = re.search(r'page_(\d+)', filename)
        
        return {
            'page_number': int(page_match.group(1)) if page_match else None,
            'filename': filename
        }
    
    def _match_location_description(self, expected: str, actual: str) -> bool:
        """
        Match location descriptions like 'top section', 'center', etc.
        
        This is a basic implementation that could be enhanced with more
        sophisticated position detection or image analysis.
        """
        expected_lower = expected.lower()
        actual_lower = actual.lower()
        
        # Basic keyword matching
        location_keywords = {
            'top': ['top', 'upper', 'above'],
            'center': ['center', 'middle', 'central'],
            'bottom': ['bottom', 'lower', 'below'],
            'left': ['left'],
            'right': ['right']
        }
        
        for location, keywords in location_keywords.items():
            if location in expected_lower:
                return any(keyword in actual_lower for keyword in keywords)
        
        return False
    
    def _match_section_context(self, expected_context: str, filename: str) -> bool:
        """
        Match section context with filename or other available metadata.
        
        This is a basic implementation using keyword matching.
        Could be enhanced with more sophisticated context analysis.
        """
        expected_lower = expected_context.lower()
        filename_lower = filename.lower()
        
        # Look for context keywords in the filename or path
        context_keywords = [
            'electrical', 'plumbing', 'hvac', 'structural', 'basement', 
            'kitchen', 'bathroom', 'exterior', 'roof', 'foundation'
        ]
        
        for keyword in context_keywords:
            if keyword in expected_lower and keyword in filename_lower:
                return True
        
        return False
    
    def get_matching_statistics(self, issues: List[InspectionIssue]) -> Dict:
        """
        Generate statistics about image matching performance.
        
        Args:
            issues: List of issues with enhanced image associations
            
        Returns:
            Dictionary with matching statistics
        """
        stats = {
            'total_issues': len(issues),
            'issues_with_expected_locations': 0,
            'total_enhanced_matches': 0,
            'high_confidence_matches': 0,
            'medium_confidence_matches': 0,
            'low_confidence_matches': 0,
            'location_based_matches': 0,
            'legacy_matches': 0,
            'average_confidence': 0.0,
            'matching_methods': {}
        }
        
        confidence_scores = []
        
        for issue in issues:
            if issue.expected_image_locations:
                stats['issues_with_expected_locations'] += 1
            
            for img_meta in issue.enhanced_images:
                stats['total_enhanced_matches'] += 1
                
                if img_meta.confidence_score:
                    confidence_scores.append(img_meta.confidence_score)
                    
                    if img_meta.confidence_score >= 85:
                        stats['high_confidence_matches'] += 1
                    elif img_meta.confidence_score >= 70:
                        stats['medium_confidence_matches'] += 1
                    else:
                        stats['low_confidence_matches'] += 1
                
                method = img_meta.matching_method or 'unknown'
                stats['matching_methods'][method] = stats['matching_methods'].get(method, 0) + 1
                
                if method == 'location_based':
                    stats['location_based_matches'] += 1
                elif method == 'legacy_proximity':
                    stats['legacy_matches'] += 1
        
        if confidence_scores:
            stats['average_confidence'] = sum(confidence_scores) / len(confidence_scores)
        
        return stats


# Utility function for easy usage
def enhance_image_associations(issues: List[InspectionIssue], extracted_images: List[str]) -> List[InspectionIssue]:
    """
    Quick utility to enhance image associations for a list of issues.
    
    Args:
        issues: List of extracted issues
        extracted_images: List of extracted image file paths
        
    Returns:
        List of issues with enhanced image associations
    """
    matcher = ImageMatcher()
    return matcher.enhance_image_associations(issues, extracted_images)


if __name__ == "__main__":
    # Test the image matcher
    from .schemas import ImageLocation, InspectionIssue
    
    # Create test data
    test_issue = InspectionIssue(
        issue_name="Test Electrical Issue",
        issue_type="Electrical",
        issue_description="Test description",
        issue_summary="Test summary",
        expected_image_locations=[
            ImageLocation(
                page_number=9,
                location_description="center section",
                section_context="electrical panel area"
            )
        ]
    )
    
    test_images = [
        "outputs/images/2/page_09_image_001.png",
        "outputs/images/2/page_09_image_002.png",
        "outputs/images/2/page_10_image_001.png"
    ]
    
    # Test matching
    matcher = ImageMatcher()
    enhanced_issues = matcher.enhance_image_associations([test_issue], test_images)
    
    print("Enhanced Image Matching Test:")
    print(f"Enhanced issues: {len(enhanced_issues)}")
    for issue in enhanced_issues:
        print(f"  Issue: {issue.issue_name}")
        print(f"  Enhanced images: {len(issue.enhanced_images)}")
        for img in issue.enhanced_images:
            print(f"    - {img.image_path} (confidence: {img.confidence_score})")
    
    # Print statistics
    stats = matcher.get_matching_statistics(enhanced_issues)
    print(f"  Statistics: {stats}")