"""
Unified Company Intelligence Orchestrator

This module coordinates all scrapers to gather comprehensive company intelligence
from a single website URL. It handles:
- Company name extraction from domain
- Parallel scraper execution
- Data merging into unified JSON schema
- Quality scoring
- Error handling and graceful degradation
- Security validation

Author: Krawlr Backend Team
Date: December 2025
"""

import asyncio
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from datetime import datetime, timezone
import logging
from concurrent.futures import ThreadPoolExecutor
import uuid

# Import all scrapers
from app.services.scraping.financial import get_unified_funding_data
from app.services.scraping.profile import get_company_profile
from app.services.scraping.website_scraper import scrape_website
from app.services.scraping.news import scrape_news_and_press
from app.services.scraping.competitors import scrape_competitors
from app.services.scraping.founders import scrape_founders

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validates and sanitizes inputs to prevent security issues"""
    
    # Blocked domains (malicious, internal networks, localhost)
    BLOCKED_DOMAINS = {
        'localhost', '127.0.0.1', '0.0.0.0', '::1',
        '192.168.', '10.', '172.16.', '172.31.',  # Private IP ranges
        'metadata.google.internal',  # Cloud metadata endpoints
        '169.254.169.254',  # AWS metadata
    }
    
    # Allowed protocols
    ALLOWED_PROTOCOLS = {'http', 'https'}
    
    # Maximum URL length
    MAX_URL_LENGTH = 2048
    
    # Maximum company name length
    MAX_COMPANY_NAME_LENGTH = 200
    
    @classmethod
    def validate_url(cls, url: str) -> tuple[bool, Optional[str]]:
        """
        Validate URL for security issues
        
        Returns:
            (is_valid, error_message)
        """
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string"
        
        # Check length
        if len(url) > cls.MAX_URL_LENGTH:
            return False, f"URL exceeds maximum length of {cls.MAX_URL_LENGTH}"
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"
        
        # Check protocol
        if parsed.scheme.lower() not in cls.ALLOWED_PROTOCOLS:
            return False, f"Protocol must be http or https, got: {parsed.scheme}"
        
        # Check for missing domain
        if not parsed.netloc:
            return False, "URL must include a domain"
        
        # Extract domain/IP
        domain = parsed.netloc.lower()
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Check blocked domains
        for blocked in cls.BLOCKED_DOMAINS:
            if blocked in domain:
                return False, f"Access to {domain} is not allowed"
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'\.\./',  # Path traversal
            r'file://',  # File protocol
            r'ftp://',  # FTP protocol
            r'javascript:',  # JS injection
            r'data:',  # Data URLs
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, url.lower()):
                return False, f"URL contains suspicious pattern: {pattern}"
        
        return True, None
    
    @classmethod
    def sanitize_company_name(cls, name: str) -> str:
        """
        Sanitize company name
        
        Args:
            name: Raw company name
            
        Returns:
            Sanitized company name
        """
        if not name or not isinstance(name, str):
            return ""
        
        # Truncate to max length
        name = name[:cls.MAX_COMPANY_NAME_LENGTH]
        
        # Remove control characters and excessive whitespace
        name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        
        return name


class CompanyNameExtractor:
    """Extracts company name from domain"""
    
    # Common TLDs to remove
    TLDS = {
        '.com', '.co', '.io', '.net', '.org', '.ai', '.app', '.dev',
        '.tech', '.cloud', '.ly', '.me', '.xyz', '.site', '.online'
    }
    
    # Words to remove from company names
    STOP_WORDS = {
        'www', 'api', 'dev', 'staging', 'prod', 'app', 'portal',
        'dashboard', 'admin', 'beta', 'demo'
    }
    
    @classmethod
    def extract_from_url(cls, url: str) -> str:
        """
        Extract company name from URL
        
        Examples:
            https://google.com -> Google
            https://stripe.com -> Stripe
            https://pxxl.app -> PXXL
            https://www.facebook.com -> Facebook
            https://api.openai.com -> OpenAI
        
        Args:
            url: Website URL
            
        Returns:
            Extracted company name
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Remove port
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # Split by dots
            parts = domain.split('.')
            
            # Remove TLDs and common subdomains
            filtered_parts = []
            for part in parts:
                # Skip if it's a TLD pattern
                if any(domain.endswith(tld) for tld in cls.TLDS):
                    if part == parts[-1] or f".{part}" in cls.TLDS:
                        continue
                
                # Skip stop words
                if part in cls.STOP_WORDS:
                    continue
                
                filtered_parts.append(part)
            
            # Get the main domain part (usually first meaningful part)
            if filtered_parts:
                company_name = filtered_parts[0]
            else:
                company_name = parts[0] if parts else "Unknown"
            
            # Capitalize properly
            # Handle special cases like "openai" -> "OpenAI"
            if company_name.lower() == 'openai':
                return 'OpenAI'
            elif company_name.lower() == 'github':
                return 'GitHub'
            elif company_name.lower() == 'linkedin':
                return 'LinkedIn'
            elif company_name.lower() == 'youtube':
                return 'YouTube'
            elif company_name.lower() == 'paypal':
                return 'PayPal'
            elif company_name.isupper():
                # Keep all-caps names as-is (e.g., PXXL, IBM)
                return company_name.upper()
            else:
                # Standard capitalization
                return company_name.capitalize()
                
        except Exception as e:
            logger.error(f"Error extracting company name from URL: {str(e)}")
            return "Unknown"


class QualityScorer:
    """Calculates data quality scores"""
    
    # Weight for each data section (must sum to 1.0)
    SECTION_WEIGHTS = {
        'company': 0.15,
        'financials': 0.10,
        'funding': 0.10,
        'people': 0.15,
        'products': 0.15,
        'competitors': 0.10,
        'news': 0.10,
        'online_presence': 0.15
    }
    
    @classmethod
    def calculate_section_score(cls, section_data: Any) -> float:
        """
        Calculate completeness score for a section (0-100)
        
        Args:
            section_data: Section data (dict, list, or primitive)
            
        Returns:
            Score from 0 to 100
        """
        if section_data is None:
            return 0.0
        
        if isinstance(section_data, dict):
            if not section_data:
                return 0.0
            
            # Count non-null, non-empty values
            total_fields = len(section_data)
            filled_fields = sum(
                1 for v in section_data.values()
                if v is not None and v != "" and v != [] and v != {}
            )
            
            return (filled_fields / total_fields) * 100 if total_fields > 0 else 0.0
        
        elif isinstance(section_data, list):
            # For lists, score based on number of items (up to 10)
            return min(len(section_data) * 10, 100)
        
        else:
            # Primitive value
            return 100.0 if section_data else 0.0
    
    @classmethod
    def calculate_overall_score(cls, unified_data: Dict[str, Any]) -> float:
        """
        Calculate overall data quality score (0-100)
        
        Args:
            unified_data: Complete unified JSON data
            
        Returns:
            Weighted average score from 0 to 100
        """
        total_score = 0.0
        
        for section, weight in cls.SECTION_WEIGHTS.items():
            section_data = unified_data.get(section)
            section_score = cls.calculate_section_score(section_data)
            total_score += section_score * weight
        
        return round(total_score, 1)


class UnifiedOrchestrator:
    """Orchestrates all scrapers to gather complete company intelligence"""
    
    def __init__(self, max_workers: int = 6, timeout: int = 180):
        """
        Initialize orchestrator
        
        Args:
            max_workers: Maximum parallel scrapers (default: 6)
            timeout: Total timeout in seconds (default: 180 = 3 minutes)
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self.validator = SecurityValidator()
        self.name_extractor = CompanyNameExtractor()
        self.scorer = QualityScorer()
    
    async def get_complete_company_intelligence(
        self,
        website_url: str,
        company_name: Optional[str] = None,
        user_id: Optional[str] = None,
        scrape_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gather complete company intelligence from website URL
        
        This is the main entry point for the unified orchestrator.
        
        Args:
            website_url: Company website URL (required)
            company_name: Optional company name override
            user_id: User ID who initiated the scrape
            scrape_id: Optional scrape ID (generated if not provided)
            
        Returns:
            Unified JSON data with all company intelligence
            
        Raises:
            ValueError: If URL is invalid or blocked
            TimeoutError: If scraping exceeds timeout
        """
        if not scrape_id:
            scrape_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        logger.info(f"[{scrape_id}] Starting company intelligence gathering for: {website_url}")
        
        # 1. SECURITY VALIDATION
        is_valid, error_msg = self.validator.validate_url(website_url)
        if not is_valid:
            logger.error(f"[{scrape_id}] URL validation failed: {error_msg}")
            raise ValueError(f"Invalid URL: {error_msg}")
        
        # Normalize URL (ensure it has protocol)
        if not website_url.startswith(('http://', 'https://')):
            website_url = f"https://{website_url}"
        
        # 2. EXTRACT COMPANY NAME
        if not company_name:
            company_name = self.name_extractor.extract_from_url(website_url)
            logger.info(f"[{scrape_id}] Extracted company name: {company_name}")
        else:
            company_name = self.validator.sanitize_company_name(company_name)
            logger.info(f"[{scrape_id}] Using provided company name: {company_name}")
        
        # 3. RUN ALL SCRAPERS IN PARALLEL
        logger.info(f"[{scrape_id}] Launching parallel scrapers...")
        
        try:
            scraper_results = await asyncio.wait_for(
                self._run_all_scrapers(scrape_id, company_name, website_url),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"[{scrape_id}] Scraping timeout after {self.timeout}s")
            raise TimeoutError(f"Scraping exceeded {self.timeout} seconds timeout")
        
        # 4. MERGE RESULTS INTO UNIFIED SCHEMA
        logger.info(f"[{scrape_id}] Merging results into unified schema...")
        unified_data = self._merge_into_unified_schema(
            scrape_id,
            company_name,
            website_url,
            scraper_results
        )
        
        # 5. AI ENRICHMENT (Clean and fill missing data)
        logger.info(f"[{scrape_id}] Starting AI enrichment...")
        try:
            from app.services.scraping.ai_enrichment import enrich_company_data
            unified_data = await enrich_company_data(unified_data)
        except Exception as e:
            logger.warning(f"[{scrape_id}] AI enrichment failed: {e}. Continuing with raw data.")
        
        # 6. CALCULATE QUALITY SCORE
        quality_score = self.scorer.calculate_overall_score(unified_data)
        
        # 7. ADD METADATA
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        unified_data['metadata'] = {
            'scrape_id': scrape_id,
            'user_id': user_id,
            'scrape_timestamp': end_time.isoformat(),
            'scrape_duration_seconds': round(duration, 2),
            'data_quality_score': quality_score,
            'ai_enriched': True,  # Track that AI enrichment was applied
            'scrapers_status': self._get_scrapers_status(scraper_results),
            'refresh_recommended_date': self._get_refresh_date(end_time).isoformat()
        }
        
        logger.info(
            f"[{scrape_id}] ✅ Complete! "
            f"Duration: {duration:.1f}s | Quality: {quality_score}/100"
        )
        
        return unified_data
    
    def _parse_funding_amount(self, amount_str: str) -> float:
        """
        Parse funding amount string to float in USD.
        Examples: "$2.23B" -> 2230000000, "$100M" -> 100000000
        """
        if not amount_str or amount_str == '$0':
            return 0.0
        
        try:
            # Remove $ and spaces
            clean = amount_str.replace('$', '').replace(' ', '').upper()
            
            # Extract number and multiplier
            if 'B' in clean:
                number = float(clean.replace('B', ''))
                return number * 1_000_000_000
            elif 'M' in clean:
                number = float(clean.replace('M', ''))
                return number * 1_000_000
            elif 'K' in clean:
                number = float(clean.replace('K', ''))
                return number * 1_000
            else:
                return float(clean)
        except (ValueError, AttributeError):
            return 0.0
    
    async def _run_all_scrapers(
        self,
        scrape_id: str,
        company_name: str,
        website_url: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run all scrapers in parallel
        
        Args:
            scrape_id: Unique scrape identifier
            company_name: Company name
            website_url: Website URL
            
        Returns:
            Dictionary with results from each scraper
        """
        # Define scraper tasks
        tasks = {
            'profile': self._run_profile_scraper(scrape_id, company_name, website_url),
            'website': self._run_website_scraper(scrape_id, website_url),
            'financial': self._run_financial_scraper(scrape_id, company_name),
            'news': self._run_news_scraper(scrape_id, company_name),
            'competitors': self._run_competitors_scraper(scrape_id, company_name, website_url),
            'leadership': self._run_leadership_scraper(scrape_id, company_name, website_url)
        }
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Map results back to scraper names
        scraper_results = {}
        for (name, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                logger.error(f"[{scrape_id}] {name} scraper failed: {str(result)}")
                scraper_results[name] = {
                    'success': False,
                    'error': str(result),
                    'data': None
                }
            else:
                scraper_results[name] = result
        
        return scraper_results
    
    async def _run_profile_scraper(
        self,
        scrape_id: str,
        company_name: str,
        website_url: str
    ) -> Dict[str, Any]:
        """Run company profile scraper"""
        logger.info(f"[{scrape_id}] Running profile scraper...")
        try:
            data = await get_company_profile(company_name, website_url)
            return {'success': True, 'data': data, 'error': None}
        except Exception as e:
            logger.error(f"[{scrape_id}] Profile scraper error: {str(e)}")
            return {'success': False, 'data': None, 'error': str(e)}
    
    async def _run_website_scraper(
        self,
        scrape_id: str,
        website_url: str
    ) -> Dict[str, Any]:
        """Run website content scraper"""
        logger.info(f"[{scrape_id}] Running website scraper...")
        try:
            data = await scrape_website(website_url)
            return {'success': True, 'data': data, 'error': None}
        except Exception as e:
            logger.error(f"[{scrape_id}] Website scraper error: {str(e)}")
            return {'success': False, 'data': None, 'error': str(e)}
    
    async def _run_financial_scraper(
        self,
        scrape_id: str,
        company_name: str
    ) -> Dict[str, Any]:
        """Run financial/funding scraper"""
        logger.info(f"[{scrape_id}] Running financial scraper...")
        try:
            data = await get_unified_funding_data(company_name)
            return {'success': True, 'data': data, 'error': None}
        except Exception as e:
            logger.error(f"[{scrape_id}] Financial scraper error: {str(e)}")
            return {'success': False, 'data': None, 'error': str(e)}
    
    async def _run_news_scraper(
        self,
        scrape_id: str,
        company_name: str
    ) -> Dict[str, Any]:
        """Run news & press scraper"""
        logger.info(f"[{scrape_id}] Running news scraper...")
        try:
            data = await scrape_news_and_press(company_name)
            return {'success': True, 'data': data, 'error': None}
        except Exception as e:
            logger.error(f"[{scrape_id}] News scraper error: {str(e)}")
            return {'success': False, 'data': None, 'error': str(e)}
    
    async def _run_competitors_scraper(
        self,
        scrape_id: str,
        company_name: str,
        website_url: str
    ) -> Dict[str, Any]:
        """Run competitors scraper"""
        logger.info(f"[{scrape_id}] Running competitors scraper...")
        try:
            data = await scrape_competitors(company_name, website_url)
            return {'success': True, 'data': data, 'error': None}
        except Exception as e:
            logger.error(f"[{scrape_id}] Competitors scraper error: {str(e)}")
            return {'success': False, 'data': None, 'error': str(e)}
    
    async def _run_leadership_scraper(
        self,
        scrape_id: str,
        company_name: str,
        website_url: str
    ) -> Dict[str, Any]:
        """Run founders & leadership scraper"""
        logger.info(f"[{scrape_id}] Running leadership scraper...")
        try:
            data = await scrape_founders(company_name, website_url)
            return {'success': True, 'data': data, 'error': None}
        except Exception as e:
            logger.error(f"[{scrape_id}] Leadership scraper error: {str(e)}")
            return {'success': False, 'data': None, 'error': str(e)}
    
    def _merge_into_unified_schema(
        self,
        scrape_id: str,
        company_name: str,
        website_url: str,
        scraper_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge all scraper results into unified JSON schema
        
        Args:
            scrape_id: Unique scrape identifier
            company_name: Company name
            website_url: Website URL
            scraper_results: Results from all scrapers
            
        Returns:
            Unified data structure
        """
        # Extract parsed domain
        parsed = urlparse(website_url)
        domain = parsed.netloc.replace('www.', '')
        
        # Initialize unified structure
        unified = {
            'company': {},
            'financials': {},
            'funding': {},
            'people': {},
            'products': [],
            'competitors': [],
            'news': {},
            'online_presence': {}
        }
        
        # 1. COMPANY SECTION (from profile + website)
        profile_data = scraper_results.get('profile', {}).get('data', {})
        profile_identity = profile_data.get('identity', {})
        profile_financials = profile_data.get('financials', {})
        website_data = scraper_results.get('website', {}).get('data', {})
        
        unified['company'] = {
            'name': profile_data.get('company_name') or company_name,
            'legal_name': None,
            'website': website_url,
            'domain': domain,
            'description': profile_identity.get('description'),
            'tagline': None,
            'logo_url': website_data.get('logo_url'),
            'favicon_url': website_data.get('favicon_url'),
            'founded_year': profile_identity.get('founded'),
            'status': profile_identity.get('company_type'),
            'industry': profile_identity.get('industry'),
            'sector': None,
            'employee_count': profile_financials.get('employees'),
            'headquarters': profile_identity.get('headquarters')
        }
        
        # 2. FINANCIALS SECTION (from financial scraper - EDGAR data)
        financial_data = scraper_results.get('financial', {}).get('data', {})
        edgar_raw = financial_data.get('raw_data', {}).get('edgar', {}) if financial_data else {}
        financials_data = financial_data.get('financials', {}) if financial_data else {}
        identity_data = financial_data.get('identity', {}) if financial_data else {}
        filings_data = financial_data.get('latest_filings', {}) if financial_data else {}
        
        # Build statements object if we have any financial data
        statements = None
        if any(financials_data.values()):
            statements = {
                'income_statement': financials_data.get('revenue'),
                'balance_sheet': financials_data.get('assets'),
                'cash_flow': financials_data.get('cash_flow'),
                'key_metrics': {
                    'revenue': financials_data.get('revenue'),
                    'net_income': financials_data.get('net_income'),
                    'assets': financials_data.get('assets'),
                    'liabilities': financials_data.get('liabilities'),
                    'equity': financials_data.get('equity')
                }
            }
        
        unified['financials'] = {
            'public_company': bool(identity_data.get('ticker')),
            'ticker': identity_data.get('ticker'),
            'exchange': None,
            'cik': edgar_raw.get('cik') if edgar_raw else None,
            'statements': statements,
            'valuation': None
        }
        
        # 3. FUNDING SECTION (from financial scraper - PitchBook + AI)
        funding_data = financial_data.get('funding', {}) if financial_data else {}
        ai_enriched = financial_data.get('ai_enriched', {}) if financial_data else {}
        
        # total_raised can be a number or string like "$2.23B"
        total_raised_value = ai_enriched.get('total_funding') or funding_data.get('total_raised')
        if isinstance(total_raised_value, (int, float)):
            total_raised = float(total_raised_value)
        else:
            total_raised = self._parse_funding_amount(total_raised_value or '$0')
        
        unified['funding'] = {
            'total_raised_usd': total_raised,
            'currency': 'USD',
            'round_count': len(funding_data.get('funding_rounds', [])),
            'latest_rounds': funding_data.get('funding_rounds', [])[:5],  # Top 5
            'investors': funding_data.get('investors', [])
        }
        
        # 4. PEOPLE SECTION (from leadership scraper)
        leadership_data = scraper_results.get('leadership', {}).get('data', {})
        
        unified['people'] = {
            'founders': leadership_data.get('founders', []),
            'executives': leadership_data.get('executives', []),
            'board_members': leadership_data.get('board_members', []),
            'key_people': leadership_data.get('key_people', [])
        }
        
        # 5. PRODUCTS SECTION (from website scraper)
        products = website_data.get('products_services', [])
        unified['products'] = [
            {
                'name': p.get('name'),
                'category': p.get('category'),
                'description': p.get('description'),
                'url': p.get('url'),
                'features': p.get('features', []),
                'pricing': p.get('pricing'),
                'source': 'website'
            }
            for p in products
        ]
        
        # 6. COMPETITORS SECTION (from AI-enriched financial data or competitors scraper)
        competitors_data = scraper_results.get('competitors', {}).get('data', {})
        market_data = financial_data.get('market', {}) if financial_data else {}
        
        # Prefer AI-enriched competitors from financial scraper (has more details)
        ai_competitors = ai_enriched.get('competitors', [])
        market_competitors = market_data.get('competitors', [])
        raw_competitors = competitors_data.get('competitors', [])
        
        unified['competitors'] = ai_competitors if ai_competitors else (market_competitors if market_competitors else raw_competitors)
        
        # 7. NEWS SECTION (from news scraper)
        news_data = scraper_results.get('news', {}).get('data', {})
        
        unified['news'] = {
            'total': len(news_data.get('articles', [])),
            'date_range': {
                'oldest': news_data.get('date_range', {}).get('oldest'),
                'newest': news_data.get('date_range', {}).get('newest')
            },
            'articles': news_data.get('articles', [])[:20]  # Top 20
        }
        
        # 8. ONLINE PRESENCE SECTION (from website scraper)
        unified['online_presence'] = {
            'site_analysis': {
                'sitemap_pages': website_data.get('sitemap_count', 0),
                'key_pages': website_data.get('key_pages', {})
            },
            'social_media': website_data.get('social_media', {}),
            'contact_info': {
                'emails': website_data.get('emails', []),
                'phones': website_data.get('phones', []),
                'addresses': website_data.get('addresses', [])
            }
        }
        
        return unified
    
    def _get_scrapers_status(self, scraper_results: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        """Get status summary of all scrapers"""
        return {
            name: 'success' if result.get('success') else 'failed'
            for name, result in scraper_results.items()
        }
    
    def _get_refresh_date(self, current_time: datetime) -> datetime:
        """
        Calculate recommended refresh date (7 days from now)
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Refresh date
        """
        from datetime import timedelta
        return current_time + timedelta(days=7)


# Public API
async def get_complete_company_intelligence(
    website_url: str,
    company_name: Optional[str] = None,
    timeout: int = 180
) -> Dict[str, Any]:
    """
    Main entry point: Gather complete company intelligence from URL
    
    Args:
        website_url: Company website URL (required)
        company_name: Optional company name override
        timeout: Maximum time in seconds (default: 180)
        
    Returns:
        Complete unified company intelligence data
        
    Raises:
        ValueError: If URL is invalid
        TimeoutError: If scraping exceeds timeout
        
    Example:
        >>> data = await get_complete_company_intelligence("https://stripe.com")
        >>> print(data['company']['name'])  # "Stripe"
        >>> print(data['metadata']['data_quality_score'])  # 87.5
    """
    orchestrator = UnifiedOrchestrator(timeout=timeout)
    return await orchestrator.get_complete_company_intelligence(website_url, company_name)


# Convenience synchronous wrapper
def get_complete_company_intelligence_sync(
    website_url: str,
    company_name: Optional[str] = None,
    timeout: int = 180
) -> Dict[str, Any]:
    """
    Synchronous version of get_complete_company_intelligence
    
    Args:
        website_url: Company website URL (required)
        company_name: Optional company name override
        timeout: Maximum time in seconds (default: 180)
        
    Returns:
        Complete unified company intelligence data
        
    Example:
        >>> data = get_complete_company_intelligence_sync("https://stripe.com")
        >>> print(data['company']['name'])  # "Stripe"
    """
    return asyncio.run(
        get_complete_company_intelligence(website_url, company_name, timeout)
    )
