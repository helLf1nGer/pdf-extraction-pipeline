#!/usr/bin/env python3
"""
Update model routing to use:
- Easy: Gemini 2.5 Flash (primary), Claude 3.5 Sonnet (backup)
- Medium: Gemini 2.5 Pro (primary), Claude 3.5 Sonnet (backup)
- Complex: Gemini 2.5 Pro (primary), Claude Opus 4 (backup)
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ComplexityLevel(Enum):
    """PDF complexity levels."""
    EASY = "easy"  # Renamed from SIMPLE
    MEDIUM = "medium"
    COMPLEX = "complex"


class ModelType(Enum):
    """Available AI models for extraction."""
    GEMINI_FLASH = "gemini-2.5-flash"  # For easy documents
    GEMINI_PRO = "gemini-2.5-pro"  # For medium/complex documents
    CLAUDE_SONNET = "claude-3.5-sonnet"  # Backup for easy/medium
    CLAUDE_OPUS_4 = "claude-opus-4"  # Backup for complex


class ModelConfiguration:
    """Model configurations and routing rules."""
    
    # Primary models by complexity
    PRIMARY_MODELS = {
        ComplexityLevel.EASY: ModelType.GEMINI_FLASH,
        ComplexityLevel.MEDIUM: ModelType.GEMINI_PRO,
        ComplexityLevel.COMPLEX: ModelType.GEMINI_PRO,
    }
    
    # Backup models by complexity
    BACKUP_MODELS = {
        ComplexityLevel.EASY: ModelType.CLAUDE_SONNET,
        ComplexityLevel.MEDIUM: ModelType.CLAUDE_SONNET,
        ComplexityLevel.COMPLEX: ModelType.CLAUDE_OPUS_4,
    }
    
    # Model specifications
    MODEL_SPECS = {
        ModelType.GEMINI_FLASH: {
            'api_name': 'gemini-2.5-flash',
            'max_tokens': 8192,
            'cost_per_1k_tokens': 0.00015,  # Flash is cheapest
            'best_for': 'Simple documents with clear structure'
        },
        ModelType.GEMINI_PRO: {
            'api_name': 'gemini-2.5-pro',
            'max_tokens': 8192,
            'cost_per_1k_tokens': 0.002,
            'best_for': 'Medium to complex documents requiring deeper analysis'
        },
        ModelType.CLAUDE_SONNET: {
            'api_name': 'claude-3-5-sonnet-20241022',
            'max_tokens': 8192,
            'cost_per_1k_tokens': 0.003,
            'best_for': 'Backup for easy/medium documents when Gemini fails'
        },
        ModelType.CLAUDE_OPUS_4: {
            'api_name': 'claude-opus-4-20250514',  # Opus 4!
            'max_tokens': 8192,
            'cost_per_1k_tokens': 0.015,
            'best_for': 'Complex technical documents requiring advanced reasoning'
        }
    }


class EnhancedModelRouter:
    """Enhanced model router with primary/backup logic."""
    
    def __init__(self):
        self.config = ModelConfiguration()
        
    def get_models_for_complexity(self, complexity: ComplexityLevel) -> Tuple[ModelType, ModelType]:
        """
        Get primary and backup models for a given complexity level.
        
        Returns:
            Tuple of (primary_model, backup_model)
        """
        primary = self.config.PRIMARY_MODELS[complexity]
        backup = self.config.BACKUP_MODELS[complexity]
        return primary, backup
    
    def get_model_config(self, model_type: ModelType) -> Dict[str, Any]:
        """Get configuration for a specific model."""
        return self.config.MODEL_SPECS[model_type]
    
    def route_pdf(self, pdf_path: str, complexity: ComplexityLevel) -> Dict[str, Any]:
        """
        Route a PDF based on its complexity.
        
        Returns:
            Dictionary with routing decision including primary and backup models
        """
        primary_model, backup_model = self.get_models_for_complexity(complexity)
        
        result = {
            'pdf_path': pdf_path,
            'filename': Path(pdf_path).name,
            'complexity': complexity.value,
            'primary_model': {
                'type': primary_model.value,
                'config': self.get_model_config(primary_model)
            },
            'backup_model': {
                'type': backup_model.value,
                'config': self.get_model_config(backup_model)
            },
            'routing_strategy': f"{primary_model.value} → {backup_model.value} (if needed)"
        }
        
        logger.info(f"Routed {Path(pdf_path).name}: {complexity.value} → "
                   f"{primary_model.value} (primary), {backup_model.value} (backup)")
        
        return result


def test_new_routing():
    """Test the new routing configuration."""
    router = EnhancedModelRouter()
    
    print("Enhanced Model Routing Configuration")
    print("=" * 50)
    
    # Test each complexity level
    for complexity in ComplexityLevel:
        primary, backup = router.get_models_for_complexity(complexity)
        print(f"\n{complexity.value.upper()} Documents:")
        print(f"  Primary: {primary.value}")
        print(f"  Backup: {backup.value}")
        
        # Show model details
        primary_config = router.get_model_config(primary)
        backup_config = router.get_model_config(backup)
        
        print(f"\n  Primary Model Details:")
        print(f"    API Name: {primary_config['api_name']}")
        print(f"    Max Tokens: {primary_config['max_tokens']}")
        print(f"    Cost/1K: ${primary_config['cost_per_1k_tokens']}")
        
        print(f"\n  Backup Model Details:")
        print(f"    API Name: {backup_config['api_name']}")
        print(f"    Max Tokens: {backup_config['max_tokens']}")
        print(f"    Cost/1K: ${backup_config['cost_per_1k_tokens']}")
    
    # Test routing for sample PDFs
    print("\n" + "=" * 50)
    print("Sample PDF Routing:")
    
    test_pdfs = [
        ("data/simple_report.pdf", ComplexityLevel.EASY),
        ("data/standard_inspection.pdf", ComplexityLevel.MEDIUM),
        ("data/complex_commercial.pdf", ComplexityLevel.COMPLEX),
    ]
    
    for pdf_path, complexity in test_pdfs:
        result = router.route_pdf(pdf_path, complexity)
        print(f"\n{result['filename']}:")
        print(f"  Strategy: {result['routing_strategy']}")


if __name__ == "__main__":
    test_new_routing()