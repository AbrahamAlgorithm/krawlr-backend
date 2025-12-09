"""
Standalone test for Founders & Leadership Scraper

Tests comprehensive team scraping from multiple sources:
- Wikipedia
- Google Search
- Crunchbase
- Company website team pages
- LinkedIn

Usage:
    python3 tests/test_founders_standalone.py "COMPANY_NAME" [max_people] [website_url]
    
Examples:
    python3 tests/test_founders_standalone.py "Stripe"
    python3 tests/test_founders_standalone.py "Stripe" 20 "https://stripe.com"
    python3 tests/test_founders_standalone.py "Microsoft" 15
"""

import sys
import asyncio
import json
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.scraping.founders import scrape_founders


async def test_founders_scraper(company_name: str, max_people: int = 20, website_url: str = None):
    """Test the founders & leadership scraper."""
    
    print(f"\n{'='*70}")
    print(f"FOUNDERS & LEADERSHIP SCRAPER - STANDALONE TEST")
    print(f"{'='*70}")
    print(f"Company: {company_name}")
    print(f"Max People: {max_people}")
    if website_url:
        print(f"Website: {website_url}")
    print(f"{'='*70}\n")
    
    try:
        # Scrape founders
        data = await scrape_founders(company_name, website_url, max_people)
        
        # Print results
        print_results(data, company_name)
        
        # Save to JSON
        save_results(data, company_name)
        
        return data
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def print_results(data: dict, company_name: str):
    """Print scraping results in a formatted way."""
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"Total People Found: {data['total_count']}")
    
    print(f"\nBy Source:")
    for source, count in data['source_counts'].items():
        print(f"  - {source.title()}: {count}")
    
    print(f"\nBy Category:")
    print(f"  - Founders: {len(data['founders'])}")
    print(f"  - Executives: {len(data['executives'])}")
    print(f"  - Leadership: {len(data['leadership'])}")
    print(f"  - Board: {len(data['board'])}")
    
    # Print founders
    if data['founders']:
        print(f"\n{'='*70}")
        print(f"FOUNDERS ({len(data['founders'])})")
        print(f"{'='*70}\n")
        
        for i, person in enumerate(data['founders'], 1):
            sources = person.get('sources', [person['source']])
            print(f"{i}. {person['name']}")
            print(f"   Role: {person['role']}")
            print(f"   Sources: {', '.join(sources)} ({len(sources)} source(s))")
            if person.get('url'):
                print(f"   URL: {person['url']}")
            print()
    
    # Print executives
    if data['executives']:
        print(f"\n{'='*70}")
        print(f"EXECUTIVES ({len(data['executives'])})")
        print(f"{'='*70}\n")
        
        for i, person in enumerate(data['executives'], 1):
            sources = person.get('sources', [person['source']])
            print(f"{i}. {person['name']}")
            print(f"   Role: {person['role']}")
            print(f"   Sources: {', '.join(sources)} ({len(sources)} source(s))")
            if person.get('url'):
                print(f"   URL: {person['url']}")
            print()
    
    # Print leadership (first 5)
    if data['leadership']:
        print(f"\n{'='*70}")
        print(f"LEADERSHIP TEAM (Showing first 5 of {len(data['leadership'])})")
        print(f"{'='*70}\n")
        
        for i, person in enumerate(data['leadership'][:5], 1):
            sources = person.get('sources', [person['source']])
            print(f"{i}. {person['name']}")
            print(f"   Role: {person['role']}")
            print(f"   Sources: {', '.join(sources)} ({len(sources)} source(s))")
            print()
    
    # Print board (first 5)
    if data['board']:
        print(f"\n{'='*70}")
        print(f"BOARD MEMBERS (Showing first 5 of {len(data['board'])})")
        print(f"{'='*70}\n")
        
        for i, person in enumerate(data['board'][:5], 1):
            sources = person.get('sources', [person['source']])
            print(f"{i}. {person['name']}")
            print(f"   Role: {person['role']}")
            print(f"   Sources: {', '.join(sources)} ({len(sources)} source(s))")
            print()


def save_results(data: dict, company_name: str):
    """Save results to JSON file."""
    
    # Sanitize company name for filename
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', company_name.lower().replace(' ', '_'))
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')
    
    output_filename = f"founders_{safe_name}.json"
    output_path = project_root / output_filename
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ Full results saved to: {output_filename}")
    print(f"{'='*70}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 tests/test_founders_standalone.py \"COMPANY_NAME\" [max_people] [website_url]")
        print("\nExamples:")
        print("  python3 tests/test_founders_standalone.py \"Stripe\"")
        print("  python3 tests/test_founders_standalone.py \"Stripe\" 20 \"https://stripe.com\"")
        print("  python3 tests/test_founders_standalone.py \"Microsoft\" 15")
        sys.exit(1)
    
    company_name = sys.argv[1]
    max_people = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    website_url = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Run the test
    asyncio.run(test_founders_scraper(company_name, max_people, website_url))


if __name__ == "__main__":
    main()
