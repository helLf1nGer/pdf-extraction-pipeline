#!/usr/bin/env python3
"""
Startup script for the PDF Extraction API.

This script starts the FastAPI server with appropriate configuration
for development and production environments.
"""

import os
import sys
import logging
from pathlib import Path

# Add src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    import uvicorn
    from api.core.config import get_settings
    from api.core.logging import setup_logging
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all dependencies are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)


def main():
    """Main entry point for the API server."""
    
    # Load settings
    settings = get_settings()
    
    # Setup logging
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    
    # Log startup information
    logger.info(f"Starting PDF Extraction API v{settings.api_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Host: {settings.host}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Mock mode: {settings.mock_mode}")
    
    # Check API keys (warn if missing in production)
    if not settings.mock_mode and not settings.has_required_api_keys:
        if settings.environment == "production":
            logger.error("Required API keys are missing in production mode!")
            logger.error("Please set LLAMA_PARSE_API_KEY and GEMINI_API_KEY environment variables")
            sys.exit(1)
        else:
            logger.warning("Required API keys are missing - some features may not work")
            logger.warning("Set LLAMA_PARSE_API_KEY and GEMINI_API_KEY environment variables")
    
    # Create required directories
    settings.create_directories()
    
    # Configure uvicorn
    uvicorn_config = {
        "app": "api.main:app",
        "host": settings.host,
        "port": settings.port,
        "log_level": settings.log_level.lower(),
        "access_log": True,
        "use_colors": True,
    }
    
    # Development-specific configuration
    if settings.environment == "development":
        uvicorn_config.update({
            "reload": True,
            "reload_dirs": ["api", "src"],
            "reload_includes": ["*.py"],
        })
    
    # Production-specific configuration
    elif settings.environment == "production":
        uvicorn_config.update({
            "reload": False,
            "workers": 1,  # Single worker for now due to in-memory job storage
            "loop": "uvloop",
            "http": "httptools",
        })
    
    logger.info("Starting uvicorn server...")
    
    try:
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server startup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()