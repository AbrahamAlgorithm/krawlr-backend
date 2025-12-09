"""
Company Profile Scraper Service

Aggregates company profile information from multiple sources:
- Company website (About page)
- LinkedIn company profile
- Wikipedia page

Returns a unified profile with company description, industry, founding info, and more.
"""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.utils.http_client import http_client
from app.services.utils.validators import normalize_url, extract_domain

logger = logging.getLogger(__name__)


def extract_company_name_from_url(url_or_name: str) -> tuple[str, str | None]:
    """
    Extract company name from URL or return cleaned name.
    
    Examples:
        "tesla.com" -> ("Tesla", "https://tesla.com")
        "https://microsoft.org" -> ("Microsoft", "https://microsoft.org")
        "https://futminna.edu.ng" -> ("Futminna", "https://futminna.edu.ng")
        "https://www.youtube.com/" -> ("YouTube", "https://www.youtube.com")
        "Stripe" -> ("Stripe", None)
    
    Returns:
        Tuple of (company_name, website_url)
    """
    original = url_or_name.strip()
    
    # Check if it looks like a URL
    is_url = any([
        original.startswith('http://'),
        original.startswith('https://'),
        '.' in original and '/' in original,
        original.count('.') >= 1 and ' ' not in original
    ])
    
    if not is_url:
        # It's just a company name
        return (original, None)
    
    # Normalize URL
    if not original.startswith('http'):
        url = f"https://{original}"
    else:
        url = original
    
    # Parse URL
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Split by dots and get the main part
        parts = domain.split('.')
        
        # Handle cases like "futminna.edu.ng" - take first part
        # Handle cases like "youtube.com" - take first part
        # Handle cases like "microsoft.org" - take first part
        company_part = parts[0] if parts else domain
        
        # Capitalize first letter
        company_name = company_part.capitalize()
        
        # Clean up the URL for return
        website_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else f"https://{domain}"
        
        return (company_name, website_url)
        
    except Exception as e:
        logger.error(f"Error parsing URL {original}: {e}")
        # Fallback: just return the original as name
        return (original, None)


class CompanyProfileScraper:
    """Scrapes company profile data from multiple sources."""
    
    def __init__(self):
        self.linkedin_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    async def get_company_profile(self, company_name_or_url: str, website: str | None = None) -> dict:
        """
        Get unified company profile from multiple sources.
        
        Args:
            company_name_or_url: Company name or URL (e.g., "Stripe", "tesla.com", "https://microsoft.org")
            website: Company website URL (optional, will be extracted from company_name_or_url if it's a URL)
        
        Returns:
            Unified profile data from all sources
        """
        # Extract company name from URL if provided
        company_name, extracted_website = extract_company_name_from_url(company_name_or_url)
        
        # Use extracted website if no explicit website provided
        if not website and extracted_website:
            website = extracted_website
        
        print(f"\n🏢 Getting company profile for: {company_name}")
        if website:
            print(f"🌐 Website: {website}")
        print("=" * 70)
        
        try:
            # Run all scrapers in parallel with timeout
            tasks = [
                self._scrape_website_about(company_name, website),
                self._scrape_linkedin_profile(company_name),
                self._scrape_wikipedia(company_name),
            ]
            
            # Add overall timeout to prevent hanging
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=60.0  # 60 second timeout for all scrapers
            )
            
            website_data = results[0] if not isinstance(results[0], Exception) else {}
            linkedin_data = results[1] if not isinstance(results[1], Exception) else {}
            wikipedia_data = results[2] if not isinstance(results[2], Exception) else {}
            
            # Log any exceptions that occurred
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    source = ['Website', 'LinkedIn', 'Wikipedia'][i]
                    logger.warning(f"{source} scraper failed: {str(result)}")
            
        except asyncio.TimeoutError:
            logger.error("Profile scraping timed out after 60 seconds")
            print("⚠️  Scraping timed out, returning partial results...")
            website_data = {}
            linkedin_data = {}
            wikipedia_data = {}
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}")
            print(f"⚠️  Error during scraping: {str(e)}")
            website_data = {}
            linkedin_data = {}
            wikipedia_data = {}
        
        # Merge all data intelligently
        unified_profile = self._merge_profile_data(
            company_name,
            website_data,
            linkedin_data,
            wikipedia_data
        )
        
        self._print_summary(unified_profile)
        
        return unified_profile
    
    async def _scrape_website_about(self, company_name: str, website: str | None) -> dict:
        """Scrape company website's About page."""
        print("\n[Website] Scraping company website...")
        
        try:
            if not website:
                print("[Website] ⚠️  No website provided, searching...")
                website = await asyncio.wait_for(
                    self._find_company_website(company_name),
                    timeout=15.0
                )
                if not website:
                    print("[Website] ❌ Could not find website")
                    return {}
            
            website = normalize_url(website)
            print(f"[Website] 🌐 Target: {website}")
            
            # First, try to find and scrape the About page
            about_url = await asyncio.wait_for(
                self._find_about_page(website),
                timeout=15.0
            )
            
            if about_url:
                print(f"[Website] 📄 Found About page: {about_url}")
                response = await http_client.get(about_url)
                if response:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    data = self._extract_website_data(soup, about_url)
                    print(f"[Website] ✅ Extracted profile data")
                    return data
            
            # Fallback to homepage if About page not found
            print(f"[Website] 📄 Using homepage")
            response = await http_client.get(website)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                data = self._extract_website_data(soup, website)
                print(f"[Website] ✅ Extracted profile data from homepage")
                return data
            
        except asyncio.TimeoutError:
            logger.warning(f"Website scraping timed out for {company_name}")
            print(f"[Website] ⏱️  Timeout")
        except Exception as e:
            logger.error(f"Error scraping website: {e}")
            print(f"[Website] ❌ Error: {str(e)[:100]}")
        
        return {}
    
    async def _find_about_page(self, website: str) -> str | None:
        """Find the About page URL."""
        domain = extract_domain(website)
        
        # Common About page patterns
        about_patterns = [
            f"{website}/about",
            f"{website}/about-us",
            f"{website}/about/",
            f"{website}/about-us/",
            f"{website}/company",
            f"{website}/company/",
            f"{website}/who-we-are",
            f"{website}/our-story",
        ]
        
        # Try each pattern
        for url in about_patterns:
            try:
                response = await http_client.get(url)
                if response and response.status_code == 200:
                    return url
            except:
                continue
        
        # Try to find About link on homepage
        try:
            response = await http_client.get(website)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for About link
                for link in soup.find_all('a', href=True):
                    href = link['href'].lower()
                    text = link.get_text().lower()
                    
                    if any(keyword in href or keyword in text for keyword in ['about', 'company', 'who-we-are', 'our-story']):
                        # Make absolute URL
                        if href.startswith('http'):
                            return href
                        elif href.startswith('/'):
                            return f"{website.rstrip('/')}{href}"
                        else:
                            return f"{website.rstrip('/')}/{href}"
        except:
            pass
        
        return None
    
    def _extract_website_data(self, soup: BeautifulSoup, url: str) -> dict:
        """Extract company data from website HTML."""
        data = {
            "source": "website",
            "url": url,
            "description": None,
            "mission": None,
            "founded": None,
            "headquarters": None,
            "industry": None,
            "company_size": None,
        }
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            data['description'] = meta_desc['content'].strip()
        
        # Extract Open Graph description
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content') and not data['description']:
            data['description'] = og_desc['content'].strip()
        
        # Extract main content text
        main_content = soup.find(['main', 'article', 'div'], class_=re.compile(r'about|content|main', re.I))
        if main_content:
            # Get all paragraph texts
            paragraphs = main_content.find_all('p', limit=5)
            content_texts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50]
            
            if content_texts and not data['description']:
                data['description'] = ' '.join(content_texts[:2])
        
        # Extract structured data (JSON-LD)
        json_ld = soup.find_all('script', type='application/ld+json')
        for script in json_ld:
            try:
                import json
                ld_data = json.loads(script.string)
                
                if isinstance(ld_data, dict):
                    if ld_data.get('@type') in ['Organization', 'Corporation', 'Company']:
                        if not data['description'] and ld_data.get('description'):
                            data['description'] = ld_data['description']
                        if ld_data.get('foundingDate'):
                            data['founded'] = ld_data['foundingDate']
                        if ld_data.get('address'):
                            addr = ld_data['address']
                            if isinstance(addr, dict):
                                city = addr.get('addressLocality', '')
                                country = addr.get('addressCountry', '')
                                data['headquarters'] = f"{city}, {country}".strip(', ')
            except:
                continue
        
        # Look for founded year in text
        if not data['founded']:
            text_content = soup.get_text()
            founded_match = re.search(r'(?:founded|established|started).*?(\d{4})', text_content, re.I)
            if founded_match:
                data['founded'] = founded_match.group(1)
        
        return data
    
    async def _scrape_linkedin_profile(self, company_name: str) -> dict:
        """Scrape LinkedIn company profile."""
        print("\n[LinkedIn] Searching for company profile...")
        
        try:
            # Search for LinkedIn company page with timeout
            linkedin_url = await asyncio.wait_for(
                self._find_linkedin_company_url(company_name),
                timeout=15.0
            )
            
            if not linkedin_url:
                print("[LinkedIn] ❌ Could not find company profile")
                return {}
            
            print(f"[LinkedIn] 🔗 Found profile: {linkedin_url}")
            
            # Scrape LinkedIn page
            response = await http_client.get(linkedin_url, headers=self.linkedin_headers)
            if not response:
                print("[LinkedIn] ❌ Failed to fetch profile")
                return {}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            data = self._extract_linkedin_data(soup, linkedin_url)
            
            print(f"[LinkedIn] ✅ Extracted profile data")
            return data
            
        except asyncio.TimeoutError:
            logger.warning(f"LinkedIn scraping timed out for {company_name}")
            print(f"[LinkedIn] ⏱️  Timeout")
        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {e}")
            print(f"[LinkedIn] ❌ Error: {str(e)[:100]}")
        
        return {}
    
    async def _find_linkedin_company_url(self, company_name: str) -> str | None:
        """Find LinkedIn company page URL via Google search."""
        try:
            query = f'site:linkedin.com/company "{company_name}"'
            encoded_query = quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            response = await http_client.get(search_url, headers=self.linkedin_headers)
            if not response:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find LinkedIn company URLs in search results
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/company/' in href:
                    # Extract clean URL
                    match = re.search(r'(https?://[a-z]{2,3}\.linkedin\.com/company/[^/&\?]+)', href)
                    if match:
                        return match.group(1)
            
        except Exception as e:
            logger.error(f"Error finding LinkedIn URL: {e}")
        
        return None
    
    def _extract_linkedin_data(self, soup: BeautifulSoup, url: str) -> dict:
        """Extract company data from LinkedIn HTML."""
        data = {
            "source": "linkedin",
            "url": url,
            "description": None,
            "industry": None,
            "company_size": None,
            "headquarters": None,
            "founded": None,
            "specialties": [],
        }
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            data['description'] = meta_desc['content'].strip()
        
        # Extract Open Graph data
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content') and not data['description']:
            data['description'] = og_desc['content'].strip()
        
        # Try to extract structured data from page
        # Note: LinkedIn is heavily JS-rendered, so this may be limited
        
        return data
    
    async def _scrape_wikipedia(self, company_name: str) -> dict:
        """Scrape Wikipedia page for company."""
        print("\n[Wikipedia] Searching for company page...")
        
        try:
            # Search Wikipedia with timeout
            wiki_url = await asyncio.wait_for(
                self._find_wikipedia_url(company_name),
                timeout=15.0
            )
            
            if not wiki_url:
                print("[Wikipedia] ❌ No Wikipedia page found")
                return {}
            
            print(f"[Wikipedia] 📖 Found page: {wiki_url}")
            
            # Scrape Wikipedia page
            response = await http_client.get(wiki_url)
            if not response:
                print("[Wikipedia] ❌ Failed to fetch page")
                return {}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            data = self._extract_wikipedia_data(soup, wiki_url)
            
            print(f"[Wikipedia] ✅ Extracted profile data")
            return data
            
        except asyncio.TimeoutError:
            logger.warning(f"Wikipedia scraping timed out for {company_name}")
            print(f"[Wikipedia] ⏱️  Timeout")
        except Exception as e:
            logger.error(f"Error scraping Wikipedia: {e}")
            print(f"[Wikipedia] ❌ Error: {str(e)[:100]}")
        
        return {}
    
    async def _find_wikipedia_url(self, company_name: str) -> str | None:
        """Find Wikipedia page URL."""
        try:
            # Try direct Wikipedia search API
            # Add "company" or "Inc" to improve search results
            from urllib.parse import urlencode
            
            search_terms = [
                f"{company_name} company",
                f"{company_name} Inc",
                company_name,
            ]
            
            for search_term in search_terms:
                params = {
                    'action': 'opensearch',
                    'search': search_term,
                    'limit': 5,
                    'namespace': 0,
                    'format': 'json'
                }
                search_url = f"https://en.wikipedia.org/w/api.php?{urlencode(params)}"
                
                response = await http_client.get(search_url)
                if response:
                    import json
                    results = json.loads(response.text)
                    
                    # results[3] contains URLs
                    if len(results) > 3 and results[3]:
                        # Check if it's a company page (not a fruit, person, etc.)
                        for i, url in enumerate(results[3]):
                            title = results[1][i].lower() if len(results) > 1 and i < len(results[1]) else ""
                            # Look for company-related keywords in title
                            if any(keyword in title for keyword in ['inc', 'corporation', 'company', 'technologies', 'systems']):
                                return url
                        # If no company keywords found, return first result
                        return results[3][0]
            
        except Exception as e:
            logger.error(f"Error finding Wikipedia URL: {e}")
        
        return None
    
    def _extract_wikipedia_data(self, soup: BeautifulSoup, url: str) -> dict:
        """Extract company data from Wikipedia HTML."""
        data = {
            "source": "wikipedia",
            "url": url,
            "description": None,
            "industry": None,
            "founded": None,
            "headquarters": None,
            "founders": [],
            "type": None,
            "revenue": None,
            "employees": None,
        }
        
        # Extract first paragraph (usually the summary)
        content = soup.find('div', id='mw-content-text')
        if content:
            paragraphs = content.find_all('p', recursive=False)
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 50 and not text.startswith('Coordinates'):
                    data['description'] = text
                    break
        
        # Extract infobox data
        infobox = soup.find('table', class_=re.compile(r'infobox', re.I))
        if infobox:
            rows = infobox.find_all('tr')
            
            for row in rows:
                header = row.find('th')
                value_cell = row.find('td')
                
                if not header or not value_cell:
                    continue
                
                header_text = header.get_text().strip().lower()
                value_text = value_cell.get_text().strip()
                
                if 'industry' in header_text or 'industries' in header_text:
                    data['industry'] = value_text
                elif 'founded' in header_text:
                    data['founded'] = value_text
                elif 'headquarters' in header_text or 'hq' in header_text:
                    data['headquarters'] = value_text
                elif 'founder' in header_text:
                    # Extract founder names
                    founders = [a.get_text().strip() for a in value_cell.find_all('a')]
                    data['founders'] = founders if founders else [value_text]
                elif 'type' in header_text:
                    data['type'] = value_text
                elif 'revenue' in header_text:
                    data['revenue'] = value_text
                elif 'employees' in header_text or 'number of employees' in header_text:
                    data['employees'] = value_text
        
        return data
    
    async def _find_company_website(self, company_name: str) -> str | None:
        """Find company website via Google search."""
        try:
            query = f'"{company_name}" official website'
            encoded_query = quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            response = await http_client.get(search_url, headers=self.linkedin_headers)
            if not response:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find first non-social media link
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com' not in href and 'facebook.com' not in href and 'twitter.com' not in href:
                    match = re.search(r'https?://[^\s&]+', href)
                    if match:
                        url = match.group(0)
                        if not any(x in url for x in ['google.com', 'youtube.com', 'wikipedia.org']):
                            return url
            
        except Exception as e:
            logger.error(f"Error finding website: {e}")
        
        return None
    
    def _merge_profile_data(
        self,
        company_name: str,
        website_data: dict,
        linkedin_data: dict,
        wikipedia_data: dict
    ) -> dict:
        """Merge data from all sources intelligently."""
        
        unified = {
            "company_name": company_name,
            "identity": {
                "description": None,
                "industry": None,
                "founded": None,
                "headquarters": None,
                "founders": [],
                "company_type": None,
                "company_size": None,
                "specialties": [],
            },
            "financials": {
                "revenue": None,
                "employees": None,
            },
            "sources": {
                "website": website_data.get("url"),
                "linkedin": linkedin_data.get("url"),
                "wikipedia": wikipedia_data.get("url"),
            },
            "raw_data": {
                "website": website_data,
                "linkedin": linkedin_data,
                "wikipedia": wikipedia_data,
            },
            "metadata": {
                "scraped_at": __import__('datetime').datetime.now().isoformat(),
                "sources_found": sum([
                    bool(website_data),
                    bool(linkedin_data),
                    bool(wikipedia_data)
                ])
            }
        }
        
        # Merge descriptions - prefer Wikipedia (most comprehensive), then website, then LinkedIn
        unified["identity"]["description"] = (
            wikipedia_data.get("description") or
            website_data.get("description") or
            linkedin_data.get("description")
        )
        
        # Merge industry - prefer LinkedIn (most structured), then Wikipedia, then website
        unified["identity"]["industry"] = (
            linkedin_data.get("industry") or
            wikipedia_data.get("industry") or
            website_data.get("industry")
        )
        
        # Merge founded - prefer Wikipedia (most accurate), then website, then LinkedIn
        unified["identity"]["founded"] = (
            wikipedia_data.get("founded") or
            website_data.get("founded") or
            linkedin_data.get("founded")
        )
        
        # Merge headquarters - prefer Wikipedia, then LinkedIn, then website
        unified["identity"]["headquarters"] = (
            wikipedia_data.get("headquarters") or
            linkedin_data.get("headquarters") or
            website_data.get("headquarters")
        )
        
        # Get founders from Wikipedia
        if wikipedia_data.get("founders"):
            unified["identity"]["founders"] = wikipedia_data["founders"]
        
        # Get company type from Wikipedia
        if wikipedia_data.get("type"):
            unified["identity"]["company_type"] = wikipedia_data["type"]
        
        # Get company size from LinkedIn
        if linkedin_data.get("company_size"):
            unified["identity"]["company_size"] = linkedin_data["company_size"]
        
        # Get specialties from LinkedIn
        if linkedin_data.get("specialties"):
            unified["identity"]["specialties"] = linkedin_data["specialties"]
        
        # Get financials from Wikipedia
        if wikipedia_data.get("revenue"):
            unified["financials"]["revenue"] = wikipedia_data["revenue"]
        if wikipedia_data.get("employees"):
            unified["financials"]["employees"] = wikipedia_data["employees"]
        
        return unified
    
    def _print_summary(self, profile: dict) -> None:
        """Print a summary of the extracted profile."""
        print("\n" + "=" * 70)
        print("📊 COMPANY PROFILE SUMMARY")
        print("=" * 70)
        
        identity = profile["identity"]
        
        print(f"\n🏢 Company: {profile['company_name']}")
        
        if identity.get("description"):
            desc = identity["description"][:200] + "..." if len(identity["description"]) > 200 else identity["description"]
            print(f"📝 Description: {desc}")
        
        if identity.get("industry"):
            print(f"🏭 Industry: {identity['industry']}")
        
        if identity.get("founded"):
            print(f"📅 Founded: {identity['founded']}")
        
        if identity.get("headquarters"):
            print(f"📍 Headquarters: {identity['headquarters']}")
        
        if identity.get("founders"):
            print(f"👥 Founders: {', '.join(identity['founders'])}")
        
        if identity.get("company_type"):
            print(f"🏛️  Type: {identity['company_type']}")
        
        if identity.get("company_size"):
            print(f"👔 Size: {identity['company_size']}")
        
        # Sources
        print(f"\n📚 Data Sources:")
        sources = profile["sources"]
        if sources.get("website"):
            print(f"  ✅ Website: {sources['website']}")
        else:
            print(f"  ❌ Website: Not found")
        
        if sources.get("linkedin"):
            print(f"  ✅ LinkedIn: {sources['linkedin']}")
        else:
            print(f"  ❌ LinkedIn: Not found")
        
        if sources.get("wikipedia"):
            print(f"  ✅ Wikipedia: {sources['wikipedia']}")
        else:
            print(f"  ❌ Wikipedia: Not found")
        
        print("\n" + "=" * 70)


# Singleton instance
company_profile_scraper = CompanyProfileScraper()


# Public API
async def get_company_profile(company_name_or_url: str, website: str | None = None) -> dict:
    """
    Get unified company profile from website, LinkedIn, and Wikipedia.
    
    Args:
        company_name_or_url: Company name or URL
            Examples: "Stripe", "tesla.com", "https://microsoft.org", "https://www.youtube.com/"
        website: Company website URL (optional, will be extracted from company_name_or_url if it's a URL)
    
    Returns:
        Unified profile with company description, industry, founding info, etc.
    
    Examples:
        >>> await get_company_profile("Stripe")
        >>> await get_company_profile("tesla.com")
        >>> await get_company_profile("https://microsoft.org")
        >>> await get_company_profile("https://www.youtube.com/")
    """
    return await company_profile_scraper.get_company_profile(company_name_or_url, website)
