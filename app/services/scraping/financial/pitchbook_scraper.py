"""
PitchBook scraper service for company financial and funding data.
Extracts data from PitchBook company profile pages.

PitchBook has data on both public and private companies, including:
- Revenue estimates
- Employee counts
- Funding rounds
- Investors
- Executives/Founders
"""

from __future__ import annotations

import logging
import re
import asyncio
from typing import Any
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)


async def search_pitchbook_url(company_name: str) -> str | None:
    """
    Search for a company's PitchBook profile URL using DuckDuckGo HTML search.
    DuckDuckGo is more bot-friendly than Google and doesn't require API keys.
    
    Implements retry logic with exponential backoff to handle rate limiting.
    
    Args:
        company_name: Company name to search for
        
    Returns:
        PitchBook profile URL string or None if not found
    """
    print(f"\n[PITCHBOOK] 🔍 Step 1: Searching for: {company_name}")
    logger.info(f"Starting DuckDuckGo search for PitchBook profile: {company_name}")
    
    max_retries = 3
    base_delay = 2.0  # seconds
    
    for attempt in range(max_retries):
        try:
            # Use DuckDuckGo HTML search (no JavaScript required, more bot-friendly)
            query = f"site:pitchbook.com/profiles/company {company_name}"
            search_url = "https://html.duckduckgo.com/html/"
            
            if attempt > 0:
                print(f"[PITCHBOOK] 🔄 Retry attempt {attempt + 1}/{max_retries}")
                logger.info(f"Retry attempt {attempt + 1} for: {company_name}")
            
            print(f"[PITCHBOOK] 🌐 DuckDuckGo search query: '{query}'")
            logger.info(f"DuckDuckGo search for: {query}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            # DuckDuckGo HTML requires POST with form data
            data = {
                'q': query,
                'b': '',  # Start from first result
                'kl': 'us-en'  # Region
            }
            
            print(f"[PITCHBOOK] 📡 Sending request to DuckDuckGo...")
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.post(search_url, data=data, headers=headers)
                
                print(f"[PITCHBOOK] 📥 DuckDuckGo response status: {response.status_code}")
                logger.info(f"DuckDuckGo search response status: {response.status_code}")
                
                # Handle 202 (Accepted) - DuckDuckGo rate limiting
                if response.status_code == 202:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"[PITCHBOOK] ⏳ Rate limited (202). Waiting {delay}s before retry...")
                    logger.warning(f"DuckDuckGo returned 202, retrying after {delay}s")
                    await asyncio.sleep(delay)
                    continue
                
                response.raise_for_status()
                
                # Parse search results
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # DuckDuckGo HTML uses class 'result__url' for result links
                result_links = soup.find_all('a', class_='result__url')
                print(f"[PITCHBOOK] 🔗 Found {len(result_links)} result links")
                logger.info(f"Found {len(result_links)} result links from DuckDuckGo")
                
                # If no results and we have retries left, retry
                if len(result_links) == 0 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"[PITCHBOOK] ⚠️  No results found. Retrying after {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                
                # Also check all links as fallback
                all_links = soup.find_all('a', href=True)
                print(f"[PITCHBOOK] 🔗 Total links in page: {len(all_links)}")
                
                # Log first 10 result URLs
                if result_links:
                    print(f"[PITCHBOOK] 📋 First {min(10, len(result_links))} result URLs:")
                    for i, link in enumerate(result_links[:10]):
                        url_text = link.get_text(strip=True)
                        print(f"   {i+1}. {url_text}")
                
                pitchbook_links_found = []
                
                # Check result links first
                for link in result_links:
                    url_text = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Check if it's a PitchBook company profile URL
                    if 'pitchbook.com/profiles/company/' in url_text:
                        # Construct full URL from the text
                        if not url_text.startswith('http'):
                            url = f"https://{url_text}"
                        else:
                            url = url_text
                        
                        pitchbook_links_found.append(url)
                        print(f"[PITCHBOOK] ✅ FOUND PITCHBOOK URL: {url}")
                        logger.info(f"Found PitchBook URL: {url}")
                        return url
                
                # Fallback: check all links
                print(f"[PITCHBOOK] 🔍 Checking all links as fallback...")
                for link in all_links:
                    href = link.get('href', '')
                    
                    # Direct PitchBook profile URL
                    if 'pitchbook.com/profiles/company/' in href:
                        if href.startswith('http'):
                            pitchbook_links_found.append(href)
                            print(f"[PITCHBOOK] ✅ FOUND PITCHBOOK URL (direct): {href}")
                            logger.info(f"Found PitchBook URL (direct): {href}")
                            return href
                        elif href.startswith('//'):
                            url = f"https:{href}"
                            pitchbook_links_found.append(url)
                            print(f"[PITCHBOOK] ✅ FOUND PITCHBOOK URL (protocol-relative): {url}")
                            logger.info(f"Found PitchBook URL: {url}")
                            return url
                
                print(f"[PITCHBOOK] ⚠️  Total PitchBook links found: {len(pitchbook_links_found)}")
                if pitchbook_links_found:
                    print(f"[PITCHBOOK] 📋 Links found: {pitchbook_links_found}")
                else:
                    print(f"[PITCHBOOK] ❌ No PitchBook profile links found in search results")
                
                # If no results found and no retries left, return None
                logger.warning(f"No PitchBook profile found for: {company_name}")
                return None
                
        except httpx.HTTPStatusError as e:
            print(f"[PITCHBOOK] ❌ HTTP Error: {e.response.status_code}")
            logger.error(f"HTTP error searching DuckDuckGo: {e}")
            
            # If we have retries left and it's a 5xx error, retry
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[PITCHBOOK] ⏳ Server error. Retrying after {delay}s...")
                await asyncio.sleep(delay)
                continue
            
            return None
        except Exception as e:
            print(f"[PITCHBOOK] ❌ Error searching: {e}")
            logger.error(f"Error searching PitchBook for {company_name}: {e}")
            
            # If we have retries left, retry
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[PITCHBOOK] ⏳ Error occurred. Retrying after {delay}s...")
                await asyncio.sleep(delay)
                continue
            
            import traceback
            traceback.print_exc()
            return None
    
    # All retries exhausted
    print(f"[PITCHBOOK] ❌ All {max_retries} attempts failed")
    logger.error(f"All retry attempts exhausted for: {company_name}")
    return None


async def scrape_pitchbook_profile(url: str) -> dict | None:
    """
    Scrape data from a PitchBook company profile preview page.
    
    Args:
        url: PitchBook profile URL (e.g., https://pitchbook.com/profiles/company/1234-56)
        
    Returns:
        Dictionary containing:
        {
            "company_name": str,
            "description": str,
            "website": str,
            "headquarters": str,
            "industry": str,
            "employees": str,
            "revenue": str,
            "founded_year": str,
            "status": str,  # Private/Public
            "latest_deal_type": str,
            "total_raised": str,
            "funding_rounds": list[dict],  # [{date, round_type, amount, status}, ...]
            "investors": list[str],
            "competitors": list[str],
            "pitchbook_url": str
        }
    """
    print(f"\n[PITCHBOOK] 🔄 Step 2: Scraping profile page...")
    print(f"[PITCHBOOK] 📄 URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.duckduckgo.com/',
        }
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            
            print(f"[PITCHBOOK] 📥 Response status: {response.status_code}")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Initialize data structure
            data = {
                "company_name": None,
                "description": None,
                "website": None,
                "headquarters": None,
                "industry": None,
                "employees": None,
                "revenue": None,
                "founded_year": None,
                "status": None,
                "latest_deal_type": None,
                "total_raised": None,
                "funding_rounds": [],
                "investors": [],
                "competitors": [],
                "pitchbook_url": url
            }
            
            # Extract company name from the "Stripe Overview" heading
            overview_heading = soup.find('h2', class_='h2-small-mobile')
            if overview_heading:
                # Get the span with M-0 class inside the h2
                company_span = overview_heading.find('span', class_='M-0')
                if company_span:
                    data["company_name"] = company_span.get_text(strip=True)
                    print(f"[PITCHBOOK] ✓ Company: {data['company_name']}")
            
            # Extract data from Quick Facts (pp-overview-item divs)
            overview_items = soup.find_all('div', attrs={'data-pp-overview-item': ''})
            print(f"[PITCHBOOK] 🔍 Found {len(overview_items)} overview items")
            
            for item in overview_items:
                # Find the label (text-small class)
                label_tag = item.find('li', class_='text-small')
                # Find the value (pp-overview-item__title class)
                value_tag = item.find('span', class_='pp-overview-item__title')
                
                if label_tag and value_tag:
                    label = label_tag.get_text(strip=True).lower()
                    value = value_tag.get_text(strip=True)
                    
                    if 'year founded' in label:
                        data["founded_year"] = value
                        print(f"[PITCHBOOK]   • Founded: {value}")
                    elif 'status' in label:
                        data["status"] = value
                        print(f"[PITCHBOOK]   • Status: {value}")
                    elif 'employees' in label:
                        data["employees"] = value
                        print(f"[PITCHBOOK]   • Employees: {value}")
                    elif 'latest deal type' in label:
                        data["latest_deal_type"] = value
                        print(f"[PITCHBOOK]   • Latest Deal: {value}")
                    elif 'investors' in label:
                        print(f"[PITCHBOOK]   • Investor Count: {value}")
            
            # Extract description from pp-description_text
            desc_tag = soup.find('p', class_='pp-description_text')
            if desc_tag:
                data["description"] = desc_tag.get_text(strip=True)
                print(f"[PITCHBOOK] ✓ Description: {data['description'][:100]}...")
            
            # Extract contact information from pp-contact-info
            contact_info = soup.find('div', class_='pp-contact-info')
            if contact_info:
                # Website
                website_link = contact_info.find('a', href=re.compile(r'http'))
                if website_link:
                    data["website"] = website_link.get_text(strip=True)
                    print(f"[PITCHBOOK] ✓ Website: {data['website']}")
                
                # Primary Industry
                industry_div = contact_info.find('div', string=re.compile('Primary Industry', re.I))
                if industry_div:
                    industry_value = industry_div.find_next_sibling('div')
                    if industry_value:
                        data["industry"] = industry_value.get_text(strip=True)
                        print(f"[PITCHBOOK] ✓ Industry: {data['industry']}")
                
                # Corporate Office (headquarters)
                office_heading = contact_info.find('h5', string=re.compile('Corporate Office', re.I))
                if office_heading:
                    office_list = office_heading.find_next('ul')
                    if office_list:
                        address_parts = [li.get_text(strip=True) for li in office_list.find_all('li')]
                        data["headquarters"] = ', '.join(address_parts)
                        print(f"[PITCHBOOK] ✓ HQ: {data['headquarters']}")
            
            # Extract funding rounds from Valuation & Funding table
            funding_table = soup.find('table')
            if funding_table:
                tbody = funding_table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    print(f"[PITCHBOOK] 💰 Found {len(rows)} funding rounds")
                    
                    for row in rows[:10]:  # Limit to 10 most recent
                        cells = row.find_all('td')
                        if len(cells) >= 6:
                            round_data = {
                                "deal_type": cells[0].get_text(strip=True),
                                "date": cells[1].get_text(strip=True),
                                "amount": cells[2].get_text(strip=True) if not cells[2].find('span', class_='data-table__gray-box') else None,
                                "raised_to_date": cells[3].get_text(strip=True) if not cells[3].find('span', class_='data-table__gray-box') else None,
                                "post_val": cells[4].get_text(strip=True) if not cells[4].find('span', class_='data-table__gray-box') else None,
                                "status": cells[5].get_text(strip=True)
                            }
                            data["funding_rounds"].append(round_data)
                    
                    # Get the most recent "Raised to Date" value that's visible
                    for round in data["funding_rounds"]:
                        if round["raised_to_date"] and round["raised_to_date"] != "":
                            data["total_raised"] = round["raised_to_date"]
                            print(f"[PITCHBOOK] ✓ Total Raised: {data['total_raised']}")
                            break
            
            # Extract investors from FAQs section
            faqs_section = soup.find('section', id='faqs')
            if faqs_section:
                # Find the FAQ about investors
                investor_question = faqs_section.find('h3', string=re.compile("Who are.*investors", re.I))
                if investor_question:
                    investor_answer = investor_question.find_next('p')
                    if investor_answer:
                        # Extract investor names from links
                        investor_links = investor_answer.find_all('a', href=re.compile(r'/profiles/investor/'))
                        data["investors"] = [link.get_text(strip=True) for link in investor_links]
                        print(f"[PITCHBOOK] ✓ Investors: {len(data['investors'])} found")
            
            # Extract competitors from FAQs section
            if faqs_section:
                competitor_question = faqs_section.find('h3', string=re.compile("Who are.*competitors", re.I))
                if competitor_question:
                    competitor_answer = competitor_question.find_next('p')
                    if competitor_answer:
                        # Extract competitor names from links
                        competitor_links = competitor_answer.find_all('a', href=re.compile(r'/profiles/company/'))
                        data["competitors"] = [link.get_text(strip=True) for link in competitor_links]
                        print(f"[PITCHBOOK] ✓ Competitors: {len(data['competitors'])} found")
            
            # Log summary
            print(f"\n[PITCHBOOK] 📊 Extraction Summary:")
            print(f"  • Company Name: {'✓' if data['company_name'] else '✗'}")
            print(f"  • Description: {'✓' if data['description'] else '✗'}")
            print(f"  • Website: {'✓' if data['website'] else '✗'}")
            print(f"  • Headquarters: {'✓' if data['headquarters'] else '✗'}")
            print(f"  • Industry: {'✓' if data['industry'] else '✗'}")
            print(f"  • Founded: {'✓' if data['founded_year'] else '✗'}")
            print(f"  • Status: {'✓' if data['status'] else '✗'}")
            print(f"  • Employees: {'✓' if data['employees'] else '✗'}")
            print(f"  • Latest Deal: {'✓' if data['latest_deal_type'] else '✗'}")
            print(f"  • Total Raised: {'✓' if data['total_raised'] else '✗'}")
            print(f"  • Funding Rounds: {len(data['funding_rounds'])}")
            print(f"  • Investors: {len(data['investors'])}")
            print(f"  • Competitors: {len(data['competitors'])}")
            
            return data
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print(f"[PITCHBOOK] ✗ Access denied (403) - PitchBook may be blocking scrapers")
        elif e.response.status_code == 404:
            print(f"[PITCHBOOK] ✗ Profile not found (404)")
        else:
            print(f"[PITCHBOOK] ✗ HTTP error: {e.response.status_code}")
        logger.error(f"HTTP error scraping PitchBook: {e}")
        return None
    except Exception as e:
        print(f"[PITCHBOOK] ✗ Error scraping profile: {e}")
        logger.error(f"Error scraping PitchBook profile: {e}")
        import traceback
        traceback.print_exc()
        return None


async def get_company_data(company_name: str) -> dict | None:
    """
    Get comprehensive company data from PitchBook.
    Searches for the company and scrapes the profile page.
    
    Args:
        company_name: Company name to search for
        
    Returns:
        Dictionary with company data or None if not found
    """
    print(f"\n{'='*70}")
    print(f"[PITCHBOOK] 🚀 Getting data for: {company_name}")
    print(f"{'='*70}")
    
    # Step 1: Search for PitchBook URL
    url = await search_pitchbook_url(company_name)
    
    if not url:
        logger.warning(f"No PitchBook URL found for: {company_name}")
        print(f"\n[PITCHBOOK] ❌ No PitchBook profile URL found")
        print(f"{'='*70}\n")
        return {
            "error": "Company not found on PitchBook",
            "company_name": company_name,
            "suggestion": "Company may be private or not tracked by PitchBook"
        }
    
    # Log the URL we found
    print(f"\n[PITCHBOOK] ✅ SUCCESS! Got PitchBook URL: {url}")
    print(f"[PITCHBOOK] 🔄 Now proceeding to scrape the profile page...")
    print(f"{'='*70}\n")
    
    logger.info(f"Found PitchBook URL, now scraping: {url}")
    
    # Step 2: Scrape the profile page
    data = await scrape_pitchbook_profile(url)
    
    if not data:
        logger.error(f"Failed to scrape data from PitchBook profile: {url}")
        print(f"\n[PITCHBOOK] ❌ Failed to scrape profile")
        print(f"{'='*70}\n")
        return {
            "error": "Failed to extract data from PitchBook",
            "company_name": company_name,
            "pitchbook_url": url
        }
    
    logger.info(f"Successfully scraped PitchBook data for: {data.get('company_name', company_name)}")
    print(f"\n{'='*70}")
    print(f"[PITCHBOOK] ✅ Successfully scraped data for: {data.get('company_name', company_name)}")
    print(f"{'='*70}\n")
    return data


# Singleton instance for compatibility
class PitchBookScraper:
    """PitchBook scraper service."""
    
    async def scrape_company(self, company_name: str) -> dict:
        """
        Scrape company data from PitchBook.
        
        Args:
            company_name: Company name to search for
            
        Returns:
            Dictionary with company data
        """
        return await get_company_data(company_name)


# Create singleton instance
pitchbook_scraper = PitchBookScraper()
