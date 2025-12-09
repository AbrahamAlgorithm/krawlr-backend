"""
Founders & Leadership Scraper

Public API for scraping company founders, executives, and leadership team information.
"""

from .founders_scraper import FoundersScraper

async def scrape_founders(
    company_name: str,
    website_url: str = None,
    max_people: int = 20
) -> dict:
    """
    Scrape founders and leadership team information.
    
    Args:
        company_name: Company name to search for
        website_url: Optional company website URL
        max_people: Maximum number of people to return (default: 20)
    
    Returns:
        Dictionary containing:
        - founders: List of company founders
        - executives: List of C-level executives
        - leadership: Other leadership team members
        - board: Board members
        - total_count: Total people found
        - sources_used: List of data sources
        - metadata: Scraping metadata
    """
    scraper = FoundersScraper()
    return await scraper.scrape_founders(company_name, website_url, max_people)


__all__ = ['scrape_founders', 'FoundersScraper']
