#!/usr/bin/env python
"""Test configuration loading."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from api.core.config import get_settings
    print("Import successful")
    
    # Test getting settings
    settings = get_settings()
    print(f"Settings loaded successfully:")
    print(f"  API Title: {settings.api_title}")
    print(f"  API Version: {settings.api_version}")
    print(f"  Environment: {settings.environment}")
    print(f"  Port: {settings.port}")
    print(f"  Mock Mode: {settings.mock_mode}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()