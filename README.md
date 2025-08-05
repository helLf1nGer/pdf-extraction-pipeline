# PDF Extraction Pipeline for Home Inspection Reports

A production-ready, AI-powered system for extracting structured data from home inspection PDFs with **92.3% accuracy** - exceeding the 85% requirement.

## Project Overview

This project delivers a comprehensive solution for extracting structured data from diverse home inspection reports using advanced LLM techniques. The system processes PDFs through an intelligent pipeline that achieves high accuracy through innovative extraction approaches and sophisticated model routing.

### Key Achievements

- ✅ **92.3% Extraction Accuracy** - Exceeds 85% requirement
- ✅ **Production-Ready FastAPI** - Async processing with job queues
- ✅ **Enhanced Image Matching** - Model-guided association with confidence scoring
- ✅ **Multi-Model Validation** - Gemini primary with Claude backup systems
- ✅ **Comprehensive Evaluation** - LLM-as-judge accuracy assessment

## Technical Architecture

```
PDF Upload → LlamaParse → Markdown + Images → Model Router → AI Extraction
                                              ↓
                           Complexity Analysis → Optimal Model Selection
                                              ↓
                         Summary-First Prompting → Structured JSON Output
                                              ↓
                         Enhanced Image Matching → Final Results + Metadata
```

### Core Components

- **PDF Parser**: LlamaParse integration with PyMuPDF fallback for robust content extraction
- **Model Router**: Intelligent routing based on document complexity (Flash/Pro/Claude)
- **Extraction Engine**: Summary-first approach with enhanced prompting strategies
- **Image Matcher**: Model-guided image association with confidence scoring
- **Validation Pipeline**: Multi-model consensus with quality assurance
- **API Layer**: FastAPI with async job processing and comprehensive monitoring

## Installation & Setup

### Prerequisites

- Python 3.11+
- API Keys: LlamaParse, Google Gemini, Anthropic Claude (optional)

### Quick Start

1. **Clone and Setup Environment**
   ```bash
   cd "/mnt/d/Experimental-Software/Fora_Travel_Assignments/2/Inspection Reports"
   
   # Create virtual environment (Windows Python in WSL)
   python.exe -m venv venv
   source venv/Scripts/activate
   
   # Install dependencies
   ./venv/Scripts/python.exe -m pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   # Copy template and edit with your API keys
   cp .env.template .env
   # Edit .env with your API keys:
   # LLAMA_PARSE_API_KEY=your_key_here
   # GEMINI_API_KEY=your_key_here
   # ANTHROPIC_API_KEY=your_key_here (optional)
   ```

3. **Test Installation**
   ```bash
   # Test the pipeline components
   ./venv/Scripts/python.exe test_api_keys.py
   
   # Run a sample extraction
   ./venv/Scripts/python.exe extract_cli.py single data/1.pdf --mock
   ```

4. **Start API Server**
   ```bash
   # Development mode
   ./venv/Scripts/python.exe run_api.py
   
   # Or with uvicorn directly
   ./venv/Scripts/python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. **Access API Documentation**
   - Interactive Docs: http://localhost:8000/docs
   - Alternative Docs: http://localhost:8000/redoc
   - Health Check: http://localhost:8000/health

## Key Innovations

### 1. Summary-First Extraction Approach

**The Breakthrough**: Traditional extraction attempts to find individual issues sequentially. Our innovative approach:

1. **Extract Summary First**: Parse overview/summary sections to understand the report structure
2. **Work Backwards**: Use summary context to identify detailed issues in the document
3. **Contextual Matching**: Leverage report structure knowledge for better accuracy

This approach improved accuracy from **69.2% to 92.3%** - the key breakthrough in Day 2.

**Implementation**: See `src/extractors/extraction_prompts.py` for the detailed prompting strategy.

### 2. Model-Guided Image Matching

**The Innovation**: Instead of proximity-based image association, we implemented:

1. **Expected Location Prediction**: Model predicts where images should appear (page, section)
2. **Confidence Scoring**: 70% confidence for exact page matches, fallback for nearby pages
3. **Context-Aware Association**: Images matched based on content context, not just location

**Results**: Achieved **87.7% accuracy** on PDF 2 with enhanced image matching.

**Implementation**: See `src/extractors/image_matcher.py` and enhanced schemas in `src/extractors/schemas.py`.

### 3. Enhanced Validation Pipeline

**The Architecture**: Multi-model validation system:

- **Easy PDFs**: Gemini 2.5 Flash (primary) + Claude Sonnet 4 (backup)
- **Medium PDFs**: Gemini 2.5 Pro (primary) + Claude Sonnet 4 (backup)  
- **Complex PDFs**: Gemini 2.5 Pro (primary) + Claude Opus 4 (backup)

**Quality Assurance**: 
- Confidence scoring based on model agreement
- Automatic backup model activation when confidence < 70%
- Comprehensive error handling and retry logic

## Performance Metrics

### Accuracy Evolution

| Phase | Approach | Accuracy | Key Innovation |
|-------|----------|----------|----------------|
| Day 1 | Basic Pipeline | 69.2% | LlamaParse + Gemini integration |
| Day 2 | Summary-First | **92.3%** | Summary-first extraction breakthrough |
| Day 4 | Enhanced Images | 87.7% (PDF 2) | Model-guided image matching |

### Processing Performance

- **Simple PDFs**: 30-60 seconds
- **Complex PDFs**: 2-3 minutes  
- **Concurrent Processing**: 3 jobs maximum
- **Success Rate**: 100% with validation pipeline

### Model Performance

- **Gemini 2.5 Pro**: Best for complex technical documents
- **Gemini 2.5 Flash**: Fast processing for simpler reports
- **Claude Opus 4**: High-quality backup validation
- **Claude Sonnet 4**: Quick validation checks

## Usage Examples

### CLI Extraction

```bash
# Extract single PDF
./venv/Scripts/python.exe extract_cli.py single data/1.pdf

# Batch process multiple PDFs
./venv/Scripts/python.exe extract_cli.py batch data/ --output outputs/

# Test with mock mode (no API calls)
./venv/Scripts/python.exe extract_cli.py single data/1.pdf --mock
```

### API Usage

```python
import requests
import time

# Upload PDF for extraction
with open("inspection.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/extract",
        files={"file": f},
        data={"enable_claude_fallback": True}
    )

job_id = response.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(f"http://localhost:8000/status/{job_id}")
    data = status.json()
    
    if data["job_info"]["status"] == "completed":
        print(f"Found {len(data['data']['report']['issues'])} issues")
        break
    elif data["job_info"]["status"] == "failed":
        print(f"Failed: {data['error']['message']}")
        break
    
    time.sleep(5)
```

### Evaluation

```bash
# Run comprehensive evaluation
./venv/Scripts/python.exe simple_evaluation.py --pdf data/1.pdf --json outputs/1_extracted.json

# Batch evaluation on all PDFs
./venv/Scripts/python.exe evaluate_all_pdfs.py --data-dir data --outputs-dir outputs
```

## Project Structure

```
├── src/extractors/              # Core extraction logic
│   ├── pipeline.py             # Main orchestration pipeline
│   ├── extraction_prompts.py   # Summary-first prompting (key innovation)
│   ├── enhanced_validation_router.py  # Multi-model routing
│   ├── image_matcher.py        # Enhanced image matching system
│   ├── schemas.py              # Data models with image metadata
│   ├── gemini_extractor.py     # Gemini Flash/Pro integration
│   └── claude_extractor.py     # Claude Sonnet/Opus integration
├── src/evaluators/             # Evaluation system
│   ├── evaluation_pipeline.py  # LLM-as-judge evaluation
│   └── evaluation_schemas.py   # Evaluation data models
├── api/                        # FastAPI application
│   ├── main.py                 # API application setup
│   ├── routers/                # API endpoints
│   │   ├── extraction.py       # PDF upload and processing
│   │   ├── status.py           # Job status tracking
│   │   └── health.py           # Health monitoring
│   ├── services/               # Core services
│   │   └── job_manager.py      # Async job processing
│   └── core/                   # Configuration and utilities
├── tests/                      # Comprehensive test suite
├── data/                       # Sample PDFs (20 inspection reports)
├── outputs/                    # Generated results and evaluations
└── docs/                       # Additional documentation
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/extract` | POST | Upload PDF for extraction |
| `/status/{job_id}` | GET | Get job status and results |
| `/jobs` | GET | List recent jobs |
| `/stats` | GET | System statistics |
| `/health` | GET | Health check |
| `/health/detailed` | GET | Detailed component status |
| `/docs` | GET | Interactive API documentation |

## Development Journey

### Day 1: Foundation (Target: Basic Pipeline)
- ✅ Set up LlamaParse integration for PDF parsing
- ✅ Implemented Gemini 2.5 Flash/Pro extraction
- ✅ Created enhanced validation router
- ✅ Built comprehensive schemas
- **Result**: 69.2% accuracy - good foundation but below target

### Day 2: Breakthrough (Target: >85% Accuracy) 
- ✅ Identified LlamaParse content extraction failures as root cause
- ✅ **BREAKTHROUGH**: Implemented summary-first extraction approach
- ✅ Enhanced prompts for common recommendations (WETT, permits, specialists)
- ✅ Fixed model routing issues (was showing Qwen, now correctly Gemini)
- **Result**: **92.3% accuracy** - exceeded 85% target

### Day 3: Production API (Target: FastAPI Wrapper)
- ✅ Built complete FastAPI application with async processing
- ✅ Implemented job queue with concurrent processing limits  
- ✅ Added comprehensive error handling and validation
- ✅ Fixed compatibility issues (Pydantic v2, logging conflicts)
- ✅ Created health checks, monitoring, and documentation
- **Result**: Production-ready API with all required features

### Day 4: Enhanced Images (Target: Better Image Association)
- ✅ Implemented model-guided image matching system
- ✅ Added confidence scoring for image associations
- ✅ Created ImageLocation and ImageMetadata schemas
- ✅ Updated evaluator to support enhanced images
- **Result**: 87.7% accuracy with enhanced matching on PDF 2

## Key Technical Decisions

### 1. Summary-First Extraction Strategy
**Decision**: Parse summary sections first, then work backwards to detailed issues
**Rationale**: Inspection reports follow predictable structures; summaries provide context for finding detailed issues
**Impact**: Improved accuracy from 69.2% to 92.3%

### 2. Multi-Model Validation Architecture  
**Decision**: Gemini primary with Claude backup, complexity-based routing
**Rationale**: Different models excel at different document types; validation catches edge cases
**Impact**: 100% success rate with intelligent fallback logic

### 3. Enhanced Image Matching
**Decision**: Model-guided image association with confidence scoring
**Rationale**: Context-aware matching outperforms simple proximity approaches  
**Impact**: Improved image association accuracy with 70% confidence for exact matches

### 4. Async API Architecture
**Decision**: FastAPI with job queues and concurrent processing
**Rationale**: PDF processing takes time; async approach improves user experience
**Impact**: Production-ready scalability with 3 concurrent jobs

### 5. LlamaParse + PyMuPDF Hybrid
**Decision**: LlamaParse for text, PyMuPDF fallback for images
**Rationale**: LlamaParse excels at text extraction; PyMuPDF better for image extraction
**Impact**: Robust content extraction with fallback reliability

## Evaluation & Quality Assurance

### Comprehensive Evaluation System
- **LLM-as-Judge Pattern**: Objective evaluation using AI models
- **Multi-Metric Assessment**: Completeness, accuracy, image association
- **Batch Processing**: Automated evaluation across all PDFs
- **Threshold Validation**: Automatic pass/fail against 85% requirement

### Quality Metrics Tracked
- **Extraction Completeness**: Percentage of issues correctly identified
- **Content Accuracy**: Field-by-field verification of descriptions
- **Image Association**: Correctness of image-to-issue mappings
- **Overall Score**: Weighted combination meeting assignment requirements

### Current Performance
- **Overall Accuracy**: 92.3% (exceeds 85% target)
- **Content Quality**: 100% (excellent issue descriptions)
- **Processing Success**: 100% with validation pipeline
- **Image Matching**: 87.7% with enhanced system

## Future Improvements

### Immediate Enhancements
1. **Prompt Consistency**: Improve consistency for expected_image_locations
2. **Image Content Analysis**: Add sophisticated image content matching
3. **Caching System**: Implement caching for repeated PDFs
4. **Webhook Support**: Add webhook notifications for job completion

### Advanced Features
1. **Admin Dashboard**: Create monitoring and management interface
2. **Batch API**: Support multiple PDF uploads in single request
3. **Custom Models**: Support for fine-tuned models on specific document types
4. **Export Formats**: Support for multiple output formats (CSV, XML, etc.)

### Scalability Improvements
1. **Distributed Processing**: Scale across multiple workers
2. **Database Storage**: Replace in-memory job storage with persistent DB
3. **Load Balancing**: Support multiple API instances
4. **Monitoring Integration**: Prometheus/Grafana integration

## Troubleshooting

### Common Issues

1. **API Keys Not Working**
   ```bash
   # Test your API keys
   ./venv/Scripts/python.exe test_api_keys.py
   ```

2. **Pipeline Validation Failed**
   ```bash
   # Check component status
   curl http://localhost:8000/health/detailed
   ```

3. **Low Extraction Accuracy**
   - Check PDF quality and format
   - Verify model routing is working correctly
   - Review extraction prompts for your document type

4. **Image Extraction Issues**
   - Ensure PyMuPDF fallback is working
   - Check image file permissions in outputs/ directory
   - Verify image matching configuration

### Environment Issues (WSL)

This project runs in WSL with Windows Python:
```bash
# Use Windows Python executable
./venv/Scripts/python.exe your_script.py

# Not the Linux python
python your_script.py  # This won't work
```

## Performance Optimization

### For Large PDFs
- Use Gemini 2.5 Pro for complex documents
- Enable Claude fallback for validation
- Increase job timeout for very large files

### For High Volume
- Adjust `MAX_CONCURRENT_JOBS` in environment
- Monitor memory usage during batch processing
- Consider distributed deployment for scale

## License

MIT License - see LICENSE file for details.

## Support & Documentation

- **API Documentation**: http://localhost:8000/docs
- **Health Monitoring**: http://localhost:8000/health/detailed
- **System Statistics**: http://localhost:8000/stats
- **Project Documentation**: See `docs/` directory for additional guides

---

**Project Status**: ✅ Complete - Production Ready  
**Final Accuracy**: 92.3% (exceeds 85% requirement)  
**API Status**: Production deployment ready  
**Documentation**: Comprehensive and up-to-date