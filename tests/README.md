# Test Files Organization

## API Tests (`tests/api_tests/`)
- **test_api.py** - Comprehensive API testing with all endpoints
- **test_api_real.py** - Tests with real PDF processing (no mocking)
- **test_api_simple.py** - Basic endpoint connectivity tests
- **test_job_manager.py** - Job management service tests
- **test_upload.py** - PDF upload functionality tests

## Extraction Tests (`tests/extraction_tests/`)
- **test_extraction_accuracy.py** - Main accuracy evaluation (92.3% achievement)
- **test_summary_first_extraction.py** - Summary-first approach implementation
- **test_enhanced_extraction.py** - Enhanced extraction with validation

## Core Tests (`tests/`)
- **test_complete_pipeline.py** - End-to-end pipeline integration
- **test_image_extraction.py** - Image extraction and filtering
- **test_api_keys.py** - API key configuration validation

## Configuration
- **test_config.py** - Shared test configuration (root directory)