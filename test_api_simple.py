#!/usr/bin/env python3
"""Simple API test - equivalent to curl commands"""
import requests
import json

# Test 1: Health check
print("=== Test 1: Health Check ===")
print("Equivalent to: curl http://127.0.0.1:49494/health")
try:
    response = requests.get("http://127.0.0.1:49494/health", timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Test 2: Detailed Health ===")
print("Equivalent to: curl http://127.0.0.1:49494/health/detailed")
try:
    response = requests.get("http://127.0.0.1:49494/health/detailed", timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Test 3: Stats ===")
print("Equivalent to: curl http://127.0.0.1:49494/stats")
try:
    response = requests.get("http://127.0.0.1:49494/stats", timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total jobs: {data.get('total_jobs', 0)}")
    print(f"Success rate: {data.get('success_rate', 0)}%")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Upload PDF
print("\n=== Test 4: Upload PDF ===")
print("Equivalent to: curl -X POST http://127.0.0.1:49494/extract -F 'file=@data/2.pdf' -F 'mock_mode=true'")
try:
    with open("data/2.pdf", "rb") as f:
        files = {"file": ("2.pdf", f, "application/pdf")}
        data = {"mock_mode": "true"}
        response = requests.post("http://127.0.0.1:49494/extract", files=files, data=data, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Job ID: {result.get('job_id')}")
            print(f"Status URL: {result.get('status_url')}")
        else:
            print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Curl command equivalents ===")
print("# Health check:")
print("curl http://127.0.0.1:49494/health")
print("\n# Upload PDF:")
print("curl -X POST http://127.0.0.1:49494/extract \\")
print("  -F 'file=@data/2.pdf' \\")
print("  -F 'enable_claude_fallback=true' \\")
print("  -F 'confidence_threshold=70.0'")
print("\n# Check job status:")
print("curl http://127.0.0.1:49494/status/{job_id}")