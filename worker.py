"""
Pub/Sub Worker Service
Subscribes to scrape-jobs topic and processes scraping tasks.

Run this as a separate process/container:
    python worker.py

For production:
    - Deploy multiple worker instances for horizontal scaling
    - Configure auto-scaling based on queue depth
    - Monitor with Cloud Logging and Cloud Monitoring
"""

import asyncio
import logging
import signal
import sys
import json
import time
from datetime import datetime, timezone
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
from app.services.scraping.unified_orchestrator import UnifiedOrchestrator  # Use real orchestrator
from app.services.scraping.firestore_service import firestore_service


class ScrapeWorker:
    """Worker that processes scrape jobs from Pub/Sub queue."""
    
    def __init__(self):
        """Initialize worker with required services."""
        self.pubsub = get_pubsub_client()
        self.job_queue = get_job_queue()
        # Initialize with longer timeout (5 minutes)
        self.orchestrator = UnifiedOrchestrator(max_workers=6, timeout=300)
        self.running = False
        self.streaming_pull_future = None
        
        logger.info("🚀 ScrapeWorker initialized with 5-minute timeout")
    
    def callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        """
        Process incoming scrape job messages.
        
        Args:
            message: Pub/Sub message containing job data
        """
        try:
            # Parse message data
            data = json.loads(message.data.decode("utf-8"))
            job_id = data.get("job_id")
            domain = data.get("domain")
            user_id = data.get("user_id")
            
            logger.info(f"📨 Received job {job_id} for domain {domain}")
            
            # Update job status to processing
            self.job_queue.update_job_status(
                job_id=job_id,
                status="processing"
            )
            
            # Publish progress: Starting
            asyncio.run(self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="starting",
                progress_percent=0,
                message="Worker picked up job, initializing scrapers..."
            ))
            
            # Run the scraping job
            start_time = time.time()
            result = asyncio.run(self.run_scraping_job(
                job_id=job_id,
                domain=domain,
                url=data.get("url"),
                company_name=data.get("company_name"),
                user_id=user_id
            ))
            duration = time.time() - start_time
            
            if result and not result.get("error"):
                # Success - mark as completed
                self.job_queue.mark_job_completed(
                    job_id=job_id,
                    result=result,
                    duration_seconds=duration,
                    data_quality_score=result.get("metadata", {}).get("data_quality_score")
                )
                
                # Publish completion notification
                asyncio.run(self.pubsub.publish_scrape_completed(
                    job_id=job_id,
                    domain=domain,
                    user_id=user_id,
                    status="completed",
                    duration_seconds=duration,
                    data_quality_score=result.get("metadata", {}).get("data_quality_score")
                ))
                
                logger.info(f"✅ Job {job_id} completed successfully in {duration:.2f}s")
                message.ack()
                
            else:
                # Failed - mark as failed
                error = result.get("error", "Unknown error") if result else "Scraping returned no result"
                self.job_queue.mark_job_failed(
                    job_id=job_id,
                    error=error,
                    retry=False  # Don't auto-retry for now
                )
                
                # Publish failure notification
                asyncio.run(self.pubsub.publish_scrape_completed(
                    job_id=job_id,
                    domain=domain,
                    user_id=user_id,
                    status="failed",
                    duration_seconds=duration,
                    error=error
                ))
                
                logger.error(f"❌ Job {job_id} failed: {error}")
                message.ack()  # Ack anyway to prevent infinite retries
                
        except Exception as e:
            logger.error(f"💥 Error processing message: {e}", exc_info=True)
            
            # Try to mark job as failed if we have job_id
            try:
                if 'job_id' in locals():
                    self.job_queue.mark_job_failed(
                        job_id=job_id,
                        error=str(e),
                        retry=False
                    )
            except:
                pass
            
            # Nack the message to retry (Pub/Sub will retry with exponential backoff)
            message.nack()
    
    async def run_scraping_job(
        self,
        job_id: str,
        domain: str,
        url: Optional[str],
        company_name: Optional[str],
        user_id: str
    ) -> dict:
        """
        Run the actual scraping orchestration with progress updates.
        
        Args:
            job_id: Job identifier
            domain: Company domain
            url: Company URL
            company_name: Optional company name
            user_id: User ID
            
        Returns:
            Scraping result dict
        """
        try:
            # Progress: Profile scraping (10%)
            self.job_queue.update_job_progress(
                job_id=job_id,
                stage="profile",
                progress_percent=10,
                message="Scraping company profile..."
            )
            await self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="profile",
                progress_percent=10,
                message="Scraping company profile from Wikipedia, Crunchbase, etc."
            )
            
            # Progress: Website analysis (30%)
            self.job_queue.update_job_progress(
                job_id=job_id,
                stage="website",
                progress_percent=30,
                message="Analyzing website content..."
            )
            await self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="website",
                progress_percent=30,
                message="Analyzing website structure and extracting metadata"
            )
            
            # Progress: Financial data (50%)
            self.job_queue.update_job_progress(
                job_id=job_id,
                stage="financial",
                progress_percent=50,
                message="Fetching financial data..."
            )
            await self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="financial",
                progress_percent=50,
                message="Gathering financial data from EDGAR and PitchBook"
            )
            
            # Run unified orchestrator
            result = await self.orchestrator.get_complete_company_intelligence(
                website_url=url or f"https://{domain}",
                company_name=company_name,
                user_id=user_id,
                scrape_id=job_id
            )
            
            # Progress: AI enrichment (80%)
            self.job_queue.update_job_progress(
                job_id=job_id,
                stage="enrichment",
                progress_percent=80,
                message="Enriching data with AI..."
            )
            await self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="enrichment",
                progress_percent=80,
                message="AI-powered data enrichment and cleaning"
            )
            
            # Progress: Saving (95%)
            self.job_queue.update_job_progress(
                job_id=job_id,
                stage="saving",
                progress_percent=95,
                message="Saving to database..."
            )
            await self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="saving",
                progress_percent=95,
                message="Saving results to Firestore"
            )
            
            # Log result summary
            logger.info(f"Scrape result keys: {list(result.keys())}")
            logger.info(f"Company name: {result.get('company_name', 'N/A')}")
            logger.info(f"Domain: {result.get('domain', 'N/A')}")
            
            # Save to cache
            await firestore_service.save_company_data(domain, result)
            
            # Progress: Complete (100%)
            self.job_queue.update_job_progress(
                job_id=job_id,
                stage="completed",
                progress_percent=100,
                message="Scraping completed successfully!"
            )
            await self.pubsub.publish_scrape_progress(
                job_id=job_id,
                stage="completed",
                progress_percent=100,
                message="All data scraped, enriched, and saved successfully"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in scraping job {job_id}: {e}", exc_info=True)
            return {
                "error": str(e),
                "job_id": job_id,
                "domain": domain
            }
    
    def start(self):
        """Start the worker to listen for jobs."""
        logger.info("🔥 Starting ScrapeWorker...")
        logger.info("📡 Subscribing to scrape-jobs topic...")
        
        self.running = True
        
        # Subscribe to scrape-jobs topic
        self.streaming_pull_future = self.pubsub.subscribe_to_scrape_jobs(
            callback=self.callback,
            subscription_name="scrape-jobs-worker"
        )
        
        logger.info("✅ Worker is running and listening for jobs!")
        logger.info("💡 Press Ctrl+C to stop gracefully...")
        
        try:
            # Block and listen for messages
            self.streaming_pull_future.result()
        except KeyboardInterrupt:
            logger.info("⚠️  Received interrupt signal, shutting down gracefully...")
            self.stop()
        except Exception as e:
            logger.error(f"💥 Worker error: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop the worker gracefully."""
        logger.info("🛑 Stopping ScrapeWorker...")
        
        self.running = False
        
        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()
            logger.info("✅ Cancelled subscription")
        
        logger.info("👋 Worker stopped")


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point for worker."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start worker
    worker = ScrapeWorker()
    worker.start()


if __name__ == "__main__":
    main()
