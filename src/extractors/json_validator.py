"""
JSON Validation and QA Module

Uses a fast LLM to validate and fix JSON syntax from extraction results.
"""

import json
import logging
from typing import Dict, Any, Optional
import os

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class JSONValidator:
    """Validates and fixes JSON using Claude Sonnet as QA."""
    
    def __init__(self):
        """Initialize with Claude client."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.client = Anthropic(api_key=api_key)
            self.enabled = True
        else:
            self.client = None
            self.enabled = False
            logger.warning("ANTHROPIC_API_KEY not set - JSON validation disabled")
    
    def validate_and_fix(self, json_string: str) -> Optional[Dict[str, Any]]:
        """
        Validate and fix JSON using Claude Sonnet.
        
        Args:
            json_string: Potentially malformed JSON string
            
        Returns:
            Fixed and parsed JSON object or None if fix fails
        """
        if not self.enabled:
            return None
            
        # First try to parse as-is
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            pass
            
        # Use Claude to fix the JSON
        try:
            prompt = f"""Fix the following JSON to make it valid. Return ONLY the corrected JSON without any explanation or markdown formatting.

Common issues to fix:
- Unterminated strings
- Missing commas between elements
- Trailing commas before closing brackets/braces
- Unescaped quotes in strings
- Unclosed brackets or braces

Input JSON:
{json_string}

Output only valid JSON:"""
            
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            fixed_json = response.content[0].text.strip()
            
            # Remove markdown formatting if present
            if fixed_json.startswith('```json'):
                fixed_json = fixed_json[7:]
            if fixed_json.startswith('```'):
                fixed_json = fixed_json[3:]
            if fixed_json.endswith('```'):
                fixed_json = fixed_json[:-3]
            fixed_json = fixed_json.strip()
            
            # Try to parse the fixed JSON
            result = json.loads(fixed_json)
            logger.info("Successfully fixed JSON using Claude Sonnet")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Claude fix still invalid JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Claude validation failed: {e}")
            return None


def validate_json(json_string: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to validate and fix JSON.
    
    Args:
        json_string: Potentially malformed JSON string
        
    Returns:
        Fixed and parsed JSON object or None if fix fails
    """
    validator = JSONValidator()
    return validator.validate_and_fix(json_string)