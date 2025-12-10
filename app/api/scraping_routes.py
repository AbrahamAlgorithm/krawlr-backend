"""
Scraping API endpoints with Pub/Sub job queue
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from app.core.auth import get_current_user
from app.schemas.scraping import (
    ScrapeRequest,
    ScrapeResponse,
    ScrapeJobStatus,
    CompanyIntelligence,
    UserScrapeHistory,
    HealthCheck
)
from app.services.scraping.unified_orchestrator import UnifiedOrchestrator
from app.services.scraping.firestore_service import firestore_service
from app.services.pubsub import get_job_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Scraping"])

# Initialize services
orchestrator = UnifiedOrchestrator()
job_queue = get_job_queue()


@router.post("/scrape/company", response_model=ScrapeResponse, status_code=status.HTTP_202_ACCEPTED)
async def scrape_company(
    request: ScrapeRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Start a comprehensive company intelligence scraping job via Pub/Sub queue.
    
    **🚀 HIGH-PERFORMANCE ASYNC PROCESSING**
    - Returns instantly (< 1 second) with job_id
    - Job queued in Google Cloud Pub/Sub for processing
    - Worker processes scrape in background (60-120 seconds)
    - Poll GET /scrape/status/{job_id} for progress
    - Webhook notification when complete (if configured)
    
    **Data Sources:**
    - Company profile (Wikipedia, Crunchbase, etc.)
    - Website content and structure analysis
    - Financial data (SEC EDGAR for public companies)
    - Funding and investor information (PitchBook)
    - Competitor identification
    - Founders and leadership team
    - Recent news mentions
    - **AI-powered data enrichment and cleaning**
    
    **Authentication Required**: Bearer token or API key
    
    **Rate Limits**: 
    - Free tier: 10 scrapes/day
    - Pro tier: 100 scrapes/day
    - Enterprise: Unlimited
    
    **Caching**: Results cached for 7 days (instant return if available)
    """
    user_id = current_user.get('uid') or current_user.get('id')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in authentication token"
        )
    
    try:
        # Extract domain for cache lookup
        from urllib.parse import urlparse
        parsed = urlparse(request.url if request.url.startswith('http') else f'https://{request.url}')
        domain = parsed.netloc or parsed.path
        
        # Check if recently scraped (within 7 days by anyone)
        cached_data = await firestore_service.get_cached_company_data(domain, max_age_days=7)
        
        if cached_data:
            # Return cached data immediately - no need to scrape again!
            try:
                # Handle different data structures (new vs old cached data)
                company_name = None
                scrape_id = None
                scrape_timestamp = None
                
                if 'metadata' in cached_data:
                    scrape_id = cached_data['metadata'].get('scrape_id')
                    scrape_timestamp = cached_data['metadata'].get('scrape_timestamp', 'recent')
                
                if 'company' in cached_data:
                    company_name = cached_data['company'].get('name')
                elif 'company_name' in cached_data:
                    company_name = cached_data.get('company_name')
                
                return ScrapeResponse(
                    scrape_id=scrape_id or 'cached',
                    status="completed",
                    url=request.url,
                    company_name=company_name or request.company_name,
                    message=f"✅ Returning cached data from {scrape_timestamp} scrape. Fresh data available instantly!",
                    estimated_completion_seconds=0
                )
            except Exception as e:
                # If cached data is malformed, ignore it and re-scrape
                logger.warning(f"Cached data for {domain} is malformed: {e}. Re-scraping...")
        
        # Not in cache - enqueue new scraping job via Pub/Sub
        job_result = await job_queue.enqueue_scrape_job(
            domain=domain,
            user_id=user_id,
            url=request.url,
            company_name=request.company_name,
            priority="high" if current_user.get("tier") == "enterprise" else "normal",
            webhook_url=current_user.get("webhook_url")  # Optional webhook for completion
        )
        
        return ScrapeResponse(
            scrape_id=job_result['job_id'],
            status="queued",
            url=request.url,
            company_name=request.company_name,
            message=f"🚀 Scraping job queued successfully! Job ID: {job_result['job_id']}. Check status at GET /api/v1/scrape/status/{job_result['job_id']}",
            estimated_completion_seconds=90
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue scraping job: {str(e)}"
        )


@router.get("/scrape/{scrape_id}/status", response_model=ScrapeJobStatus)
async def get_scrape_status(
    scrape_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get the current status of a scraping job from Pub/Sub queue.
    
    **Status values**:
    - `queued`: Job is in Pub/Sub queue, waiting for worker
    - `processing`: Worker is currently scraping (check progress_percent field)
    - `completed`: Scraping finished successfully (result available)
    - `failed`: Scraping encountered an error (check error field)
    - `retrying`: Job failed but will retry
    
    **Real-time progress**: progress_percent (0-100) and current_stage fields updated live
    
    **Authentication Required**: Must be the owner of the scrape job
    """
    user_id = current_user.get('uid') or current_user.get('id')
    
    try:
        job_data = job_queue.get_job_status(scrape_id)
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scraping job {scrape_id} not found"
            )
        
        # Verify ownership
        if job_data.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this scraping job"
            )
        
        # Map job_queue fields to ScrapeJobStatus schema
        return ScrapeJobStatus(
            scrape_id=job_data.get('job_id', scrape_id),
            user_id=job_data['user_id'],
            status=job_data['status'],
            progress=job_data.get('progress_percent', 0),
            url=job_data.get('url', ''),
            company_name=job_data.get('company_name'),
            created_at=job_data['created_at'],
            updated_at=job_data.get('updated_at', job_data['created_at']),
            completed_at=job_data.get('completed_at'),
            error=job_data.get('error'),
            data_quality_score=job_data.get('data_quality_score')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job status: {str(e)}"
        )


@router.get("/scrape/{scrape_id}", response_model=CompanyIntelligence)
async def get_scrape_results(
    scrape_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get the complete results of a scraping job.
    
    Returns full company intelligence data including:
    - Company profile and identity
    - Financial information and statements
    - Funding history and investors
    - Leadership team and founders
    - Products and services
    - Competitors
    - Recent news
    - Online presence and social media
    
    **Note**: This endpoint only returns data for completed jobs.
    Use GET /scrape/{scrape_id}/status to check if job is completed.
    
    **Authentication Required**: Must be the owner of the scrape job
    """
    user_id = current_user.get('uid') or current_user.get('id')
    
    try:
        job_data = await firestore_service.get_job_status(scrape_id)
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scraping job {scrape_id} not found"
            )
        
        # Verify ownership
        if job_data.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this scraping job"
            )
        
        # Check if job is completed
        if job_data.get('status') != 'completed':
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scraping job is not completed yet. Current status: {job_data.get('status')}"
            )
        
        # Get result data
        result = job_data.get('result')
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No results found for this scraping job"
            )
        
        return CompanyIntelligence(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve results: {str(e)}"
        )


@router.get("/scrape/user/history", response_model=UserScrapeHistory)
async def get_user_scrape_history(
    limit: int = 20,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get the authenticated user's scraping history.
    
    Returns a list of all scraping jobs initiated by the current user,
    ordered by creation date (most recent first).
    
    **Query Parameters**:
    - `limit`: Maximum number of scrapes to return (default: 20, max: 100)
    
    **Authentication Required**: Bearer token or API key
    """
    user_id = current_user.get('uid') or current_user.get('id')
    
    if limit > 100:
        limit = 100
    
    try:
        scrapes = await firestore_service.get_user_scrapes(user_id, limit=limit)
        
        return UserScrapeHistory(
            user_id=user_id,
            total_scrapes=len(scrapes),
            scrapes=scrapes
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scrape history: {str(e)}"
        )


@router.get("/scrape/cache/{domain}", response_model=CompanyIntelligence)
async def get_cached_company(
    domain: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get cached company data by domain (if available).
    
    This endpoint returns cached company intelligence data without scraping.
    Useful for quickly checking if data is available before starting a new scrape.
    
    **Cache Policy**: Data is cached for 7 days
    
    **Example domains**: 
    - stripe.com
    - openai.com
    - google.com
    
    **Authentication Required**: Bearer token or API key
    
    **Returns**: 
    - 200: Cached company data
    - 404: No cached data available (need to scrape)
    """
    try:
        cached_data = await firestore_service.get_cached_company_data(domain, max_age_days=7)
        
        if not cached_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cached data for {domain}. Please start a new scrape with POST /api/v1/scrape/company"
            )
        
        return CompanyIntelligence(**cached_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cached data: {str(e)}"
        )


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    API health check endpoint.
    
    Returns the current status of the API and its dependencies.
    """
    try:
        # Check Firestore connection
        firestore_status = "healthy"
        try:
            await firestore_service.health_check()
        except Exception:
            firestore_status = "unhealthy"
        
        # Check orchestrator
        orchestrator_status = "healthy" if orchestrator else "unhealthy"
        
        return HealthCheck(
            status="healthy",
            timestamp=datetime.utcnow(),
            services={
                "firestore": firestore_status,
                "orchestrator": orchestrator_status,
                "ai_enrichment": "healthy"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


# ============================================================================
# BACKGROUND TASK
# ============================================================================

async def run_scraping_job(
    scrape_id: str,
    url: str,
    user_id: str,
    company_name: Optional[str] = None
):
    """
    Background task to run the actual scraping job.
    
    This function:
    1. Updates job status to 'processing'
    2. Runs the unified orchestrator
    3. Saves results to Firestore
    4. Updates job status to 'completed' or 'failed'
    """
    try:
        # Update status to processing
        await firestore_service.update_job_status(
            scrape_id,
            status="processing",
            progress=5
        )
        
        # Run the unified orchestrator
        result = await orchestrator.get_complete_company_intelligence(
            website_url=url,
            company_name=company_name,
            user_id=user_id,
            scrape_id=scrape_id
        )
        
        # Save results
        await firestore_service.save_job_result(scrape_id, result)
        
        # Mark as completed
        await firestore_service.update_job_status(
            scrape_id,
            status="completed",
            progress=100
        )
        
    except Exception as e:
        # Mark as failed
        await firestore_service.update_job_status(
            scrape_id,
            status="failed",
            progress=0,
            error=str(e)
        )
        # Log error but don't raise (background task)
        print(f"❌ Scraping job {scrape_id} failed: {str(e)}")
