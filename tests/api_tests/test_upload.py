#!/usr/bin/env python
"""Test PDF upload to API."""

import requests
import os

def test_upload():
    """Test PDF upload endpoint."""
    url = "http://localhost:49494/extract"
    
    # Test with mock mode first
    print("Testing PDF upload with mock mode...")
    
    # Find a PDF file
    pdf_file = "data/2.pdf"
    if not os.path.exists(pdf_file):
        print(f"PDF file not found: {pdf_file}")
        return
    
    # Upload with mock mode
    with open(pdf_file, 'rb') as f:
        files = {'file': ('test.pdf', f, 'application/pdf')}
        data = {'mock_mode': 'true'}
        
        try:
            response = requests.post(url, files=files, data=data)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == 200:
                job_id = response.json().get('job_id')
                if job_id:
                    print(f"\nJob ID: {job_id}")
                    print("Use this to check status: GET /status/{job_id}")
                    
                    # Check status
                    status_url = f"http://localhost:49494/status/{job_id}"
                    status_response = requests.get(status_url)
                    print(f"\nStatus Response: {status_response.json()}")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()