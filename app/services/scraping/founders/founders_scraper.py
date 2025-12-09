"""
Founders & Leadership Scraper

Discovers company founders, executives, and leadership team from multiple sources:
- Company website team/about pages
- LinkedIn company profiles
- Crunchbase
- Wikipedia
- Google Search results
"""

import asyncio
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.services.utils.http_client import http_client
from app.services.utils.validators import normalize_url, extract_domain
import logging

logger = logging.getLogger(__name__)


class FoundersScraper:
    """Comprehensive scraper for company founders and leadership team."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # Role keywords for classification
        self.founder_keywords = ['founder', 'co-founder', 'cofounder', 'creator', 'established by']
        self.ceo_keywords = ['ceo', 'chief executive', 'president']
        self.cfo_keywords = ['cfo', 'chief financial']
        self.cto_keywords = ['cto', 'chief technology', 'chief technical']
        self.executive_keywords = ['chief', 'executive', 'president', 'vp', 'vice president', 'evp']
        self.board_keywords = ['board member', 'director', 'board of directors', 'chairman', 'chairwoman']
    
    async def scrape_founders(
        self,
        company_name: str,
        website_url: Optional[str] = None,
        max_people: int = 20
    ) -> Dict:
        """
        Main scraping function for founders and leadership.
        
        Args:
            company_name: Company name
            website_url: Optional company website
            max_people: Maximum people to return
        
        Returns:
            Dictionary with founders, executives, leadership, and metadata
        """
        print(f"\n{'='*60}")
        print(f"👥 FOUNDERS & LEADERSHIP SCRAPER - {company_name}")
        print(f"{'='*60}\n")
        
        try:
            # Run all sources in parallel with timeout
            results = await asyncio.wait_for(
                self._run_scraping_tasks(company_name, website_url, max_people),
                timeout=120.0
            )
            
            # Combine and deduplicate
            all_people = self._combine_and_deduplicate(results)
            
            # Classify by role
            classified = self._classify_people(all_people)
            
            # Sort by importance
            sorted_people = self._sort_by_importance(classified)
            
            # Limit results
            limited = self._limit_results(sorted_people, max_people)
            
            # Print summary
            self._print_summary(company_name, limited, results)
            
            return {
                'company_name': company_name,
                'website_url': website_url,
                'founders': limited.get('founders', []),
                'executives': limited.get('executives', []),
                'leadership': limited.get('leadership', []),
                'board': limited.get('board', []),
                'total_count': sum(len(v) for v in limited.values()),
                'sources_used': [k for k, v in results.items() if v['count'] > 0],
                'source_counts': {k: v['count'] for k, v in results.items()},
                'metadata': {
                    'max_people_requested': max_people,
                    'scrape_timestamp': None,
                }
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Scraping timed out for {company_name}")
            return self._empty_result(company_name, website_url, "Timeout")
        except Exception as e:
            logger.error(f"Error scraping founders for {company_name}: {str(e)}")
            return self._empty_result(company_name, website_url, str(e))
    
    async def _run_scraping_tasks(
        self,
        company_name: str,
        website_url: Optional[str],
        max_people: int
    ) -> Dict:
        """Run all scraping tasks in parallel."""
        tasks = []
        task_names = []
        
        # Wikipedia search
        tasks.append(self._wikipedia_search(company_name, max_people))
        task_names.append('wikipedia')
        
        # Google Search
        tasks.append(self._google_search(company_name, max_people))
        task_names.append('google_search')
        
        # Crunchbase search
        tasks.append(self._crunchbase_search(company_name, max_people))
        task_names.append('crunchbase')
        
        # Website team pages (if website provided)
        if website_url:
            tasks.append(self._website_team_pages(website_url, company_name, max_people))
            task_names.append('website')
        
        # LinkedIn (if website provided)
        if website_url:
            tasks.append(self._linkedin_search(company_name, website_url, max_people))
            task_names.append('linkedin')
        
        # Run all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results with task names
        combined = {}
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.error(f"Error in {name}: {str(result)}")
                combined[name] = {'people': [], 'count': 0}
            else:
                combined[name] = result
        
        return combined
    
    async def _wikipedia_search(self, company_name: str, limit: int) -> Dict:
        """Search Wikipedia for founder information."""
        print(f"📖 Searching Wikipedia for '{company_name}' founders...")
        
        try:
            people = await asyncio.wait_for(
                self._scrape_wikipedia_founders(company_name),
                timeout=20.0
            )
            
            print(f"✅ Found {len(people)} people on Wikipedia")
            return {'people': people, 'count': len(people)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Wikipedia search timed out for {company_name}")
            return {'people': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with Wikipedia search: {str(e)}")
            return {'people': [], 'count': 0}
    
    async def _scrape_wikipedia_founders(self, company_name: str) -> List[Dict]:
        """Scrape founder data from Wikipedia."""
        people = []
        
        # Try multiple Wikipedia URL variations
        wiki_queries = [
            company_name.replace(' ', '_'),
            f"{company_name.replace(' ', '_')}_(company)",
            f"{company_name.replace(' ', '_')},_Inc.",
        ]
        
        response = None
        wiki_url = None
        
        # Try each variation until we get a successful response
        for query in wiki_queries:
            url = f"https://en.wikipedia.org/wiki/{query}"
            try:
                resp = await http_client.get(url, headers=self.headers)
                if resp and resp.status_code == 200:
                    response = resp
                    wiki_url = url
                    break
            except:
                continue
        
        try:
            
            if not response or response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check infobox for founders
            infobox = soup.find('table', class_='infobox')
            if infobox:
                for row in infobox.find_all('tr'):
                    header = row.find('th')
                    if header:
                        header_text = header.get_text().lower()
                        
                        # Look for founder fields
                        if any(keyword in header_text for keyword in ['founder', 'founded by', 'created by']):
                            cell = row.find('td')
                            if cell:
                                # Extract names
                                links = cell.find_all('a', href=re.compile(r'/wiki/'))
                                for link in links:
                                    name = link.get_text(strip=True)
                                    href = link.get('href', '')
                                    
                                    if len(name) > 2 and not href.startswith('/wiki/Wikipedia:'):
                                        people.append({
                                            'name': name,
                                            'role': 'Founder',
                                            'source': 'wikipedia',
                                            'url': urljoin('https://en.wikipedia.org', href),
                                            'description': f'Founder of {company_name}',
                                        })
                        
                        # Look for key people
                        elif 'key people' in header_text:
                            cell = row.find('td')
                            if cell:
                                # Parse key people section
                                text = cell.get_text()
                                lines = [line.strip() for line in text.split('\n') if line.strip()]
                                
                                for line in lines:
                                    # Match patterns like "John Doe (CEO)" or "Jane Smith, CFO"
                                    match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)[\s,\(]+(.*?)[\)\,\n]?', line)
                                    if match:
                                        name = match.group(1).strip()
                                        role = match.group(2).strip()
                                        
                                        if len(name) > 2:
                                            people.append({
                                                'name': name,
                                                'role': role or 'Key Person',
                                                'source': 'wikipedia',
                                                'url': wiki_url,
                                                'description': f'{role} at {company_name}',
                                            })
            
            # Look for "Founders" section
            for heading in soup.find_all(['h2', 'h3']):
                heading_text = heading.get_text().lower()
                
                if 'founder' in heading_text:
                    # Get content after this heading
                    content = heading.find_next(['p', 'ul'])
                    if content:
                        links = content.find_all('a', href=re.compile(r'/wiki/'), limit=10)
                        for link in links:
                            name = link.get_text(strip=True)
                            href = link.get('href', '')
                            
                            if len(name) > 2 and not href.startswith('/wiki/Wikipedia:'):
                                people.append({
                                    'name': name,
                                    'role': 'Founder',
                                    'source': 'wikipedia',
                                    'url': urljoin('https://en.wikipedia.org', href),
                                    'description': f'Founder mentioned on Wikipedia',
                                })
        
        except Exception as e:
            logger.debug(f"Error scraping Wikipedia: {str(e)}")
        
        return people
    
    async def _google_search(self, company_name: str, limit: int) -> Dict:
        """Search Google for founder information."""
        print(f"🔍 Searching Google for '{company_name}' founders...")
        
        try:
            people = await asyncio.wait_for(
                self._scrape_google_founders(company_name),
                timeout=30.0
            )
            
            print(f"✅ Found {len(people)} people via Google")
            return {'people': people, 'count': len(people)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Google search timed out for {company_name}")
            return {'people': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with Google search: {str(e)}")
            return {'people': [], 'count': 0}
    
    async def _scrape_google_founders(self, company_name: str) -> List[Dict]:
        """Scrape founder info from Google search results."""
        people = []
        
        search_url = f"https://www.google.com/search?q={company_name}+founders"
        
        try:
            response = await http_client.get(search_url, headers=self.headers)
            
            if not response or response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for Google Knowledge Panel
            # Founders often appear in structured data
            knowledge_panels = soup.find_all('div', {'data-attrid': True})
            
            for panel in knowledge_panels:
                attrid = panel.get('data-attrid', '')
                
                if 'founder' in attrid.lower():
                    text = panel.get_text(strip=True)
                    
                    # Extract names using patterns
                    names = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
                    
                    for name in names[:5]:  # Limit to 5
                        if len(name) > 2:
                            people.append({
                                'name': name,
                                'role': 'Founder',
                                'source': 'google',
                                'url': '',
                                'description': f'Founder of {company_name}',
                            })
        
        except Exception as e:
            logger.debug(f"Error scraping Google: {str(e)}")
        
        return people
    
    async def _crunchbase_search(self, company_name: str, limit: int) -> Dict:
        """Search Crunchbase for founder/leadership information."""
        print(f"🚀 Searching Crunchbase for '{company_name}' team...")
        
        try:
            people = await asyncio.wait_for(
                self._scrape_crunchbase_people(company_name),
                timeout=30.0
            )
            
            print(f"✅ Found {len(people)} people on Crunchbase")
            return {'people': people, 'count': len(people)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Crunchbase search timed out for {company_name}")
            return {'people': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with Crunchbase search: {str(e)}")
            return {'people': [], 'count': 0}
    
    async def _scrape_crunchbase_people(self, company_name: str) -> List[Dict]:
        """Scrape people data from Crunchbase."""
        people = []
        limit = 20  # Limit number of people to scrape
        
        # Search Crunchbase
        search_query = company_name.replace(' ', '+')
        search_url = f"https://www.crunchbase.com/organization/{search_query.lower()}"
        
        try:
            response = await http_client.get(search_url, headers=self.headers)
            
            if not response or response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Crunchbase often has founder info in structured sections
            # Look for people sections
            sections = soup.find_all(['section', 'div'], class_=re.compile(r'(people|team|founder)', re.I))
            
            for section in sections:
                # Extract names and roles
                links = section.find_all('a', href=re.compile(r'/person/'))
                
                for link in links[:limit]:
                    name = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Look for role near the name
                    parent = link.find_parent(['div', 'li', 'span'])
                    role = 'Team Member'
                    
                    if parent:
                        role_text = parent.get_text()
                        # Extract role
                        if 'founder' in role_text.lower():
                            role = 'Founder'
                        elif 'ceo' in role_text.lower():
                            role = 'CEO'
                        elif 'cto' in role_text.lower():
                            role = 'CTO'
                        elif 'cfo' in role_text.lower():
                            role = 'CFO'
                    
                    if len(name) > 2:
                        people.append({
                            'name': name,
                            'role': role,
                            'source': 'crunchbase',
                            'url': urljoin('https://www.crunchbase.com', href),
                            'description': f'{role} at {company_name}',
                        })
        
        except Exception as e:
            logger.debug(f"Error scraping Crunchbase: {str(e)}")
        
        return people
    
    async def _website_team_pages(self, website_url: str, company_name: str, limit: int) -> Dict:
        """Scrape team/about pages from company website."""
        print(f"🌐 Checking {website_url} for team pages...")
        
        try:
            people = await asyncio.wait_for(
                self._scrape_website_team(website_url, company_name),
                timeout=30.0
            )
            
            print(f"✅ Found {len(people)} people on website")
            return {'people': people, 'count': len(people)}
            
        except asyncio.TimeoutError:
            logger.warning(f"Website scraping timed out for {website_url}")
            return {'people': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with website scraping: {str(e)}")
            return {'people': [], 'count': 0}
    
    async def _scrape_website_team(self, website_url: str, company_name: str) -> List[Dict]:
        """Scrape team information from website."""
        people = []
        
        website_url = normalize_url(website_url)
        domain = extract_domain(website_url)
        
        # Common team page URLs
        team_paths = [
            '/team',
            '/about/team',
            '/about-us/team',
            '/leadership',
            '/about/leadership',
            '/company/team',
            '/company/leadership',
            '/about',
            '/about-us',
        ]
        
        for path in team_paths:
            try:
                url = urljoin(website_url, path)
                response = await http_client.get(url, headers=self.headers, timeout=10)
                
                if not response or response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for people sections
                # Common patterns: team member cards, leadership sections
                
                # Pattern 1: Look for names in headings near role descriptions
                headings = soup.find_all(['h2', 'h3', 'h4', 'h5'])
                
                for heading in headings:
                    text = heading.get_text(strip=True)
                    
                    # Check if it looks like a person's name (2-4 words, starts with capital)
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$', text):
                        name = text
                        
                        # Look for role in nearby text
                        role = 'Team Member'
                        next_elem = heading.find_next(['p', 'div', 'span'])
                        if next_elem:
                            role_text = next_elem.get_text(strip=True)
                            # First line is usually the role
                            role = role_text.split('\n')[0][:100]
                        
                        people.append({
                            'name': name,
                            'role': role,
                            'source': 'website',
                            'url': url,
                            'description': f'{role} at {company_name}',
                        })
                
                # Pattern 2: Look for structured team sections
                team_sections = soup.find_all(['div', 'section'], class_=re.compile(r'(team|member|person|leader)', re.I))
                
                for section in team_sections[:20]:  # Limit to 20 sections
                    # Look for name and role patterns
                    name_elem = section.find(['h2', 'h3', 'h4', 'h5', 'strong'])
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        
                        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$', name):
                            # Look for role
                            role_elem = section.find(['p', 'span', 'div'], class_=re.compile(r'(role|title|position)', re.I))
                            role = role_elem.get_text(strip=True)[:100] if role_elem else 'Team Member'
                            
                            people.append({
                                'name': name,
                                'role': role,
                                'source': 'website',
                                'url': url,
                                'description': f'{role} at {company_name}',
                            })
                
                # If we found people on this page, stop searching other paths
                if people:
                    break
                    
            except Exception as e:
                logger.debug(f"Error checking {path}: {str(e)}")
                continue
        
        return people
    
    async def _linkedin_search(self, company_name: str, website_url: str, limit: int) -> Dict:
        """Search LinkedIn for company leadership."""
        print(f"💼 Searching LinkedIn for '{company_name}' leadership...")
        
        try:
            people = await asyncio.wait_for(
                self._scrape_linkedin_people(company_name),
                timeout=30.0
            )
            
            print(f"✅ Found {len(people)} people on LinkedIn")
            return {'people': people, 'count': len(people)}
            
        except asyncio.TimeoutError:
            logger.warning(f"LinkedIn search timed out for {company_name}")
            return {'people': [], 'count': 0}
        except Exception as e:
            logger.error(f"Error with LinkedIn search: {str(e)}")
            return {'people': [], 'count': 0}
    
    async def _scrape_linkedin_people(self, company_name: str) -> List[Dict]:
        """Scrape people from LinkedIn."""
        people = []
        limit = 20  # Limit number of people to scrape
        
        # LinkedIn often blocks scraping, but we can try
        search_query = company_name.replace(' ', '%20')
        linkedin_url = f"https://www.linkedin.com/company/{search_query.lower()}"
        
        try:
            response = await http_client.get(linkedin_url, headers=self.headers)
            
            if not response or response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for people sections
            # LinkedIn structure varies, this is a basic attempt
            sections = soup.find_all(['section', 'div'], class_=re.compile(r'(people|employee)', re.I))
            
            for section in sections:
                links = section.find_all('a', href=re.compile(r'/in/'))
                
                for link in links[:limit]:
                    name = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    if len(name) > 2:
                        people.append({
                            'name': name,
                            'role': 'Employee',
                            'source': 'linkedin',
                            'url': urljoin('https://www.linkedin.com', href),
                            'description': f'Employee at {company_name}',
                        })
        
        except Exception as e:
            logger.debug(f"Error scraping LinkedIn: {str(e)}")
        
        return people
    
    def _combine_and_deduplicate(self, results: Dict) -> List[Dict]:
        """Combine results from all sources and deduplicate."""
        seen_names = {}
        combined = []
        
        # Process each source
        for source_name, source_data in results.items():
            for person in source_data.get('people', []):
                name = person['name'].strip()
                name_lower = name.lower()
                
                # Check if we've seen this person
                if name_lower in seen_names:
                    # Merge data (prefer more specific roles)
                    existing = seen_names[name_lower]
                    
                    # Add source
                    if 'sources' not in existing:
                        existing['sources'] = [existing['source']]
                    existing['sources'].append(person['source'])
                    
                    # Update role if new one is more specific
                    if len(person['role']) > len(existing['role']):
                        existing['role'] = person['role']
                    
                else:
                    # New person
                    person['sources'] = [person['source']]
                    seen_names[name_lower] = person
                    combined.append(person)
        
        return combined
    
    def _classify_people(self, people: List[Dict]) -> Dict:
        """Classify people by their roles."""
        classified = {
            'founders': [],
            'executives': [],
            'leadership': [],
            'board': [],
        }
        
        for person in people:
            role_lower = person['role'].lower()
            
            # Check if founder
            if any(keyword in role_lower for keyword in self.founder_keywords):
                classified['founders'].append(person)
            
            # Check if board member
            elif any(keyword in role_lower for keyword in self.board_keywords):
                classified['board'].append(person)
            
            # Check if executive (C-level)
            elif any(keyword in role_lower for keyword in self.executive_keywords):
                classified['executives'].append(person)
            
            # Otherwise leadership
            else:
                classified['leadership'].append(person)
        
        return classified
    
    def _sort_by_importance(self, classified: Dict) -> Dict:
        """Sort people within each category by importance."""
        
        def importance_score(person):
            """Calculate importance score for sorting."""
            score = 0
            role_lower = person['role'].lower()
            
            # Founder is most important
            if any(kw in role_lower for kw in self.founder_keywords):
                score += 1000
            
            # CEO
            if any(kw in role_lower for kw in self.ceo_keywords):
                score += 500
            
            # Other C-level
            if 'chief' in role_lower:
                score += 100
            
            # Number of sources
            score += len(person.get('sources', [person['source']])) * 50
            
            # Role length (more detailed = more important)
            score += min(len(person['role']), 50)
            
            return score
        
        sorted_classified = {}
        for category, people_list in classified.items():
            sorted_classified[category] = sorted(
                people_list,
                key=importance_score,
                reverse=True
            )
        
        return sorted_classified
    
    def _limit_results(self, classified: Dict, max_people: int) -> Dict:
        """Limit total results while maintaining category balance."""
        limited = {}
        
        # Calculate per-category limits (prioritize founders/executives)
        founder_limit = min(len(classified['founders']), max(5, max_people // 4))
        exec_limit = min(len(classified['executives']), max(5, max_people // 3))
        remaining = max_people - founder_limit - exec_limit
        
        limited['founders'] = classified['founders'][:founder_limit]
        limited['executives'] = classified['executives'][:exec_limit]
        
        # Split remaining between leadership and board
        if remaining > 0:
            lead_limit = remaining // 2
            board_limit = remaining - lead_limit
            limited['leadership'] = classified['leadership'][:lead_limit]
            limited['board'] = classified['board'][:board_limit]
        else:
            limited['leadership'] = []
            limited['board'] = []
        
        return limited
    
    def _print_summary(self, company_name: str, classified: Dict, results: Dict):
        """Print scraping summary."""
        print(f"\n{'='*60}")
        print(f"📊 SCRAPING SUMMARY")
        print(f"{'='*60}")
        print(f"Company: {company_name}")
        
        total = sum(len(v) for v in classified.values())
        print(f"Total People: {total}")
        print(f"\nBy Category:")
        print(f"  - Founders: {len(classified['founders'])}")
        print(f"  - Executives: {len(classified['executives'])}")
        print(f"  - Leadership: {len(classified['leadership'])}")
        print(f"  - Board: {len(classified['board'])}")
        
        print(f"\nSources:")
        for source, data in results.items():
            print(f"  - {source.title()}: {data['count']}")
        
        # Show top people
        if classified['founders']:
            print(f"\nTop Founders:")
            for person in classified['founders'][:3]:
                sources = person.get('sources', [person['source']])
                print(f"  • {person['name']} - {person['role']} (Sources: {len(sources)})")
        
        if classified['executives']:
            print(f"\nTop Executives:")
            for person in classified['executives'][:3]:
                sources = person.get('sources', [person['source']])
                print(f"  • {person['name']} - {person['role']} (Sources: {len(sources)})")
        
        print(f"\n{'='*60}\n")
    
    def _empty_result(self, company_name: str, website_url: Optional[str], error: str) -> Dict:
        """Return empty result structure."""
        return {
            'company_name': company_name,
            'website_url': website_url,
            'founders': [],
            'executives': [],
            'leadership': [],
            'board': [],
            'total_count': 0,
            'sources_used': [],
            'source_counts': {},
            'metadata': {
                'error': error,
            }
        }
