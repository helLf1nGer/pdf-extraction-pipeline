"""
Job Manager service for handling async PDF extraction jobs.

This service manages the job queue, coordinates with the extraction pipeline,
and provides job status tracking and cleanup functionality.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import OrderedDict

from ..models import JobStatus, JobInfo, ExtractionData, ProcessingMetadata, APIError, ErrorCode
from ..core.logging import log_job_event
from src.extractors.pipeline import HomeInspectionExtractionPipeline, ExtractionResult


class Job:
    """Individual job instance with state management."""
    
    def __init__(self, job_id: str, filename: str, file_path: str, options: dict):
        self.job_id = job_id
        self.filename = filename
        self.file_path = file_path
        self.options = options
        
        # Timestamps
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        # Status and progress
        self.status = JobStatus.PENDING
        self.progress = 0.0
        self.estimated_completion: Optional[datetime] = None
        self.processing_time: Optional[float] = None
        
        # Results
        self.result: Optional[ExtractionResult] = None
        self.error: Optional[APIError] = None
        
        # Processing task
        self.task: Optional[asyncio.Task] = None
    
    def to_job_info(self) -> JobInfo:
        """Convert to JobInfo model."""
        return JobInfo(
            job_id=self.job_id,
            status=self.status,
            filename=self.filename,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            processing_time=self.processing_time,
            progress=self.progress,
            estimated_completion=self.estimated_completion
        )
    
    def to_extraction_data(self) -> Optional[ExtractionData]:
        """Convert successful result to ExtractionData model."""
        if not self.result or not self.result.success or not self.result.report:
            return None
        
        metadata = ProcessingMetadata(
            model_used=self.result.model_used,
            processing_time=self.result.processing_time,
            pdf_complexity=self.result.pdf_complexity,
            validation_metadata=self.result.validation_metadata
        )
        
        return ExtractionData(
            report=self.result.report,
            metadata=metadata
        )


class JobManager:
    """
    Manages async job processing for PDF extraction.
    
    Handles job queuing, processing coordination, status tracking,
    and cleanup of completed jobs.
    """
    
    def __init__(
        self, 
        max_concurrent_jobs: int = 3,
        job_timeout: int = 300,
        cleanup_interval: int = 3600,
        max_job_history: int = 1000
    ):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.job_timeout = job_timeout
        self.cleanup_interval = cleanup_interval
        self.max_job_history = max_job_history
        
        # Job storage (in-memory for now, could be Redis in production)
        self.jobs: Dict[str, Job] = OrderedDict()
        self.active_jobs: Dict[str, Job] = {}
        
        # Processing infrastructure
        self.pipeline: Optional[HomeInspectionExtractionPipeline] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            'total_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'processing_times': [],
            'start_time': time.time()
        }
        
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """Start the job manager and background tasks."""
        self.logger.info("Starting Job Manager...")
        
        # Initialize semaphore for concurrent job limiting
        self.semaphore = asyncio.Semaphore(self.max_concurrent_jobs)
        
        # Start background cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info(
            f"Job Manager started with {self.max_concurrent_jobs} concurrent job slots"
        )
    
    async def stop(self):
        """Stop the job manager and cleanup resources."""
        self.logger.info("Stopping Job Manager...")
        
        # Cancel all active jobs
        for job in list(self.active_jobs.values()):
            if job.task and not job.task.done():
                job.task.cancel()
                try:
                    await job.task
                except asyncio.CancelledError:
                    pass
        
        # Stop cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup pipeline
        if self.pipeline:
            await self.pipeline.cleanup()
        
        self.logger.info("Job Manager stopped")
    
    async def submit_job(
        self, 
        filename: str, 
        file_path: str, 
        options: Optional[dict] = None
    ) -> str:
        """
        Submit a new PDF extraction job.
        
        Args:
            filename: Original filename
            file_path: Path to the uploaded PDF file
            options: Processing options
            
        Returns:
            Job ID for tracking
        """
        job_id = f"job_{uuid.uuid4()}"
        options = options or {}
        
        # Create job instance
        job = Job(job_id, filename, file_path, options)
        self.jobs[job_id] = job
        
        # Update statistics
        self.stats['total_jobs'] += 1
        
        log_job_event(
            job_id, 
            "job_created",
            pdf_filename=filename,
            options=options
        )
        
        # Start processing (will wait for semaphore)
        job.task = asyncio.create_task(self._process_job(job))
        
        self.logger.info(f"Job {job_id} submitted for file: {filename}")
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Get job status and information."""
        return self.jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
            if job.task and not job.task.done():
                job.task.cancel()
            
            job.status = JobStatus.FAILED
            job.error = APIError(
                error="Job cancelled",
                message="Job was cancelled by request",
                code=ErrorCode.PROCESSING_ERROR
            )
            job.completed_at = datetime.utcnow()
            
            # Remove from active jobs if present
            self.active_jobs.pop(job_id, None)
            
            log_job_event(job_id, "job_cancelled")
            return True
        
        return False
    
    async def _process_job(self, job: Job):
        """Process a single job with the extraction pipeline."""
        async with self.semaphore:
            try:
                # Update job status
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                job.progress = 10.0
                self.active_jobs[job.job_id] = job
                
                log_job_event(
                    job.job_id,
                    "job_started",
                    pdf_filename=job.filename
                )
                
                # Initialize pipeline if needed
                if not self.pipeline:
                    await self._initialize_pipeline(job.options)
                
                job.progress = 20.0
                
                # Process the PDF
                start_time = time.time()
                
                result = await asyncio.wait_for(
                    self.pipeline.extract_from_pdf(
                        job.file_path,
                        output_dir=job.options.get('output_dir'),
                        save_intermediate=job.options.get('save_intermediate', False)
                    ),
                    timeout=self.job_timeout
                )
                
                processing_time = time.time() - start_time
                job.processing_time = processing_time
                
                # Update job with results
                if result.success:
                    job.status = JobStatus.COMPLETED
                    job.result = result
                    job.progress = 100.0
                    
                    self.stats['completed_jobs'] += 1
                    self.stats['processing_times'].append(processing_time)
                    
                    log_job_event(
                        job.job_id,
                        "job_completed",
                        processing_time=processing_time,
                        issues_found=len(result.report.issues) if result.report else 0
                    )
                else:
                    job.status = JobStatus.FAILED
                    job.error = APIError(
                        error="Extraction failed",
                        message=result.error_message or "Unknown extraction error",
                        code=ErrorCode.PROCESSING_ERROR,
                        details={
                            "model_used": result.model_used,
                            "processing_time": processing_time
                        }
                    )
                    
                    self.stats['failed_jobs'] += 1
                    
                    log_job_event(
                        job.job_id,
                        "job_failed",
                        error=result.error_message,
                        processing_time=processing_time
                    )
                
            except asyncio.TimeoutError:
                job.status = JobStatus.TIMEOUT
                job.error = APIError(
                    error="Processing timeout",
                    message=f"Job exceeded maximum processing time of {self.job_timeout} seconds",
                    code=ErrorCode.TIMEOUT_ERROR
                )
                
                self.stats['failed_jobs'] += 1
                
                log_job_event(
                    job.job_id,
                    "job_timeout",
                    timeout=self.job_timeout
                )
                
            except asyncio.CancelledError:
                self.logger.info(f"Job {job.job_id} was cancelled")
                raise
                
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = APIError(
                    error="Processing error",
                    message=f"Unexpected error during processing: {str(e)}",
                    code=ErrorCode.INTERNAL_ERROR
                )
                
                self.stats['failed_jobs'] += 1
                
                log_job_event(
                    job.job_id,
                    "job_error",
                    error=str(e)
                )
                
                self.logger.error(f"Job {job.job_id} failed with error: {str(e)}", exc_info=True)
            
            finally:
                # Cleanup
                job.completed_at = datetime.utcnow()
                self.active_jobs.pop(job.job_id, None)
                
                # Clean up uploaded file
                try:
                    Path(job.file_path).unlink(missing_ok=True)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup file {job.file_path}: {str(e)}")
    
    async def _initialize_pipeline(self, options: dict):
        """Initialize the extraction pipeline with options."""
        if self.pipeline:
            return
        
        self.logger.info("Initializing extraction pipeline...")
        
        self.pipeline = HomeInspectionExtractionPipeline(
            mock_mode=options.get('mock_mode', False),
            enable_claude_fallback=options.get('enable_claude_fallback', True),
            confidence_threshold=options.get('confidence_threshold', 70.0)
        )
        
        self.logger.info("Extraction pipeline initialized")
    
    async def validate_pipeline(self) -> Dict[str, Any]:
        """Validate that the extraction pipeline is properly configured."""
        if not self.pipeline:
            # Initialize with default options to test
            self.pipeline = HomeInspectionExtractionPipeline(
                mock_mode=False,
                enable_claude_fallback=True,
                confidence_threshold=70.0
            )
        
        return await self.pipeline.validate_setup()
    
    async def _cleanup_loop(self):
        """Background task to cleanup old completed jobs."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_jobs()
            except asyncio.CancelledError:
                self.logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {str(e)}", exc_info=True)
    
    async def _cleanup_old_jobs(self):
        """Remove old completed jobs to prevent memory buildup."""
        if len(self.jobs) <= self.max_job_history:
            return
        
        # Keep only the most recent jobs
        cutoff = len(self.jobs) - self.max_job_history
        job_ids_to_remove = list(self.jobs.keys())[:cutoff]
        
        # Only remove completed/failed jobs, keep active ones
        removed_count = 0
        for job_id in job_ids_to_remove:
            job = self.jobs[job_id]
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMEOUT]:
                del self.jobs[job_id]
                removed_count += 1
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old jobs")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get job processing statistics."""
        stats = self.stats.copy()
        
        # Calculate additional metrics
        if stats['processing_times']:
            times = stats['processing_times']
            stats['avg_processing_time'] = sum(times) / len(times)
            stats['min_processing_time'] = min(times)
            stats['max_processing_time'] = max(times)
        
        stats['uptime'] = time.time() - stats['start_time']
        stats['active_jobs'] = len(self.active_jobs)
        stats['total_jobs_in_memory'] = len(self.jobs)
        
        if stats['total_jobs'] > 0:
            stats['success_rate'] = stats['completed_jobs'] / stats['total_jobs']
            stats['failure_rate'] = stats['failed_jobs'] / stats['total_jobs']
        
        # Add pipeline stats if available
        if self.pipeline:
            pipeline_stats = self.pipeline.get_pipeline_stats()
            stats['pipeline_stats'] = pipeline_stats
        
        return stats
    
    async def get_job_list(
        self, 
        status_filter: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[JobInfo]:
        """Get a list of jobs with optional filtering."""
        jobs = list(self.jobs.values())
        
        # Apply status filter
        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        jobs = jobs[offset:offset + limit]
        
        return [job.to_job_info() for job in jobs]