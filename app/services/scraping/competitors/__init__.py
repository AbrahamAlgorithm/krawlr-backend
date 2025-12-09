"""
Competitors & Alternatives Scraper Module

Public API for competitor and alternative company discovery.
"""

from .competitors_scraper import CompetitorsScraper


async def scrape_competitors(company_name: str, website_url: str = None, max_competitors: int = 20) -> dict:
    """
    Scrape competitors and alternative companies.
    
    Args:
        company_name: Company name to search for
        website_url: Optional company website URL (for related: search)
        max_competitors: Maximum number of competitors to retrieve (default: 20)
    
    Returns:
        Dictionary containing competitors from multiple sources
    """
    scraper = CompetitorsScraper()
    return await scraper.scrape_competitors(company_name, website_url, max_competitors)


__all__ = ['scrape_competitors', 'CompetitorsScraper']
