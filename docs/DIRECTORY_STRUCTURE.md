# Directory Structure

```
pdf-extraction-pipeline/
├── README.md                   # Main project documentation
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variable template
├── .gitignore                 # Git ignore rules
├── extract_cli.py             # Main CLI for PDF extraction
├── run_api.py                 # API server startup script
│
├── api/                       # FastAPI application
│   ├── __init__.py
│   ├── main.py               # FastAPI app initialization
│   ├── models.py             # Pydantic models
│   ├── core/                 # Core configurations
│   │   ├── config.py         # Settings management
│   │   └── logging.py        # Logging configuration
│   ├── routers/              # API endpoints
│   │   ├── extraction.py     # PDF upload endpoint
│   │   ├── health.py         # Health checks
│   │   └── status.py         # Job status endpoints
│   └── services/             # Business logic
│       └── job_manager.py    # Async job processing
│
├── src/                      # Core extraction logic
│   ├── extractors/           # PDF extraction modules
│   │   ├── pipeline.py       # Main extraction pipeline
│   │   ├── pdf_parser.py     # PDF parsing with LlamaParse
│   │   ├── gemini_extractor.py   # Gemini model integration
│   │   ├── claude_extractor.py   # Claude model integration
│   │   ├── extraction_prompts.py # Summary-first prompts
│   │   ├── image_matcher.py      # Enhanced image matching
│   │   ├── enhanced_validation_router.py # Model routing
│   │   ├── validation_metrics.py # Accuracy metrics
│   │   └── schemas.py        # Data models
│   └── evaluators/           # Evaluation framework
│       ├── evaluation_pipeline.py # LLM-as-judge system
│       └── evaluation_schemas.py  # Evaluation models
│
├── tests/                    # Test suite
│   ├── test_api_keys.py
│   ├── test_complete_pipeline.py
│   ├── test_image_extraction.py
│   ├── test_config.py
│   ├── api_tests/            # API-specific tests
│   └── extraction_tests/     # Extraction tests
│
├── scripts/                  # Utility scripts
│   ├── evaluate_all_batch.py # Batch evaluation
│   ├── evaluate_all_pdfs.py  # Full evaluation
│   ├── simple_evaluation.py  # Quick evaluation
│   ├── setup.sh              # Linux setup
│   ├── setup_windows.bat     # Windows setup
│   ├── setup_wsl.sh          # WSL setup
│   ├── extract.bat           # Windows extraction
│   └── run.sh                # Linux run script
│
├── docs/                     # Documentation
│   ├── DIRECTORY_STRUCTURE.md     # This file
│   ├── API_DOCUMENTATION.md       # API reference
│   ├── TECHNICAL_ARCHITECTURE.md  # System design
│   ├── PERFORMANCE_EVALUATION.md  # Performance metrics
│   ├── DEVELOPMENT_SUMMARY.md     # Development journey
│   ├── COMMITTEE_DEVELOPMENT_JOURNEY.md # For committee
│   ├── FINAL_DELIVERABLES.md     # Deliverables overview
│   └── ... (other docs)
│
├── data/                     # Sample PDFs (gitignored)
├── outputs/                  # Extraction results (gitignored)
├── logs/                     # Application logs (gitignored)
└── uploads/                  # Temporary uploads (gitignored)
```

## Key Files

### Entry Points
- `extract_cli.py` - Command-line interface for PDF extraction
- `run_api.py` - Starts the FastAPI server

### Core Components
- `src/extractors/pipeline.py` - Main extraction orchestration
- `src/extractors/extraction_prompts.py` - Summary-first innovation
- `src/extractors/image_matcher.py` - Enhanced image matching
- `api/main.py` - FastAPI application setup

### Configuration
- `.env.example` - Template for API keys
- `requirements.txt` - Python dependencies
- `api/core/config.py` - Application settings

### Testing
- `scripts/simple_evaluation.py` - Quick accuracy check
- `scripts/evaluate_all_batch.py` - Batch evaluation
- `tests/` - Comprehensive test suite