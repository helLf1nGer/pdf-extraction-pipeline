#!/usr/bin/env python
"""Debug API endpoint to see actual errors."""

import requests
import json

def test_health():
    """Test the health endpoint and show detailed error."""
    try:
        # Test basic health
        print("Testing health endpoint...")
        response = requests.get("http://localhost:49494/health/")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code != 200:
            print("\nTrying without trailing slash...")
            response = requests.get("http://localhost:49494/health")
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

def test_openapi():
    """Test OpenAPI endpoint."""
    try:
        print("\n\nTesting OpenAPI endpoint...")
        response = requests.get("http://localhost:49494/openapi.json")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"API Title: {data.get('info', {}).get('title')}")
            print(f"API Version: {data.get('info', {}).get('version')}")
            print(f"Available Paths: {list(data.get('paths', {}).keys())}")
        else:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_health()
    test_openapi()