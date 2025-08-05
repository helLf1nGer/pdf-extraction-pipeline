# API Usage Guide & Examples

## Quick Start

### 1. Start the API Server

```bash
# Navigate to project directory
cd "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports"

# Activate virtual environment
source venv/Scripts/activate

# Start the server
./venv/Scripts/python.exe run_api.py
```

The API will be available at: http://localhost:8000

### 2. Access Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Complete Usage Examples

### Python Client Example

```python
import requests
import time
import json
from pathlib import Path

class PDFExtractionClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def extract_pdf(self, pdf_path, **kwargs):
        """
        Extract data from a PDF file
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional parameters (enable_claude_fallback, confidence_threshold, etc.)
        
        Returns:
            dict: Extraction results with metadata
        """
        # Upload PDF
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            data = kwargs
            
            response = self.session.post(f"{self.base_url}/extract", files=files, data=data)
            response.raise_for_status()
        
        job_data = response.json()
        job_id = job_data['job_id']
        print(f"Job submitted: {job_id}")
        print(f"Estimated time: {job_data.get('estimated_time', 'unknown')} seconds")
        
        # Poll for results
        return self._wait_for_completion(job_id)
    
    def _wait_for_completion(self, job_id, poll_interval=5, max_wait=600):
        """Wait for job completion and return results"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = self.session.get(f"{self.base_url}/status/{job_id}")
            status_response.raise_for_status()
            status_data = status_response.json()
            
            job_info = status_data['job_info']
            status = job_info['status']
            progress = job_info.get('progress', 0)
            
            print(f"Status: {status} ({progress:.1f}%)")
            
            if status == 'completed':
                return status_data['data']
            elif status == 'failed':
                error_info = status_data.get('error', {})
                raise Exception(f"Extraction failed: {error_info.get('message', 'Unknown error')}")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Job {job_id} did not complete within {max_wait} seconds")
    
    def get_job_status(self, job_id):
        """Get current status of a job"""
        response = self.session.get(f"{self.base_url}/status/{job_id}")
        response.raise_for_status()
        return response.json()
    
    def list_jobs(self, status=None, limit=10):
        """List recent jobs"""
        params = {'limit': limit}
        if status:
            params['status'] = status
            
        response = self.session.get(f"{self.base_url}/jobs", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_stats(self):
        """Get system statistics"""
        response = self.session.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()

# Usage example
def main():
    client = PDFExtractionClient()
    
    # Extract a PDF with enhanced settings
    try:
        results = client.extract_pdf(
            "data/1.pdf",
            enable_claude_fallback=True,
            confidence_threshold=75.0,
            save_intermediate=True
        )
        
        # Process results
        report = results['report']
        metadata = results['metadata']
        
        print(f"\nExtraction completed successfully!")
        print(f"Report: {report['report_name']}")
        print(f"Issues found: {len(report['issues'])}")
        print(f"Model used: {metadata['model_used']}")
        print(f"Processing time: {metadata['processing_time']:.1f}s")
        print(f"Confidence: {metadata['validation_metadata']['confidence_score']:.1f}%")
        
        # Display first few issues
        print("\nTop issues found:")
        for i, issue in enumerate(report['issues'][:3], 1):
            print(f"{i}. {issue['issue_name']} ({issue['issue_type']})")
            print(f"   Severity: {issue['severity']}")
            print(f"   Location: {issue.get('location', 'Not specified')}")
            print(f"   Images: {len(issue['issue_images'])} associated")
            print()
        
        # Save results
        output_file = Path("results") / f"extraction_{int(time.time())}.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    main()
```

### JavaScript/Node.js Client Example

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class PDFExtractionClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.axios = axios.create({ baseURL: baseUrl });
    }
    
    async extractPDF(filePath, options = {}) {
        try {
            // Upload PDF
            const form = new FormData();
            form.append('file', fs.createReadStream(filePath));
            
            // Add options
            Object.entries(options).forEach(([key, value]) => {
                form.append(key, value.toString());
            });
            
            const uploadResponse = await this.axios.post('/extract', form, {
                headers: form.getHeaders()
            });
            
            const { job_id, estimated_time } = uploadResponse.data;
            console.log(`Job submitted: ${job_id}`);
            console.log(`Estimated time: ${estimated_time} seconds`);
            
            // Wait for completion
            return await this.waitForCompletion(job_id);
            
        } catch (error) {
            throw new Error(`Extraction failed: ${error.response?.data?.message || error.message}`);
        }
    }
    
    async waitForCompletion(jobId, pollInterval = 5000, maxWait = 600000) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < maxWait) {
            try {
                const response = await this.axios.get(`/status/${jobId}`);
                const { job_info, data, error } = response.data;
                
                console.log(`Status: ${job_info.status} (${job_info.progress?.toFixed(1) || 0}%)`);
                
                if (job_info.status === 'completed') {
                    return data;
                } else if (job_info.status === 'failed') {
                    throw new Error(`Job failed: ${error?.message || 'Unknown error'}`);
                }
                
                await new Promise(resolve => setTimeout(resolve, pollInterval));
                
            } catch (error) {
                if (error.response?.status === 404) {
                    throw new Error(`Job ${jobId} not found`);
                }
                throw error;
            }
        }
        
        throw new Error(`Job ${jobId} did not complete within ${maxWait}ms`);
    }
    
    async getJobStatus(jobId) {
        const response = await this.axios.get(`/status/${jobId}`);
        return response.data;
    }
    
    async listJobs(options = {}) {
        const response = await this.axios.get('/jobs', { params: options });
        return response.data;
    }
    
    async getStats() {
        const response = await this.axios.get('/stats');
        return response.data;
    }
    
    async healthCheck() {
        const response = await this.axios.get('/health');
        return response.data;
    }
}

// Usage example
async function main() {
    const client = new PDFExtractionClient();
    
    try {
        // Check API health
        const health = await client.healthCheck();
        console.log('API Status:', health.status);
        
        // Extract PDF
        const results = await client.extractPDF('data/1.pdf', {
            enable_claude_fallback: true,
            confidence_threshold: 75.0
        });
        
        // Process results
        const { report, metadata } = results;
        
        console.log('\n✅ Extraction completed successfully!');
        console.log(`📄 Report: ${report.report_name}`);
        console.log(`🔍 Issues found: ${report.issues.length}`);
        console.log(`🤖 Model used: ${metadata.model_used}`);
        console.log(`⏱️  Processing time: ${metadata.processing_time.toFixed(1)}s`);
        console.log(`📊 Confidence: ${metadata.validation_metadata.confidence_score.toFixed(1)}%`);
        
        // Display issues by severity
        const issuesBySeverity = report.issues.reduce((acc, issue) => {
            const severity = issue.severity || 'unknown';
            acc[severity] = (acc[severity] || 0) + 1;
            return acc;
        }, {});
        
        console.log('\n📋 Issues by severity:');
        Object.entries(issuesBySeverity).forEach(([severity, count]) => {
            console.log(`   ${severity}: ${count}`);
        });
        
        // Save results
        const outputFile = `results/extraction_${Date.now()}.json`;
        fs.mkdirSync('results', { recursive: true });
        fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
        console.log(`💾 Results saved to: ${outputFile}`);
        
    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

main();
```

### cURL Examples

#### Basic PDF Upload
```bash
# Upload a PDF for extraction
curl -X POST "http://localhost:8000/extract" \
  -F "file=@data/1.pdf" \
  -F "enable_claude_fallback=true" \
  -F "confidence_threshold=75.0"

# Response:
# {
#   "job_id": "job_12345678-1234-5678-9abc-123456789012",
#   "status": "pending",
#   "message": "PDF upload successful. Processing started.",
#   "estimated_time": 45,
#   "status_url": "/status/job_12345678-1234-5678-9abc-123456789012"
# }
```

#### Check Job Status
```bash
# Check job status
curl "http://localhost:8000/status/job_12345678-1234-5678-9abc-123456789012"

# Response (completed):
# {
#   "job_info": {
#     "job_id": "job_12345678-1234-5678-9abc-123456789012",
#     "status": "completed",
#     "progress": 100.0,
#     "processing_time": 67.3
#   },
#   "data": {
#     "report": { ... },
#     "metadata": { ... }
#   }
# }
```

#### List Recent Jobs
```bash
# List all recent jobs
curl "http://localhost:8000/jobs"

# List only completed jobs
curl "http://localhost:8000/jobs?status=completed&limit=5"
```

#### System Health and Stats
```bash
# Basic health check  
curl "http://localhost:8000/health"

# Detailed health check
curl "http://localhost:8000/health/detailed"

# System statistics
curl "http://localhost:8000/stats"
```

## Advanced Usage Patterns

### Batch Processing Script

```python
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
import json

class AsyncPDFClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        
    async def process_pdf_batch(self, pdf_directory, output_directory, max_concurrent=3):
        """
        Process multiple PDFs concurrently
        """
        pdf_files = list(Path(pdf_directory).glob("*.pdf"))
        output_dir = Path(output_directory)
        output_dir.mkdir(exist_ok=True)
        
        # Create semaphore to limit concurrent uploads
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._process_single_pdf(session, semaphore, pdf_file, output_dir)
                for pdf_file in pdf_files
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # Process results
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        
        print(f"Batch processing completed:")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        
        return successful, failed
    
    async def _process_single_pdf(self, session, semaphore, pdf_file, output_dir):
        """Process a single PDF with concurrency control"""
        async with semaphore:
            try:
                # Upload PDF
                job_id = await self._upload_pdf(session, pdf_file)
                
                # Wait for completion
                result = await self._wait_for_completion(session, job_id)
                
                # Save result
                output_file = output_dir / f"{pdf_file.stem}_extraction.json"
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write(json.dumps(result, indent=2))
                
                print(f"✅ Completed: {pdf_file.name}")
                return result
                
            except Exception as e:
                print(f"❌ Failed: {pdf_file.name} - {e}")
                raise
    
    async def _upload_pdf(self, session, pdf_file):
        """Upload PDF and return job ID"""
        data = aiohttp.FormData()
        data.add_field('file', open(pdf_file, 'rb'), filename=pdf_file.name)
        data.add_field('enable_claude_fallback', 'true')
        
        async with session.post(f"{self.base_url}/extract", data=data) as response:
            response.raise_for_status()
            job_data = await response.json()
            return job_data['job_id']
    
    async def _wait_for_completion(self, session, job_id, poll_interval=5):
        """Wait for job completion"""
        while True:
            async with session.get(f"{self.base_url}/status/{job_id}") as response:
                response.raise_for_status()
                status_data = await response.json()
                
                status = status_data['job_info']['status']
                if status == 'completed':
                    return status_data['data']
                elif status == 'failed':
                    error = status_data.get('error', {})
                    raise Exception(f"Job failed: {error.get('message', 'Unknown error')}")
                
                await asyncio.sleep(poll_interval)

# Usage
async def main():
    client = AsyncPDFClient()
    successful, failed = await client.process_pdf_batch(
        pdf_directory="data/",
        output_directory="batch_results/",
        max_concurrent=3
    )

# Run the batch processing
# asyncio.run(main())
```

### Monitoring and Alerting Script

```python
import requests
import time
import smtplib
from email.mime.text import MimeText
from datetime import datetime

class APIMonitor:
    def __init__(self, api_url="http://localhost:8000", alert_email=None):
        self.api_url = api_url
        self.alert_email = alert_email
        self.last_alert_time = {}
        
    def check_health(self):
        """Check API health and return status"""
        try:
            response = requests.get(f"{self.api_url}/health/detailed", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def check_stats(self):
        """Get current system statistics"""
        try:
            response = requests.get(f"{self.api_url}/stats", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def evaluate_health(self, health_data, stats_data):
        """Evaluate system health and identify issues"""
        issues = []
        
        # Check overall health
        if health_data.get("status") != "healthy":
            issues.append({
                "severity": "critical",
                "message": f"API health check failed: {health_data.get('error', 'Unknown')}"
            })
        
        # Check component health
        components = health_data.get("components", {})
        for component, status in components.items():
            if status.get("status") != "healthy":
                issues.append({
                    "severity": "warning",
                    "message": f"Component {component} unhealthy: {status.get('message', '')}"
                })
        
        # Check statistics
        if stats_data and not stats_data.get("error"):
            stats = stats_data.get("processing_stats", {})
            
            # High error rate
            error_rate = stats.get("error_rate", 0)
            if error_rate > 0.05:  # 5%
                issues.append({
                    "severity": "warning",
                    "message": f"High error rate: {error_rate:.1%}"
                })
            
            # High queue depth
            queue_depth = stats.get("queue_depth", 0)
            if queue_depth > 10:
                issues.append({
                    "severity": "warning",
                    "message": f"High queue depth: {queue_depth} jobs"
                })
            
            # Slow processing
            avg_processing_time = stats.get("average_processing_time", 0)
            if avg_processing_time > 180:  # 3 minutes
                issues.append({
                    "severity": "warning",
                    "message": f"Slow processing: {avg_processing_time:.1f}s average"
                })
        
        return issues
    
    def send_alert(self, issues):
        """Send alert email for critical issues"""
        if not self.alert_email:
            return
        
        critical_issues = [i for i in issues if i["severity"] == "critical"]
        if not critical_issues:
            return
        
        # Rate limiting: don't send alerts too frequently
        alert_key = "critical_alert"
        if alert_key in self.last_alert_time:
            time_since_last = time.time() - self.last_alert_time[alert_key]
            if time_since_last < 300:  # 5 minutes
                return
        
        # Compose alert message
        subject = f"PDF Extraction API Alert - {len(critical_issues)} Critical Issues"
        body = f"""
PDF Extraction API Alert

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Critical Issues Found: {len(critical_issues)}

Issues:
"""
        for issue in critical_issues:
            body += f"- {issue['message']}\n"
        
        # Send email (configure SMTP settings as needed)
        try:
            # This is a simplified example - configure your SMTP settings
            msg = MimeText(body)
            msg['Subject'] = subject
            msg['From'] = 'monitoring@yourcompany.com'
            msg['To'] = self.alert_email
            
            # Send email (configure your SMTP server)
            # smtp = smtplib.SMTP('localhost')
            # smtp.send_message(msg)
            # smtp.quit()
            
            print(f"Alert sent: {subject}")
            self.last_alert_time[alert_key] = time.time()
            
        except Exception as e:
            print(f"Failed to send alert: {e}")
    
    def monitor_loop(self, check_interval=60):
        """Main monitoring loop"""
        print("Starting API monitoring...")
        
        while True:
            try:
                # Check health and stats
                health_data = self.check_health()
                stats_data = self.check_stats()
                
                # Evaluate issues
                issues = self.evaluate_health(health_data, stats_data)
                
                # Report status
                timestamp = datetime.now().strftime('%H:%M:%S')
                if not issues:
                    print(f"[{timestamp}] ✅ All systems healthy")
                else:
                    critical_count = len([i for i in issues if i["severity"] == "critical"])
                    warning_count = len([i for i in issues if i["severity"] == "warning"])
                    print(f"[{timestamp}] ⚠️  Issues found: {critical_count} critical, {warning_count} warnings")
                    
                    for issue in issues:
                        severity_icon = "🚨" if issue["severity"] == "critical" else "⚠️"
                        print(f"  {severity_icon} {issue['message']}")
                    
                    # Send alerts for critical issues
                    self.send_alert(issues)
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Monitoring error: {e}")
            
            time.sleep(check_interval)

# Usage
def main():
    monitor = APIMonitor(
        api_url="http://localhost:8000",
        alert_email="admin@yourcompany.com"  # Configure your alert email
    )
    
    # Run monitoring loop
    monitor.monitor_loop(check_interval=60)  # Check every minute

if __name__ == "__main__":
    main()
```

## Response Format Reference

### Successful Extraction Response
```json
{
  "job_info": {
    "job_id": "job_12345678-1234-5678-9abc-123456789012",
    "status": "completed",
    "filename": "inspection_report.pdf",
    "created_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:30:05Z",
    "completed_at": "2024-01-15T10:31:23Z",
    "processing_time": 78.5,
    "progress": 100.0
  },
  "data": {
    "report": {
      "report_name": "123 Main Street Home Inspection",
      "issues": [
        {
          "issue_name": "Electrical Panel Issues",
          "issue_type": "Electrical",
          "issue_description": "The main electrical panel shows signs of corrosion and requires immediate attention from a qualified electrician.",
          "issue_summary": "Main panel needs inspection and repair by qualified electrician",
          "severity": "high",
          "location": "Basement utility room",
          "issue_images": ["electrical_panel_01.jpg", "electrical_panel_02.jpg"],
          "expected_image_locations": [
            {
              "page_number": 8,
              "location_description": "center section",
              "section_context": "electrical panel inspection area"
            }
          ]
        }
      ],
      "source_pdf": "inspection_report.pdf"
    },
    "metadata": {
      "model_used": "gemini-2.5-pro",
      "processing_time": 78.5,
      "pdf_complexity": "medium",
      "validation_metadata": {
        "validation_performed": true,
        "confidence_score": 87.5,
        "validation_decision": "use_primary",
        "agreement_percentage": 92.0,
        "pipeline_used": "gemini_pro_primary"
      },
      "extraction_stats": {
        "total_issues_found": 12,
        "images_extracted": 17,
        "images_associated": 15,
        "pages_processed": 16
      }
    }
  }
}
```

### Error Response Format
```json
{
  "error": "Processing failed",
  "message": "The uploaded file could not be processed due to a parsing error",
  "code": "processing_error",
  "details": {
    "stage": "pdf_parsing",
    "original_error": "LlamaParse timeout after 3 retries",
    "file_size": 15728640,
    "pages": 24
  },
  "request_id": "req_12345678-1234-5678-9abc-123456789012",
  "timestamp": "2024-01-15T10:30:00Z",
  "support_info": {
    "documentation": "http://localhost:8000/docs",
    "health_check": "http://localhost:8000/health"
  }
}
```

## Best Practices

### 1. Error Handling
```python
def extract_with_retry(client, pdf_path, max_retries=3):
    """Extract PDF with automatic retry on failure"""
    for attempt in range(max_retries):
        try:
            return client.extract_pdf(pdf_path)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
```

### 2. Rate Limiting Compliance
```python
import time
from collections import deque

class RateLimitedClient:
    def __init__(self, client, requests_per_minute=25):
        self.client = client
        self.request_times = deque()
        self.requests_per_minute = requests_per_minute
    
    def extract_pdf(self, *args, **kwargs):
        # Enforce rate limit
        now = time.time()
        minute_ago = now - 60
        
        # Remove old requests
        while self.request_times and self.request_times[0] < minute_ago:
            self.request_times.popleft()
        
        # Check if we need to wait
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                time.sleep(wait_time)
        
        # Make request
        self.request_times.append(now)
        return self.client.extract_pdf(*args, **kwargs)
```

### 3. Result Validation
```python
def validate_extraction_result(result):
    """Validate extraction result completeness"""
    checks = {
        'has_report': 'report' in result,
        'has_issues': len(result.get('report', {}).get('issues', [])) > 0,
        'has_metadata': 'metadata' in result,
        'high_confidence': result.get('metadata', {}).get('validation_metadata', {}).get('confidence_score', 0) >= 70
    }
    
    passed_checks = sum(checks.values())
    total_checks = len(checks)
    
    if passed_checks < total_checks:
        print(f"⚠️  Validation warning: {passed_checks}/{total_checks} checks passed")
        for check, passed in checks.items():
            if not passed:
                print(f"   ❌ {check}")
    
    return passed_checks == total_checks
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Connection Refused
```bash
# Error: Connection refused to localhost:8000
# Solution: Ensure API server is running
./venv/Scripts/python.exe run_api.py
```

#### 2. File Too Large Error
```python
# Error: File exceeds maximum size limit
# Solution: Check file size limits in configuration
# Default limit: 50MB (configurable via MAX_UPLOAD_SIZE)
```

#### 3. Processing Timeout
```python
# Error: Job timed out after 300 seconds
# Solutions:
# 1. Increase timeout in environment: JOB_TIMEOUT=600
# 2. Use smaller PDFs or optimize content
# 3. Check API health: GET /health/detailed
```

#### 4. Low Confidence Scores
```python
# Issue: Confidence scores below 70%
# Solutions:
# 1. Enable Claude fallback: enable_claude_fallback=true
# 2. Lower confidence threshold: confidence_threshold=60.0
# 3. Check PDF quality and format compatibility
```

## Integration Examples

### Django Integration
```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import requests
import json

@csrf_exempt
def upload_inspection_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']
        
        # Save uploaded file temporarily
        file_path = default_storage.save(f'temp/{pdf_file.name}', pdf_file)
        
        try:
            # Extract using API
            with open(default_storage.path(file_path), 'rb') as f:
                response = requests.post(
                    'http://localhost:8000/extract',
                    files={'file': f},
                    data={'enable_claude_fallback': True}
                )
            
            # Return job ID for polling
            return JsonResponse(response.json())
            
        finally:
            # Cleanup
            default_storage.delete(file_path)
    
    return JsonResponse({'error': 'No PDF file provided'}, status=400)
```

### Flask Integration
```python
# app.py
from flask import Flask, request, jsonify
import requests
import tempfile
import os

app = Flask(__name__)

@app.route('/extract', methods=['POST'])
def extract_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        file.save(tmp_file.name)
        
        try:
            # Forward to extraction API
            with open(tmp_file.name, 'rb') as f:
                response = requests.post(
                    'http://localhost:8000/extract',
                    files={'file': f},
                    data=request.form.to_dict()
                )
            
            return jsonify(response.json()), response.status_code
            
        finally:
            os.unlink(tmp_file.name)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

This comprehensive API usage guide should help users effectively integrate and use the PDF extraction system in their applications.