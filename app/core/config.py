from dotenv import load_dotenv
import os
from functools import lru_cache

load_dotenv()

class Settings:
    """Application settings."""
    
    def __init__(self):
        self.google_application_credentials = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", 
            "path/to/default/credentials.json"
        )
        self.edgar_identity = os.getenv(
            "EDGAR_IDENTITY", 
            "Krawlr scraper contact@krawlr.com"
        )
        self.gemini_api_key = os.getenv(
            "GEMINI_API_KEY",
            ""
        )
        self.openai_api_key = os.getenv(
            "OPENAI_API_KEY",
            ""
        )
        self.openai_model = os.getenv(
            "OPENAI_MODEL",
            "gpt-4o-mini"
        )
        
        # Pub/Sub Configuration
        self.gcp_project_id = os.getenv(
            "GCP_PROJECT_ID",
            ""
        )
        self.pubsub_scrape_jobs_topic = os.getenv(
            "PUBSUB_SCRAPE_JOBS_TOPIC",
            "scrape-jobs"
        )
        self.pubsub_scrape_completed_topic = os.getenv(
            "PUBSUB_SCRAPE_COMPLETED_TOPIC",
            "scrape-completed"
        )
        self.pubsub_scrape_progress_topic = os.getenv(
            "PUBSUB_SCRAPE_PROGRESS_TOPIC",
            "scrape-progress"
        )

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Legacy export for backward compatibility
GOOGLE_APPLICATION_CREDENTIALS = get_settings().google_application_credentials