#!/usr/bin/env python3
"""Test API with various endpoints - simulating curl commands"""
import requests
import json
import time
import sys
from pathlib import Path

BASE_URL = "http://localhost:49494"

def test_health():
    """Test /health endpoint"""
    print("Testing GET /health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return True
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to API server at", BASE_URL)
        print("Make sure the server is running with:")
        print("  ./venv/Scripts/python.exe run_api.py --port 49494")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_detailed_health():
    """Test /health/detailed endpoint"""
    print("\nTesting GET /health/detailed...")
    try:
        response = requests.get(f"{BASE_URL}/health/detailed")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")

def test_stats():
    """Test /stats endpoint"""
    print("\nTesting GET /stats...")
    try:
        response = requests.get(f"{BASE_URL}/stats")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")

def test_extract_pdf(pdf_path="data/2.pdf"):
    """Test PDF extraction endpoint"""
    print(f"\nTesting POST /extract with {pdf_path}...")
    
    # Check if file exists
    if not Path(pdf_path).exists():
        print(f"ERROR: PDF file not found: {pdf_path}")
        return None
    
    # Upload PDF
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        data = {
            'enable_claude_fallback': 'true',
            'confidence_threshold': '70.0'
        }
        
        try:
            print("Uploading PDF...")
            response = requests.post(f"{BASE_URL}/extract", files=files, data=data)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return result.get('job_id')
            else:
                print(f"Error Response: {response.text}")
                return None
        except Exception as e:
            print(f"ERROR: {e}")
            return None

def test_job_status(job_id):
    """Test job status endpoint"""
    print(f"\nTesting GET /status/{job_id}...")
    
    max_attempts = 60  # 5 minutes with 5 second intervals
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{BASE_URL}/status/{job_id}")
            print(f"\nAttempt {attempt + 1}: Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                job_info = result.get('job_info', {})
                status = job_info.get('status', 'unknown')
                progress = job_info.get('progress', 0)
                
                print(f"Job Status: {status} ({progress:.1f}%)")
                
                if status == 'completed':
                    print("\nExtraction completed successfully!")
                    data = result.get('data', {})
                    report = data.get('report', {})
                    issues = report.get('issues', [])
                    print(f"Found {len(issues)} issues")
                    
                    # Print first issue as example
                    if issues:
                        print("\nFirst issue example:")
                        print(json.dumps(issues[0], indent=2))
                    
                    # Print metadata
                    metadata = data.get('metadata', {})
                    print(f"\nMetadata:")
                    print(json.dumps(metadata, indent=2))
                    
                    return True
                
                elif status == 'failed':
                    error_info = result.get('error', {})
                    print(f"Extraction failed: {error_info.get('message', 'Unknown error')}")
                    return False
                
                # Still processing
                time.sleep(5)
            else:
                print(f"Error Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"ERROR: {e}")
            return False
    
    print("Timeout: Job did not complete within 5 minutes")
    return False

def test_list_jobs():
    """Test list jobs endpoint"""
    print("\nTesting GET /jobs...")
    try:
        response = requests.get(f"{BASE_URL}/jobs?limit=5")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"ERROR: {e}")

def main():
    print("=== API Testing Script (Simulating curl commands) ===")
    print(f"Base URL: {BASE_URL}")
    
    # Test health endpoint first
    if not test_health():
        return
    
    # Test other endpoints
    test_detailed_health()
    test_stats()
    
    # Test PDF extraction
    job_id = test_extract_pdf()
    if job_id:
        print(f"\nJob ID: {job_id}")
        print("Polling for results...")
        test_job_status(job_id)
    
    # List recent jobs
    test_list_jobs()
    
    print("\n=== Testing complete ===")

if __name__ == "__main__":
    main()