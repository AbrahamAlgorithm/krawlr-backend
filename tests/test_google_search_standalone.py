"""
Standalone test script for Google Search scraper.
Tests founder, funding, competitor, and news searches.

Usage:
    python tests/test_google_search_standalone.py
    python tests/test_google_search_standalone.py "Stripe"
    python tests/test_google_search_standalone.py "Stripe" "OpenAI"
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.google_search_scraper import google_search_scraper


async def test_google_search(company_name: str):
    """Test all Google search functions for a company."""
    print(f"\n{'='*70}")
    print(f"🧪 TESTING GOOGLE SEARCH SCRAPER FOR: {company_name}")
    print(f"{'='*70}\n")
    
    results = {}
    
    # Test 1: Search for founders
    print(f"👥 TEST 1: Searching for founders and executives...")
    founders = await google_search_scraper.search_founders(company_name)
    results['founders'] = founders
    print(f"   ✅ Found {len(founders)} founder/executive profiles\n")
    if founders:
        for i, founder in enumerate(founders[:5], 1):
            print(f"   {i}. {founder.get('name', 'N/A')}")
            print(f"      Title: {founder.get('title', 'N/A')}")
            print(f"      LinkedIn: {founder.get('linkedin_url', 'N/A')}")
    else:
        print(f"   ⚠️  No founders found")
    
    # Test 2: Search for funding
    print(f"\n💰 TEST 2: Searching for funding information...")
    funding = await google_search_scraper.search_funding(company_name)
    results['funding'] = funding
    print(f"   ✅ Found {len(funding)} funding mentions\n")
    if funding:
        for i, item in enumerate(funding[:5], 1):
            print(f"   {i}. {item.get('title', 'N/A')}")
            print(f"      Amount: {item.get('amount', 'N/A')}")
            print(f"      Source: {item.get('source', 'N/A')}")
            print(f"      URL: {item.get('url', 'N/A')}")
    else:
        print(f"   ⚠️  No funding information found")
    
    # Test 3: Search for competitors
    print(f"\n🏢 TEST 3: Searching for competitors...")
    # Need a domain for competitor search
    domain = f"{company_name.lower().replace(' ', '')}.com"
    competitors = await google_search_scraper.search_competitors(domain)
    results['competitors'] = competitors
    print(f"   ✅ Found {len(competitors)} competitors\n")
    if competitors:
        for i, competitor in enumerate(competitors[:10], 1):
            print(f"   {i}. {competitor.get('name', 'N/A')}")
            print(f"      Domain: {competitor.get('domain', 'N/A')}")
            print(f"      Description: {competitor.get('description', 'N/A')[:80]}...")
    else:
        print(f"   ⚠️  No competitors found")
    
    # Test 4: Search for news
    print(f"\n📰 TEST 4: Searching for recent news...")
    news = await google_search_scraper.search_news(company_name, max_results=10)
    results['news'] = news
    print(f"   ✅ Found {len(news)} news articles\n")
    if news:
        for i, article in enumerate(news[:5], 1):
            print(f"   {i}. {article.get('title', 'N/A')}")
            print(f"      Source: {article.get('source', 'N/A')}")
            print(f"      Date: {article.get('date', 'N/A')}")
            print(f"      URL: {article.get('url', 'N/A')}")
            print(f"      Snippet: {article.get('snippet', 'N/A')[:100]}...")
            print()
    else:
        print(f"   ⚠️  No news found")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📊 SUMMARY FOR {company_name}")
    print(f"{'='*70}")
    print(f"   👥 Founders/Executives: {len(results['founders'])}")
    print(f"   💰 Funding Mentions: {len(results['funding'])}")
    print(f"   🏢 Competitors: {len(results['competitors'])}")
    print(f"   📰 News Articles: {len(results['news'])}")
    
    # Save detailed output
    safe_name = company_name.lower().replace(' ', '_')
    output_file = f"google_search_output_{safe_name}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Full data saved to: {output_file}")
    print(f"\n{'='*70}")
    print(f"✅ TEST COMPLETED FOR {company_name}")
    print(f"{'='*70}\n")


async def main():
    """Main test function."""
    print("\n" + "="*70)
    print("🚀 GOOGLE SEARCH SCRAPER - STANDALONE TEST")
    print("="*70)
    print("\nℹ️  NOTE: Google may block requests if rate limit is exceeded.")
    print("   Results depend on Google's search results at the time of testing.")
    
    # Get company names from command line or use defaults
    if len(sys.argv) > 1:
        companies = sys.argv[1:]
    else:
        # Default test companies
        companies = ['Stripe', 'OpenAI']
        print(f"\nℹ️  No company names provided. Testing with defaults:")
        for company in companies:
            print(f"   - {company}")
        print(f"\n   Usage: python tests/test_google_search_standalone.py \"Company Name\" ...")
    
    # Test each company
    for company in companies:
        try:
            await test_google_search(company)
            await asyncio.sleep(3)  # Rate limiting between companies
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error testing {company}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
