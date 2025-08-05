#!/usr/bin/env python
"""Test simple API functionality."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.core.config import get_settings
from api.services.job_manager import JobManager

async def test_components():
    """Test individual components."""
    print("Testing components...")
    
    # Test settings
    try:
        settings = get_settings()
        print(f"[OK] Settings loaded: API version {settings.api_version}")
    except Exception as e:
        print(f"[ERROR] Settings error: {e}")
    
    # Test job manager
    try:
        job_manager = JobManager(
            max_concurrent_jobs=3,
            job_timeout=300,
            cleanup_interval=60
        )
        print("[OK] JobManager created")
        
        # Start job manager
        await job_manager.start()
        print("[OK] JobManager started")
        
        # Validate pipeline
        result = await job_manager.validate_pipeline()
        print(f"[OK] Pipeline validation: {result['overall_status']}")
        if not result['overall_status']:
            print(f"  Errors: {result.get('errors', [])}")
            
    except Exception as e:
        print(f"[ERROR] JobManager error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_components())