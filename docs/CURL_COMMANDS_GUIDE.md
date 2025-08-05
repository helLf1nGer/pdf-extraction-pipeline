# API Testing with curl Commands

This guide shows how to test the PDF Extraction API using curl commands with 2.pdf as an example.

## Prerequisites

1. **Start the API Server**:
   ```bash
   cd "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports"
   ./venv/Scripts/python.exe run_api.py
   ```

2. **Verify Server is Running**:
   - Server runs on: http://127.0.0.1:49494
   - Check logs show: "Application startup complete"

## Basic curl Commands

### 1. Health Check
```bash
# Basic health check
curl http://127.0.0.1:49494/health

# Expected response:
# {"status": "ok", "timestamp": "2025-08-05T10:00:00Z"}
```

### 2. Detailed Health Check
```bash
# Detailed health with component status
curl http://127.0.0.1:49494/health/detailed

# Expected response shows all components:
# {
#   "status": "healthy",
#   "components": {
#     "api": "healthy",
#     "pipeline": "healthy",
#     "job_manager": "healthy"
#   },
#   "timestamp": "2025-08-05T10:00:00Z"
# }
```

### 3. System Statistics
```bash
# Get system statistics
curl http://127.0.0.1:49494/stats

# Shows job statistics and pipeline performance
```

## PDF Extraction with 2.pdf

### 4. Upload PDF for Extraction
```bash
# Upload 2.pdf for extraction
curl -X POST http://127.0.0.1:49494/extract \
  -F "file=@data/2.pdf" \
  -F "enable_claude_fallback=true" \
  -F "confidence_threshold=70.0"

# Expected response:
# {
#   "job_id": "job_12345678-1234-5678-9abc-123456789012",
#   "status": "pending",
#   "message": "PDF upload successful. Processing started.",
#   "estimated_time": 45,
#   "status_url": "/status/job_12345678-1234-5678-9abc-123456789012"
# }
```

### 5. Check Job Status
```bash
# Replace {job_id} with actual job ID from upload response
curl http://127.0.0.1:49494/status/{job_id}

# Example with actual job ID:
curl http://127.0.0.1:49494/status/job_12345678-1234-5678-9abc-123456789012

# Response shows processing progress or results
```

### 6. List Recent Jobs
```bash
# List all recent jobs
curl http://127.0.0.1:49494/jobs

# List only completed jobs
curl "http://127.0.0.1:49494/jobs?status=completed&limit=5"
```

## Complete Workflow Example

```bash
# Step 1: Upload PDF
JOB_ID=$(curl -s -X POST http://127.0.0.1:49494/extract \
  -F "file=@data/2.pdf" \
  -F "enable_claude_fallback=true" \
  -F "confidence_threshold=70.0" | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# Step 2: Poll for results (wait for processing)
sleep 10
curl http://127.0.0.1:49494/status/$JOB_ID | jq

# Step 3: Get just the extracted data
curl -s http://127.0.0.1:49494/status/$JOB_ID | jq '.data.report'
```

## Mock Mode Testing

For testing without API keys:

```bash
# Upload with mock mode enabled
curl -X POST http://127.0.0.1:49494/extract \
  -F "file=@data/2.pdf" \
  -F "mock_mode=true"
```

## Pretty JSON Output

Use `jq` for formatted JSON output:

```bash
# Install jq if not available
# sudo apt-get install jq

# Pretty print health check
curl -s http://127.0.0.1:49494/health | jq

# Pretty print job status
curl -s http://127.0.0.1:49494/status/{job_id} | jq
```

## Save Results to File

```bash
# Save extraction results to file
curl -s http://127.0.0.1:49494/status/{job_id} | jq '.data.report' > 2_extracted.json

# Save full response with metadata
curl -s http://127.0.0.1:49494/status/{job_id} > 2_full_response.json
```

## Common Issues

1. **Connection Refused**: Ensure server is running on port 49494
2. **500 Error**: Check server logs for API key or initialization issues
3. **Timeout**: Large PDFs may take 2-3 minutes to process

## Windows/WSL Notes

In WSL environment, use:
- `127.0.0.1` instead of `localhost`
- Full paths like `/mnt/d/...` for file references
- `./venv/Scripts/python.exe` for Python executable

## Expected Results for 2.pdf

When processing 2.pdf, you should see:
- Multiple home inspection issues extracted
- Enhanced image matching with confidence scores
- Metadata showing model used (Gemini 2.5 Pro/Flash)
- Processing time around 60-90 seconds
- Validation confidence score above 70%