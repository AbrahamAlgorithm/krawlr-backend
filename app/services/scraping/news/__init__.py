"""
News & Press Scraper Module

Public API for news and press release scraping.
"""

from .news_press_scraper import NewsPresscraper


async def scrape_news_and_press(company_name: str, website_url: str = None, max_articles: int = 20) -> dict:
    """
    Scrape recent news and press releases for a company.
    
    Args:
        company_name: Company name to search for
        website_url: Optional company website URL (for press releases)
        max_articles: Maximum number of articles to retrieve (default: 20)
    
    Returns:
        Dictionary containing news articles and press releases
    """
    scraper = NewsPresscraper()
    return await scraper.scrape_news_and_press(company_name, website_url, max_articles)


__all__ = ['scrape_news_and_press', 'NewsPresscraper']
