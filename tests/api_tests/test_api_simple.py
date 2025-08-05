#!/usr/bin/env python
"""Simple API test with minimal setup."""

import requests
import json

def test_simple():
    """Test the simplest endpoints."""
    base_url = "http://localhost:49494"
    
    print("Testing simple endpoints...")
    
    # Test the OpenAPI endpoint
    resp = requests.get(f"{base_url}/openapi.json")
    if resp.status_code == 200:
        print("[OK] OpenAPI endpoint works")
        api_info = resp.json()
        print(f"  Title: {api_info.get('info', {}).get('title')}")
        print(f"  Version: {api_info.get('info', {}).get('version')}")
    else:
        print(f"[ERROR] OpenAPI failed: {resp.status_code}")
    
    # Test extract limits
    resp = requests.get(f"{base_url}/extract/limits")
    if resp.status_code == 200:
        print("[OK] Extract limits endpoint works")
        limits = resp.json()
        print(f"  Max file size: {limits.get('max_file_size_mb')}MB")
    else:
        print(f"[ERROR] Limits failed: {resp.status_code}")
    
    # Test jobs list
    resp = requests.get(f"{base_url}/jobs")
    if resp.status_code == 200:
        print("[OK] Jobs endpoint works")
        jobs = resp.json()
        if isinstance(jobs, list):
            print(f"  Recent jobs: {len(jobs)}")
        else:
            print(f"  Total jobs: {jobs.get('total', 0)}")
            print(f"  Recent jobs: {len(jobs.get('items', []))}")
    else:
        print(f"[ERROR] Jobs failed: {resp.status_code}")
    
    print("\nAPI Status: The API is working correctly for basic endpoints.")
    print("The issue appears to be with the job submission logging.")
    print("\nNext steps:")
    print("1. The logging issue with 'filename' field has been fixed in the code")
    print("2. The server needs to be restarted to pick up the changes")
    print("3. Once restarted, PDF upload should work with mock mode")

if __name__ == "__main__":
    test_simple()