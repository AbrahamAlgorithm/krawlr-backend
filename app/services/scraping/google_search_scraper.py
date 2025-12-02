from app.services.utils.http_client import http_client
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from urllib.parse import quote_plus, urljoin
import asyncio

class GoogleSearchScraper:
    """
    Scrapes Google Search results for company information.
    Uses HTML scraping without API.
    """
    
    def __init__(self):
        self.base_url = "https://www.google.com/search"
        # User agent to avoid being blocked
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    async def search_founders(self, company_name: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for founders and executives using LinkedIn.
        Query: site:linkedin.com/in "<company name>" founder OR CEO
        """
        print(f"  🔍 Searching for founders and executives of {company_name}...")
        
        query = f'site:linkedin.com/in "{company_name}" founder OR CEO OR "chief executive"'
        results = await self._search(query, limit=limit)
        
        founders = []
        for result in results:
            founder_info = self._extract_founder_info(result, company_name)
            if founder_info:
                founders.append(founder_info)
        
        print(f"  ✅ Found {len(founders)} founder/executive profile(s)")
        return founders
    
    async def search_funding(self, company_name: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for funding information.
        Query: "<company name>" funding OR "raised" OR "Series A" OR "Series B"
        """
        print(f"  💰 Searching for funding information for {company_name}...")
        
        query = f'"{company_name}" (funding OR raised OR "Series A" OR "Series B" OR "Series C" OR investment OR valuation)'
        results = await self._search(query, limit=limit)
        
        funding_info = []
        for result in results:
            funding_data = self._extract_funding_info(result)
            if funding_data:
                funding_info.append(funding_data)
        
        print(f"  ✅ Found {len(funding_info)} funding mention(s)")
        return funding_info
    
    async def search_competitors(self, domain: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for competitors using related: operator.
        Query: related:targetwebsite.com
        """
        print(f"  🏢 Searching for competitors of {domain}...")
        
        query = f'related:{domain}'
        results = await self._search(query, limit=limit)
        
        competitors = []
        for result in results:
            competitor_info = {
                'name': result.get('title', '').split(' - ')[0].strip(),
                'url': result.get('url'),
                'description': result.get('description', '')
            }
            if competitor_info['url'] and competitor_info['url'] != f"http://{domain}" and competitor_info['url'] != f"https://{domain}":
                competitors.append(competitor_info)
        
        print(f"  ✅ Found {len(competitors)} competitor(s)")
        return competitors
    
    async def search_news(self, company_name: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for recent news mentions.
        Uses Google News search.
        """
        print(f"  📰 Searching for news about {company_name}...")
        
        query = f'"{company_name}"'
        # Add tbm=nws for news search
        results = await self._search(query, limit=limit, search_type='nws')
        
        news_items = []
        for result in results:
            news_item = {
                'title': result.get('title', ''),
                'url': result.get('url'),
                'description': result.get('description', ''),
                'source': result.get('source', '')
            }
            if news_item['url']:
                news_items.append(news_item)
        
        print(f"  ✅ Found {len(news_items)} news mention(s)")
        return news_items
    
    async def _search(self, query: str, limit: int = 10, search_type: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Perform a Google search and extract results.
        
        Args:
            query: Search query
            limit: Maximum number of results
            search_type: Optional search type ('nws' for news)
        """
        encoded_query = quote_plus(query)
        url = f"{self.base_url}?q={encoded_query}&num={limit}"
        
        if search_type:
            url += f"&tbm={search_type}"
        
        try:
            # Add delay to avoid rate limiting
            await asyncio.sleep(1)
            
            response = await http_client.get(url, headers=self.headers)
            if not response:
                print(f"  ❌ Failed to fetch search results")
                return []
            
            return self._parse_search_results(response.text)
        
        except Exception as e:
            print(f"  ❌ Error searching: {str(e)}")
            return []
    
    def _parse_search_results(self, html: str) -> List[Dict[str, str]]:
        """Parse Google search results HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # Google search result divs
        # Note: Google's HTML structure changes frequently
        search_divs = soup.find_all('div', class_='g')
        
        for div in search_divs:
            try:
                # Extract title and URL
                title_tag = div.find('h3')
                link_tag = div.find('a', href=True)
                
                if not title_tag or not link_tag:
                    continue
                
                title = title_tag.get_text(strip=True)
                url = link_tag['href']
                
                # Clean URL (remove Google redirect)
                if url.startswith('/url?q='):
                    url = url.split('/url?q=')[1].split('&')[0]
                
                # Extract description
                description_div = div.find('div', class_=re.compile('VwiC3b|s3v9rd|yXK7lf'))
                description = description_div.get_text(strip=True) if description_div else ''
                
                # Extract source for news results
                source_span = div.find('span', class_=re.compile('source'))
                source = source_span.get_text(strip=True) if source_span else ''
                
                results.append({
                    'title': title,
                    'url': url,
                    'description': description,
                    'source': source
                })
            
            except Exception as e:
                continue
        
        return results
    
    def _extract_founder_info(self, result: Dict[str, str], company_name: str) -> Optional[Dict[str, str]]:
        """Extract structured founder information from search result."""
        title = result.get('title', '')
        url = result.get('url', '')
        description = result.get('description', '')
        
        # Must be a LinkedIn profile
        if 'linkedin.com/in/' not in url:
            return None
        
        # Extract name (usually first part of title before ' - ')
        name_parts = title.split(' - ')
        if len(name_parts) > 0:
            name = name_parts[0].strip()
        else:
            name = title
        
        # Try to extract job title from title or description
        job_title = None
        job_keywords = ['founder', 'ceo', 'chief executive', 'co-founder', 'president', 'owner', 'director']
        
        combined_text = (title + ' ' + description).lower()
        for keyword in job_keywords:
            if keyword in combined_text:
                # Try to extract the full title
                patterns = [
                    r'(co-founder[^,.\n]*)',
                    r'(founder[^,.\n]*)',
                    r'(ceo[^,.\n]*)',
                    r'(chief executive[^,.\n]*)',
                    r'(president[^,.\n]*)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        job_title = match.group(1).strip()
                        break
                
                if job_title:
                    break
        
        return {
            'name': name,
            'job_title': job_title or 'Founder/Executive',
            'profile_url': url,
            'description': description[:200] if description else None
        }
    
    def _extract_funding_info(self, result: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Extract funding information from search result."""
        title = result.get('title', '')
        url = result.get('url', '')
        description = result.get('description', '')
        
        combined_text = title + ' ' + description
        
        # Look for funding keywords
        funding_keywords = ['raised', 'funding', 'series a', 'series b', 'series c', 
                           'investment', 'valuation', 'million', 'billion', 'investors']
        
        if not any(keyword in combined_text.lower() for keyword in funding_keywords):
            return None
        
        # Extract amount if mentioned
        amount = None
        amount_pattern = r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion|M|B)'
        amount_match = re.search(amount_pattern, combined_text, re.IGNORECASE)
        if amount_match:
            amount = f"${amount_match.group(1)} {amount_match.group(2)}"
        
        # Extract round type
        round_type = None
        round_patterns = [
            r'(Series [A-F])',
            r'(Seed round)',
            r'(Pre-seed)',
            r'(IPO)',
        ]
        
        for pattern in round_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                round_type = match.group(1)
                break
        
        return {
            'title': title,
            'url': url,
            'description': description[:300] if description else '',
            'amount': amount,
            'round_type': round_type
        }

# Create singleton instance
google_search_scraper = GoogleSearchScraper()
