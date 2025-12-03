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

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Legacy export for backward compatibility
GOOGLE_APPLICATION_CREDENTIALS = get_settings().google_application_credentials