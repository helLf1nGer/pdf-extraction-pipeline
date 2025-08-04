"""
Model routing system for PDF extraction pipeline.

This module determines which AI model to use for extraction based on PDF complexity,
routing simpler documents to Gemini and complex documents to Claude for optimal
accuracy and cost efficiency.
"""

import os
import re
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from enum import Enum

from .extraction_prompts import ExtractionPromptTemplate

logger = logging.getLogger(__name__)


class ComplexityLevel(Enum):
    """PDF complexity levels for model routing."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class ModelType(Enum):
    """Available AI models for extraction."""
    QWEN = "qwen-2.5-72b"  # For simple documents
    GEMINI = "gemini-2.5-pro"  # For medium complexity
    CLAUDE = "claude-3.5-sonnet"  # For complex documents


class PDFComplexityClassifier:
    """Classifies PDF complexity based on content analysis."""
    
    def __init__(self):
        # Predefined classifications from PDF Analyzer results
        self.known_classifications = {
            "1.pdf": ComplexityLevel.MEDIUM,  # Baker Street - 24 pages, 12-15 issues
            "2.pdf": ComplexityLevel.MEDIUM,  # Empire Home - 16 pages, 8 issues
            "3.pdf": ComplexityLevel.COMPLEX,  # Carson Dunlop - 23 pages, 15+ issues, technical
            "4.pdf": ComplexityLevel.COMPLEX,  # Global Property - 39 pages, 20-25 issues
            "5.pdf": ComplexityLevel.COMPLEX,  # National Home - commercial, narrative format
        }
        
        # Thresholds for dynamic classification
        self.thresholds = {
            'simple': {
                'max_pages': 10,
                'max_issues': 5,
                'max_images': 2
            },
            'medium': {
                'max_pages': 30,
                'max_issues': 15,
                'max_images': 10
            }
            # Complex: anything above medium thresholds
        }
        
        # Complexity indicators
        self.complexity_keywords = {
            'simple': ['basic', 'standard', 'residential'],
            'medium': ['inspection', 'report', 'findings', 'recommendations'],
            'complex': [
                'commercial', 'industrial', 'technical', 'asbestos', 
                'electrical systems', 'hvac systems', '600-volt', 
                'structural deficiencies', 'safety-critical', 'narrative'
            ]
        }
    
    def classify_by_filename(self, filename: str) -> Optional[ComplexityLevel]:
        """Get known classification based on filename."""
        return self.known_classifications.get(filename)
    
    def classify_by_content(self, content: str, page_count: Optional[int] = None) -> ComplexityLevel:
        """
        Classify PDF complexity based on content analysis.
        
        Args:
            content: Parsed text content from PDF
            page_count: Number of pages (if available)
            
        Returns:
            ComplexityLevel enum value
        """
        content_lower = content.lower()
        
        # Count potential issues (heuristic based on common patterns)
        issue_indicators = [
            r'\b(issue|problem|defect|repair|replace|fix|concern)\b',
            r'\b(recommend|suggest|advise|should|must|need)\b',
            r'\b(safety|hazard|danger|risk|critical)\b',
            r'\b(electrical|plumbing|hvac|structural|roof|foundation)\b'
        ]
        
        estimated_issues = 0
        for pattern in issue_indicators:
            matches = len(re.findall(pattern, content_lower))
            estimated_issues += matches * 0.3  # Weight factor
        
        estimated_issues = int(estimated_issues)
        
        # Estimate images based on image references
        image_patterns = [
            r'\b(image|photo|picture|fig|figure)\b',
            r'\.(jpg|jpeg|png|gif|bmp)',
            r'image_\d+',
            r'photo_\d+'
        ]
        
        estimated_images = 0
        for pattern in image_patterns:
            estimated_images += len(re.findall(pattern, content_lower))
        
        # Content length analysis
        content_length = len(content)
        
        # Commercial/complex indicators
        complex_score = 0
        for keyword in self.complexity_keywords['complex']:
            if keyword in content_lower:
                complex_score += 1
        
        # Check for technical/narrative complexity
        technical_patterns = [
            r'\b\d+\s*(amp|volt|watt)\b',  # Electrical specs
            r'\b\d+\s*(ton|btu|cfm)\b',    # HVAC specs
            r'\b\d+\s*(psi|gpm|inch)\b',   # Pressure/flow specs
            r'\$\d+,?\d*',                 # Cost estimates
        ]
        
        technical_score = sum(len(re.findall(pattern, content_lower)) for pattern in technical_patterns)
        
        # Classification logic
        logger.debug(f"Content analysis: length={content_length}, issues={estimated_issues}, "
                    f"images={estimated_images}, complex_score={complex_score}, "
                    f"technical_score={technical_score}, pages={page_count}")
        
        # Complex classification criteria
        if (complex_score >= 3 or 
            technical_score >= 5 or 
            estimated_issues >= 16 or 
            (page_count and page_count >= 35) or
            content_length >= 50000):
            return ComplexityLevel.COMPLEX
        
        # Simple classification criteria
        elif (estimated_issues <= 5 and 
              estimated_images <= 2 and 
              (page_count is None or page_count <= 10) and
              content_length <= 10000):
            return ComplexityLevel.SIMPLE
        
        # Default to medium
        else:
            return ComplexityLevel.MEDIUM
    
    def classify_pdf(self, pdf_path: str, content: Optional[str] = None) -> Tuple[ComplexityLevel, Dict[str, Any]]:
        """
        Classify PDF complexity using multiple methods.
        
        Args:
            pdf_path: Path to PDF file
            content: Optional parsed content for analysis
            
        Returns:
            Tuple of (ComplexityLevel, classification_metadata)
        """
        filename = Path(pdf_path).name
        
        # First try known classifications
        known_complexity = self.classify_by_filename(filename)
        if known_complexity:
            metadata = {
                'method': 'known_classification',
                'filename': filename,
                'source': 'pdf_analyzer_results'
            }
            logger.info(f"Using known classification for {filename}: {known_complexity.value}")
            return known_complexity, metadata
        
        # Fall back to content analysis if available
        if content:
            complexity = self.classify_by_content(content)
            metadata = {
                'method': 'content_analysis',
                'filename': filename,
                'content_length': len(content)
            }
            logger.info(f"Classified {filename} by content: {complexity.value}")
            return complexity, metadata
        
        # Default classification for unknown files
        logger.warning(f"No classification method available for {filename}, defaulting to MEDIUM")
        return ComplexityLevel.MEDIUM, {
            'method': 'default',
            'filename': filename,
            'reason': 'no_content_or_known_classification'
        }


class ModelRouter:
    """Routes extraction requests to appropriate AI models based on complexity."""
    
    def __init__(self):
        self.classifier = PDFComplexityClassifier()
        
        # Model routing configuration
        self.model_mapping = {
            ComplexityLevel.SIMPLE: ModelType.QWEN,
            ComplexityLevel.MEDIUM: ModelType.GEMINI,
            ComplexityLevel.COMPLEX: ModelType.CLAUDE
        }
        
        # Model capabilities and limits
        self.model_specs = {
            ModelType.QWEN: {
                'max_tokens': 32000,
                'cost_per_1k_tokens': 0.0005,  # Estimated
                'best_for': 'Simple text-heavy documents with minimal formatting'
            },
            ModelType.GEMINI: {
                'max_tokens': 1000000,  # 1M context window
                'cost_per_1k_tokens': 0.002,  # Estimated
                'best_for': 'Medium complexity with mixed content and structured formats'
            },
            ModelType.CLAUDE: {
                'max_tokens': 200000,  # 200k context window
                'cost_per_1k_tokens': 0.015,  # Estimated
                'best_for': 'Complex technical documents requiring deep reasoning'
            }
        }
    
    def route_pdf(self, pdf_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """
        Route a PDF to the appropriate model for extraction.
        
        Args:
            pdf_path: Path to the PDF file
            content: Optional parsed content for analysis
            
        Returns:
            Dictionary with routing decision and metadata
        """
        # Classify complexity
        complexity, classification_metadata = self.classifier.classify_pdf(pdf_path, content)
        
        # Get recommended model
        recommended_model = self.model_mapping[complexity]
        model_specs = self.model_specs[recommended_model]
        
        # Check content length against model limits
        if content:
            content_tokens = len(content) // 4  # Rough token estimation
            max_tokens = model_specs['max_tokens']
            
            if content_tokens > max_tokens * 0.8:  # 80% threshold for safety
                logger.warning(f"Content may exceed {recommended_model.value} limits. "
                              f"Estimated tokens: {content_tokens}, Max: {max_tokens}")
                
                # Consider upgrading to higher capacity model
                if recommended_model == ModelType.QWEN:
                    recommended_model = ModelType.GEMINI
                    logger.info("Upgrading QWEN → GEMINI due to content length")
                elif recommended_model == ModelType.GEMINI and content_tokens > 800000:
                    logger.warning("Content may be too large even for Gemini. Consider chunking.")
        
        routing_result = {
            'pdf_path': pdf_path,
            'filename': Path(pdf_path).name,
            'complexity': complexity.value,
            'recommended_model': recommended_model.value,
            'model_specs': model_specs,
            'classification_metadata': classification_metadata,
            'estimated_cost': self._estimate_cost(content, recommended_model) if content else None
        }
        
        logger.info(f"Routed {Path(pdf_path).name}: {complexity.value} → {recommended_model.value}")
        return routing_result
    
    def _estimate_cost(self, content: str, model: ModelType) -> Dict[str, float]:
        """Estimate processing cost for content."""
        tokens = len(content) // 4  # Rough estimation
        cost_per_1k = self.model_specs[model]['cost_per_1k_tokens']
        estimated_cost = (tokens / 1000) * cost_per_1k
        
        return {
            'estimated_tokens': tokens,
            'cost_per_1k_tokens': cost_per_1k,
            'estimated_cost_usd': round(estimated_cost, 4)
        }
    
    def get_extraction_config(self, routing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get extraction configuration based on routing decision.
        
        Args:
            routing_result: Result from route_pdf()
            
        Returns:
            Configuration dictionary for extraction
        """
        model = routing_result['recommended_model']
        complexity = routing_result['complexity']
        
        # Base configuration
        config = {
            'model': model,
            'complexity': complexity,
            'max_retries': 3,
            'timeout': 120,  # 2 minutes
        }
        
        # Model-specific configurations
        if model == ModelType.GEMINI.value:
            config.update({
                'temperature': 0.1,  # Low temperature for consistency
                'max_output_tokens': 4096,
                'safety_settings': 'block_none',  # For technical content
            })
        elif model == ModelType.CLAUDE.value:
            config.update({
                'temperature': 0.1,
                'max_tokens': 4096,
                'timeout': 180,  # Longer timeout for complex docs
            })
        elif model == ModelType.QWEN.value:
            config.update({
                'temperature': 0.1,
                'max_tokens': 2048,
            })
        
        return config
    
    def batch_route_pdfs(self, pdf_paths: List[str]) -> List[Dict[str, Any]]:
        """Route multiple PDFs for batch processing."""
        results = []
        
        for pdf_path in pdf_paths:
            try:
                routing_result = self.route_pdf(pdf_path)
                results.append(routing_result)
            except Exception as e:
                logger.error(f"Failed to route {pdf_path}: {str(e)}")
                results.append({
                    'pdf_path': pdf_path,
                    'error': str(e),
                    'success': False
                })
        
        # Summary statistics
        complexity_counts = {}
        model_counts = {}
        
        for result in results:
            if 'complexity' in result:
                complexity_counts[result['complexity']] = complexity_counts.get(result['complexity'], 0) + 1
            if 'recommended_model' in result:
                model_counts[result['recommended_model']] = model_counts.get(result['recommended_model'], 0) + 1
        
        logger.info(f"Batch routing complete: {len(results)} PDFs")
        logger.info(f"Complexity distribution: {complexity_counts}")
        logger.info(f"Model distribution: {model_counts}")
        
        return results


# Utility functions
def route_single_pdf(pdf_path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """Quick utility to route a single PDF."""
    router = ModelRouter()
    return router.route_pdf(pdf_path, content)


def get_model_for_pdf(pdf_path: str) -> str:
    """Quick utility to get recommended model name for a PDF."""
    routing_result = route_single_pdf(pdf_path)
    return routing_result['recommended_model']


if __name__ == "__main__":
    # Test the router
    router = ModelRouter()
    
    # Test known PDFs
    test_pdfs = [
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/1.pdf",
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/2.pdf",
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/3.pdf",
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/4.pdf",
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/5.pdf",
    ]
    
    print("Testing Model Router:")
    print("=" * 50)
    
    for pdf_path in test_pdfs:
        if Path(pdf_path).exists():
            result = router.route_pdf(pdf_path)
            print(f"📄 {result['filename']}")
            print(f"   Complexity: {result['complexity']}")
            print(f"   Model: {result['recommended_model']}")
            print(f"   Method: {result['classification_metadata']['method']}")
            print()
        else:
            print(f"❌ File not found: {pdf_path}")
    
    print("Batch routing test:")
    existing_pdfs = [pdf for pdf in test_pdfs if Path(pdf).exists()]
    batch_results = router.batch_route_pdfs(existing_pdfs)
    print(f"Processed {len(batch_results)} PDFs successfully")