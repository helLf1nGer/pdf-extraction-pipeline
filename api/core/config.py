"""
Configuration settings for the PDF extraction API.

This module uses Pydantic Settings for configuration management with
environment variable support and validation.
"""

import os
from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    environment: str = "development"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    
    # API settings
    api_title: str = "PDF Extraction API"
    api_version: str = "1.0.0"
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_file_types: List[str] = [".pdf"]
    
    # CORS settings
    allowed_origins: List[str] = ["*"]
    allowed_hosts: List[str] = ["*"]
    
    # Rate limiting
    rate_limit_per_minute: int = 30
    
    # Job processing settings
    max_concurrent_jobs: int = 3
    job_timeout: int = 300  # 5 minutes
    cleanup_interval: int = 3600  # 1 hour
    max_job_history: int = 1000
    
    # Pipeline settings
    mock_mode: bool = False
    enable_claude_fallback: bool = True
    confidence_threshold: float = 70.0
    allow_startup_without_pipeline: bool = False
    
    # Storage settings
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    
    # API Keys (loaded from environment)
    llama_parse_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # Redis settings (for future job queue implementation)
    redis_url: Optional[str] = None
    use_redis_queue: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
        # Environment variable mapping
        fields = {
            "llama_parse_api_key": {"env": "LLAMA_PARSE_API_KEY"},
            "gemini_api_key": {"env": "GEMINI_API_KEY"},
            "anthropic_api_key": {"env": "ANTHROPIC_API_KEY"},
            "openai_api_key": {"env": "OPENAI_API_KEY"},
            "redis_url": {"env": "REDIS_URL"},
        }
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        allowed = ["development", "testing", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    @field_validator("max_upload_size")
    @classmethod
    def validate_upload_size(cls, v):
        if v <= 0:
            raise ValueError("Max upload size must be positive")
        if v > 100 * 1024 * 1024:  # 100MB limit
            raise ValueError("Max upload size cannot exceed 100MB")
        return v
    
    @field_validator("allowed_file_types")
    @classmethod
    def validate_file_types(cls, v):
        if not v:
            raise ValueError("At least one file type must be allowed")
        for ext in v:
            if not ext.startswith("."):
                raise ValueError(f"File extension must start with dot: {ext}")
        return v
    
    @field_validator("max_concurrent_jobs")
    @classmethod
    def validate_concurrent_jobs(cls, v):
        if v <= 0:
            raise ValueError("Max concurrent jobs must be positive")
        if v > 10:
            raise ValueError("Max concurrent jobs should not exceed 10")
        return v
    
    @field_validator("job_timeout")
    @classmethod
    def validate_job_timeout(cls, v):
        if v <= 0:
            raise ValueError("Job timeout must be positive")
        if v > 1800:  # 30 minutes
            raise ValueError("Job timeout should not exceed 30 minutes")
        return v
    
    @field_validator("confidence_threshold")
    @classmethod
    def validate_confidence_threshold(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Confidence threshold must be between 0 and 100")
        return v
    
    @property
    def api_keys(self) -> dict:
        """Get all API keys as a dictionary."""
        return {
            "LLAMA_PARSE_API_KEY": self.llama_parse_api_key,
            "GEMINI_API_KEY": self.gemini_api_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "OPENAI_API_KEY": self.openai_api_key,
        }
    
    @property
    def has_required_api_keys(self) -> bool:
        """Check if required API keys are available."""
        if self.mock_mode:
            return True
        
        # At minimum, we need LlamaParse and Gemini
        return bool(
            self.llama_parse_api_key and 
            self.gemini_api_key
        )
    
    def create_directories(self):
        """Create required directories if they don't exist."""
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.create_directories()
    return settings