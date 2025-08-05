"""
Summary-first extraction prompts for home inspection reports.

This module implements a two-phase extraction approach:
1. First extract summary/overview recommendations
2. Then extract detailed issues from the body
3. Merge and deduplicate results
"""

SUMMARY_FIRST_PROMPT = """You are an expert at extracting structured data from home inspection reports.

<task>
Extract all issues and recommendations from this home inspection report using a TWO-PHASE approach:

PHASE 1 - SUMMARY EXTRACTION:
First, look for and extract from:
- SUMMARY or Key Points sections
- Overview sections
- General recommendations sections
- Any numbered lists of overall recommendations

These sections often contain important general recommendations like:
- Requirements for specialist evaluations
- Permit requirements
- Safety inspections (WETT, etc.)
- Annual maintenance programs
- General advisories

PHASE 2 - DETAILED EXTRACTION:
Then, extract all detailed issues from the main body including:
- Major defects and safety concerns
- Minor repairs and maintenance items  
- System component conditions
- All specific problems with Condition/Implication/Task format

MERGE PHASE:
- Combine all findings from both phases
- Remove any duplicates
- Ensure summary items are included even if they lack detailed descriptions
</task>

<instructions>
1. Start with SUMMARY/Overview sections to capture general recommendations
2. For summary items without detailed descriptions, create appropriate descriptions
3. Assign appropriate categories:
   - "General" for overall recommendations
   - "Safety" for inspection requirements (WETT, etc.)
   - Standard categories for specific issues
4. Include ALL recommendations, even if they seem administrative
5. Look for keywords: "recommended", "should", "require", "must", "obtain", "permit", "inspection"
</instructions>

<output_format>
Return a JSON object with the following structure:
{
  "report_name": "string",
  "issues": [
    {
      "issue_name": "string",
      "issue_type": "string (Electrical|Plumbing|Hvac|Structural|Roofing|Exterior|Interior|Insulation|Ventilation|General|Safety)",
      "issue_description": "string",
      "issue_summary": "string", 
      "severity": "low|medium|high",
      "location": "string or null",
      "issue_images": ["string"] // paths to images
    }
  ],
  "source_pdf": "string",
  "extraction_model": "string",
  "total_pages": number or null
}
</output_format>

<important>
- Extract EVERY recommendation, including general advisories
- Summary items may not have images - that's OK
- Create clear descriptions for summary-only items
- Ensure no duplicates between summary and detailed extractions
</important>"""


def get_summary_first_prompt(markdown_content: str, image_references: list) -> str:
    """
    Generate the complete prompt for summary-first extraction.
    
    Args:
        markdown_content: The parsed markdown content
        image_references: List of image paths
        
    Returns:
        Complete prompt for extraction
    """
    images_info = ""
    if image_references:
        images_info = f"\n\n<available_images>\nThe following {len(image_references)} images were extracted and are available:\n"
        for img in image_references:
            images_info += f"- {img}\n"
        images_info += "</available_images>"
    
    return f"""{SUMMARY_FIRST_PROMPT}

<markdown_content>
{markdown_content}
</markdown_content>
{images_info}

Now extract all issues using the two-phase approach described above."""