"""Job queue service for managing scrape jobs with Firestore and Pub/Sub."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Any
import uuid
from google.cloud import firestore

from app.core.database import db
from app.services.pubsub.pubsub_client import get_pubsub_client

logger = logging.getLogger(__name__)


class JobQueue:
    """Manages scrape job lifecycle with Firestore and Pub/Sub."""
    
    def __init__(self):
        """Initialize job queue."""
        self.db = db
        self.pubsub = get_pubsub_client()
        self.jobs_collection = "scrape_jobs"
        logger.info("JobQueue initialized")
    
    async def enqueue_scrape_job(
        self,
        domain: str,
        user_id: str,
        priority: str = "normal",
        webhook_url: Optional[str] = None,
        **kwargs
    ) -> dict:
        """
        Enqueue a new scrape job.
        
        Args:
            domain: Company domain to scrape
            user_id: User requesting the scrape
            priority: Job priority (high, normal, low)
            webhook_url: Optional webhook URL for completion notification
            **kwargs: Additional job parameters
            
        Returns:
            Job metadata dict with job_id, status, etc.
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Create job document in Firestore
        job_data = {
            "job_id": job_id,
            "domain": domain,
            "user_id": user_id,
            "status": "queued",
            "priority": priority,
            "webhook_url": webhook_url,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "progress_percent": 0,
            "current_stage": "queued",
            "result": None,
            "error": None,
            "retry_count": 0,
            **kwargs
        }
        
        # Save to Firestore
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        job_ref.set(job_data)
        
        logger.info(f"Created job {job_id} for domain {domain}")
        
        # Publish to Pub/Sub queue
        try:
            message_id = await self.pubsub.publish_scrape_job(
                job_id=job_id,
                domain=domain,
                user_id=user_id,
                priority=priority,
                webhook_url=webhook_url,
                **kwargs
            )
            
            # Update job with message ID
            job_ref.update({
                "pubsub_message_id": message_id,
                "updated_at": datetime.now(timezone.utc)
            })
            
            logger.info(f"Published job {job_id} to Pub/Sub: {message_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish job {job_id} to Pub/Sub: {e}")
            # Mark job as failed
            job_ref.update({
                "status": "failed",
                "error": f"Failed to publish to queue: {str(e)}",
                "updated_at": datetime.now(timezone.utc)
            })
            raise
        
        return {
            "job_id": job_id,
            "status": "queued",
            "domain": domain,
            "created_at": now.isoformat(),
            "message": "Job queued successfully"
        }
    
    def get_job_status(self, job_id: str) -> Optional[dict]:
        """
        Get current job status.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job data dict or None if not found
        """
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            return None
        
        job_data = job_doc.to_dict()
        
        # Convert Firestore timestamps to ISO strings
        for field in ["created_at", "updated_at", "started_at", "completed_at"]:
            if job_data.get(field):
                job_data[field] = job_data[field].isoformat()
        
        return job_data
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        **kwargs
    ) -> None:
        """
        Update job status and metadata.
        
        Args:
            job_id: Job identifier
            status: New status
            **kwargs: Additional fields to update
        """
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        
        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
            **kwargs
        }
        
        # Set timestamps based on status
        if status == "processing" and "started_at" not in kwargs:
            update_data["started_at"] = datetime.now(timezone.utc)
        elif status in ["completed", "failed"] and "completed_at" not in kwargs:
            update_data["completed_at"] = datetime.now(timezone.utc)
        
        job_ref.update(update_data)
        logger.info(f"Updated job {job_id} status to {status}")
    
    def update_job_progress(
        self,
        job_id: str,
        stage: str,
        progress_percent: int,
        message: Optional[str] = None
    ) -> None:
        """
        Update job progress.
        
        Args:
            job_id: Job identifier
            stage: Current processing stage
            progress_percent: Progress percentage (0-100)
            message: Optional progress message
        """
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        
        update_data = {
            "current_stage": stage,
            "progress_percent": progress_percent,
            "updated_at": datetime.now(timezone.utc)
        }
        
        if message:
            update_data["progress_message"] = message
        
        job_ref.update(update_data)
        logger.debug(f"Updated job {job_id} progress: {progress_percent}% ({stage})")
    
    def mark_job_completed(
        self,
        job_id: str,
        result: dict,
        duration_seconds: float,
        data_quality_score: Optional[float] = None
    ) -> None:
        """
        Mark job as completed with results.
        
        Args:
            job_id: Job identifier
            result: Scrape result data
            duration_seconds: Job duration
            data_quality_score: Optional quality score
        """
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        
        update_data = {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "duration_seconds": duration_seconds,
            "progress_percent": 100,
            "current_stage": "completed",
            "result": result
        }
        
        if data_quality_score is not None:
            update_data["data_quality_score"] = data_quality_score
        
        job_ref.update(update_data)
        logger.info(f"Marked job {job_id} as completed")
    
    def mark_job_failed(
        self,
        job_id: str,
        error: str,
        retry: bool = False
    ) -> None:
        """
        Mark job as failed.
        
        Args:
            job_id: Job identifier
            error: Error message
            retry: Whether to retry the job
        """
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            logger.error(f"Job {job_id} not found")
            return
        
        job_data = job_doc.to_dict()
        retry_count = job_data.get("retry_count", 0)
        
        update_data = {
            "status": "failed" if not retry else "retrying",
            "error": error,
            "updated_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
            "retry_count": retry_count + 1 if retry else retry_count
        }
        
        job_ref.update(update_data)
        logger.warning(f"Marked job {job_id} as failed: {error}")
    
    def get_user_jobs(
        self,
        user_id: str,
        limit: int = 50,
        status: Optional[str] = None
    ) -> list[dict]:
        """
        Get jobs for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of jobs to return
            status: Optional status filter
            
        Returns:
            List of job data dicts
        """
        query = self.db.collection(self.jobs_collection).where("user_id", "==", user_id)
        
        if status:
            query = query.where("status", "==", status)
        
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        
        jobs = []
        for doc in query.stream():
            job_data = doc.to_dict()
            
            # Convert timestamps to ISO strings
            for field in ["created_at", "updated_at", "started_at", "completed_at"]:
                if job_data.get(field):
                    job_data[field] = job_data[field].isoformat()
            
            jobs.append(job_data)
        
        return jobs
    
    def get_queue_stats(self) -> dict:
        """
        Get queue statistics.
        
        Returns:
            Dict with queue stats
        """
        jobs_ref = self.db.collection(self.jobs_collection)
        
        # Count by status
        stats = {
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "total": 0
        }
        
        for status in ["queued", "processing", "completed", "failed"]:
            count = len(list(jobs_ref.where("status", "==", status).stream()))
            stats[status] = count
            stats["total"] += count
        
        return stats


# Singleton instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get or create JobQueue singleton."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue
