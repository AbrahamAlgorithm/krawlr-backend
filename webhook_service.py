"""
Webhook notification service.
Subscribes to scrape-completed topic and sends webhooks to users.

Run this as a separate service:
    python webhook_service.py
"""

import asyncio
import logging
import signal
import sys
import json
import httpx
from typing import Optional

from google.cloud import pubsub_v1

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import services
from app.services.pubsub import get_pubsub_client, get_job_queue
from app.core.database import db


class WebhookService:
    """Service that sends webhook notifications when scrapes complete."""
    
    def __init__(self):
        """Initialize webhook service."""
        self.pubsub = get_pubsub_client()
        self.job_queue = get_job_queue()
        self.db = db
        self.running = False
        self.streaming_pull_future = None
        
        logger.info("🔔 WebhookService initialized")
    
    def callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """
        Process scrape completion notifications and send webhooks.
        
        Args:
            message: Pub/Sub message containing completion data
        """
        try:
            # Parse message data
            data = json.loads(message.data.decode("utf-8"))
            job_id = data.get("job_id")
            user_id = data.get("user_id")
            status = data.get("status")
            domain = data.get("domain")
            
            logger.info(f"📨 Received completion notification for job {job_id}: {status}")
            
            # Get job data to check for webhook URL
            job_data = self.job_queue.get_job_status(job_id)
            
            if not job_data:
                logger.warning(f"Job {job_id} not found in database")
                message.ack()
                return
            
            webhook_url = job_data.get("webhook_url")
            
            if not webhook_url:
                # No webhook configured, check user settings
                user_ref = self.db.collection("users").document(user_id)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    webhook_url = user_data.get("webhook_url")
            
            if webhook_url:
                # Send webhook
                asyncio.run(self.send_webhook(
                    webhook_url=webhook_url,
                    job_id=job_id,
                    domain=domain,
                    status=status,
                    data=data
                ))
            else:
                logger.debug(f"No webhook URL configured for job {job_id}")
            
            message.ack()
            
        except Exception as e:
            logger.error(f"💥 Error processing webhook notification: {e}", exc_info=True)
            message.nack()
    
    async def send_webhook(
        self,
        webhook_url: str,
        job_id: str,
        domain: str,
        status: str,
        data: dict
    ) -> None:
        """
        Send webhook HTTP POST to user's configured URL.
        
        Args:
            webhook_url: User's webhook endpoint
            job_id: Job identifier
            domain: Company domain
            status: Job status (completed, failed)
            data: Complete job data
        """
        try:
            payload = {
                "event": "scrape.completed",
                "job_id": job_id,
                "domain": domain,
                "status": status,
                "duration_seconds": data.get("duration_seconds"),
                "data_quality_score": data.get("data_quality_score"),
                "error": data.get("error"),
                "timestamp": data.get("timestamp"),
                "result_url": f"/api/v1/scrape/{job_id}"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Krawlr-Webhook/1.0",
                        "X-Krawlr-Event": "scrape.completed",
                        "X-Krawlr-Job-Id": job_id
                    }
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"✅ Webhook sent successfully to {webhook_url} for job {job_id}")
                else:
                    logger.warning(f"⚠️  Webhook returned {response.status_code} for job {job_id}")
                    
        except httpx.TimeoutException:
            logger.error(f"⏰ Webhook timeout for {webhook_url} (job {job_id})")
        except Exception as e:
            logger.error(f"❌ Failed to send webhook to {webhook_url}: {e}")
    
    def start(self):
        """Start the webhook service."""
        logger.info("🔥 Starting WebhookService...")
        logger.info("📡 Subscribing to scrape-completed topic...")
        
        self.running = True
        
        # Subscribe to scrape-completed topic
        self.streaming_pull_future = self.pubsub.subscribe_to_scrape_completed(
            callback=self.callback,
            subscription_name="scrape-completed-webhook"
        )
        
        logger.info("✅ WebhookService is running!")
        logger.info("💡 Press Ctrl+C to stop gracefully...")
        
        try:
            # Block and listen for messages
            self.streaming_pull_future.result()
        except KeyboardInterrupt:
            logger.info("⚠️  Received interrupt signal, shutting down gracefully...")
            self.stop()
        except Exception as e:
            logger.error(f"💥 WebhookService error: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop the service gracefully."""
        logger.info("🛑 Stopping WebhookService...")
        
        self.running = False
        
        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()
            logger.info("✅ Cancelled subscription")
        
        logger.info("👋 WebhookService stopped")


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point for webhook service."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start service
    service = WebhookService()
    service.start()


if __name__ == "__main__":
    main()
