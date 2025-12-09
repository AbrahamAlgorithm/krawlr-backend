"""
Scraping API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Dict, Any, Optional
from datetime import datetime

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

router = APIRouter(prefix="/api/v1", tags=["Scraping"])

# Initialize orchestrator
orchestrator = UnifiedOrchestrator()


@router.post("/scrape/company", response_model=ScrapeResponse, status_code=status.HTTP_202_ACCEPTED)
async def scrape_company(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """
    Start a comprehensive company intelligence scraping job.
    
    This endpoint initiates an asynchronous scraping process that:
    - Scrapes company profile (Wikipedia, Crunchbase, etc.)
    - Analyzes website content and structure
    - Extracts financial data (SEC EDGAR for public companies)
    - Gathers funding information
    - Identifies competitors
    - Finds founders and leadership
    - Collects recent news mentions
    - **Enriches and cleans data with AI**
    
    The job runs in the background. Use the returned `scrape_id` to check progress.
    
    **Authentication Required**: Bearer token or API key
    
    **Rate Limits**: 
    - Free tier: 10 scrapes/day
    - Pro tier: 100 scrapes/day
    - Enterprise: Unlimited
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
            return ScrapeResponse(
                scrape_id=cached_data['metadata']['scrape_id'],
                status="completed",
                url=request.url,
                company_name=cached_data['company'].get('name'),
                message=f"✅ Returning cached data from {cached_data['metadata'].get('scrape_timestamp', 'recent')} scrape. Fresh data available instantly!",
                estimated_completion_seconds=0
            )
        
        # Not in cache - create new scraping job
        scrape_id = await firestore_service.create_scraping_job(
            url=request.url,
            user_id=user_id,
            company_name=request.company_name
        )
        
        # Start background scraping task
        background_tasks.add_task(
            run_scraping_job,
            scrape_id=scrape_id,
            url=request.url,
            company_name=request.company_name,
            user_id=user_id
        )
        
        return ScrapeResponse(
            scrape_id=scrape_id,
            status="pending",
            url=request.url,
            company_name=request.company_name,
            message="Scraping job started successfully. Check status at GET /api/v1/scrape/{scrape_id}",
            estimated_completion_seconds=120
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scraping job: {str(e)}"
        )


@router.get("/scrape/{scrape_id}/status", response_model=ScrapeJobStatus)
async def get_scrape_status(
    scrape_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get the current status of a scraping job.
    
    **Status values**:
    - `pending`: Job is queued, not started yet
    - `processing`: Currently scraping (check progress field)
    - `completed`: Scraping finished successfully
    - `failed`: Scraping encountered an error
    
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
        
        return ScrapeJobStatus(**job_data)
        
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
