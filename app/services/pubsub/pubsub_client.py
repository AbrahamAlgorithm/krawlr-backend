"""Google Cloud Pub/Sub client for publishing and subscribing to messages."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional
from google.cloud import pubsub_v1
from google.api_core import retry
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PubSubClient:
    """Google Cloud Pub/Sub client wrapper."""
    
    def __init__(self):
        """Initialize Pub/Sub publisher and subscriber clients."""
        self.project_id = settings.gcp_project_id
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        
        # Topic paths
        self.scrape_jobs_topic = self.publisher.topic_path(
            self.project_id, 
            settings.pubsub_scrape_jobs_topic
        )
        self.scrape_completed_topic = self.publisher.topic_path(
            self.project_id, 
            settings.pubsub_scrape_completed_topic
        )
        self.scrape_progress_topic = self.publisher.topic_path(
            self.project_id, 
            settings.pubsub_scrape_progress_topic
        )
        
        logger.info(f"PubSubClient initialized for project: {self.project_id}")
    
    async def publish_scrape_job(
        self, 
        job_id: str, 
        domain: str, 
        user_id: str,
        priority: str = "normal",
        **kwargs
    ) -> str:
        """
        Publish a scrape job to the queue.
        
        Args:
            job_id: Unique job identifier
            domain: Company domain to scrape
            user_id: User who requested the scrape
            priority: Job priority (high, normal, low)
            **kwargs: Additional job parameters
            
        Returns:
            Message ID from Pub/Sub
        """
        message_data = {
            "job_id": job_id,
            "domain": domain,
            "user_id": user_id,
            "priority": priority,
            **kwargs
        }
        
        # Convert to JSON bytes
        data = json.dumps(message_data).encode("utf-8")
        
        # Publish with retry
        future = self.publisher.publish(
            self.scrape_jobs_topic,
            data,
            job_id=job_id,
            domain=domain,
            priority=priority
        )
        
        message_id = future.result()
        logger.info(f"Published scrape job {job_id} to Pub/Sub: {message_id}")
        return message_id
    
    async def publish_scrape_completed(
        self,
        job_id: str,
        domain: str,
        user_id: str,
        status: str,
        duration_seconds: float,
        data_quality_score: Optional[float] = None,
        error: Optional[str] = None
    ) -> str:
        """
        Publish scrape completion notification.
        
        Args:
            job_id: Job identifier
            domain: Company domain
            user_id: User ID
            status: Job status (completed, failed)
            duration_seconds: Scrape duration
            data_quality_score: Optional data quality score
            error: Optional error message if failed
            
        Returns:
            Message ID from Pub/Sub
        """
        message_data = {
            "job_id": job_id,
            "domain": domain,
            "user_id": user_id,
            "status": status,
            "duration_seconds": duration_seconds,
            "data_quality_score": data_quality_score,
            "error": error
        }
        
        data = json.dumps(message_data).encode("utf-8")
        
        future = self.publisher.publish(
            self.scrape_completed_topic,
            data,
            job_id=job_id,
            status=status
        )
        
        message_id = future.result()
        logger.info(f"Published completion for job {job_id}: {message_id}")
        return message_id
    
    async def publish_scrape_progress(
        self,
        job_id: str,
        stage: str,
        progress_percent: int,
        message: str
    ) -> str:
        """
        Publish scrape progress update for real-time tracking.
        
        Args:
            job_id: Job identifier
            stage: Current scraping stage
            progress_percent: Progress percentage (0-100)
            message: Progress message
            
        Returns:
            Message ID from Pub/Sub
        """
        message_data = {
            "job_id": job_id,
            "stage": stage,
            "progress_percent": progress_percent,
            "message": message
        }
        
        data = json.dumps(message_data).encode("utf-8")
        
        future = self.publisher.publish(
            self.scrape_progress_topic,
            data,
            job_id=job_id
        )
        
        message_id = future.result()
        logger.debug(f"Published progress for job {job_id}: {progress_percent}%")
        return message_id
    
    def subscribe_to_scrape_jobs(
        self,
        callback: Callable[[pubsub_v1.subscriber.message.Message], None],
        subscription_name: str = "scrape-jobs-worker"
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """
        Subscribe to scrape jobs topic.
        
        Args:
            callback: Function to handle incoming messages
            subscription_name: Subscription identifier
            
        Returns:
            Streaming pull future
        """
        subscription_path = self.subscriber.subscription_path(
            self.project_id,
            subscription_name
        )
        
        # Create subscription if it doesn't exist
        try:
            self.subscriber.create_subscription(
                request={
                    "name": subscription_path,
                    "topic": self.scrape_jobs_topic,
                    "ack_deadline_seconds": 600  # 10 minutes for long scrapes
                }
            )
            logger.info(f"Created subscription: {subscription_name}")
        except Exception as e:
            logger.debug(f"Subscription {subscription_name} already exists: {e}")
        
        # Subscribe with callback
        streaming_pull_future = self.subscriber.subscribe(
            subscription_path,
            callback
        )
        
        logger.info(f"Subscribed to {subscription_name}")
        return streaming_pull_future
    
    def subscribe_to_scrape_completed(
        self,
        callback: Callable[[pubsub_v1.subscriber.message.Message], None],
        subscription_name: str = "scrape-completed-webhook"
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """
        Subscribe to scrape completed topic for webhooks.
        
        Args:
            callback: Function to handle incoming messages
            subscription_name: Subscription identifier
            
        Returns:
            Streaming pull future
        """
        subscription_path = self.subscriber.subscription_path(
            self.project_id,
            subscription_name
        )
        
        # Create subscription if it doesn't exist
        try:
            self.subscriber.create_subscription(
                request={
                    "name": subscription_path,
                    "topic": self.scrape_completed_topic,
                    "ack_deadline_seconds": 60
                }
            )
            logger.info(f"Created subscription: {subscription_name}")
        except Exception as e:
            logger.debug(f"Subscription {subscription_name} already exists: {e}")
        
        streaming_pull_future = self.subscriber.subscribe(
            subscription_path,
            callback
        )
        
        logger.info(f"Subscribed to {subscription_name}")
        return streaming_pull_future
    
    def create_topics(self):
        """Create all required Pub/Sub topics if they don't exist."""
        topics = [
            self.scrape_jobs_topic,
            self.scrape_completed_topic,
            self.scrape_progress_topic
        ]
        
        for topic_path in topics:
            try:
                self.publisher.create_topic(request={"name": topic_path})
                logger.info(f"Created topic: {topic_path}")
            except Exception as e:
                logger.debug(f"Topic {topic_path} already exists: {e}")


# Singleton instance
_pubsub_client: Optional[PubSubClient] = None


def get_pubsub_client() -> PubSubClient:
    """Get or create PubSubClient singleton."""
    global _pubsub_client
    if _pubsub_client is None:
        _pubsub_client = PubSubClient()
    return _pubsub_client
