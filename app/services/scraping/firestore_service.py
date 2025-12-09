from app.core.database import db
from datetime import datetime
from typing import Dict, Optional, List
import uuid
from google.cloud import firestore

class FirestoreService:
    """
    Service for storing and retrieving scraping job data in Firestore.
    """
    
    def __init__(self):
        self.db = db
        self.jobs_collection = 'scraping_jobs'
        self.companies_collection = 'companies'
    
    async def create_scraping_job(
        self, 
        url: str, 
        user_id: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> str:
        """
        Create a new scraping job.
        
        Args:
            url: Website URL to scrape
            user_id: User who initiated the scrape
            company_name: Optional company name override
        
        Returns:
            job_id: Unique identifier for the job
        """
        job_id = str(uuid.uuid4())
        
        job_data = {
            'scrape_id': job_id,
            'url': url,
            'user_id': user_id,
            'company_name': company_name,
            'status': 'pending',  # pending, processing, completed, failed
            'progress': 0,  # 0-100
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'result': None,
            'error': None
        }
        
        self.db.collection(self.jobs_collection).document(job_id).set(job_data)
        
        print(f"✅ Created scraping job: {job_id} for user: {user_id}")
        return job_id
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[int] = None,
        error: Optional[str] = None
    ):
        """Update job status and progress."""
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        
        update_data = {
            'status': status,
            'updated_at': datetime.utcnow()
        }
        
        if progress is not None:
            update_data['progress'] = progress
        
        if error:
            update_data['error'] = error
        
        job_ref.update(update_data)
        
        print(f"📝 Updated job {job_id}: {status} ({progress}%)" if progress else f"📝 Updated job {job_id}: {status}")
    
    async def save_job_result(self, job_id: str, result: Dict):
        """
        Save the final scraping result.
        Also saves to companies collection for faster lookups.
        """
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        
        # Update job with result
        job_ref.update({
            'status': 'completed',
            'progress': 100,
            'result': result,
            'updated_at': datetime.utcnow(),
            'completed_at': datetime.utcnow()
        })
        
        # Save to companies collection (keyed by domain)
        # Domain is in result['company']['domain'] in the unified schema
        domain = result.get('company', {}).get('domain')
        if domain:
            company_ref = self.db.collection(self.companies_collection).document(domain)
            company_ref.set({
                'domain': domain,
                'data': result,
                'last_scraped': datetime.utcnow(),
                'scrape_count': firestore.Increment(1)
            }, merge=True)
            
            print(f"💾 Saved company data for: {domain}")
        else:
            print(f"⚠️  No domain found in result - cannot cache company data")
        
        print(f"✅ Job completed: {job_id}")
    
    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get current status of a scraping job."""
        job_ref = self.db.collection(self.jobs_collection).document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            return None
        
        return job_doc.to_dict()
    
    async def get_company_data(self, domain: str) -> Optional[Dict]:
        """Get cached company data by domain."""
        company_ref = self.db.collection(self.companies_collection).document(domain)
        company_doc = company_ref.get()
        
        if not company_doc.exists:
            return None
        
        return company_doc.to_dict().get('data')
    
    async def is_recently_scraped(self, domain: str, hours: int = 24) -> bool:
        """Check if a domain was recently scraped."""
        company_ref = self.db.collection(self.companies_collection).document(domain)
        company_doc = company_ref.get()
        
        if not company_doc.exists:
            return False
        
        data = company_doc.to_dict()
        last_scraped = data.get('last_scraped')
        
        if not last_scraped:
            return False
        
        # Check if scraped within specified hours
        time_diff = datetime.utcnow() - last_scraped
        return time_diff.total_seconds() < (hours * 3600)
    
    async def get_cached_company_data(self, domain: str, max_age_days: int = 7) -> Optional[Dict]:
        """
        Get cached company data if it exists and is fresh enough.
        
        Args:
            domain: Company domain (e.g., 'stripe.com')
            max_age_days: Maximum age of cached data in days (default: 7)
            
        Returns:
            Company intelligence data if cached and fresh, None otherwise
        """
        company_ref = self.db.collection(self.companies_collection).document(domain)
        company_doc = company_ref.get()
        
        if not company_doc.exists:
            return None
        
        data = company_doc.to_dict()
        last_scraped = data.get('last_scraped')
        
        if not last_scraped:
            return None
        
        # Check if cache is still fresh
        time_diff = datetime.utcnow() - last_scraped
        max_age_seconds = max_age_days * 24 * 3600
        
        if time_diff.total_seconds() > max_age_seconds:
            print(f"⏰ Cache expired for {domain} (age: {time_diff.days} days)")
            return None
        
        company_data = data.get('data')
        if company_data:
            print(f"✅ Cache HIT for {domain} (age: {time_diff.days} days, {time_diff.seconds // 3600} hours)")
            return company_data
        
        return None
    
    async def get_user_jobs(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get all scraping jobs for a user."""
        jobs_ref = (
            self.db.collection(self.jobs_collection)
            .where('user_id', '==', user_id)
            .order_by('created_at', direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        
        jobs = []
        for doc in jobs_ref.stream():
            job_data = doc.to_dict()
            # Remove large result data for list view
            if 'result' in job_data:
                job_data['has_result'] = True
                del job_data['result']
            jobs.append(job_data)
        
        return jobs
    
    async def get_user_scrapes(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get user's scraping history with formatted data."""
        jobs = await self.get_user_jobs(user_id, limit)
        
        # Format for API response
        formatted = []
        for job in jobs:
            formatted.append({
                'scrape_id': job.get('scrape_id', job.get('job_id')),
                'user_id': job.get('user_id'),
                'status': job.get('status'),
                'progress': job.get('progress', 0),
                'url': job.get('url'),
                'company_name': job.get('company_name'),
                'created_at': job.get('created_at'),
                'updated_at': job.get('updated_at'),
                'completed_at': job.get('completed_at'),
                'error': job.get('error'),
                'data_quality_score': job.get('result', {}).get('metadata', {}).get('data_quality_score') if job.get('has_result') else None
            })
        
        return formatted
    
    async def health_check(self) -> bool:
        """Check if Firestore connection is healthy."""
        try:
            # Try to read a document (creates it if doesn't exist)
            self.db.collection('_health_check').document('ping').set({
                'timestamp': datetime.utcnow()
            })
            return True
        except Exception as e:
            print(f"❌ Firestore health check failed: {e}")
            return False

# Create singleton instance
firestore_service = FirestoreService()
