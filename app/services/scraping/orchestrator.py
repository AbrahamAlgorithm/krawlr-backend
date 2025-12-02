from app.services.scraping.website_scraper import website_scraper
from app.services.scraping.google_search_scraper import google_search_scraper
from app.services.scraping.edgar_scraper import sec_edgar_scraper
from app.services.scraping.firestore_service import firestore_service
from app.services.utils.validators import extract_domain
from typing import Dict, Optional
import asyncio

class ScrapingOrchestrator:
    """
    Orchestrates all scraping services to build a comprehensive company profile.
    Runs as a background task and stores results in Firestore.
    """
    
    async def start_scraping_job(self, url: str, user_id: Optional[str] = None) -> str:
        """
        Start a comprehensive scraping job as a background task.
        
        Args:
            url: Target company website URL
            user_id: Optional user ID who initiated the scrape
        
        Returns:
            job_id: Unique identifier to track job progress
        """
        # Create job in Firestore
        job_id = await firestore_service.create_scraping_job(url, user_id)
        
        # Run scraping in background
        asyncio.create_task(self._run_scraping_job(job_id, url))
        
        print(f"🚀 Started scraping job {job_id} for {url}")
        return job_id
    
    async def _run_scraping_job(self, job_id: str, url: str):
        """
        Execute the complete scraping workflow.
        Updates job progress in Firestore as it proceeds.
        """
        try:
            await firestore_service.update_job_status(job_id, 'in_progress', progress=0)
            
            domain = extract_domain(url)
            company_name = None
            
            result = {
                'url': url,
                'domain': domain,
                'identity': {},
                'founders': [],
                'financials': {},
                'funding': [],
                'investors': [],
                'competitors': [],
                'products': [],
                'sitemap': [],
                'pages': [],
                'news': []
            }
            
            # Step 1: Identity Scraping (40% of work)
            print(f"\n{'='*70}")
            print(f"🔍 STEP 1/5: Scraping company identity from website")
            print(f"{'='*70}")
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=10)
            
            identity_data = await website_scraper.scrape(url, max_pages=200)
            result['identity'] = identity_data
            result['sitemap'] = identity_data.get('sitemap_urls', [])
            result['pages'] = identity_data.get('internal_links', [])
            result['products'] = identity_data.get('products', [])
            
            company_name = identity_data.get('company_name', domain)
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=40)
            
            # Step 2: Founder & Management (10% of work)
            print(f"\n{'='*70}")
            print(f"👥 STEP 2/5: Searching for founders and executives")
            print(f"{'='*70}")
            
            founders = await google_search_scraper.search_founders(company_name, limit=10)
            result['founders'] = founders
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=50)
            
            # Step 3: Financial Data (15% of work)
            print(f"\n{'='*70}")
            print(f"💰 STEP 3/5: Scraping financial data from SEC EDGAR")
            print(f"{'='*70}")
            
            financial_data = await sec_edgar_scraper.scrape_financials(company_name)
            result['financials'] = financial_data
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=65)
            
            # Step 4: Funding & Investors (10% of work)
            print(f"\n{'='*70}")
            print(f"💸 STEP 4/5: Searching for funding information")
            print(f"{'='*70}")
            
            funding_data = await google_search_scraper.search_funding(company_name, limit=10)
            result['funding'] = funding_data
            
            # Extract investor names from funding data
            investors = []
            for funding_item in funding_data:
                desc = funding_item.get('description', '').lower()
                # Simple investor extraction (could be enhanced)
                if 'led by' in desc or 'investors include' in desc:
                    investors.append({
                        'source': funding_item.get('title'),
                        'details': funding_item.get('description')
                    })
            result['investors'] = investors
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=75)
            
            # Step 5: Competitors & News (15% of work)
            print(f"\n{'='*70}")
            print(f"📊 STEP 5/5: Finding competitors and news")
            print(f"{'='*70}")
            
            # Get competitors
            competitors = await google_search_scraper.search_competitors(domain, limit=10)
            result['competitors'] = competitors
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=85)
            
            # Get news mentions
            news = await google_search_scraper.search_news(company_name, limit=15)
            result['news'] = news
            
            await firestore_service.update_job_status(job_id, 'in_progress', progress=95)
            
            # Save final result
            await firestore_service.save_job_result(job_id, result)
            
            print(f"\n{'='*70}")
            print(f"✅ SCRAPING COMPLETED SUCCESSFULLY")
            print(f"{'='*70}")
            print(f"📊 Summary:")
            print(f"  - Company: {company_name}")
            print(f"  - Products: {len(result['products'])}")
            print(f"  - Founders: {len(result['founders'])}")
            print(f"  - Competitors: {len(result['competitors'])}")
            print(f"  - News: {len(result['news'])}")
            print(f"  - Pages crawled: {len(result['sitemap']) + len(result['pages'])}")
            print(f"{'='*70}\n")
        
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            print(f"❌ {error_msg}")
            await firestore_service.update_job_status(
                job_id,
                'failed',
                progress=0,
                error=error_msg
            )
    
    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get the current status of a scraping job."""
        return await firestore_service.get_job_status(job_id)
    
    async def get_cached_company_data(self, domain: str) -> Optional[Dict]:
        """Get cached company data if available."""
        return await firestore_service.get_company_data(domain)

# Create singleton instance
scraping_orchestrator = ScrapingOrchestrator()
