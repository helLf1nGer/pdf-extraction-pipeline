# API curl Command Examples

## Quick Reference

### Start the Server
```bash
# Navigate to project directory
cd "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports"

# Start server (runs on port 49494 by default)
./venv/Scripts/python.exe run_api.py
```

### Basic API Testing

```bash
# 1. Health Check
curl http://127.0.0.1:49494/health

# 2. Upload 2.pdf
curl -X POST http://127.0.0.1:49494/extract \
  -F "file=@data/2.pdf" \
  -F "enable_claude_fallback=true" \
  -F "confidence_threshold=70.0"

# 3. Check Status (replace job_id with actual ID)
curl http://127.0.0.1:49494/status/job_12345678-1234-5678-9abc-123456789012

# 4. List Jobs
curl http://127.0.0.1:49494/jobs
```

### Complete Example with 2.pdf

```bash
# Upload and extract job ID using grep
RESPONSE=$(curl -s -X POST http://127.0.0.1:49494/extract \
  -F "file=@data/2.pdf" \
  -F "enable_claude_fallback=true" \
  -F "confidence_threshold=70.0")

echo "Response: $RESPONSE"

# Extract job ID (if you have jq installed)
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# Or extract job ID using grep/sed
JOB_ID=$(echo $RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

# Check status after waiting
sleep 30
curl http://127.0.0.1:49494/status/$JOB_ID
```

### Save Results

```bash
# Save extraction results
curl -s http://127.0.0.1:49494/status/$JOB_ID > outputs/2_api_result.json
```

## Python Equivalent (for WSL issues)

If curl doesn't work in WSL, use this Python script:

```python
import requests
import time
import json

# Upload PDF
with open("data/2.pdf", "rb") as f:
    response = requests.post(
        "http://127.0.0.1:49494/extract",
        files={"file": f},
        data={
            "enable_claude_fallback": "true",
            "confidence_threshold": "70.0"
        }
    )

job_id = response.json()["job_id"]
print(f"Job ID: {job_id}")

# Wait and check status
time.sleep(30)
status = requests.get(f"http://127.0.0.1:49494/status/{job_id}")
print(json.dumps(status.json(), indent=2))
```

## Expected Output Structure

```json
{
  "job_info": {
    "job_id": "job_...",
    "status": "completed",
    "filename": "2.pdf",
    "processing_time": 87.5
  },
  "data": {
    "report": {
      "report_name": "Home Inspection Report",
      "issues": [
        {
          "issue_name": "Example Issue",
          "issue_type": "Structural",
          "issue_description": "...",
          "severity": "medium",
          "location": "...",
          "issue_images": ["..."],
          "enhanced_images": [
            {
              "filename": "image.jpg",
              "confidence_score": 85,
              "expected_location": {"page": 5}
            }
          ]
        }
      ]
    },
    "metadata": {
      "model_used": "gemini-2.5-pro",
      "validation_metadata": {
        "confidence_score": 92.3
      }
    }
  }
}
```