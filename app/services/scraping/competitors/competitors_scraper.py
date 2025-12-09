"""
Competitors & Alternatives Scraper Service

Comprehensive competitor discovery from multiple sources:
- Google related: search (similar companies)
- Google search (competitor keywords)
- Owler.com scraping (competitor listings)
- PitchBook competitors (if available)
- Company website mentions

Production-ready with error handling, timeouts, and parallel scraping.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse, quote_plus

from bs4 import BeautifulSoup

from app.services.utils.http_client import http_client
from app.services.utils.validators import normalize_url, extract_domain

logger = logging.getLogger(__name__)


class CompetitorsScraper:
    """
    Enhanced competitors and alternatives scraper.
    
    Features:
    - Google related: search (similar sites)
    - Google keyword search (competitor mentions)
    - Owler.com scraping (free competitor data)
    - Company website competitor mentions
    - Smart deduplication by domain
    - Similarity scoring
    """
    
    # Keywords that indicate competitor relationships
    COMPETITOR_KEYWORDS = [
        'competitor', 'alternative', 'vs', 'versus', 'compared to',
        'similar to', 'like', 'competes with', 'rival'
    ]
    
    # Owler search patterns
    OWLER_SEARCH_URL = "https://www.owler.com/iaApp/searchResults.htm?q={query}&type=company"
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    async def scrape_competitors(
        self,
        company_name: str,
        website_url: Optional[str] = None,
        max_competitors: int = 20
    ) -> Dict:
        """
        Comprehensive competitor discovery.
        
        Args:
            company_name: Company name to search for
            website_url: Optional company website URL
            max_competitors: Maximum competitors to retrieve
        
        Returns:
            Dictionary with competitors from all sources
        """
        print(f"\n{'='*60}")
        print(f"🏢 COMPETITORS SCRAPER - {company_name}")
        print(f"{'='*60}\n")
        
        try:
            # Run all scraping tasks in parallel with timeout
            results = await asyncio.wait_for(
                self._run_scraping_tasks(company_name, website_url, max_competitors),
                timeout=120.0  # 2 minute overall timeout
            )
            
            # Combine and deduplicate
            all_competitors = self._combine_and_deduplicate(results, website_url)
            
            # Score similarity
            all_competitors = self._score_competitors(all_competitors, company_name)
            
            # Sort by similarity and source count
            all_competitors = self._sort_competitors(all_competitors)
            
            # Build final result
            result = {
                'company_name': company_name,
                'company_website': website_url,
                'scraped_at': datetime.now().isoformat(),
                'total_competitors': len(all_competitors),
                'competitors': all_competitors[:max_competitors],
                'sources': {
                    'google_related': results.get('google_related', {}).get('count', 0),
                    'google_search': results.get('google_search', {}).get('count', 0),
                    'owler': results.get('owler', {}).get('count', 0),
                    'website_mentions': results.get('website_mentions', {}).get('count', 0),
                },
            }
            
            self._print_summary(result)
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Competitor scraping timed out after 120s for {company_name}")
            return self._error_result(company_name, website_url, "Scraping timed out")
        except Exception as e:
            logger.error(f"Error scraping competitors for {company_name}: {str(e)}")
            return self._error_result(company_name, website_url, str(e))
    
    async def _run_scraping_tasks(
        self,
        company_name: str,
        website_url: Optional[str],
        max_competitors: int
    ) -> Dict:
        """Run all scraping tasks in parallel."""
        tasks = []
        task_names = []
        
        # Google related: search (if website provided)
        if website_url:
            domain = extract_domain(website_url)
            tasks.append(self._google_related_search(domain, max_competitors))
            task_names.append('google_related')
        
        # Google keyword search
        tasks.append(self._google_keyword_search(company_name, max_competitors))
        task_names.append('google_search')
        
        # Owler.com search
        tasks.append(self._owler_search(company_name, max_competitors))
        task_names.append('owler')
        
        # Website competitor mentions (if website provided)
        if website_url:
            tasks.append(self._website_competitor_mentions(website_url, company_name))
            task_names.append('website_mentions')
        
        # Run all tasks with individual timeouts
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build results dict
        result_dict = {}
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.error(f"Task {name} failed: {str(result)}")
                result_dict[name] = {'competitors': [], 'count': 0}
            else:
                result_dict[name] = result
        
        return result_dict
    
    async def _google_related_search(self, domain: str, limit: int) -> Dict:
        """
        Use Google's related: operator to find similar sites.
        
        Args:
            domain: Domain to search (e.g., stripe.com)
            limit: Maximum results
        
        Returns:
            Dictionary with competitors and count
        """
        print(f"🔍 Searching Google related: for {domain}...")
        
        try:
            competitors = await asyncio.wait_for(
                self._execute_related_search(domain, limit),
                timeout=30.0
            )
            
            print(f"✅ Found {len(competitors)} related sites")
            return {'competitors': competitors, 'count': len(competitors)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Google related: search timed out for {domain}")
            return {'competitors': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with Google related: search: {str(e)}")
            return {'competitors': [], 'count': 0}
    
    async def _execute_related_search(self, domain: str, limit: int) -> List[Dict]:
        """Execute Google related: search."""
        query = f"related:{domain}"
        encoded_query = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}&num={limit}"
        
        try:
            await asyncio.sleep(2)  # Rate limiting
            
            response = await http_client.get(url, headers=self.headers)
            if not response or response.status_code != 200:
                logger.warning("Google related: search request failed")
                return []
            
            return self._parse_google_related_results(response.text, domain)
        
        except Exception as e:
            logger.error(f"Error executing related: search: {str(e)}")
            return []
    
    def _parse_google_related_results(self, html: str, original_domain: str) -> List[Dict]:
        """Parse Google related: search results."""
        soup = BeautifulSoup(html, 'html.parser')
        competitors = []
        
        # Find all search result divs
        result_divs = soup.find_all('div', class_='g') or soup.find_all('div', {'data-sokoban-container': True})
        
        for div in result_divs:
            try:
                # Find link
                link = div.find('a', href=True)
                if not link:
                    continue
                
                url = link['href']
                
                # Skip internal Google links
                if url.startswith('/search') or 'google.com' in url:
                    continue
                
                # Skip original domain
                if original_domain in url:
                    continue
                
                # Get title
                title = link.get_text(strip=True)
                if not title:
                    heading = div.find(['h3', 'h2'])
                    if heading:
                        title = heading.get_text(strip=True)
                
                if not title or len(title) < 3:
                    continue
                
                # Get description
                description = ''
                desc_div = div.find('div', {'data-sncf': '1'}) or div.find('div', class_=re.compile(r'(VwiC3b|s3v9rd)', re.I))
                if desc_div:
                    description = desc_div.get_text(strip=True)
                
                # Extract domain
                domain = extract_domain(url)
                
                # Clean company name from title
                company_name = title.split(' - ')[0].split(' | ')[0].strip()
                
                competitors.append({
                    'name': company_name,
                    'domain': domain,
                    'url': url,
                    'description': description[:300] if description else '',
                    'source': 'google_related',
                    'similarity_score': 0  # Will be calculated later
                })
                
            except Exception as e:
                logger.debug(f"Error parsing related result: {str(e)}")
                continue
        
        return competitors
    
    async def _google_keyword_search(self, company_name: str, limit: int) -> Dict:
        """
        Search Google for competitor mentions using keywords.
        
        Args:
            company_name: Company name
            limit: Maximum results
        
        Returns:
            Dictionary with competitors and count
        """
        print(f"🔍 Searching Google for '{company_name}' competitors...")
        
        try:
            competitors = await asyncio.wait_for(
                self._execute_keyword_search(company_name, limit),
                timeout=30.0
            )
            
            print(f"✅ Found {len(competitors)} competitor mentions")
            return {'competitors': competitors, 'count': len(competitors)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Google keyword search timed out for {company_name}")
            return {'competitors': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with Google keyword search: {str(e)}")
            return {'competitors': [], 'count': 0}
    
    async def _execute_keyword_search(self, company_name: str, limit: int) -> List[Dict]:
        """Execute Google competitor keyword search."""
        query = f'"{company_name}" competitors OR alternatives OR "vs" OR "similar to"'
        encoded_query = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded_query}&num={limit}"
        
        try:
            await asyncio.sleep(2)  # Rate limiting
            
            response = await http_client.get(url, headers=self.headers)
            if not response or response.status_code != 200:
                logger.warning("Google keyword search request failed")
                return []
            
            return self._parse_google_keyword_results(response.text, company_name)
        
        except Exception as e:
            logger.error(f"Error executing keyword search: {str(e)}")
            return []
    
    def _parse_google_keyword_results(self, html: str, company_name: str) -> List[Dict]:
        """Parse competitor mentions from Google search."""
        soup = BeautifulSoup(html, 'html.parser')
        competitors = []
        
        # Find all search results
        result_divs = soup.find_all('div', class_='g') or soup.find_all('div', {'data-sokoban-container': True})
        
        for div in result_divs:
            try:
                # Get text content
                text_content = div.get_text()
                
                # Check if mentions competitors
                if not any(keyword in text_content.lower() for keyword in self.COMPETITOR_KEYWORDS):
                    continue
                
                # Find link
                link = div.find('a', href=True)
                if not link:
                    continue
                
                url = link['href']
                
                # Skip internal Google links
                if url.startswith('/search') or 'google.com' in url:
                    continue
                
                # Get title
                title = link.get_text(strip=True)
                
                # Get description
                description = ''
                desc_div = div.find('div', {'data-sncf': '1'}) or div.find('div', class_=re.compile(r'(VwiC3b|s3v9rd)', re.I))
                if desc_div:
                    description = desc_div.get_text(strip=True)
                
                # Extract competitor names from text
                extracted_competitors = self._extract_competitor_names(text_content, company_name)
                
                if extracted_competitors:
                    for comp_name in extracted_competitors:
                        competitors.append({
                            'name': comp_name,
                            'domain': '',  # Unknown from keyword search
                            'url': url,
                            'description': description[:300] if description else '',
                            'source': 'google_search',
                            'similarity_score': 0
                        })
                
            except Exception as e:
                logger.debug(f"Error parsing keyword result: {str(e)}")
                continue
        
        return competitors
    
    def _extract_competitor_names(self, text: str, company_name: str) -> List[str]:
        """Extract competitor names from text."""
        competitors = set()
        
        # Look for patterns like "X vs Y", "X, Y, and Z", "alternatives to X: Y, Z"
        patterns = [
            # "X vs Y" or "X versus Y" pattern - capture both sides
            r'(\b[A-Z][\w\s]{2,30})\s+vs\.?\s+(\b[A-Z][\w\s]{2,30})',
            r'(\b[A-Z][\w\s]{2,30})\s+versus\s+(\b[A-Z][\w\s]{2,30})',
            # "competitors: X, Y, Z" or "alternatives: X, Y, Z"
            r'(?:competitors?|alternatives?|similar\s+(?:to|companies)|rivals?)[:\s]+([A-Z][\w\s,;&]+)',
            # "X, Y, and Z are competitors"
            r'([A-Z][\w\s,;&]+)\s+(?:are|is)\s+(?:competitors?|alternatives?|rivals?)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                for group in match.groups():
                    if group:
                        # Clean and split
                        group = group.strip()
                        # Split by common delimiters
                        names = re.split(r'[,;&]|\s+and\s+|\s+or\s+', group)
                        for name in names:
                            name = name.strip()
                            # Clean up common suffixes/prefixes
                            name = re.sub(r'\s+(Inc\.?|Corp\.?|LLC|Ltd\.?|Limited)$', '', name, flags=re.IGNORECASE)
                            # Remove the company name if it appears in the match
                            name = re.sub(re.escape(company_name), '', name, flags=re.IGNORECASE).strip()
                            # Remove common prefixes like "vs", "versus"
                            name = re.sub(r'^(vs\.?|versus)\s+', '', name, flags=re.IGNORECASE).strip()
                            name = re.sub(r'\s+(vs\.?|versus)$', '', name, flags=re.IGNORECASE).strip()
                            
                            # Stop at common connecting words (take only first word if followed by lowercase)
                            if re.match(r'^[A-Z][a-z]+[A-Z]', name):  # e.g., "VagaroWhy"
                                # Split on uppercase after lowercase
                                parts = re.split(r'(?<=[a-z])(?=[A-Z])', name)
                                if len(parts) > 1:
                                    name = parts[0]
                            
                            # Validate: 
                            # - Must start with capital letter
                            # - 3-40 chars
                            # - Not the original company
                            # - Not common words
                            # - Not URLs
                            if (re.match(r'^[A-Z]', name) and
                                3 <= len(name) <= 40 and 
                                name.lower() != company_name.lower() and
                                not name.lower().startswith('http') and
                                not name.lower() in ['the', 'this', 'that', 'these', 'those', 'and', 'or', 'why', 'how', 'what'] and
                                not re.search(r'\d{3,}', name)):  # No long numbers
                                competitors.add(name)
        
        return list(competitors)[:15]  # Limit to 15 per result
    
    async def _owler_search(self, company_name: str, limit: int) -> Dict:
        """
        Search Owler.com for competitor data.
        
        Args:
            company_name: Company name
            limit: Maximum results
        
        Returns:
            Dictionary with competitors and count
        """
        print(f"🦉 Searching Owler.com for '{company_name}'...")
        
        try:
            competitors = await asyncio.wait_for(
                self._execute_owler_search(company_name, limit),
                timeout=30.0
            )
            
            print(f"✅ Found {len(competitors)} competitors on Owler")
            return {'competitors': competitors, 'count': len(competitors)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Owler search timed out for {company_name}")
            return {'competitors': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with Owler search: {str(e)}")
            return {'competitors': [], 'count': 0}
    
    async def _execute_owler_search(self, company_name: str, limit: int) -> List[Dict]:
        """Execute Owler.com search."""
        # First, find the company page
        search_url = self.OWLER_SEARCH_URL.format(query=quote_plus(company_name))
        
        try:
            await asyncio.sleep(2)  # Rate limiting
            
            response = await http_client.get(search_url, headers=self.headers)
            if not response or response.status_code != 200:
                logger.warning("Owler search request failed")
                return []
            
            # Parse search results to find company page
            company_url = self._parse_owler_search_results(response.text, company_name)
            
            if not company_url:
                logger.info("Company not found on Owler")
                return []
            
            # Get company page with competitors
            await asyncio.sleep(2)
            company_response = await http_client.get(company_url, headers=self.headers)
            
            if not company_response or company_response.status_code != 200:
                logger.warning("Failed to fetch Owler company page")
                return []
            
            return self._parse_owler_competitors(company_response.text)
        
        except Exception as e:
            logger.error(f"Error executing Owler search: {str(e)}")
            return []
    
    def _parse_owler_search_results(self, html: str, company_name: str) -> Optional[str]:
        """Parse Owler search results to find company page URL."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for company links
        company_links = soup.find_all('a', href=re.compile(r'/company/'))
        
        for link in company_links:
            link_text = link.get_text().strip().lower()
            if company_name.lower() in link_text:
                href = link['href']
                if not href.startswith('http'):
                    href = urljoin('https://www.owler.com', href)
                return href
        
        return None
    
    def _parse_owler_competitors(self, html: str) -> List[Dict]:
        """Parse competitors from Owler company page."""
        soup = BeautifulSoup(html, 'html.parser')
        competitors = []
        
        # Owler shows competitors in various sections
        # Look for competitor cards/sections
        competitor_sections = soup.find_all(['div', 'section'], class_=re.compile(r'competitor', re.I))
        
        for section in competitor_sections:
            # Find company links
            company_links = section.find_all('a', href=re.compile(r'/company/'))
            
            for link in company_links[:20]:  # Limit per section
                try:
                    name = link.get_text(strip=True)
                    url = link['href']
                    
                    if not url.startswith('http'):
                        url = urljoin('https://www.owler.com', url)
                    
                    # Find description near the link
                    description = ''
                    parent = link.find_parent(['div', 'li', 'article'])
                    if parent:
                        desc_elem = parent.find(['p', 'div'], class_=re.compile(r'(description|summary)', re.I))
                        if desc_elem:
                            description = desc_elem.get_text(strip=True)
                    
                    competitors.append({
                        'name': name,
                        'domain': '',  # Can be extracted from Owler page later
                        'url': url,
                        'description': description[:300] if description else '',
                        'source': 'owler',
                        'similarity_score': 0
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing Owler competitor: {str(e)}")
                    continue
        
        return competitors
    
    async def _website_competitor_mentions(self, website_url: str, company_name: str) -> Dict:
        """
        Find competitor mentions on company website.
        
        Args:
            website_url: Company website
            company_name: Company name
        
        Returns:
            Dictionary with competitors and count
        """
        print(f"🌐 Checking {website_url} for competitor mentions...")
        
        try:
            competitors = await asyncio.wait_for(
                self._scrape_website_competitors(website_url, company_name),
                timeout=20.0
            )
            
            print(f"✅ Found {len(competitors)} competitor mentions on website")
            return {'competitors': competitors, 'count': len(competitors)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Website scraping timed out for {website_url}")
            return {'competitors': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error scraping website: {str(e)}")
            return {'competitors': [], 'count': 0}
    
    async def _scrape_website_competitors(self, website_url: str, company_name: str) -> List[Dict]:
        """Scrape competitor mentions from company website."""
        competitors = []
        
        # Pages likely to have competitor info
        pages_to_check = [
            '',  # Homepage
            '/about',
            '/compare',
            '/comparison',
            '/alternatives',
            '/vs',
        ]
        
        base_url = normalize_url(website_url)
        
        for page_path in pages_to_check:
            try:
                url = urljoin(base_url, page_path)
                response = await http_client.get(url, headers=self.headers)
                
                if not response or response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for competitor mentions
                text_content = soup.get_text()
                
                # Extract competitor names
                extracted = self._extract_competitor_names(text_content, company_name)
                
                for comp_name in extracted:
                    competitors.append({
                        'name': comp_name,
                        'domain': '',
                        'url': website_url,
                        'description': f'Mentioned on {page_path or "homepage"}',
                        'source': 'website_mention',
                        'similarity_score': 0
                    })
                
                # Be nice to the server
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.debug(f"Error checking page {page_path}: {str(e)}")
                continue
        
        return competitors
    
    def _combine_and_deduplicate(self, results: Dict, company_website: Optional[str]) -> List[Dict]:
        """
        Combine competitors from all sources and remove duplicates.
        """
        all_competitors = []
        seen_domains = set()
        seen_names = set()
        
        # Add company's own domain to seen list
        if company_website:
            company_domain = extract_domain(company_website)
            seen_domains.add(company_domain)
        
        # Collect all competitors
        for source_name, source_data in results.items():
            competitors = source_data.get('competitors', [])
            
            for comp in competitors:
                domain = comp.get('domain', '').lower()
                name = comp.get('name', '').lower().strip()
                
                # Skip if no name
                if not name or len(name) < 3:
                    continue
                
                # Create a key for deduplication
                dedup_key = domain if domain else name
                
                if dedup_key in seen_domains or dedup_key in seen_names:
                    # Already have this competitor, add source
                    for existing in all_competitors:
                        existing_domain = existing.get('domain', '').lower()
                        existing_name = existing.get('name', '').lower()
                        
                        if existing_domain == domain or existing_name == name:
                            # Add source if not already listed
                            if comp['source'] not in existing.get('sources', []):
                                existing.setdefault('sources', []).append(comp['source'])
                                existing['source_count'] = len(existing['sources'])
                            break
                else:
                    # New competitor
                    if domain:
                        seen_domains.add(domain)
                    seen_names.add(name)
                    
                    comp['sources'] = [comp['source']]
                    comp['source_count'] = 1
                    all_competitors.append(comp)
        
        return all_competitors
    
    def _score_competitors(self, competitors: List[Dict], company_name: str) -> List[Dict]:
        """
        Score competitors based on similarity and source reliability.
        """
        for comp in competitors:
            score = 0
            
            # Source scoring
            sources = comp.get('sources', [])
            if 'google_related' in sources:
                score += 30  # Google related: is highly relevant
            if 'owler' in sources:
                score += 25  # Owler is reliable
            if 'google_search' in sources:
                score += 15  # Keyword search is moderately reliable
            if 'website_mention' in sources:
                score += 10  # Website mentions are somewhat reliable
            
            # Multiple sources boost
            source_count = comp.get('source_count', 1)
            if source_count > 1:
                score += (source_count - 1) * 10
            
            # Description quality
            description = comp.get('description', '')
            if len(description) > 50:
                score += 5
            
            # Domain presence
            if comp.get('domain'):
                score += 5
            
            comp['similarity_score'] = min(score, 100)  # Cap at 100
        
        return competitors
    
    def _sort_competitors(self, competitors: List[Dict]) -> List[Dict]:
        """
        Sort competitors by similarity score and source count.
        """
        def sort_key(comp):
            return (
                comp.get('similarity_score', 0),
                comp.get('source_count', 0),
                len(comp.get('description', ''))
            )
        
        return sorted(competitors, key=sort_key, reverse=True)
    
    def _error_result(self, company_name: str, website_url: Optional[str], error: str) -> Dict:
        """Return error result."""
        return {
            'company_name': company_name,
            'company_website': website_url,
            'scraped_at': datetime.now().isoformat(),
            'total_competitors': 0,
            'competitors': [],
            'sources': {},
            'error': error
        }
    
    def _print_summary(self, result: Dict):
        """Print scraping summary."""
        print(f"\n{'='*60}")
        print(f"📊 SCRAPING SUMMARY")
        print(f"{'='*60}")
        print(f"Company: {result['company_name']}")
        print(f"Total Competitors: {result['total_competitors']}")
        print(f"\nSources:")
        for source, count in result['sources'].items():
            print(f"  - {source.replace('_', ' ').title()}: {count}")
        
        if result['competitors']:
            print(f"\nTop Competitors:")
            for i, comp in enumerate(result['competitors'][:5], 1):
                print(f"  {i}. {comp['name']} (Score: {comp['similarity_score']}, Sources: {comp['source_count']})")
        
        print(f"\n{'='*60}\n")
