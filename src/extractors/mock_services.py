"""
Mock services for testing the extraction pipeline without API keys.

This module provides mock implementations of external services to enable
development and testing without requiring actual API credentials.
"""

import json
import time
import random
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path

from .schemas import HomeInspectionReport, InspectionIssue, ExtractionResult


class MockLlamaParseService:
    """Mock implementation of LlamaParse for testing."""
    
    def __init__(self):
        self.processing_delay = 2.0  # Simulate processing time
    
    async def parse_pdf_async(self, pdf_path: str, max_retries: int = 3) -> Dict[str, Any]:
        """Mock PDF parsing that returns sample markdown content."""
        await asyncio.sleep(self.processing_delay)
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {
                'success': False,
                'error_message': f"PDF file not found: {pdf_path}",
                'source_pdf': str(pdf_path),
                'processing_time': 0,
                'markdown_content': '',
                'images': []
            }
        
        # Generate mock markdown content based on PDF filename
        mock_content = self._generate_mock_markdown(pdf_path.name)
        
        return {
            'success': True,
            'markdown_content': mock_content,
            'images': [f"image_{i}.jpg" for i in range(random.randint(0, 3))],
            'processing_time': self.processing_delay,
            'source_pdf': str(pdf_path),
            'content_length': len(mock_content),
            'attempt_count': 1
        }
    
    def _generate_mock_markdown(self, filename: str) -> str:
        """Generate mock markdown content for testing."""
        return f"""# Home Inspection Report - {filename}

## Property Information
- Address: 123 Mock Street, Test City
- Inspection Date: 2024-01-15
- Inspector: Mock Inspector Services

## Executive Summary
This inspection identified several areas requiring attention including electrical, plumbing, and structural components.

## Electrical System
### Issue: Outdated Wiring
The basement contains old knob and tube wiring that should be replaced for safety compliance.
Priority: High
Location: Basement electrical panel area

### Issue: Missing GFCI Outlets
Bathrooms lack proper GFCI outlet protection as required by current codes.
Priority: Medium
Location: All bathrooms

## Plumbing System
### Issue: Minor Kitchen Leak
Small leak observed under kitchen sink near the P-trap connection.
Priority: Low
Location: Kitchen sink cabinet

### Issue: Water Pressure Issues
Low water pressure noted in upstairs shower.
Priority: Medium
Location: Master bathroom

## Structural Components
### Issue: Foundation Crack
Minor crack in basement foundation wall, should be monitored.
Priority: Medium
Location: East basement wall

## HVAC System
### Issue: Filter Replacement Needed
HVAC filter is dirty and requires replacement.
Priority: Low
Location: Utility room

## Recommendations
1. Replace knob and tube wiring immediately
2. Install GFCI outlets in all bathrooms
3. Repair kitchen sink leak
4. Monitor foundation crack for changes
5. Replace HVAC filter regularly

## Images Referenced
- electrical_panel.jpg
- basement_wiring.jpg
- kitchen_leak.jpg
- foundation_crack.jpg
"""


class MockGeminiService:
    """Mock implementation of Gemini for testing medium complexity extractions."""
    
    def __init__(self):
        self.processing_delay = 3.0
    
    async def extract_async(self, prompt: str) -> Dict[str, Any]:
        """Mock extraction that returns structured data."""
        await asyncio.sleep(self.processing_delay)
        
        # Generate mock extraction result
        mock_result = {
            "report_name": "Mock Home Inspection Report",
            "issues": [
                {
                    "issue_name": "Outdated Knob and Tube Wiring",
                    "issue_type": "Electrical",
                    "issue_description": "The basement contains old knob and tube wiring that should be replaced for safety compliance. This type of wiring is outdated and may not meet current electrical codes.",
                    "issue_summary": "Replace knob and tube wiring immediately for safety compliance.",
                    "issue_images": ["electrical_panel.jpg", "basement_wiring.jpg"]
                },
                {
                    "issue_name": "Missing GFCI Outlets in Bathrooms",
                    "issue_type": "Electrical",
                    "issue_description": "Bathrooms lack proper GFCI outlet protection as required by current electrical codes for wet locations.",
                    "issue_summary": "Install GFCI outlets in all bathroom locations for code compliance.",
                    "issue_images": []
                },
                {
                    "issue_name": "Kitchen Sink Leak",
                    "issue_type": "Plumbing",
                    "issue_description": "Small leak observed under kitchen sink near the P-trap connection. This could lead to water damage if not addressed.",
                    "issue_summary": "Repair P-trap connection to prevent water damage.",
                    "issue_images": ["kitchen_leak.jpg"]
                },
                {
                    "issue_name": "Foundation Wall Crack",
                    "issue_type": "Structural",
                    "issue_description": "Minor crack in basement foundation wall on the east side. Should be monitored for changes over time.",
                    "issue_summary": "Monitor foundation crack and consult structural engineer if it expands.",
                    "issue_images": ["foundation_crack.jpg"]
                }
            ]
        }
        
        return {
            'success': True,
            'extracted_data': mock_result,
            'processing_time': self.processing_delay,
            'model_used': 'mock-gemini-2.5-pro'
        }


class MockClaudeService:
    """Mock implementation of Claude for testing complex extractions."""
    
    def __init__(self):
        self.processing_delay = 4.0
    
    async def extract_async(self, prompt: str) -> Dict[str, Any]:
        """Mock extraction for complex documents."""
        await asyncio.sleep(self.processing_delay)
        
        # Generate more complex mock result
        mock_result = {
            "report_name": "Complex Commercial Property Inspection",
            "issues": [
                {
                    "issue_name": "Commercial HVAC System Deficiency",
                    "issue_type": "HVAC",
                    "issue_description": "The commercial HVAC system shows signs of inadequate maintenance with multiple components requiring immediate attention. Air handling units have dirty filters, and some ductwork connections are loose.",
                    "issue_summary": "Service HVAC system immediately and establish regular maintenance schedule.",
                    "issue_images": ["hvac_unit_1.jpg", "ductwork_loose.jpg"]
                },
                {
                    "issue_name": "Electrical Panel Overcrowding",
                    "issue_type": "Electrical",
                    "issue_description": "Main electrical panel shows overcrowding with multiple circuits improperly installed. Some breakers appear to be oversized for the wire gauge used.",
                    "issue_summary": "Electrical panel requires professional evaluation and potential upgrade.",
                    "issue_images": ["electrical_panel_main.jpg", "overcrowded_circuits.jpg"]
                },
                {
                    "issue_name": "Roof Membrane Deterioration",
                    "issue_type": "Exterior",
                    "issue_description": "Commercial flat roof membrane shows signs of deterioration with multiple areas of concern. Several seams are separating and there is evidence of ponding water.",
                    "issue_summary": "Roof requires immediate professional assessment and likely partial replacement.",
                    "issue_images": ["roof_membrane_1.jpg", "roof_ponding.jpg", "seam_separation.jpg"]
                },
                {
                    "issue_name": "Fire Safety System Compliance",
                    "issue_type": "Safety",
                    "issue_description": "Fire safety systems including sprinklers and alarm systems require testing and certification. Some sprinkler heads appear corroded and alarm panel shows fault conditions.",
                    "issue_summary": "Complete fire safety system inspection and bring up to current code compliance.",
                    "issue_images": ["sprinkler_corrosion.jpg", "alarm_panel.jpg"]
                },
                {
                    "issue_name": "Commercial Kitchen Exhaust Issues",
                    "issue_type": "HVAC",
                    "issue_description": "Kitchen exhaust system shows grease buildup and inadequate ventilation. Hood system requires professional cleaning and some ductwork needs repair.",
                    "issue_summary": "Professional kitchen exhaust cleaning and ductwork repair required.",
                    "issue_images": ["kitchen_hood.jpg", "exhaust_duct.jpg"]
                }
            ]
        }
        
        return {
            'success': True,
            'extracted_data': mock_result,
            'processing_time': self.processing_delay,
            'model_used': 'mock-claude-3.5-sonnet'
        }


class MockExtractionPipeline:
    """Mock extraction pipeline for testing without API keys."""
    
    def __init__(self):
        self.llamaparse = MockLlamaParseService()
        self.gemini = MockGeminiService()
        self.claude = MockClaudeService()
    
    async def extract_from_pdf(self, pdf_path: str, complexity: str = 'medium') -> ExtractionResult:
        """
        Mock end-to-end extraction process.
        
        Args:
            pdf_path: Path to PDF file
            complexity: Complexity level ('medium' or 'complex')
            
        Returns:
            ExtractionResult with mock data
        """
        start_time = time.time()
        
        try:
            # Step 1: Mock PDF parsing
            parse_result = await self.llamaparse.parse_pdf_async(pdf_path)
            
            if not parse_result['success']:
                return ExtractionResult(
                    success=False,
                    error_message=parse_result['error_message'],
                    processing_time=time.time() - start_time,
                    model_used='mock-parser',
                    pdf_complexity=complexity
                )
            
            # Step 2: Mock extraction based on complexity
            if complexity.lower() == 'complex':
                extract_result = await self.claude.extract_async(parse_result['markdown_content'])
                model_used = 'mock-claude-3.5-sonnet'
            else:
                extract_result = await self.gemini.extract_async(parse_result['markdown_content'])
                model_used = 'mock-gemini-2.5-pro'
            
            if not extract_result['success']:
                return ExtractionResult(
                    success=False,
                    error_message="Mock extraction failed",
                    processing_time=time.time() - start_time,
                    model_used=model_used,
                    pdf_complexity=complexity
                )
            
            # Step 3: Create structured result
            extracted_data = extract_result['extracted_data']
            
            # Convert to Pydantic models
            issues = [InspectionIssue(**issue) for issue in extracted_data['issues']]
            report = HomeInspectionReport(
                report_name=extracted_data['report_name'],
                issues=issues,
                source_pdf=pdf_path,
                extraction_model=model_used,
                total_pages=random.randint(15, 40)
            )
            
            return ExtractionResult(
                success=True,
                report=report,
                processing_time=time.time() - start_time,
                model_used=model_used,
                pdf_complexity=complexity
            )
            
        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"Mock extraction error: {str(e)}",
                processing_time=time.time() - start_time,
                model_used='mock-error',
                pdf_complexity=complexity
            )
    
    def get_pdf_complexity(self, pdf_path: str) -> str:
        """Mock complexity classification based on filename."""
        filename = Path(pdf_path).name.lower()
        
        # Simple classification based on filename patterns
        if any(term in filename for term in ['1.pdf', '2.pdf']):
            return 'medium'
        elif any(term in filename for term in ['3.pdf', '4.pdf', '5.pdf']):
            return 'complex'
        else:
            return 'medium'  # Default


# Test utilities
async def test_mock_pipeline():
    """Test the mock pipeline with sample PDFs."""
    pipeline = MockExtractionPipeline()
    
    test_pdfs = [
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/1.pdf",
        "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/3.pdf"
    ]
    
    for pdf_path in test_pdfs:
        if Path(pdf_path).exists():
            complexity = pipeline.get_pdf_complexity(pdf_path)
            print(f"\nTesting {Path(pdf_path).name} (complexity: {complexity})")
            
            result = await pipeline.extract_from_pdf(pdf_path, complexity)
            
            print(f"Success: {result.success}")
            if result.success and result.report:
                print(f"Report: {result.report.report_name}")
                print(f"Issues found: {result.report.issue_count}")
                print(f"Processing time: {result.processing_time:.2f}s")
            else:
                print(f"Error: {result.error_message}")


if __name__ == "__main__":
    print("Testing Mock Extraction Pipeline")
    asyncio.run(test_mock_pipeline())