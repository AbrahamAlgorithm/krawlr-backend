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

IMPORTANT - AI Enrichment Architecture:
- AI enrichment is handled WITHIN individual scrapers (e.g., funding_scraper.py)
- The orchestrator does NOT apply AI enrichment at the merge level
- This prevents AI hallucinations from overwriting accurate scraped data
- Merge logic ALWAYS prioritizes scraped data over AI-generated data
- AI only fills gaps where scraping returned null/empty values

Data Priority Rules:
1. Hard-scraped data (from APIs, web scraping) = HIGHEST PRIORITY
2. AI enrichment within scrapers (fills gaps only) = MEDIUM PRIORITY  
3. AI enrichment at orchestrator level = REMOVED (caused hallucinations)
"""

import asyncio
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from datetime import datetime, timezone
import logging
from concurrent.futures import ThreadPoolExecutor
import uuid
import os
import json
from openai import AsyncOpenAI

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

# Configure OpenAI for data enrichment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
openai_client = None
if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY not found - AI enrichment will be disabled")


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
        
        # 5. CALCULATE QUALITY SCORE
        # Note: AI enrichment is now handled within individual scrapers (e.g., funding_scraper)
        # to prevent hallucinations and ensure scraped data always takes priority
        quality_score = self.scorer.calculate_overall_score(unified_data)
        
        # 6. AI ENRICHMENT FOR INCOMPLETE DATA
        # Fill missing fields with AI-researched data
        logger.info(f"[{scrape_id}] Enriching incomplete data with AI...")
        unified_data = await self._enrich_incomplete_data(unified_data, company_name)
        
        # 7. REMOVE METADATA FROM FINAL OUTPUT (user requested)
        # We'll add it temporarily for logging but remove before returning
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
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
        
        # 1. COMPANY SECTION (from financial + website)
        financial_data = scraper_results.get('financial', {}).get('data') or {}
        identity_data = financial_data.get('identity', {}) if financial_data else {}
        website_data = scraper_results.get('website', {}).get('data') or {}
        
        # Prioritize user input name over EDGAR legal name
        # EDGAR returns legal entity name (e.g., "Alphabet Inc."), but user input is the brand name (e.g., "Google")
        display_name = company_name  # Use the name extracted from URL/user input as primary
        legal_name = identity_data.get('name') if identity_data.get('name') != company_name else None
        
        unified['company'] = {
            'name': display_name,
            'legal_name': legal_name,
            'website': identity_data.get('website') or website_url,
            'domain': domain,
            'description': identity_data.get('description'),
            'tagline': None,
            'logo_url': website_data.get('logo_url') if website_data else None,
            'favicon_url': website_data.get('favicon_url') if website_data else None,
            'founded_year': identity_data.get('founded_year'),
            'status': identity_data.get('status'),
            'industry': identity_data.get('industry'),
            'sector': None,
            'employee_count': identity_data.get('employees'),
            'headquarters': identity_data.get('headquarters')
        }
        
        # 2. FINANCIALS SECTION (from financial scraper - EDGAR data)
        financial_data = scraper_results.get('financial', {}).get('data') or {}
        financials_data = financial_data.get('financials', {}) if financial_data else {}
        identity_data = financial_data.get('identity', {}) if financial_data else {}
        key_metrics = financial_data.get('key_metrics', {}) if financial_data else {}
        
        # Get latest filings (array of filing objects)
        latest_filings = financial_data.get('latest_filings', []) if financial_data else []
        
        # Get insiders (array of insider objects)
        insiders = financial_data.get('insiders', []) if financial_data else []
        
        # Build statements object with detailed financial data
        statements = None
        income_statement = financials_data.get('income_statement', [])
        balance_sheet = financials_data.get('balance_sheet', [])
        cash_flow_statement = financials_data.get('cash_flow_statement', [])
        
        if income_statement or balance_sheet or cash_flow_statement:
            statements = {
                'income_statement': income_statement,
                'balance_sheet': balance_sheet,
                'cash_flow_statement': cash_flow_statement,
                'fiscal_year': financials_data.get('fiscal_year')
            }
        elif any([financials_data.get('revenue'), financials_data.get('net_income')]):
            # Fallback to summary data if no detailed statements
            statements = {
                'summary': {
                    'revenue': financials_data.get('revenue'),
                    'net_income': financials_data.get('net_income'),
                    'assets': financials_data.get('assets'),
                    'liabilities': financials_data.get('liabilities'),
                    'equity': financials_data.get('equity'),
                    'cash_flow': financials_data.get('cash_flow'),
                    'fiscal_year': financials_data.get('fiscal_year')
                }
            }
        
        unified['financials'] = {
            'public_company': bool(identity_data.get('ticker')),
            'ticker': identity_data.get('ticker'),
            'exchange': None,
            'cik': None,
            'sic': None,
            'shares_outstanding': key_metrics.get('shares_outstanding'),
            'public_float': key_metrics.get('public_float'),
            'statements': statements,
            'latest_filings': latest_filings[:5],
            'insiders': insiders,
            'valuation': None
        }
        
        # 3. FUNDING SECTION (from financial scraper - PitchBook + AI)
        # CRITICAL: Always prefer scraped data over AI to prevent hallucinations
        funding_data = financial_data.get('funding', {}) if financial_data else {}
        
        # total_raised can be a number or string like "$2.23B"
        # Scraped data takes priority - AI only fills gaps, never overwrites
        total_raised_value = funding_data.get('total_raised')
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
        
        # 4. PEOPLE SECTION (merge from leadership scraper + financial insiders)
        leadership_data = scraper_results.get('leadership', {}).get('data') or {}
        
        # Get insiders from financial data (SEC filings)
        financial_insiders = financial_data.get('insiders', []) if financial_data else []
        
        # Separate insiders by role
        executives_from_insiders = []
        board_members_from_insiders = []
        
        for insider in financial_insiders:
            position = insider.get('position', '').lower()
            name = insider.get('insider')
            
            if not name:
                continue
            
            person_data = {
                'name': name,
                'position': insider.get('position'),
                'source': 'SEC Filings'
            }
            
            # Categorize: Directors/Board members vs Executives
            if any(keyword in position for keyword in ['director', 'board']):
                board_members_from_insiders.append(person_data)
            else:  # CEO, CFO, VP, President, etc.
                executives_from_insiders.append(person_data)
        
        # Merge with leadership scraper data (leadership scraper takes priority if available)
        leadership_executives = leadership_data.get('executives', [])
        leadership_board = leadership_data.get('board_members', [])
        
        # Use leadership data if available, otherwise use insiders from financial data
        unified['people'] = {
            'founders': leadership_data.get('founders', []),
            'executives': leadership_executives if leadership_executives else executives_from_insiders,
            'board_members': leadership_board if leadership_board else board_members_from_insiders,
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
        
        # 6. COMPETITORS SECTION (merge from financial scraper + competitors scraper)
        # Financial scraper provides AI-enriched competitors from EDGAR/PitchBook analysis
        # Competitors scraper provides web-scraped competitors
        competitors_data = scraper_results.get('competitors', {}).get('data') or {}
        
        financial_competitors = financial_data.get('competitors', []) if financial_data else []
        scraper_competitors = competitors_data.get('competitors', [])
        
        # Merge both sources, prioritizing financial scraper (more detailed)
        # Remove duplicates by company name (case-insensitive)
        merged_competitors = []
        seen_names = set()
        
        # Add financial competitors first (higher quality, AI-enriched)
        for comp in financial_competitors:
            name_lower = comp.get('name', '').lower()
            if name_lower and name_lower not in seen_names:
                merged_competitors.append(comp)
                seen_names.add(name_lower)
        
        # Add scraper competitors if not already present
        for comp in scraper_competitors:
            name_lower = comp.get('name', '').lower()
            if name_lower and name_lower not in seen_names:
                merged_competitors.append(comp)
                seen_names.add(name_lower)
        
        unified['competitors'] = merged_competitors
        
        # 7. NEWS SECTION (from news scraper)
        news_data = scraper_results.get('news', {}).get('data') or {}
        
        unified['news'] = {
            'total': len(news_data.get('articles', [])) if news_data else 0,
            'date_range': {
                'oldest': (news_data.get('date_range') or {}).get('oldest') if news_data else None,
                'newest': (news_data.get('date_range') or {}).get('newest') if news_data else None
            },
            'articles': news_data.get('articles', [])[:20] if news_data else []  # Top 20
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
    
    async def _enrich_incomplete_data(self, unified_data: Dict[str, Any], company_name: str) -> Dict[str, Any]:
        """
        Use AI to enrich incomplete data fields with valid, researched information.
        
        Enriches:
        - Null fields in identity (website, description, industry, founded_year, employees)
        - Null fields in financials (assets, liabilities, equity)
        - Incomplete funding rounds (missing amounts, dates, valuations)
        - Empty products list
        - Missing people (founders, executives from financial data)
        - Empty social media links
        - Missing contact information
        - Empty competitors list
        """
        if not openai_client:
            logger.warning("OpenAI not configured, skipping data enrichment")
            return unified_data
        
        try:
            # Get the actual company name from unified_data (this is the user's input name like "Google")
            # NOT the legal name from EDGAR (like "Alphabet Inc.")
            actual_company_name = unified_data.get('company', {}).get('name', company_name)
            
            # Identify what needs enrichment
            needs_enrichment = False
            identity = unified_data.get('company', {})
            financials = unified_data.get('financials', {})
            
            # Check for null/empty fields
            null_identity_fields = [k for k, v in identity.items() if v is None and k not in ['ticker', 'headquarters', 'legal_name']]
            null_financial_fields = [k for k, v in financials.items() if v is None and k in ['assets', 'liabilities', 'equity']]
            products_list = unified_data.get('products', [])
            empty_products = not products_list or len(products_list) == 0
            competitors_list = unified_data.get('competitors', [])
            empty_competitors = not competitors_list or len(competitors_list) == 0
            empty_social = not unified_data.get('online_presence', {}).get('social_media')
            
            if null_identity_fields or null_financial_fields or empty_products or empty_competitors or empty_social:
                needs_enrichment = True
            
            if not needs_enrichment:
                logger.info("[AI] No null/empty fields to enrich, skipping AI call")
                return unified_data
            
            # Build enrichment prompt using the actual company name (user's input like "Google")
            # NOT the legal entity name from EDGAR (like "Alphabet Inc.")
            prompt = f"""You are a product research analyst and company intelligence expert. Fill ONLY the NULL/EMPTY fields with REAL, FACTUAL data.

Company: {actual_company_name}
Ticker: {identity.get('ticker', 'N/A')}
Website: {identity.get('website') or 'N/A'}

FIELDS TO FILL (ONLY if currently null/empty):

1. IDENTITY (company section):
   - website: {identity.get('website')}
   - description: {identity.get('description')} 
     **IMPORTANT**: If description is null, write a detailed, expert-level description as a product manager would.
     The description MUST be about "{actual_company_name}" (the brand/product name), NOT the legal entity name.
     Format: "{actual_company_name} is a [company type] that [what they do]. The company [key offerings/services]. 
     Known for [unique value proposition], {actual_company_name} serves [target market] through [how they deliver value].
     Their platform/products include [main products]. [Additional strategic context]."
     Example: "Google is a multinational technology company that specializes in internet-related services and products. 
     The company offers search engine technology, online advertising, cloud computing, software, and hardware. 
     Known for its dominant search engine and advertising platforms, Google serves billions of users worldwide through 
     innovative products like Google Search, YouTube, Android, Chrome, and Google Cloud. The company generates revenue 
     primarily through advertising on its search and video platforms while expanding into enterprise cloud services and 
     consumer hardware."
   - industry: {identity.get('industry')}
   - founded_year: {identity.get('founded_year')}
   - employees: {identity.get('employees')}

2. FINANCIALS (only if null):
   - assets: {financials.get('assets')}
   - liabilities: {financials.get('liabilities')}
   - equity: {financials.get('equity')}

3. PRODUCTS: {len(products_list)} products found
   **REQUIRED**: If products list is empty, research and list the company's main products/services (3-7 products minimum).
   Include product name, category, and detailed description for each.

4. COMPETITORS: {len(competitors_list)} competitors found
   **REQUIRED**: If competitors list is empty, research and list top 5-7 direct competitors.

5. SOCIAL MEDIA: {len(unified_data.get('online_presence', {}).get('social_media', {}))} links found

CRITICAL RULES:
- Use ONLY real, factual data from reliable sources
- For description: Write a comprehensive, professional description (150-250 words) that explains the company's business model, products, market position, and revenue streams like an expert product manager would
- For financials: Use latest available data (millions/billions format)
- **For products: ALWAYS generate 3-7 main products/services if the list is empty. Research the company's actual product offerings.**
- **For competitors: ALWAYS generate 5-7 direct competitors if the list is empty.**
- For social media: Official company accounts only (LinkedIn, Twitter, Facebook, Instagram, YouTube)
- If you cannot find valid data for identity/financial fields, return null for that field

OUTPUT FORMAT (JSON only, include ONLY non-null values):
{{
  "identity_enrichment": {{
    "website": "https://...",
    "description": "Detailed product manager-style company description...",
    "industry": "Industry name",
    "founded_year": 2023,
    "employees": "50,000"
  }},
  "financial_enrichment": {{
    "assets": 500000000000.0,
    "liabilities": 100000000000.0,
    "equity": 400000000000.0
  }},
  "products": [
    {{
      "name": "Product Name",
      "category": "Category",
      "description": "Detailed description of what it does and who it serves"
    }}
  ],
  "competitors": [
    {{
      "name": "Competitor Name",
      "website": "https://...",
      "description": "Brief description"
    }}
  ],
  "social_media": {{
    "linkedin": "https://linkedin.com/company/...",
    "twitter": "https://twitter.com/...",
    "facebook": "https://facebook.com/...",
    "instagram": "https://instagram.com/..."
  }}
}}

RESPOND WITH ONLY VALID JSON. No markdown, no explanation."""

            logger.info("[AI] Enriching null/empty fields...")
            response = await openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a company research assistant. Return ONLY valid JSON with factual company data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=8192,
                response_format={"type": "json_object"}
            )
            
            # Parse AI response
            ai_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if ai_text.startswith("```json"):
                ai_text = ai_text[7:]
            if ai_text.startswith("```"):
                ai_text = ai_text[3:]
            if ai_text.endswith("```"):
                ai_text = ai_text[:-3]
            ai_text = ai_text.strip()
            
            enriched = json.loads(ai_text)
            
            # Apply enrichments
            # 1. Fill null identity fields
            if enriched.get('identity_enrichment'):
                identity_data = enriched['identity_enrichment']
                for key, value in identity_data.items():
                    if unified_data['company'].get(key) is None and value is not None:
                        unified_data['company'][key] = value
                        logger.info(f"[AI] ✓ Filled identity.{key}: {value}")
            
            # 2. Fill null financial fields
            if enriched.get('financial_enrichment'):
                financial_data = enriched['financial_enrichment']
                for key, value in financial_data.items():
                    if unified_data['financials'].get(key) is None and value is not None:
                        unified_data['financials'][key] = value
                        logger.info(f"[AI] ✓ Filled financials.{key}: {value}")
            
            # 3. Add products if empty
            if enriched.get('products'):
                # Only add if products list is actually empty
                if not unified_data.get('products') or len(unified_data.get('products', [])) == 0:
                    unified_data['products'] = enriched['products']
                    logger.info(f"[AI] ✓ Added {len(enriched['products'])} products")
            
            # 4. Add competitors if empty
            if enriched.get('competitors'):
                # Only add if competitors list is actually empty
                if not unified_data.get('competitors') or len(unified_data.get('competitors', [])) == 0:
                    unified_data['competitors'] = enriched['competitors']
                    logger.info(f"[AI] ✓ Added {len(enriched['competitors'])} competitors")
            
            # 5. Add social media if empty
            if enriched.get('social_media') and not unified_data.get('online_presence', {}).get('social_media'):
                unified_data['online_presence']['social_media'] = enriched['social_media']
                logger.info("[AI] ✓ Added social media links")
            
            logger.info("[AI] ✅ Data enrichment completed")
            
        except json.JSONDecodeError as e:
            logger.warning(f"[AI] Failed to parse enrichment response: {e}")
            logger.warning(f"[AI] Response was: {ai_text[:500]}...")
        except Exception as e:
            logger.error(f"[AI] Enrichment error: {e}")
        
        return unified_data


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
