#!/usr/bin/env python3
"""
Test script for enhanced PDF extraction pipeline.
Tests the improved PDF parser and Gemini extraction on PDF 2.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractors.pdf_parser import LlamaParseIntegration
from extractors.gemini_extractor import GeminiExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_enhanced_extraction():
    """Test the enhanced extraction pipeline on PDF 2."""
    
    pdf_path = "./data/2.pdf"
    
    if not Path(pdf_path).exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return
    
    try:
        # Step 1: Test enhanced PDF parsing
        logger.info("=== Testing Enhanced PDF Parser ===")
        parser = LlamaParseIntegration()
        
        parse_result = await parser.parse_pdf_async(pdf_path)
        
        if parse_result['success']:
            logger.info(f"✅ PDF parsing successful!")
            logger.info(f"   Content length: {parse_result['content_length']} characters")
            logger.info(f"   Extraction method: {parse_result.get('extraction_method', 'unknown')}")
            logger.info(f"   LlamaParse failure rate: {parse_result.get('llamaparse_failure_rate', 0):.1%}")
            logger.info(f"   Failed documents: {parse_result.get('failed_documents', 0)}/{parse_result.get('total_documents', 0)}")
            logger.info(f"   Images extracted: {parse_result['image_count']}")
            
            # Save the enhanced markdown for comparison
            enhanced_markdown_path = "./outputs/2_enhanced_markdown.md"
            with open(enhanced_markdown_path, 'w', encoding='utf-8') as f:
                f.write(parse_result['markdown_content'])
            logger.info(f"   Saved enhanced markdown to: {enhanced_markdown_path}")
            
        else:
            logger.error(f"❌ PDF parsing failed: {parse_result.get('error_message', 'Unknown error')}")
            return
        
        # Step 2: Test Gemini extraction with enhanced content
        logger.info("\n=== Testing Gemini Extraction with Enhanced Content ===")
        
        # Use Gemini 2.5 Pro for better accuracy
        extractor = GeminiExtractor(model_name='gemini-2.5-pro')
        
        extraction_result = await extractor.extract_async(
            markdown_content=parse_result['markdown_content'],
            image_references=parse_result['images'],
            source_filename="2.pdf"
        )
        
        if extraction_result.success and extraction_result.report:
            logger.info(f"✅ Gemini extraction successful!")
            logger.info(f"   Issues found: {len(extraction_result.report.issues)}")
            logger.info(f"   Processing time: {extraction_result.processing_time:.2f}s")
            
            # Save the enhanced extraction results
            enhanced_extraction_path = "./outputs/2_enhanced_extracted.json"
            with open(enhanced_extraction_path, 'w', encoding='utf-8') as f:
                json.dump(extraction_result.report.model_dump(), f, indent=2, ensure_ascii=False)
            logger.info(f"   Saved enhanced extraction to: {enhanced_extraction_path}")
            
            # Compare with original results
            original_extraction_path = "./outputs/2_extracted.json"
            if Path(original_extraction_path).exists():
                with open(original_extraction_path, 'r', encoding='utf-8') as f:
                    original_data = json.load(f)
                
                original_issues = len(original_data.get('issues', []))
                enhanced_issues = len(extraction_result.report.issues)
                improvement = enhanced_issues - original_issues
                
                logger.info(f"\n=== Comparison with Original Results ===")
                logger.info(f"   Original issues found: {original_issues}")
                logger.info(f"   Enhanced issues found: {enhanced_issues}")
                logger.info(f"   Improvement: {improvement:+d} issues ({improvement/13*100:+.1f}% of total 13)")
                
                if enhanced_issues >= 11:  # Target >85% of 13 issues
                    logger.info(f"🎯 SUCCESS! Found {enhanced_issues}/13 issues ({enhanced_issues/13*100:.1f}% > 85% target)")
                else:
                    logger.warning(f"⚠️  Still below target: {enhanced_issues}/13 issues ({enhanced_issues/13*100:.1f}% < 85% target)")
                
                # Show the new issues found
                original_issue_names = {issue['issue_name'] for issue in original_data.get('issues', [])}
                enhanced_issue_names = {issue.issue_name for issue in extraction_result.report.issues}
                new_issues = enhanced_issue_names - original_issue_names
                
                if new_issues:
                    logger.info(f"\n=== New Issues Found ({len(new_issues)}) ===")
                    for i, issue_name in enumerate(new_issues, 1):
                        logger.info(f"   {i}. {issue_name}")
                else:
                    logger.info(f"\n=== No new issues found ===")
            else:
                logger.info(f"   Original extraction file not found for comparison")
            
        else:
            logger.error(f"❌ Gemini extraction failed: {extraction_result.error_message}")
            return
        
        logger.info(f"\n=== Test Complete ===")
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_enhanced_extraction())