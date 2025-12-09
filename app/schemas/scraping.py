"""
Pydantic schemas for scraping API endpoints
"""
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime


class ScrapeRequest(BaseModel):
    """Request to scrape a company website"""
    url: str = Field(..., description="Company website URL to scrape")
    company_name: Optional[str] = Field(None, description="Optional company name override")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is properly formatted"""
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            v = f"https://{v}"
        return v


class ScrapeResponse(BaseModel):
    """Response from starting a scrape job"""
    scrape_id: str = Field(..., description="Unique identifier for this scrape")
    status: str = Field(..., description="Job status: pending, processing, completed, failed")
    url: str = Field(..., description="URL being scraped")
    company_name: Optional[str] = Field(None, description="Extracted or provided company name")
    message: str = Field(..., description="Human-readable status message")
    estimated_completion_seconds: Optional[int] = Field(None, description="Estimated time to completion")
    

class ScrapeJobStatus(BaseModel):
    """Status of a scraping job"""
    scrape_id: str
    user_id: str
    status: str = Field(..., description="pending, processing, completed, failed")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage 0-100")
    url: str
    company_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    data_quality_score: Optional[float] = Field(None, ge=0, le=100, description="Data completeness score")


class CompanyIntelligence(BaseModel):
    """Complete company intelligence data - matches orchestrator output"""
    company: Dict[str, Any]
    financials: Dict[str, Any]
    funding: Dict[str, Any]
    people: Dict[str, Any]
    products: List[Any]  # Can be strings or dicts - AI enrichment may return either
    competitors: List[Any]  # Can be strings or dicts - AI enrichment may return either
    news: Dict[str, Any]
    online_presence: Dict[str, Any]
    metadata: Dict[str, Any]  # Contains scrape_id, user_id, quality_score, etc.


class UserScrapeHistory(BaseModel):
    """User's scraping history"""
    user_id: str
    total_scrapes: int
    scrapes: List[ScrapeJobStatus]


class HealthCheck(BaseModel):
    """API health check response"""
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    services: Dict[str, str] = Field(default_factory=dict)
