"""
Claude 3.5 Sonnet integration for home inspection report extraction.

This module handles extraction of structured data from complex
PDF inspection reports using Anthropic's Claude 3.5 Sonnet model.
"""

import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    anthropic = None
    logging.warning("anthropic not available. Install with: pip install anthropic")

from .schemas import HomeInspectionReport, InspectionIssue, ExtractionResult
from .extraction_prompts import ExtractionPromptTemplate

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class ClaudeExtractionError(Exception):
    """Custom exception for Claude extraction errors."""
    pass


class ClaudeExtractor:
    """
    Claude extractor supporting both Sonnet 3.5 and Opus 4.
    
    - Sonnet 3.5: Backup for easy/medium documents
    - Opus 4: For complex technical documents requiring advanced reasoning
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = 'claude-3-5-sonnet-20241022'):
        """
        Initialize Claude extractor.
        
        Args:
            api_key: Anthropic API key. If None, will try to get from environment.
        """
        if anthropic is None:
            raise ImportError("anthropic is not installed. Run: pip install anthropic")
        
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable.")
        
        # Initialize Claude client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Store model name
        self.model_name = model_name
        
        # Model configuration optimized for complex extraction
        self.model_config = {
            'model': self.model_name,
            'max_tokens': 8192,  # Increased for complex documents
            'temperature': 0.1,  # Low temperature for consistency
        }
        
        logger.info(f"Claude extractor initialized with model: {self.model_name}")
    
    async def extract_async(
        self, 
        markdown_content: str, 
        image_references: Optional[List[str]] = None,
        source_filename: Optional[str] = None,
        max_retries: int = 3
    ) -> ExtractionResult:
        """
        Extract structured data from markdown content asynchronously.
        
        Args:
            markdown_content: Parsed markdown content from PDF
            image_references: List of image filenames/references
            source_filename: Original PDF filename
            max_retries: Maximum number of retry attempts
            
        Returns:
            ExtractionResult with success status and extracted data
        """
        start_time = time.time()
        last_error = None
        
        # Generate extraction prompt
        prompt = ExtractionPromptTemplate.get_home_inspection_extraction_prompt(
            markdown_content=markdown_content,
            image_references=image_references,
            report_filename=source_filename
        )
        
        # Validate prompt length (Claude has 200k context limit)
        if len(prompt) > 180000:  # Conservative limit
            logger.warning(f"Prompt very long ({len(prompt)} chars), may hit Claude limits")
            # Truncate content if needed but preserve structure
            truncated_content = markdown_content[:150000] + "\n\n[CONTENT TRUNCATED DUE TO LENGTH LIMITS]"
            prompt = ExtractionPromptTemplate.get_home_inspection_extraction_prompt(
                markdown_content=truncated_content,
                image_references=image_references,
                report_filename=source_filename
            )
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Claude extraction attempt {attempt + 1}/{max_retries + 1} for {source_filename or 'unknown'}")
                
                # Generate response with Claude
                response = await self._generate_with_retry(prompt)
                
                if not response or not response.content:
                    raise ClaudeExtractionError("Empty response from Claude")
                
                # Extract text from response
                response_text = self._extract_response_text(response)
                
                # Parse JSON response
                extracted_data = self._parse_response(response_text)
                
                # Validate and convert to Pydantic models
                report = self._create_report_model(extracted_data, source_filename)
                
                processing_time = time.time() - start_time
                
                logger.info(f"Claude extraction successful for {source_filename or 'unknown'} "
                           f"in {processing_time:.2f}s. Found {len(report.issues)} issues.")
                
                return ExtractionResult(
                    success=True,
                    report=report,
                    processing_time=processing_time,
                    model_used=self.model_name,
                    pdf_complexity='complex'
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"Claude extraction attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All Claude extraction attempts failed for {source_filename or 'unknown'}")
        
        # All attempts failed
        processing_time = time.time() - start_time
        return ExtractionResult(
            success=False,
            error_message=f"Claude extraction failed after {max_retries + 1} attempts: {str(last_error)}",
            processing_time=processing_time,
            model_used='claude-3.5-sonnet',
            pdf_complexity='complex'
        )
    
    async def _generate_with_retry(self, prompt: str, timeout: int = 180) -> Any:
        """Generate response with timeout and error handling."""
        try:
            # Claude API call with timeout
            response = await asyncio.wait_for(
                self._make_api_call(prompt),
                timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            raise ClaudeExtractionError(f"Claude request timed out after {timeout} seconds")
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'too many requests' in error_str:
                raise ClaudeExtractionError(f"Rate limit exceeded: {str(e)}")
            elif 'credit' in error_str or 'balance' in error_str:
                raise ClaudeExtractionError(f"Insufficient credits: {str(e)}")
            elif 'authentication' in error_str or 'api key' in error_str:
                raise ClaudeExtractionError(f"Authentication error: {str(e)}")
            else:
                raise ClaudeExtractionError(f"Claude API error: {str(e)}")
    
    async def _make_api_call(self, prompt: str) -> Any:
        """Make async API call to Claude."""
        # Anthropic client doesn't have native async support, so we use a thread pool
        loop = asyncio.get_event_loop()
        
        def sync_call():
            return self.client.messages.create(
                **self.model_config,
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
        
        return await loop.run_in_executor(None, sync_call)
    
    def _extract_response_text(self, response: Any) -> str:
        """Extract text content from Claude response."""
        try:
            if hasattr(response, 'content') and response.content:
                # Handle list of content blocks
                if isinstance(response.content, list):
                    text_parts = []
                    for content_block in response.content:
                        if hasattr(content_block, 'text'):
                            text_parts.append(content_block.text)
                        elif hasattr(content_block, 'content'):
                            text_parts.append(str(content_block.content))
                    return '\n'.join(text_parts)
                else:
                    return str(response.content)
            else:
                raise ClaudeExtractionError("No content in Claude response")
        except Exception as e:
            raise ClaudeExtractionError(f"Failed to extract response text: {str(e)}")
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate JSON response from Claude."""
        try:
            # Clean up response text (remove markdown formatting if present)
            cleaned_text = response_text.strip()
            
            # Handle markdown code blocks
            if '```json' in cleaned_text:
                start_idx = cleaned_text.find('```json') + 7
                end_idx = cleaned_text.find('```', start_idx)
                if end_idx != -1:
                    cleaned_text = cleaned_text[start_idx:end_idx].strip()
            elif '```' in cleaned_text:
                # Generic code block
                parts = cleaned_text.split('```')
                if len(parts) >= 3:
                    cleaned_text = parts[1].strip()
            
            # Find JSON object boundaries
            if not cleaned_text.startswith('{'):
                start_idx = cleaned_text.find('{')
                if start_idx != -1:
                    cleaned_text = cleaned_text[start_idx:]
            
            if not cleaned_text.endswith('}'):
                end_idx = cleaned_text.rfind('}')
                if end_idx != -1:
                    cleaned_text = cleaned_text[:end_idx + 1]
            
            # Parse JSON
            data = json.loads(cleaned_text)
            
            # Validate required fields
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")
            
            if 'report_name' not in data:
                raise ValueError("Missing required field: report_name")
            
            if 'issues' not in data or not isinstance(data['issues'], list):
                raise ValueError("Missing or invalid field: issues")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            raise ClaudeExtractionError(f"Invalid JSON response: {str(e)}")
        except ValueError as e:
            raise ClaudeExtractionError(f"Response validation error: {str(e)}")
    
    def _create_report_model(self, data: Dict[str, Any], source_filename: Optional[str]) -> HomeInspectionReport:
        """Convert extracted data to Pydantic model with validation."""
        try:
            # Convert issues to Pydantic models
            issues = []
            for issue_data in data.get('issues', []):
                # Handle missing fields with defaults
                issue = InspectionIssue(
                    issue_name=issue_data.get('issue_name', 'Unknown Issue'),
                    issue_type=issue_data.get('issue_type', 'General'),
                    issue_description=issue_data.get('issue_description', 'No description available'),
                    issue_summary=issue_data.get('issue_summary', 'No summary available'),
                    issue_images=issue_data.get('issue_images', [])
                )
                issues.append(issue)
            
            # Create report model
            report = HomeInspectionReport(
                report_name=data.get('report_name', 'Unknown Report'),
                issues=issues,
                source_pdf=source_filename,
                extraction_model=self.model_name
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to create report model: {str(e)}")
            raise ClaudeExtractionError(f"Model validation error: {str(e)}")
    
    def extract_sync(
        self, 
        markdown_content: str, 
        image_references: Optional[List[str]] = None,
        source_filename: Optional[str] = None,
        max_retries: int = 3
    ) -> ExtractionResult:
        """
        Synchronous wrapper for extraction.
        
        Args:
            markdown_content: Parsed markdown content from PDF
            image_references: List of image filenames/references
            source_filename: Original PDF filename
            max_retries: Maximum number of retry attempts
            
        Returns:
            ExtractionResult with success status and extracted data
        """
        try:
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.extract_async(markdown_content, image_references, source_filename, max_retries)
                )
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Synchronous extraction failed: {str(e)}")
            return ExtractionResult(
                success=False,
                error_message=str(e),
                processing_time=0,
                model_used='claude-3.5-sonnet',
                pdf_complexity='complex'
            )
    
    def validate_api_connection(self) -> bool:
        """
        Validate API connection with a simple test call.
        
        Returns:
            True if connection is working, False otherwise
        """
        try:
            # Check if client is properly initialized
            if not hasattr(self, 'client') or self.client is None:
                logger.error("Claude client not properly initialized")
                return False
                
            # Simple test message
            response = self.client.messages.create(
                model=self.model_config['model'],
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}],
                temperature=0.1
            )
            
            if response and response.content and len(response.content) > 0:
                logger.info("Claude API validation successful")
                return True
            else:
                logger.error("No response content from Claude API")
                return False
                
        except Exception as e:
            logger.error(f"Claude API validation failed: {str(e)}")
            return False


# Utility functions
def create_claude_extractor(api_key: Optional[str] = None, model_name: str = 'claude-3-5-sonnet-20241022') -> ClaudeExtractor:
    """Create a Claude extractor instance with specified model."""
    return ClaudeExtractor(api_key=api_key, model_name=model_name)


async def extract_with_claude(
    markdown_content: str, 
    image_references: Optional[List[str]] = None,
    source_filename: Optional[str] = None,
    api_key: Optional[str] = None
) -> ExtractionResult:
    """
    Quick utility to extract data using Claude.
    
    Args:
        markdown_content: Parsed markdown content from PDF
        image_references: List of image filenames/references
        source_filename: Original PDF filename
        api_key: Optional API key
        
    Returns:
        ExtractionResult
    """
    extractor = create_claude_extractor(api_key)
    return await extractor.extract_async(markdown_content, image_references, source_filename)


if __name__ == "__main__":
    # Test the extractor
    async def test_claude():
        extractor = create_claude_extractor()
        
        # Test API connection
        if not extractor.validate_api_connection():
            print("ERROR: Claude API validation failed")
            return
        
        # Test extraction with sample complex content
        sample_content = """
        # Commercial Property Inspection Report - Complex Analysis
        
        ## Executive Summary
        This comprehensive inspection of the commercial facility identified multiple 
        safety-critical issues requiring immediate attention, including electrical 
        system deficiencies, HVAC maintenance requirements, and structural concerns.
        
        ## Electrical Systems Analysis
        ### Priority Issues
        - Main electrical panel shows overcrowding with multiple circuits improperly installed
        - Several breakers appear oversized for wire gauge used (safety hazard)
        - 600-volt systems require professional evaluation for code compliance
        - Ground fault circuit interrupters missing in wet locations
        
        ## HVAC Systems Assessment
        ### Commercial Unit Deficiencies
        - Air handling units showing signs of inadequate maintenance
        - Multiple filter replacements needed immediately
        - Ductwork connections loose in several areas
        - Commercial kitchen exhaust system requires professional cleaning
        
        ## Structural Analysis
        ### Foundation and Support Systems
        - Minor settling cracks observed in east foundation wall
        - Support beam connections require inspection by structural engineer
        - Commercial roof membrane showing deterioration
        - Fire safety systems need testing and certification
        """
        
        sample_images = [
            "electrical_panel_main.jpg", "hvac_unit_1.jpg", 
            "foundation_crack.jpg", "roof_membrane.jpg"
        ]
        
        result = await extractor.extract_async(
            markdown_content=sample_content,
            image_references=sample_images,
            source_filename="complex_commercial.pdf"
        )
        
        print(f"Claude extraction result: {result.success}")
        if result.success and result.report:
            print(f"Report: {result.report.report_name}")
            print(f"Issues found: {len(result.report.issues)}")
            for issue in result.report.issues:
                print(f"  - {issue.issue_name} ({issue.issue_type})")
        else:
            print(f"Error: {result.error_message}")
    
    # Run test
    asyncio.run(test_claude())