"""
Qwen 3-32B integration via Groq API for home inspection report extraction.

This module handles extraction of structured data from PDF inspection reports
using Qwen 3-32B through the Groq API as the primary extractor in our
validation-based pipeline.
"""

import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

try:
    from groq import Groq, AsyncGroq
except ImportError:
    Groq = None
    AsyncGroq = None
    logging.warning("groq not available. Install with: pip install groq")

from .schemas import HomeInspectionReport, InspectionIssue, ExtractionResult
from .extraction_prompts import ExtractionPromptTemplate

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class QwenExtractionError(Exception):
    """Custom exception for Qwen extraction errors."""
    pass


class QwenExtractor:
    """
    Qwen 3-32B extractor via Groq API for home inspection reports.
    
    Serves as the primary extractor in our validation pipeline,
    processing all PDFs regardless of complexity before validation.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Qwen extractor.
        
        Args:
            api_key: Groq API key. If None, will try to get from environment.
        """
        if not Groq:
            raise ValueError("Groq SDK not available. Install with: pip install groq")
            
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("Groq API key not found. Set GROQ_API_KEY environment variable.")
        
        # Initialize Groq clients
        self.client = Groq(api_key=self.api_key)
        self.async_client = AsyncGroq(api_key=self.api_key)
        
        # Model configuration
        self.model_name = "qwen/qwen3-32b"  # Correct model name from Groq
        
        # Model configuration optimized for extraction tasks
        self.generation_config = {
            'model': self.model_name,
            'temperature': 0.1,  # Low temperature for consistency
            'max_tokens': 4096,
            'top_p': 0.8,
            'stream': False,
            'response_format': {'type': 'json_object'}  # Request JSON response
        }
        
        logger.info("Qwen 3-32B extractor via Groq API initialized successfully")
    
    
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
        
        # Validate prompt length (Groq has token limits)
        if len(prompt) > 200000:  # Conservative limit for Groq
            logger.warning(f"Prompt very long ({len(prompt)} chars), truncating")
            # Truncate content if needed
            truncated_content = markdown_content[:100000] + "\n\n[CONTENT TRUNCATED DUE TO LENGTH]"
            prompt = ExtractionPromptTemplate.get_home_inspection_extraction_prompt(
                markdown_content=truncated_content,
                image_references=image_references,
                report_filename=source_filename
            )
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Qwen extraction attempt {attempt + 1}/{max_retries + 1} for {source_filename or 'unknown'}")
                
                # Generate response via Groq API
                response_text = await self._generate_with_retry(prompt)
                
                if not response_text:
                    raise QwenExtractionError("Empty response from Qwen")
                
                # Parse JSON response
                extracted_data = self._parse_response(response_text)
                
                # Validate and convert to Pydantic models
                report = self._create_report_model(extracted_data, source_filename)
                
                processing_time = time.time() - start_time
                
                logger.info(f"Qwen extraction successful for {source_filename or 'unknown'} "
                           f"in {processing_time:.2f}s. Found {len(report.issues)} issues.")
                
                return ExtractionResult(
                    success=True,
                    report=report,
                    processing_time=processing_time,
                    model_used='qwen-3-32b-groq',
                    pdf_complexity='dynamic'  # No complexity classification in validation approach
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"Qwen extraction attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All Qwen extraction attempts failed for {source_filename or 'unknown'}")
        
        # All attempts failed
        processing_time = time.time() - start_time
        return ExtractionResult(
            success=False,
            error_message=f"Qwen extraction failed after {max_retries + 1} attempts: {str(last_error)}",
            processing_time=processing_time,
            model_used='qwen-3-32b-groq',
            pdf_complexity='dynamic'
        )
    
    async def _generate_with_retry(self, prompt: str) -> str:
        """Generate response with Groq API using official client."""
        try:
            # Prepare messages
            messages = [
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
            
            # Make API request using async client
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.generation_config['temperature'],
                max_tokens=self.generation_config['max_tokens'],
                top_p=self.generation_config['top_p'],
                stream=False,
                response_format={'type': 'json_object'}
            )
            
            # Extract response text
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
            else:
                raise QwenExtractionError("No response content in API result")
                    
        except Exception as e:
            error_str = str(e)
            if 'rate limit' in error_str.lower() or 'quota' in error_str.lower():
                raise QwenExtractionError(f"Rate limit or quota exceeded: {error_str}")
            elif 'invalid' in error_str.lower() and 'key' in error_str.lower():
                raise QwenExtractionError("Invalid API key")
            elif 'timeout' in error_str.lower():
                raise QwenExtractionError("Request timed out")
            else:
                raise QwenExtractionError(f"Groq API error: {error_str}")
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate JSON response from Qwen."""
        try:
            # Clean up response text (remove markdown formatting if present)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
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
            raise QwenExtractionError(f"Invalid JSON response: {str(e)}")
        except ValueError as e:
            raise QwenExtractionError(f"Response validation error: {str(e)}")
    
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
                extraction_model='qwen-3-32b-groq'
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to create report model: {str(e)}")
            raise QwenExtractionError(f"Model validation error: {str(e)}")
    
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
                model_used='qwen-3-32b-groq',
                pdf_complexity='dynamic'
            )
    
    async def validate_api_connection(self) -> bool:
        """
        Validate API connection and model availability.
        
        Returns:
            True if connection is working, False otherwise
        """
        try:
            # Simple validation test without JSON format
            test_messages = [
                {
                    'role': 'user',
                    'content': 'Hello, please respond with a simple greeting.'
                }
            ]
            
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=test_messages,
                max_tokens=50,
                temperature=0.1
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message.content:
                logger.info("Qwen API validation successful")
                return True
            else:
                logger.error("API validation failed - no response choices or content")
                return False
                
        except Exception as e:
            logger.error(f"API validation failed: {str(e)}")
            return False
    
    async def close(self):
        """Close Groq client connections."""
        # Groq clients don't need explicit closing, but we can clear references
        pass


# Utility functions
def create_qwen_extractor(api_key: Optional[str] = None) -> QwenExtractor:
    """Create a Qwen extractor instance."""
    return QwenExtractor(api_key=api_key)


async def extract_with_qwen(
    markdown_content: str, 
    image_references: Optional[List[str]] = None,
    source_filename: Optional[str] = None,
    api_key: Optional[str] = None
) -> ExtractionResult:
    """
    Quick utility to extract data using Qwen.
    
    Args:
        markdown_content: Parsed markdown content from PDF
        image_references: List of image filenames/references
        source_filename: Original PDF filename
        api_key: Optional API key
        
    Returns:
        ExtractionResult
    """
    extractor = create_qwen_extractor(api_key)
    try:
        return await extractor.extract_async(markdown_content, image_references, source_filename)
    finally:
        await extractor.close()


if __name__ == "__main__":
    # Test the extractor
    async def test_qwen():
        extractor = create_qwen_extractor()
        
        # Test API connection
        if not await extractor.validate_api_connection():
            print("ERROR: Qwen API validation failed")
            return
        
        # Test extraction with sample content
        sample_content = """
        # Home Inspection Report - Test Property
        
        ## Electrical System
        - Knob and tube wiring found in basement requiring replacement
        - GFCI outlets missing in bathrooms
        
        ## Plumbing
        - Minor leak under kitchen sink
        - Low water pressure in master bathroom
        """
        
        sample_images = ["electrical_01.jpg", "plumbing_kitchen.jpg"]
        
        result = await extractor.extract_async(
            markdown_content=sample_content,
            image_references=sample_images,
            source_filename="test.pdf"
        )
        
        print(f"Extraction result: {result.success}")
        if result.success and result.report:
            print(f"Report: {result.report.report_name}")
            print(f"Issues found: {len(result.report.issues)}")
            for issue in result.report.issues:
                print(f"  - {issue.issue_name} ({issue.issue_type})")
        else:
            print(f"Error: {result.error_message}")
        
        await extractor.close()
    
    # Run test
    asyncio.run(test_qwen())