#!/usr/bin/env python3
"""Debug script to understand why extraction is returning 0 issues."""

import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv

from src.extractors.pdf_parser import LlamaParseIntegration
from src.extractors.extraction_prompts import ExtractionPromptTemplate
from src.extractors.gemini_extractor import GeminiExtractor

load_dotenv()

async def debug_extraction(pdf_path: str):
    """Debug the extraction pipeline step by step."""
    
    print(f"=== DEBUGGING EXTRACTION FOR: {pdf_path} ===\n")
    
    # Step 1: Parse PDF
    print("STEP 1: Parsing PDF with LlamaParse...")
    parser = LlamaParseIntegration()
    parse_result = await parser.parse_pdf_async(pdf_path)
    
    if not parse_result['success']:
        print(f"ERROR: PDF parsing failed: {parse_result.get('error_message')}")
        return
    
    markdown_content = parse_result['markdown_content']
    images = parse_result.get('images', [])
    
    print(f"[OK] PDF parsed successfully")
    print(f"  - Content length: {len(markdown_content)} characters")
    print(f"  - Images found: {len(images)}")
    
    # Save markdown for inspection
    debug_dir = Path("debug_output")
    debug_dir.mkdir(exist_ok=True)
    
    markdown_file = debug_dir / "parsed_markdown.md"
    with open(markdown_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"  - Saved markdown to: {markdown_file}")
    
    # Show first 2000 characters of markdown
    print("\nMARKDOWN PREVIEW (first 2000 chars):")
    print("-" * 50)
    try:
        print(markdown_content[:2000])
    except UnicodeEncodeError:
        # Encode problematic characters
        preview = markdown_content[:2000].encode('ascii', 'replace').decode('ascii')
        print(preview)
    print("-" * 50)
    
    # Step 2: Generate extraction prompt
    print("\nSTEP 2: Generating extraction prompt...")
    prompt = ExtractionPromptTemplate.get_home_inspection_extraction_prompt(
        markdown_content=markdown_content,
        image_references=images,
        report_filename=Path(pdf_path).name
    )
    
    prompt_file = debug_dir / "extraction_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"[OK] Prompt generated ({len(prompt)} characters)")
    print(f"  - Saved to: {prompt_file}")
    
    # Step 3: Test Gemini extraction
    print("\nSTEP 3: Testing Gemini extraction...")
    
    # Create extractor with debug logging
    extractor = GeminiExtractor()
    
    # Test with a simple direct call first
    print("Testing direct Gemini API call...")
    
    import google.generativeai as genai
    
    # Configure with API key
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    
    # Create model with simpler config
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        generation_config={
            'temperature': 0.1,
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 8192,  # Increased for PDFs with many issues
            # Remove response_mime_type to see raw response
        }
    )
    
    try:
        # Send prompt directly
        response = model.generate_content(prompt)
        
        print("[OK] Gemini responded")
        print("\nRAW RESPONSE:")
        print("-" * 50)
        # Handle encoding for Windows terminal
        try:
            print(response.text)
        except UnicodeEncodeError:
            # Replace problematic characters for Windows terminal
            safe_text = response.text.encode('ascii', 'replace').decode('ascii')
            print(safe_text)
        print("-" * 50)
        
        # Save raw response
        response_file = debug_dir / "gemini_raw_response.txt"
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\nSaved raw response to: {response_file}")
        
        # Try to parse as JSON
        try:
            # Clean up response
            cleaned = response.text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            print(f"\n[OK] Successfully parsed JSON")
            print(f"  - Report name: {data.get('report_name', 'N/A')}")
            print(f"  - Issues found: {len(data.get('issues', []))}")
            
            if data.get('issues'):
                print("\nISSUES EXTRACTED:")
                for i, issue in enumerate(data['issues'][:5], 1):  # Show first 5
                    print(f"\n  {i}. {issue.get('issue_name', 'N/A')}")
                    print(f"     Type: {issue.get('issue_type', 'N/A')}")
                    print(f"     Summary: {issue.get('issue_summary', 'N/A')}")
                    
                if len(data['issues']) > 5:
                    print(f"\n  ... and {len(data['issues']) - 5} more issues")
            
            # Save parsed JSON
            json_file = debug_dir / "parsed_response.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"\nSaved parsed JSON to: {json_file}")
            
        except json.JSONDecodeError as e:
            print(f"\n[ERROR] Failed to parse JSON: {e}")
            
    except Exception as e:
        print(f"\n[ERROR] Gemini API error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run debug on first PDF."""
    pdf_path = "data/1.pdf"
    
    if not Path(pdf_path).exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return
    
    await debug_extraction(pdf_path)


if __name__ == "__main__":
    asyncio.run(main())