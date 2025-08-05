"""
JSON Repair Module

Fixes common JSON syntax errors from LLM outputs:
- Unterminated strings
- Missing commas
- Trailing commas
- Unescaped quotes in strings
"""

import json
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class JSONRepair:
    """Repairs common JSON syntax errors from LLM outputs."""
    
    @staticmethod
    def repair(json_string: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to repair and parse JSON string.
        
        Args:
            json_string: Potentially malformed JSON string
            
        Returns:
            Parsed JSON object or None if repair fails
        """
        if not json_string:
            return None
            
        # Try parsing as-is first
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            logger.debug(f"Initial parse failed: {e}")
            
        # Apply repairs
        repaired = json_string
        
        # Fix unterminated strings
        repaired = JSONRepair._fix_unterminated_strings(repaired)
        
        # Fix missing commas between array/object elements
        repaired = JSONRepair._fix_missing_commas(repaired)
        
        # Fix trailing commas
        repaired = JSONRepair._fix_trailing_commas(repaired)
        
        # Fix unescaped quotes in strings
        repaired = JSONRepair._fix_unescaped_quotes(repaired)
        
        # Try parsing repaired JSON
        try:
            result = json.loads(repaired)
            logger.info("Successfully repaired JSON")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"Repair attempt 1 failed: {e}")
            
        # More aggressive fixes
        repaired = JSONRepair._aggressive_repair(json_string)
        
        try:
            result = json.loads(repaired)
            logger.info("Successfully repaired JSON with aggressive fixes")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"All repair attempts failed: {e}")
            return None
    
    @staticmethod
    def _fix_unterminated_strings(json_str: str) -> str:
        """Fix unterminated string literals."""
        # This is complex - we need to find strings that start but don't end
        lines = json_str.split('\n')
        fixed_lines = []
        in_string = False
        escape_next = False
        
        for line in lines:
            fixed_line = []
            i = 0
            while i < len(line):
                char = line[i]
                
                if escape_next:
                    escape_next = False
                    fixed_line.append(char)
                    i += 1
                    continue
                    
                if char == '\\':
                    escape_next = True
                    fixed_line.append(char)
                    i += 1
                    continue
                    
                if char == '"':
                    in_string = not in_string
                    fixed_line.append(char)
                    i += 1
                    continue
                    
                fixed_line.append(char)
                i += 1
            
            # If we're still in a string at end of line, close it
            if in_string and not line.rstrip().endswith('"'):
                fixed_line.append('"')
                in_string = False
                
            fixed_lines.append(''.join(fixed_line))
            
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _fix_missing_commas(json_str: str) -> str:
        """Add missing commas between array/object elements."""
        # Pattern: "value" "nextkey" or ] [ or } {
        patterns = [
            (r'"\s*\n\s*"', '",\n"'),  # String followed by string
            (r'}\s*\n\s*{', '},\n{'),  # Object followed by object  
            (r']\s*\n\s*\[', '],\n['), # Array followed by array
            (r'"\s*\n\s*{', '",\n{'),  # String followed by object
            (r'}\s*\n\s*"', '},\n"'),  # Object followed by string
            (r'([0-9])\s*\n\s*"', r'\1,\n"'),  # Number followed by string
            (r'([0-9])\s*\n\s*{', r'\1,\n{'),  # Number followed by object
            (r'(true|false|null)\s*\n\s*"', r'\1,\n"'),  # Boolean/null followed by string
        ]
        
        result = json_str
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
            
        return result
    
    @staticmethod
    def _fix_trailing_commas(json_str: str) -> str:
        """Remove trailing commas before closing brackets/braces."""
        # Pattern: , followed by ] or }
        result = re.sub(r',\s*]', ']', json_str)
        result = re.sub(r',\s*}', '}', result)
        return result
    
    @staticmethod
    def _fix_unescaped_quotes(json_str: str) -> str:
        """Fix unescaped quotes inside string values."""
        # This is tricky - we need to identify quotes that are inside strings
        # For now, we'll do a simple fix for common cases
        
        # Fix quotes in the middle of obvious strings
        # Pattern: "text " text" -> "text \" text"
        lines = json_str.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Skip lines that look like they're just keys or simple values
            if line.strip().startswith('"') and line.strip().endswith('",'):
                # Check if there are quotes in the middle
                content = line.strip()[1:-2]  # Remove outer quotes and comma
                if '"' in content:
                    content = content.replace('"', '\\"')
                    line = line.replace(line.strip()[1:-2], content)
                    
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _aggressive_repair(json_str: str) -> str:
        """More aggressive repairs as last resort."""
        result = json_str
        
        # Ensure all strings are properly closed
        # Count quotes and add one if odd number
        quote_count = result.count('"') - result.count('\\"')
        if quote_count % 2 == 1:
            # Find the last unclosed string and close it
            lines = result.split('\n')
            for i in range(len(lines) - 1, -1, -1):
                if '"' in lines[i]:
                    if not lines[i].rstrip().endswith('"') and not lines[i].rstrip().endswith('",'):
                        lines[i] = lines[i].rstrip() + '"'
                        break
            result = '\n'.join(lines)
        
        # Ensure JSON ends with closing brace
        result = result.rstrip()
        if not result.endswith('}'):
            # Count opening and closing braces
            open_braces = result.count('{')
            close_braces = result.count('}')
            if open_braces > close_braces:
                result += '\n' + '}' * (open_braces - close_braces)
        
        # Fix any arrays that aren't closed
        open_brackets = result.count('[')
        close_brackets = result.count(']')
        if open_brackets > close_brackets:
            result += ']' * (open_brackets - close_brackets)
            
        return result


def repair_json(json_string: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to repair JSON string.
    
    Args:
        json_string: Potentially malformed JSON string
        
    Returns:
        Parsed JSON object or None if repair fails
    """
    return JSONRepair.repair(json_string)