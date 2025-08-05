#!/usr/bin/env python3
"""
API Key Validation Script

This script tests all required API keys to ensure they're properly configured
before running the full extraction pipeline.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

class APIKeyValidator:
    """Validates all required API keys for the extraction pipeline."""
    
    def __init__(self):
        self.results = {}
        self.required_keys = {
            'LLAMA_PARSE_API_KEY': 'LlamaParse (PDF parsing)',
            'GOOGLE_API_KEY': 'Google AI (Gemini)',
            'GEMINI_API_KEY': 'Google AI (Gemini - alternative)',
            'ANTHROPIC_API_KEY': 'Anthropic (Claude)',
        }
        self.optional_keys = {
            'OPENAI_API_KEY': 'OpenAI (optional backup)',
        }
    
    def check_environment_variables(self) -> Dict[str, Any]:
        """Check if all required environment variables are set."""
        print("🔍 Checking environment variables...")
        
        env_results = {
            'required': {},
            'optional': {},
            'missing_required': [],
            'all_required_present': True
        }
        
        # Check required keys
        for key, description in self.required_keys.items():
            value = os.getenv(key)
            if value and len(value.strip()) > 10:  # Basic validation
                env_results['required'][key] = {
                    'present': True,
                    'length': len(value),
                    'description': description,
                    'prefix': value[:8] + '...' if len(value) > 8 else value
                }
                print(f"  ✅ {key}: Found ({len(value)} chars)")
            else:
                env_results['required'][key] = {
                    'present': False,
                    'description': description
                }
                env_results['missing_required'].append(key)
                env_results['all_required_present'] = False
                print(f"  ❌ {key}: Missing or invalid")
        
        # Check optional keys
        for key, description in self.optional_keys.items():
            value = os.getenv(key)
            if value and len(value.strip()) > 10:
                env_results['optional'][key] = {
                    'present': True,
                    'length': len(value),
                    'description': description
                }
                print(f"  ✅ {key}: Found ({len(value)} chars) [OPTIONAL]")
            else:
                env_results['optional'][key] = {
                    'present': False,
                    'description': description
                }
                print(f"  ⚠️  {key}: Missing [OPTIONAL]")
        
        return env_results
    
    async def test_llamaparse_api(self) -> Dict[str, Any]:
        """Test LlamaParse API key."""
        print("\n🦙 Testing LlamaParse API...")
        
        api_key = os.getenv('LLAMA_PARSE_API_KEY')
        if not api_key:
            return {'success': False, 'error': 'API key not found'}
        
        try:
            # Try to import and create parser instance
            from llama_parse import LlamaParse
            from llama_parse.base import ResultType
            
            parser = LlamaParse(
                api_key=api_key,
                result_type=ResultType.MARKDOWN,
                verbose=False,
                check_interval=1,
                max_timeout=10
            )
            
            print("  ✅ LlamaParse client created successfully")
            return {'success': True, 'message': 'API key appears valid'}
            
        except ImportError:
            return {
                'success': False, 
                'error': 'LlamaParse not installed. Run: pip install llama-parse'
            }
        except Exception as e:
            return {'success': False, 'error': f'API validation failed: {str(e)}'}
    
    async def test_gemini_api(self) -> Dict[str, Any]:
        """Test Google Gemini API key."""
        print("\n🤖 Testing Google Gemini API...")
        
        api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            return {'success': False, 'error': 'API key not found'}
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=api_key)
            
            # Try to list models to validate key
            models = list(genai.list_models())
            gemini_models = [m for m in models if 'gemini' in m.name.lower()]
            
            if gemini_models:
                print(f"  ✅ Found {len(gemini_models)} Gemini models")
                print(f"  📋 Available: {', '.join([m.name.split('/')[-1] for m in gemini_models[:3]])}")
                return {'success': True, 'models': len(gemini_models)}
            else:
                return {'success': False, 'error': 'No Gemini models found'}
                
        except ImportError:
            return {
                'success': False, 
                'error': 'google-generativeai not installed. Run: pip install google-generativeai'
            }
        except Exception as e:
            return {'success': False, 'error': f'API validation failed: {str(e)}'}
    
    async def test_anthropic_api(self) -> Dict[str, Any]:
        """Test Anthropic Claude API key."""
        print("\n🧠 Testing Anthropic Claude API...")
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return {'success': False, 'error': 'API key not found'}
        
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # Test with a simple message
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            if response and response.content:
                print("  ✅ Claude API responding correctly")
                return {'success': True, 'message': 'API key working'}
            else:
                return {'success': False, 'error': 'Unexpected response format'}
                
        except ImportError:
            return {
                'success': False, 
                'error': 'anthropic not installed. Run: pip install anthropic'
            }
        except Exception as e:
            error_msg = str(e)
            if 'credit balance is too low' in error_msg.lower():
                return {
                    'success': False, 
                    'error': 'Insufficient credits in Anthropic account. Please add billing.'
                }
            elif 'authentication' in error_msg.lower():
                return {'success': False, 'error': 'Invalid API key'}
            else:
                return {'success': False, 'error': f'API test failed: {error_msg}'}
    
    async def test_openai_api(self) -> Dict[str, Any]:
        """Test OpenAI API key (optional)."""
        print("\n🔮 Testing OpenAI API (optional)...")
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return {'success': False, 'error': 'API key not found (optional)'}
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=api_key)
            
            # List models to validate key
            models = client.models.list()
            if models and models.data:
                print(f"  ✅ Found {len(models.data)} OpenAI models")
                return {'success': True, 'models': len(models.data)}
            else:
                return {'success': False, 'error': 'No models accessible'}
                
        except ImportError:
            return {
                'success': False, 
                'error': 'openai not installed. Run: pip install openai'
            }
        except Exception as e:
            return {'success': False, 'error': f'API test failed: {str(e)}'}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all API key validation tests."""
        print("🚀 Starting API Key Validation\n")
        
        # Check environment variables first
        env_results = self.check_environment_variables()
        
        if not env_results['all_required_present']:
            print(f"\n❌ Missing required environment variables:")
            for key in env_results['missing_required']:
                description = self.required_keys[key]
                print(f"   • {key} ({description})")
            print(f"\n📖 Please check API_SETUP.md for instructions on obtaining these keys.")
            return {
                'overall_success': False,
                'environment': env_results,
                'api_tests': {}
            }
        
        # Run API tests
        api_tests = {}
        
        # Test required APIs
        api_tests['llamaparse'] = await self.test_llamaparse_api()
        api_tests['gemini'] = await self.test_gemini_api()
        api_tests['anthropic'] = await self.test_anthropic_api()
        
        # Test optional APIs
        api_tests['openai'] = await self.test_openai_api()
        
        # Calculate overall success
        required_success = all([
            api_tests['llamaparse']['success'],
            api_tests['gemini']['success'],
            api_tests['anthropic']['success']
        ])
        
        print(f"\n{'='*50}")
        print("📊 VALIDATION SUMMARY")
        print(f"{'='*50}")
        
        for service, result in api_tests.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            service_name = service.upper()
            print(f"{service_name:12} | {status}")
            if not result['success']:
                print(f"             | Error: {result['error']}")
        
        print(f"{'='*50}")
        if required_success:
            print("🎉 All required APIs are working! You're ready to run the pipeline.")
        else:
            print("⚠️  Some required APIs failed. Please check the errors above.")
            print("📖 See API_SETUP.md for troubleshooting guidance.")
        
        return {
            'overall_success': required_success,
            'environment': env_results,
            'api_tests': api_tests
        }


def main():
    """Main function to run validation."""
    validator = APIKeyValidator()
    
    # Check if .env file exists
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ No .env file found!")
        print("📖 Please copy .env.template to .env and add your API keys.")
        print("   cp .env.template .env")
        return False
    
    # Run validation
    try:
        results = asyncio.run(validator.run_all_tests())
        return results['overall_success']
    except KeyboardInterrupt:
        print("\n\n⏹️  Validation interrupted by user.")
        return False
    except Exception as e:
        print(f"\n❌ Validation failed with error: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)