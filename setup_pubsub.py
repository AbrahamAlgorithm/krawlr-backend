"""
Setup Google Cloud Pub/Sub topics and subscriptions.
Run this once to initialize the Pub/Sub infrastructure.

Usage:
    python setup_pubsub.py
"""

import logging
from app.services.pubsub import get_pubsub_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Create all required Pub/Sub topics and subscriptions."""
    logger.info("🚀 Setting up Google Cloud Pub/Sub infrastructure...")
    
    try:
        pubsub = get_pubsub_client()
        
        # Create topics
        logger.info("📝 Creating topics...")
        pubsub.create_topics()
        
        logger.info("✅ Pub/Sub setup complete!")
        logger.info("")
        logger.info("📋 Created topics:")
        logger.info(f"   - {pubsub.scrape_jobs_topic}")
        logger.info(f"   - {pubsub.scrape_completed_topic}")
        logger.info(f"   - {pubsub.scrape_progress_topic}")
        logger.info("")
        logger.info("🎯 Next steps:")
        logger.info("   1. Start the API server: uvicorn app.main:app --reload")
        logger.info("   2. Start workers: python worker.py")
        logger.info("   3. Start webhook service: python webhook_service.py")
        
    except Exception as e:
        logger.error(f"❌ Failed to setup Pub/Sub: {e}")
        raise


if __name__ == "__main__":
    main()
