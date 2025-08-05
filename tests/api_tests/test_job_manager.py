#!/usr/bin/env python
"""Test JobManager directly."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.services.job_manager import JobManager

async def test_job_manager():
    """Test job manager creation and submission."""
    print("Testing JobManager...")
    
    try:
        # Create job manager
        job_manager = JobManager(
            max_concurrent_jobs=3,
            job_timeout=300,
            cleanup_interval=60
        )
        print("[OK] JobManager created")
        
        # Start job manager
        await job_manager.start()
        print("[OK] JobManager started")
        
        # Test job submission
        job_id = await job_manager.submit_job(
            filename="test.pdf",
            file_path="data/2.pdf",
            options={'mock_mode': True}
        )
        print(f"[OK] Job submitted: {job_id}")
        
        # Check job status
        job = await job_manager.get_job_status(job_id)
        if job:
            print(f"[OK] Job status: {job.status}")
        else:
            print("[ERROR] Job not found")
            
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_job_manager())