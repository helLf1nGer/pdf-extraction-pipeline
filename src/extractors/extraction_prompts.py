"""
Extraction prompt templates for home inspection report processing.

This module contains XML-structured prompts designed to ensure consistent
and accurate extraction of structured data from home inspection reports.
"""

from typing import Dict, List, Optional
import json


class ExtractionPromptTemplate:
    """Template manager for extraction prompts with XML formatting."""
    
    @staticmethod
    def get_home_inspection_extraction_prompt(
        markdown_content: str, 
        image_references: Optional[List[str]] = None,
        report_filename: Optional[str] = None
    ) -> str:
        """
        Generate XML-formatted extraction prompt for home inspection reports.
        
        Args:
            markdown_content: Parsed markdown content from the PDF
            image_references: List of image filenames/references found in the document
            report_filename: Original filename of the report
            
        Returns:
            XML-formatted prompt string
        """
        images_section = ""
        if image_references:
            images_list = '\n'.join([f"    - {img}" for img in image_references])
            images_section = f"""
  <images>
{images_list}
  </images>"""
        
        filename_section = ""
        if report_filename:
            filename_section = f"\n  <source_filename>{report_filename}</source_filename>"
        
        prompt = f"""<role>You are an expert at extracting structured data from home inspection reports.</role>

<context>
  <document_type>Home Inspection Report</document_type>{filename_section}
  <report_content>
{markdown_content}
  </report_content>{images_section}
</context>

<instructions>
  1. Extract ALL issues/findings from the report, including:
     - Major defects and safety concerns
     - Minor repairs and maintenance items
     - Recommendations for further evaluation
     - System component conditions and observations
  
  2. For each issue, extract the following fields:
     - issue_name: Clear, concise name/title of the issue
     - issue_type: Category (e.g., "Electrical", "Plumbing", "Structural", "HVAC", "Exterior", "Interior", "Safety")
     - issue_description: Detailed description maintaining original technical language
     - issue_summary: Brief 1-2 sentence summary of the issue and recommended action
     - severity: Priority level (low, medium, high) based on safety, cost, or urgency indicators
     - location: Specific location within the property where the issue was found
     - issue_images: List of associated image references based on proximity and context
  
  3. Extraction guidelines:
     - Maintain original technical terminology and wording where possible
     - Associate images with issues based on their proximity in the document and contextual relevance
     - Include priority/severity indicators if present in the original text
     - Group related sub-issues under appropriate main categories
     - Extract both immediate concerns and discretionary recommendations
  
  4. Quality requirements:
     - Ensure no duplicate issues
     - Verify all extracted text accurately reflects the original content
     - Include cost estimates or timeframes if mentioned in the report
     - Preserve inspector's specific observations and recommendations
</instructions>

<output_format>
{{
  "report_name": "string - Extract the report title, property address, or inspection company name",
  "issues": [
    {{
      "issue_name": "string - Concise name of the issue",
      "issue_type": "string - Category of the issue",
      "issue_description": "string - Detailed description from the report",
      "issue_summary": "string - Brief summary with recommended action",
      "severity": "string - Priority level: low, medium, or high",
      "location": "string - Specific location where issue was found (optional)",
      "issue_images": ["string"] - Array of associated image references
    }}
  ]
}}
</output_format>

<examples>
  <example_issue>
    {{
      "issue_name": "Knob and Tube Wiring in Basement",
      "issue_type": "Electrical",
      "issue_description": "Old knob and tube wiring was observed in the basement areas. This type of wiring is outdated and may not meet current safety standards. The wiring should be evaluated by a qualified electrician for compliance and safety.",
      "issue_summary": "Replace outdated knob and tube wiring with modern electrical system for safety compliance.",
      "severity": "high",
      "location": "Basement",
      "issue_images": ["electrical_basement_01.jpg", "knob_tube_wiring.jpg"]
    }}
  </example_issue>
</examples>

Now extract all issues from the provided home inspection report and return the results in the exact JSON format specified above."""
        
        return prompt
    
    @staticmethod
    def get_validation_prompt(extracted_json: str, original_content: str) -> str:
        """
        Generate validation prompt to check extraction accuracy.
        
        Args:
            extracted_json: The extracted JSON data
            original_content: Original report content
            
        Returns:
            Validation prompt string
        """
        return f"""<role>You are a quality assurance expert for data extraction systems.</role>

<task>Validate the accuracy and completeness of extracted home inspection data.</task>

<context>
  <original_report>
{original_content}
  </original_report>
  
  <extracted_data>
{extracted_json}
  </extracted_data>
</context>

<validation_criteria>
  1. Completeness: Are all significant issues from the original report included?
  2. Accuracy: Do the extracted descriptions match the original content?
  3. Categorization: Are issues properly categorized by type?
  4. Image Association: Are images correctly associated with relevant issues?
  5. Consistency: Is the data format consistent and properly structured?
</validation_criteria>

<output_format>
{{
  "validation_passed": boolean,
  "completeness_score": number (0-100),
  "accuracy_score": number (0-100),
  "issues_found": [
    {{
      "type": "string - missing_issue|incorrect_description|wrong_category|etc",
      "description": "string - Description of the validation issue",
      "severity": "string - low|medium|high"
    }}
  ],
  "recommendations": ["string - List of improvement recommendations"]
}}
</output_format>"""
    
    @staticmethod
    def get_complexity_classification_prompt(pdf_content: str, filename: str) -> str:
        """
        Generate prompt for classifying PDF complexity to route to appropriate model.
        
        Args:
            pdf_content: Parsed content from PDF
            filename: Name of the PDF file
            
        Returns:
            Classification prompt string
        """
        return f"""<role>You are an expert at analyzing document complexity for optimal AI model routing.</role>

<context>
  <document_filename>{filename}</document_filename>
  <document_content>
{pdf_content}
  </document_content>
</context>

<classification_criteria>
  <simple>
    - Text-heavy with minimal formatting
    - 0-5 issues/findings
    - Few or no tables, images, or complex layouts
    - Straightforward narrative structure
  </simple>
  
  <medium>
    - Mixed content with moderate complexity
    - 6-15 issues/findings
    - Some tables, images, or structured sections
    - Standard inspection report format
  </medium>
  
  <complex>
    - Heavy use of tables, complex layouts, or dense formatting
    - 16+ issues/findings
    - Multiple images requiring correlation
    - Technical diagrams or specialized content
    - Commercial property reports
    - Narrative formats requiring deep interpretation
  </complex>
</classification_criteria>

<instructions>
  1. Analyze the document structure, formatting complexity, and content density
  2. Estimate the number of issues/findings that would need extraction
  3. Assess the technical complexity and interpretation requirements
  4. Classify as SIMPLE, MEDIUM, or COMPLEX based on the criteria above
</instructions>

<output_format>
{{
  "complexity": "string - SIMPLE|MEDIUM|COMPLEX",
  "estimated_issues": number,
  "reasoning": "string - Brief explanation for the classification",
  "recommended_model": "string - qwen|gemini-2.5-pro|claude-3.5-sonnet"
}}
</output_format>"""


class PromptFormatter:
    """Utility class for formatting and validating prompts."""
    
    @staticmethod
    def format_json_for_prompt(data: Dict) -> str:
        """Format JSON data for inclusion in prompts."""
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @staticmethod
    def validate_prompt_length(prompt: str, max_tokens: int = 128000) -> bool:
        """
        Validate that prompt doesn't exceed token limits.
        
        Args:
            prompt: The prompt string
            max_tokens: Maximum allowed tokens (conservative estimate)
            
        Returns:
            True if prompt is within limits
        """
        # Rough estimation: 1 token ≈ 4 characters
        estimated_tokens = len(prompt) // 4
        return estimated_tokens <= max_tokens
    
    @staticmethod
    def truncate_content(content: str, max_chars: int = 400000) -> str:
        """
        Truncate content if it's too long while preserving structure.
        
        Args:
            content: Content to potentially truncate
            max_chars: Maximum characters allowed
            
        Returns:
            Truncated content with truncation notice if needed
        """
        if len(content) <= max_chars:
            return content
        
        truncated = content[:max_chars]
        return truncated + "\n\n[CONTENT TRUNCATED DUE TO LENGTH LIMITS]"


# Example usage and testing
if __name__ == "__main__":
    # Test prompt generation
    sample_markdown = """
    # Home Inspection Report
    
    ## Electrical System
    - Knob and tube wiring found in basement
    - GFCI outlets missing in bathrooms
    
    ## Plumbing
    - Minor leak observed under kitchen sink
    """
    
    sample_images = ["electrical_01.jpg", "plumbing_kitchen.jpg"]
    
    prompt = ExtractionPromptTemplate.get_home_inspection_extraction_prompt(
        markdown_content=sample_markdown,
        image_references=sample_images,
        report_filename="sample_report.pdf"
    )
    
    print("Generated extraction prompt:")
    print("=" * 50)
    print(prompt)
    print("=" * 50)
    print(f"Prompt length: {len(prompt)} characters")
    print(f"Within limits: {PromptFormatter.validate_prompt_length(prompt)}")