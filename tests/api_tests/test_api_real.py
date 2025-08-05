#!/usr/bin/env python
"""Test API without mock mode."""

import requests
import time
import json

def test_real_upload():
    """Test real PDF upload."""
    base_url = "http://localhost:49494"
    
    # Test basic endpoints first
    print("Testing basic endpoints...")
    
    # Test limits
    resp = requests.get(f"{base_url}/extract/limits")
    print(f"Limits endpoint: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  Limits: {json.dumps(resp.json(), indent=2)}")
    
    # Test job stats
    resp = requests.get(f"{base_url}/stats")
    print(f"\nStats endpoint: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  Stats: {json.dumps(resp.json(), indent=2)}")
    
    # Test upload with real processing
    print("\n\nTesting PDF upload (MOCK MODE)...")
    
    import os
    pdf_path = os.path.join(os.path.dirname(__file__), "data", "1.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found at: {pdf_path}")
        # Try alternate path
        pdf_path = "/mnt/d/Experimental-Software/Fora_Travel_Assignments/data/2.pdf"
        if not os.path.exists(pdf_path):
            print("Cannot find test PDF file")
            return
            
    print(f"Using PDF: {pdf_path}")
    
    with open(pdf_path, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        data = {
            "mock_mode": "true",  # Use mock mode first
            "enable_claude_fallback": "false",
            "confidence_threshold": "50.0"
        }
        
        resp = requests.post(f"{base_url}/extract", files=files, data=data)
        print(f"Upload status: {resp.status_code}")
        
        if resp.status_code in [200, 202]:
            result = resp.json()
            print(f"Success! Job ID: {result.get('job_id')}")
            print(f"Message: {result.get('message')}")
            
            # Check job status
            job_id = result.get('job_id')
            if job_id:
                print(f"\nChecking job status...")
                time.sleep(2)
                
                status_resp = requests.get(f"{base_url}/status/{job_id}")
                print(f"Status check: {status_resp.status_code}")
                if status_resp.status_code == 200:
                    print(f"Job details: {json.dumps(status_resp.json(), indent=2)}")
        else:
            print(f"Error response: {json.dumps(resp.json(), indent=2)}")

if __name__ == "__main__":
    test_real_upload()