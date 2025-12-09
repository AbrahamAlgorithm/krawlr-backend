"""
Standalone test script for News & Press Scraper.

Tests the news and press release scraping functionality without requiring
the full application setup.

Usage:
    python3 tests/test_news_press_standalone.py "Stripe"
    python3 tests/test_news_press_standalone.py "Apple" 25
    python3 tests/test_news_press_standalone.py "OpenAI" 15 "https://openai.com"
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.scraping.news import scrape_news_and_press


def safe_filename(company_name: str) -> str:
    """Convert company name to safe filename."""
    # Remove special characters and spaces
    safe_name = ''.join(c if c.isalnum() else '_' for c in company_name.lower())
    # Remove multiple underscores
    safe_name = '_'.join(filter(None, safe_name.split('_')))
    return safe_name


async def main():
    """Main test function."""
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python3 tests/test_news_press_standalone.py <company_name> [max_articles] [website_url]")
        print("Example: python3 tests/test_news_press_standalone.py 'Stripe' 20 'https://stripe.com'")
        sys.exit(1)
    
    company_name = sys.argv[1]
    max_articles = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    website_url = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"\n{'='*70}")
    print(f"NEWS & PRESS SCRAPER - STANDALONE TEST")
    print(f"{'='*70}")
    print(f"Company: {company_name}")
    print(f"Max Articles: {max_articles}")
    if website_url:
        print(f"Website: {website_url}")
    print(f"{'='*70}\n")
    
    # Run scraper
    result = await scrape_news_and_press(company_name, website_url, max_articles)
    
    # Print results
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Total Articles Found: {result['total_articles']}")
    print(f"\nBy Source:")
    for source, count in result['sources'].items():
        print(f"  - {source.replace('_', ' ').title()}: {count}")
    
    if result.get('date_range'):
        print(f"\nDate Range:")
        print(f"  Oldest: {result['date_range']['oldest']}")
        print(f"  Newest: {result['date_range']['newest']}")
    
    # Show sample articles
    if result['articles']:
        print(f"\n{'='*70}")
        print(f"SAMPLE ARTICLES (Top 5)")
        print(f"{'='*70}")
        
        for i, article in enumerate(result['articles'][:5], 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Source: {article['source']}")
            print(f"   Type: {article['article_type']}")
            print(f"   Date: {article['date_string']}")
            print(f"   Credibility: {article['credibility_score']}/10")
            print(f"   URL: {article['url']}")
            if article.get('description'):
                desc = article['description'][:150] + '...' if len(article['description']) > 150 else article['description']
                print(f"   Description: {desc}")
    
    # Save full results to JSON
    safe_name = safe_filename(company_name)
    output_file = f"news_press_{safe_name}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"✅ Full results saved to: {output_file}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    asyncio.run(main())
