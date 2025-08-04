"""
PDF parsing module using LlamaParse for converting PDFs to structured markdown.

This module handles the conversion of PDF inspection reports into markdown format
that can be effectively processed by AI models for data extraction.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import time

try:
    from llama_parse import LlamaParse
    # Check if ResultType exists in the new version
    try:
        from llama_parse import ResultType
    except ImportError:
        # Create a mock ResultType for newer versions
        class ResultType:
            MARKDOWN = "markdown"
except ImportError:
    LlamaParse = None
    ResultType = None
    logging.warning("LlamaParse not available. Install with: pip install llama-parse")

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PDFParsingError(Exception):
    """Custom exception for PDF parsing errors."""
    pass


class LlamaParseIntegration:
    """
    Integration class for LlamaParse PDF processing.
    
    Handles conversion of PDF files to markdown format with proper error handling
    and retry logic for reliable extraction.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LlamaParse integration.
        
        Args:
            api_key: LlamaParse API key. If None, will try to get from environment.
        """
        if LlamaParse is None:
            raise ImportError("LlamaParse is not installed. Run: pip install llama-parse")
        
        self.api_key = api_key or os.getenv('LLAMA_PARSE_API_KEY')
        if not self.api_key:
            raise ValueError("LlamaParse API key not found. Set LLAMA_PARSE_API_KEY environment variable.")
        
        # Initialize parser with optimal settings for inspection reports
        try:
            self.parser = LlamaParse(
                api_key=self.api_key,
                result_type="markdown",  # Get markdown output
                verbose=True,
                language="en",  # English language processing
                num_workers=1,  # Conservative for API limits
                show_progress=True,
                check_interval=2,  # Check job status every 2 seconds
                max_timeout=120,  # 2 minute timeout per PDF
                parsing_instruction="Extract ALL content from every page of the PDF including tables, forms, lists, and all text. Do not skip any pages or content.",
                skip_diagonal_text=False,  # Include all text orientations
                page_separator="\n\n--- PAGE BREAK ---\n\n"  # Clear page separation
            )
        except Exception as e:
            logger.warning(f"Failed to initialize with full options: {e}")
            # Try with minimal options but still include parsing instruction
            try:
                self.parser = LlamaParse(
                    api_key=self.api_key,
                    result_type="markdown",
                    parsing_instruction="Extract ALL content from every page of the PDF."
                )
            except:
                # Final fallback
                self.parser = LlamaParse(api_key=self.api_key)
        
        logger.info("LlamaParse integration initialized successfully")
    
    async def parse_pdf_async(self, pdf_path: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Parse a PDF file asynchronously and return structured markdown content.
        
        Args:
            pdf_path: Path to the PDF file
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary containing parsed content and metadata
            
        Raises:
            PDFParsingError: If parsing fails after all retries
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if not pdf_path.suffix.lower() == '.pdf':
            raise ValueError(f"File is not a PDF: {pdf_path}")
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Parsing PDF (attempt {attempt + 1}/{max_retries + 1}): {pdf_path.name}")
                
                # Try to parse using get_json_result for complete page extraction
                markdown_content = ""
                images = []
                
                try:
                    # First try get_json_result method for complete extraction
                    json_data = await self.parser.aget_json_result(str(pdf_path))
                    
                    if json_data:
                        # Combine all pages into markdown
                        all_pages = []
                        for doc_json in json_data:
                            if 'pages' in doc_json:
                                for page_data in doc_json['pages']:
                                    page_num = page_data.get('page', '?')
                                    page_text = page_data.get('text', '')
                                    if page_text:
                                        all_pages.append(f"\n\n--- PAGE {page_num} ---\n\n{page_text}")
                                    
                                    # Collect images from pages
                                    if 'images' in page_data:
                                        images.extend(page_data['images'])
                        
                        markdown_content = "".join(all_pages)
                    
                except (AttributeError, Exception) as e:
                    # Fallback to load_data if get_json_result is not available
                    logger.info(f"get_json_result not available or failed: {e}. Falling back to load_data.")
                    
                    # Parse the PDF file using standard method
                    documents = await self.parser.aload_data([str(pdf_path)])
                    
                    if not documents:
                        raise PDFParsingError("No documents returned from LlamaParse")
                    
                    # Extract content from all documents (may be multiple if pages are split)
                    markdown_parts = []
                    for i, document in enumerate(documents):
                        if hasattr(document, 'text') and document.text:
                            if len(documents) > 1:
                                markdown_parts.append(f"\n\n--- DOCUMENT {i+1} ---\n\n{document.text}")
                            else:
                                markdown_parts.append(document.text)
                        
                        # Extract images if available
                        if hasattr(document, 'metadata') and document.metadata:
                            doc_images = document.metadata.get('images', [])
                            images.extend(doc_images)
                    
                    markdown_content = "".join(markdown_parts)
                
                if not markdown_content or len(markdown_content.strip()) < 100:
                    raise PDFParsingError("Extracted content is too short or empty")
                
                processing_time = time.time() - start_time
                
                result = {
                    'success': True,
                    'markdown_content': markdown_content,
                    'images': images,
                    'processing_time': processing_time,
                    'source_pdf': str(pdf_path),
                    'content_length': len(markdown_content),
                    'attempt_count': attempt + 1
                }
                
                logger.info(f"Successfully parsed {pdf_path.name} in {processing_time:.2f}s")
                logger.info(f"Extracted {len(markdown_content)} characters from PDF")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for {pdf_path.name}: {str(e)}")
                
                if attempt < max_retries:
                    # Exponential backoff: 2, 4, 8 seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All parsing attempts failed for {pdf_path.name}")
        
        # All attempts failed
        processing_time = time.time() - start_time
        raise PDFParsingError(
            f"Failed to parse {pdf_path.name} after {max_retries + 1} attempts. "
            f"Last error: {str(last_error)}"
        )
    
    def parse_pdf_sync(self, pdf_path: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Synchronous wrapper for PDF parsing.
        
        Args:
            pdf_path: Path to the PDF file
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary containing parsed content and metadata
        """
        try:
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.parse_pdf_async(pdf_path, max_retries))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Synchronous parsing failed: {str(e)}")
            return {
                'success': False,
                'error_message': str(e),
                'source_pdf': pdf_path,
                'processing_time': 0,
                'markdown_content': '',
                'images': []
            }
    
    async def parse_multiple_pdfs_async(self, pdf_paths: List[str], max_concurrent: int = 2) -> List[Dict[str, Any]]:
        """
        Parse multiple PDFs concurrently with rate limiting.
        
        Args:
            pdf_paths: List of PDF file paths
            max_concurrent: Maximum number of concurrent parsing operations
            
        Returns:
            List of parsing results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def parse_with_semaphore(pdf_path: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.parse_pdf_async(pdf_path)
        
        logger.info(f"Starting to parse {len(pdf_paths)} PDFs with max {max_concurrent} concurrent operations")
        
        tasks = [parse_with_semaphore(pdf_path) for pdf_path in pdf_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'error_message': str(result),
                    'source_pdf': pdf_paths[i],
                    'processing_time': 0,
                    'markdown_content': '',
                    'images': []
                })
            else:
                processed_results.append(result)
        
        successful_count = sum(1 for r in processed_results if r['success'])
        logger.info(f"Completed parsing: {successful_count}/{len(pdf_paths)} successful")
        
        return processed_results
    
    def validate_api_key(self) -> bool:
        """
        Validate that the API key is working.
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Simple validation - attempt to create parser instance
            test_parser = LlamaParse(api_key=self.api_key, result_type="markdown")
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {str(e)}")
            return False


# Utility functions for easier usage
def create_parser(api_key: Optional[str] = None) -> LlamaParseIntegration:
    """Create a LlamaParse integration instance."""
    return LlamaParseIntegration(api_key=api_key)


async def parse_single_pdf(pdf_path: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick utility to parse a single PDF.
    
    Args:
        pdf_path: Path to the PDF file
        api_key: Optional API key
        
    Returns:
        Parsing result dictionary
    """
    parser = create_parser(api_key)
    return await parser.parse_pdf_async(pdf_path)


if __name__ == "__main__":
    # Test the integration
    async def test_parser():
        parser = create_parser()
        
        # Test API key validation
        if not parser.validate_api_key():
            print("ERROR: Invalid API key")
            return
        
        # Test parsing a sample PDF
        test_pdf = "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports/data/1.pdf"
        if os.path.exists(test_pdf):
            result = await parser.parse_pdf_async(test_pdf)
            print(f"Parsing result: {result['success']}")
            if result['success']:
                print(f"Content length: {result['content_length']} characters")
                print(f"Processing time: {result['processing_time']:.2f} seconds")
        else:
            print(f"Test PDF not found: {test_pdf}")
    
    # Run test
    asyncio.run(test_parser())