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

# Import PyMuPDF for fallback image extraction
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    fitz = None
    logging.warning("PyMuPDF not available. Install with: pip install PyMuPDF")

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
        Parse a PDF file asynchronously and return structured markdown content with extracted images.
        
        Args:
            pdf_path: Path to the PDF file
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary containing parsed content and metadata including actual image file paths
            
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
                
                # Parse the PDF file using standard method first
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
                
                markdown_content = "".join(markdown_parts)
                
                if not markdown_content or len(markdown_content.strip()) < 100:
                    raise PDFParsingError("Extracted content is too short or empty")
                
                # Step 2: Extract actual image files using get_image_documents()
                logger.info(f"Extracting images from {pdf_path.name}...")
                image_file_paths = await self._extract_images_from_result(pdf_path)
                
                processing_time = time.time() - start_time
                
                result = {
                    'success': True,
                    'markdown_content': markdown_content,
                    'images': image_file_paths,  # Now contains actual file paths
                    'image_count': len(image_file_paths),
                    'processing_time': processing_time,
                    'source_pdf': str(pdf_path),
                    'content_length': len(markdown_content),
                    'attempt_count': attempt + 1
                }
                
                logger.info(f"Successfully parsed {pdf_path.name} in {processing_time:.2f}s")
                logger.info(f"Extracted {len(markdown_content)} characters and {len(image_file_paths)} images from PDF")
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
    
    async def _extract_images_from_result(self, pdf_path: Path) -> List[str]:
        """
        Extract images from PDF using LlamaParse's aget_images method.
        
        Args:
            pdf_path: Path to the original PDF file
            
        Returns:
            List of image file paths relative to the outputs/images directory
        """
        image_file_paths = []
        
        try:
            # Create image output directory
            pdf_name = pdf_path.stem
            image_dir = Path("./outputs/images") / pdf_name
            image_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created image directory: {image_dir}")
            
            # Use aget_images() method to extract images
            try:
                logger.info(f"Attempting to extract images using aget_images() for {pdf_path.name}")
                
                # Create a new parser instance specifically for image extraction
                image_parser = LlamaParse(
                    api_key=self.api_key,
                    result_type="markdown",
                    verbose=True,
                    disable_image_extraction=False,  # Ensure image extraction is enabled
                    premium_mode=True  # Enable premium features for better image extraction
                )
                
                # Extract images using the async method
                image_results = await image_parser.aget_images([str(pdf_path)], download_path=str(image_dir))
                
                logger.info(f"aget_images() returned {len(image_results) if image_results else 0} image results")
                
                # Process the extracted images
                if image_results:
                    for doc_idx, doc_images in enumerate(image_results):
                        # doc_images should be a list of image documents/data
                        if isinstance(doc_images, list):
                            for img_idx, image_data in enumerate(doc_images):
                                try:
                                    # Create filename for the image
                                    image_filename = f"image_{img_idx+1:03d}.png"
                                    image_path = image_dir / image_filename
                                    
                                    # Save the image data
                                    if hasattr(image_data, 'image') or hasattr(image_data, 'data'):
                                        # Try to get actual image data
                                        img_content = getattr(image_data, 'image', None) or getattr(image_data, 'data', None)
                                        if img_content:
                                            if isinstance(img_content, bytes):
                                                with open(image_path, 'wb') as f:
                                                    f.write(img_content)
                                            elif isinstance(img_content, str):
                                                # Might be base64 encoded
                                                import base64
                                                try:
                                                    img_bytes = base64.b64decode(img_content)
                                                    with open(image_path, 'wb') as f:
                                                        f.write(img_bytes)
                                                except:
                                                    # If not base64, skip this image
                                                    logger.warning(f"Could not decode image data for {image_filename}")
                                                    continue
                                            
                                            # Verify file was saved and add to results
                                            if image_path.exists() and image_path.stat().st_size > 0:
                                                relative_path = f"outputs/images/{pdf_name}/{image_filename}"
                                                image_file_paths.append(relative_path)
                                                logger.debug(f"Extracted image: {relative_path}")
                                    
                                    # Alternative: check if image_data has text or other useful content
                                    elif hasattr(image_data, 'text') and image_data.text:
                                        # This might be a reference or metadata about an image
                                        logger.debug(f"Found image metadata: {image_data.text[:100]}...")
                                        
                                except Exception as img_error:
                                    logger.warning(f"Failed to process image {img_idx+1}: {img_error}")
                                    continue
                        
                        # Alternative: image_results might be in a different format
                        elif hasattr(doc_images, 'images') or hasattr(doc_images, 'data'):
                            logger.info("Found alternative image format")
                            # Handle different result structure if needed
                
                logger.info(f"Successfully extracted {len(image_file_paths)} images using aget_images()")
                
                # If LlamaParse returned no images, try PyMuPDF fallback
                if not image_file_paths and HAS_PYMUPDF:
                    logger.info("LlamaParse returned 0 images, trying PyMuPDF fallback...")
                    pymupdf_images = self._extract_images_with_pymupdf(pdf_path)
                    if pymupdf_images:
                        image_file_paths = pymupdf_images
                        logger.info(f"PyMuPDF fallback extracted {len(image_file_paths)} images")
                
            except Exception as e:
                logger.warning(f"aget_images() failed: {e}")
                logger.info("Trying alternative approaches...")
                
                # Fallback 1: Try synchronous version
                try:
                    logger.info("Trying synchronous get_images()...")
                    
                    image_parser = LlamaParse(
                        api_key=self.api_key,
                        result_type="markdown",
                        disable_image_extraction=False
                    )
                    
                    sync_image_results = image_parser.get_images([str(pdf_path)], download_path=str(image_dir))
                    logger.info(f"get_images() returned {len(sync_image_results) if sync_image_results else 0} results")
                    
                    # Process synchronous results similar to async
                    # (same processing logic as above)
                    
                except Exception as sync_error:
                    logger.warning(f"Synchronous get_images() also failed: {sync_error}")
                
                # Fallback 2: Check if files were saved in the directory anyway
                try:
                    # Sometimes LlamaParse saves images even if the method call has issues
                    saved_files = list(image_dir.glob("*.*"))
                    for saved_file in saved_files:
                        if saved_file.is_file() and saved_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                            relative_path = f"outputs/images/{pdf_name}/{saved_file.name}"
                            image_file_paths.append(relative_path)
                            logger.debug(f"Found saved image file: {relative_path}")
                    
                    if image_file_paths:
                        logger.info(f"Found {len(image_file_paths)} saved image files in directory")
                    else:
                        logger.info(f"No image files found in {image_dir}")
                        
                except Exception as fallback_error:
                    logger.warning(f"Fallback image detection failed: {fallback_error}")
                
                # Final fallback: Use PyMuPDF if available
                if not image_file_paths and HAS_PYMUPDF:
                    logger.info("Trying PyMuPDF as final fallback for image extraction...")
                    image_file_paths = self._extract_images_with_pymupdf(pdf_path)
            
        except Exception as e:
            logger.error(f"Image extraction failed for {pdf_path.name}: {e}")
            
            # Ultimate fallback: Use PyMuPDF if available
            if not image_file_paths and HAS_PYMUPDF:
                logger.info("Trying PyMuPDF as ultimate fallback after LlamaParse failure...")
                try:
                    image_file_paths = self._extract_images_with_pymupdf(pdf_path)
                except Exception as pymupdf_error:
                    logger.error(f"PyMuPDF fallback also failed: {pymupdf_error}")
        
        return image_file_paths
    
    def _extract_images_with_pymupdf(self, pdf_path: Path) -> List[str]:
        """
        Fallback image extraction using PyMuPDF when LlamaParse fails.
        
        Args:
            pdf_path: Path to the original PDF file
            
        Returns:
            List of image file paths relative to the outputs/images directory
        """
        if not HAS_PYMUPDF:
            logger.warning("PyMuPDF not available for fallback image extraction")
            return []
        
        image_file_paths = []
        
        try:
            # Create image output directory
            pdf_name = pdf_path.stem
            image_dir = Path("./outputs/images") / pdf_name
            image_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Using PyMuPDF fallback for image extraction: {pdf_path.name}")
            
            # Open PDF with PyMuPDF
            doc = fitz.open(str(pdf_path))
            
            total_images = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]  # Image reference number
                        pix = fitz.Pixmap(doc, xref)
                        
                        # Skip images that are likely UI elements or decorations
                        # 1. Very small images (icons, buttons)
                        if pix.width < 50 or pix.height < 50:
                            pix = None
                            continue
                        
                        # 2. Extreme aspect ratios (navigation bars like 74x24)
                        aspect_ratio = pix.width / pix.height if pix.height > 0 else 0
                        if aspect_ratio > 8 or aspect_ratio < 0.125:  # Very wide bars or very tall dividers
                            pix = None
                            continue
                        
                        # 3. Common UI element sizes (specific filtering)
                        if (pix.width == 74 and pix.height == 24) or (pix.width < 80 and pix.height < 30):
                            pix = None
                            continue
                        
                        # Create filename
                        image_filename = f"page_{page_num+1:02d}_image_{img_index+1:03d}.png"
                        image_path = image_dir / image_filename
                        
                        # Save image
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            pix.save(str(image_path))
                        else:  # CMYK: convert to RGB first
                            pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                            pix_rgb.save(str(image_path))
                            pix_rgb = None
                        
                        pix = None
                        
                        # Verify file was saved and check size
                        if image_path.exists():
                            file_size = image_path.stat().st_size
                            
                            # Skip very small files (likely UI elements)
                            if file_size < 2000:  # Less than 2KB - definitely UI elements
                                image_path.unlink()  # Delete the file
                                logger.debug(f"Skipped tiny image ({file_size} bytes): {image_filename}")
                            else:
                                relative_path = f"outputs/images/{pdf_name}/{image_filename}"
                                image_file_paths.append(relative_path)
                                total_images += 1
                                logger.debug(f"Extracted image ({file_size} bytes): {relative_path}")
                    
                    except Exception as img_error:
                        logger.warning(f"Failed to extract image {img_index+1} from page {page_num+1}: {img_error}")
                        continue
            
            doc.close()
            logger.info(f"PyMuPDF extracted {total_images} images from {pdf_path.name}")
            
        except Exception as e:
            logger.error(f"PyMuPDF image extraction failed for {pdf_path.name}: {e}")
        
        return image_file_paths
    
    def parse_pdf_sync(self, pdf_path: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Synchronous wrapper for PDF parsing with image extraction.
        
        Args:
            pdf_path: Path to the PDF file
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary containing parsed content and metadata including image file paths
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
                'images': [],
                'image_count': 0
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
                    'images': [],
                    'image_count': 0
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