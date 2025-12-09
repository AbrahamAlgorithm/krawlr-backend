"""
Standalone test script for Competitors & Alternatives Scraper.

Tests the competitor discovery functionality from multiple sources.

Usage:
    python3 tests/test_competitors_standalone.py "Stripe"
    python3 tests/test_competitors_standalone.py "Stripe" 25
    python3 tests/test_competitors_standalone.py "Stripe" 20 "https://stripe.com"
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.scraping.competitors import scrape_competitors


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
        print("Usage: python3 tests/test_competitors_standalone.py <company_name> [max_competitors] [website_url]")
        print("Example: python3 tests/test_competitors_standalone.py 'Stripe' 20 'https://stripe.com'")
        sys.exit(1)
    
    company_name = sys.argv[1]
    max_competitors = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    website_url = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"\n{'='*70}")
    print(f"COMPETITORS & ALTERNATIVES SCRAPER - STANDALONE TEST")
    print(f"{'='*70}")
    print(f"Company: {company_name}")
    print(f"Max Competitors: {max_competitors}")
    if website_url:
        print(f"Website: {website_url}")
    print(f"{'='*70}\n")
    
    # Run scraper
    result = await scrape_competitors(company_name, website_url, max_competitors)
    
    # Print results
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Total Competitors Found: {result['total_competitors']}")
    print(f"\nBy Source:")
    for source, count in result['sources'].items():
        print(f"  - {source.replace('_', ' ').title()}: {count}")
    
    # Show top competitors
    if result['competitors']:
        print(f"\n{'='*70}")
        print(f"TOP COMPETITORS (Sorted by Relevance)")
        print(f"{'='*70}")
        
        for i, comp in enumerate(result['competitors'][:10], 1):
            print(f"\n{i}. {comp['name']}")
            if comp.get('domain'):
                print(f"   Domain: {comp['domain']}")
            print(f"   Similarity Score: {comp['similarity_score']}/100")
            print(f"   Found in {comp['source_count']} source(s): {', '.join(comp.get('sources', []))}")
            if comp.get('description'):
                desc = comp['description'][:150] + '...' if len(comp['description']) > 150 else comp['description']
                print(f"   Description: {desc}")
    
    # Save full results to JSON
    safe_name = safe_filename(company_name)
    output_file = f"competitors_{safe_name}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"✅ Full results saved to: {output_file}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    asyncio.run(main())
