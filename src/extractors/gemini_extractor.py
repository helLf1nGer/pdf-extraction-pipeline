"""
Gemini 2.5 Pro integration for home inspection report extraction.

This module handles extraction of structured data from medium complexity
PDF inspection reports using Google's Gemini 2.5 Pro model.
"""

import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None
    HarmCategory = None
    HarmBlockThreshold = None
    logging.warning("google.generativeai not available. Install with: pip install google-generativeai")

from .schemas import HomeInspectionReport, InspectionIssue, ExtractionResult, ImageLocation
from .extraction_prompts import ExtractionPromptTemplate
from .image_matcher import ImageMatcher
from .json_repair import repair_json
from .json_validator import validate_json

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class GeminiExtractionError(Exception):
    """Custom exception for Gemini extraction errors."""
    pass


class GeminiExtractor:
    """
    Gemini extractor supporting both Flash and Pro models.
    
    - Flash: For easy documents with clear structure
    - Pro: For medium/complex documents requiring deeper analysis
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = 'gemini-2.5-flash'):
        """
        Initialize Gemini extractor.
        
        Args:
            api_key: Google AI API key. If None, will try to get from environment.
        """
        if genai is None:
            raise ImportError("google.generativeai is not installed. Run: pip install google-generativeai")
        
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Google AI API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Model configuration optimized for extraction tasks
        self.generation_config = {
            'temperature': 0.1,  # Low temperature for consistency
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 8192,  # Increased for PDFs with many issues
            'response_mime_type': 'application/json',  # Request JSON response
        }
        
        # Safety settings for technical content
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Store model name
        self.model_name = model_name
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        
        logger.info(f"Gemini extractor initialized with model: {self.model_name}")
    
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
        
        # Validate prompt length
        if len(prompt) > 900000:  # Conservative limit for Gemini
            logger.warning(f"Prompt very long ({len(prompt)} chars), may hit limits")
            # Truncate content if needed
            truncated_content = markdown_content[:400000] + "\n\n[CONTENT TRUNCATED DUE TO LENGTH]"
            prompt = ExtractionPromptTemplate.get_home_inspection_extraction_prompt(
                markdown_content=truncated_content,
                image_references=image_references,
                report_filename=source_filename
            )
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Gemini extraction attempt {attempt + 1}/{max_retries + 1} for {source_filename or 'unknown'}")
                
                # Generate response
                response = await self._generate_with_retry(prompt)
                
                if not response or not response.text:
                    raise GeminiExtractionError("Empty response from Gemini")
                
                # Parse JSON response
                extracted_data = self._parse_response(response.text)
                
                # Validate and convert to Pydantic models
                report = self._create_report_model(extracted_data, source_filename, image_references)
                
                processing_time = time.time() - start_time
                
                logger.info(f"Gemini extraction successful for {source_filename or 'unknown'} "
                           f"in {processing_time:.2f}s. Found {len(report.issues)} issues.")
                
                return ExtractionResult(
                    success=True,
                    report=report,
                    processing_time=processing_time,
                    model_used=self.model_name,
                    pdf_complexity='medium'
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini extraction attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All Gemini extraction attempts failed for {source_filename or 'unknown'}")
        
        # All attempts failed
        processing_time = time.time() - start_time
        return ExtractionResult(
            success=False,
            error_message=f"Gemini extraction failed after {max_retries + 1} attempts: {str(last_error)}",
            processing_time=processing_time,
            model_used='gemini-2.5-pro',
            pdf_complexity='medium'
        )
    
    async def _generate_with_retry(self, prompt: str, timeout: int = 120) -> Any:
        """Generate response with timeout and basic retry logic."""
        try:
            # Use async generation for better timeout control
            response = await asyncio.wait_for(
                self.model.generate_content_async(prompt),
                timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            raise GeminiExtractionError(f"Gemini request timed out after {timeout} seconds")
        except Exception as e:
            if 'quota' in str(e).lower() or 'rate limit' in str(e).lower():
                raise GeminiExtractionError(f"Rate limit or quota exceeded: {str(e)}")
            elif 'safety' in str(e).lower():
                raise GeminiExtractionError(f"Content blocked by safety filters: {str(e)}")
            else:
                raise GeminiExtractionError(f"Gemini API error: {str(e)}")
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and validate JSON response from Gemini."""
        try:
            # Clean up response text (remove markdown formatting if present)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Try normal parsing first
            data = None
            try:
                data = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Initial JSON parse failed: {str(e)}")
                # Try JSON repair
                logger.info("Attempting JSON repair...")
                data = repair_json(cleaned_text)
                
                if data is None:
                    # Try Claude validation as last resort
                    logger.info("JSON repair failed, attempting Claude validation...")
                    data = validate_json(cleaned_text)
                    
                    if data is None:
                        raise GeminiExtractionError(f"All JSON fix attempts failed - Invalid JSON response: {str(e)}")
                    else:
                        logger.info("Claude JSON validation successful!")
                else:
                    logger.info("JSON repair successful!")
            
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
            raise GeminiExtractionError(f"Invalid JSON response: {str(e)}")
        except ValueError as e:
            raise GeminiExtractionError(f"Response validation error: {str(e)}")
    
    def _create_report_model(
        self, 
        data: Dict[str, Any], 
        source_filename: Optional[str],
        image_references: Optional[List[str]] = None
    ) -> HomeInspectionReport:
        """Convert extracted data to Pydantic model with validation and enhanced image matching."""
        try:
            # Convert issues to Pydantic models
            issues = []
            for issue_data in data.get('issues', []):
                # Parse expected image locations
                expected_locations = []
                for loc_data in issue_data.get('expected_image_locations', []):
                    if isinstance(loc_data, dict):
                        location = ImageLocation(
                            page_number=loc_data.get('page_number', 1),
                            location_description=loc_data.get('location_description'),
                            section_context=loc_data.get('section_context')
                        )
                        expected_locations.append(location)
                
                # Handle missing fields with defaults
                issue = InspectionIssue(
                    issue_name=issue_data.get('issue_name', 'Unknown Issue'),
                    issue_type=issue_data.get('issue_type', 'General'),
                    issue_description=issue_data.get('issue_description', 'No description available'),
                    issue_summary=issue_data.get('issue_summary', 'No summary available'),
                    severity=issue_data.get('severity', 'medium'),
                    location=issue_data.get('location'),
                    issue_images=issue_data.get('issue_images', []),  # Legacy format
                    expected_image_locations=expected_locations
                )
                issues.append(issue)
            
            # Apply enhanced image matching if image references are available
            if image_references and any(issue.expected_image_locations for issue in issues):
                logger.info("Applying enhanced image matching based on model-provided locations")
                image_matcher = ImageMatcher()
                issues = image_matcher.enhance_image_associations(issues, image_references)
                
                # Log matching statistics
                stats = image_matcher.get_matching_statistics(issues)
                logger.info(f"Enhanced image matching results: {stats['total_enhanced_matches']} matches, "
                           f"avg confidence: {stats['average_confidence']:.1f}")
            
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
            raise GeminiExtractionError(f"Model validation error: {str(e)}")
    
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
                model_used='gemini-2.5-pro',
                pdf_complexity='medium'
            )
    
    def validate_api_connection(self) -> bool:
        """
        Validate API connection and model availability.
        
        Returns:
            True if connection is working, False otherwise
        """
        try:
            # Try to list models to validate API key
            models = list(genai.list_models())
            gemini_models = [m for m in models if 'gemini' in m.name.lower()]
            
            if gemini_models:
                logger.info(f"API validation successful. Found {len(gemini_models)} Gemini models.")
                return True
            else:
                logger.error("No Gemini models found in API response")
                return False
                
        except Exception as e:
            logger.error(f"API validation failed: {str(e)}")
            return False


# Utility functions
def create_gemini_extractor(api_key: Optional[str] = None, model_name: str = 'gemini-2.0-flash-exp') -> GeminiExtractor:
    """Create a Gemini extractor instance with specified model."""
    return GeminiExtractor(api_key=api_key, model_name=model_name)


async def extract_with_gemini(
    markdown_content: str, 
    image_references: Optional[List[str]] = None,
    source_filename: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: str = 'gemini-2.0-flash-exp'
) -> ExtractionResult:
    """
    Quick utility to extract data using Gemini.
    
    Args:
        markdown_content: Parsed markdown content from PDF
        image_references: List of image filenames/references
        source_filename: Original PDF filename
        api_key: Optional API key
        
    Returns:
        ExtractionResult
    """
    extractor = create_gemini_extractor(api_key, model_name)
    return await extractor.extract_async(markdown_content, image_references, source_filename)


if __name__ == "__main__":
    # Test the extractor
    async def test_gemini():
        extractor = create_gemini_extractor()
        
        # Test API connection
        if not extractor.validate_api_connection():
            print("ERROR: Gemini API validation failed")
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
    
    # Run test
    asyncio.run(test_gemini())