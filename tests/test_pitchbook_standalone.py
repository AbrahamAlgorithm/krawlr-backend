"""
Standalone test script for PitchBook scraper.
Tests company data extraction from PitchBook profiles.

Usage:
    python tests/test_pitchbook_standalone.py
    python tests/test_pitchbook_standalone.py "Stripe"
    python tests/test_pitchbook_standalone.py "OpenAI" "Anthropic" "Databricks"
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.financial.pitchbook_scraper import (
    get_company_data,
    search_pitchbook_url,
    scrape_pitchbook_profile
)


async def test_pitchbook_search(company_name: str):
    """Test PitchBook URL search."""
    print(f"\n{'='*70}")
    print(f"🔍 TESTING PITCHBOOK URL SEARCH")
    print(f"{'='*70}\n")
    print(f"Company: {company_name}\n")
    
    url = await search_pitchbook_url(company_name)
    
    if url:
        print(f"✅ PitchBook URL found: {url}\n")
        return url
    else:
        print(f"❌ No PitchBook profile found\n")
        return None


async def test_pitchbook_scraper(company_name: str):
    """Test PitchBook scraper with a specific company."""
    print(f"\n{'='*70}")
    print(f"🧪 TESTING PITCHBOOK SCRAPER FOR: {company_name}")
    print(f"{'='*70}\n")
    
    # Get company data
    print(f"📊 Fetching PitchBook data for {company_name}...\n")
    result = await get_company_data(company_name)
    
    if not result or result.get('error'):
        print(f"❌ {result.get('error', 'No data found')}\n")
        if result.get('suggestion'):
            print(f"💡 {result['suggestion']}\n")
        return
    
    print(f"\n{'='*70}")
    print(f"📈 RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    # Basic company info
    print(f"🏢 Company Information:")
    print(f"   - Name: {result.get('company_name', 'N/A')}")
    print(f"   - Website: {result.get('website', 'N/A')}")
    print(f"   - PitchBook URL: {result.get('pitchbook_url', 'N/A')}")
    
    # Description
    description = result.get('description')
    if description:
        print(f"\n📝 Description:")
        print(f"   {description[:200]}{'...' if len(description) > 200 else ''}")
    
    # Company details
    print(f"\n🏭 Company Details:")
    print(f"   - Industry: {result.get('industry', 'N/A')}")
    print(f"   - Headquarters: {result.get('headquarters', 'N/A')}")
    print(f"   - Founded: {result.get('founded_year', 'N/A')}")
    print(f"   - Status: {result.get('status', 'N/A')}")
    print(f"   - Employees: {result.get('employees', 'N/A')}")
    print(f"   - Revenue: {result.get('revenue', 'N/A')}")
    
    # Funding information
    total_raised = result.get('total_raised')
    latest_deal = result.get('latest_deal_type')
    funding_rounds = result.get('funding_rounds', [])
    
    print(f"\n💰 Funding Information:")
    print(f"   - Total Raised: {total_raised if total_raised else 'N/A'}")
    print(f"   - Latest Deal: {latest_deal if latest_deal else 'N/A'}")
    print(f"   - Funding Rounds: {len(funding_rounds)}")
    
    if funding_rounds:
        print(f"\n   Funding Rounds Details:")
        for i, round_data in enumerate(funding_rounds[:5], 1):
            print(f"   {i}. Deal Type: {round_data.get('deal_type', 'N/A')}")
            print(f"      Date: {round_data.get('date', 'N/A')}")
            print(f"      Amount: {round_data.get('amount', 'N/A')}")
            print(f"      Raised to Date: {round_data.get('raised_to_date', 'N/A')}")
            print(f"      Post-Val: {round_data.get('post_val', 'N/A')}")
    
    # Investors
    investors = result.get('investors', [])
    print(f"\n🤝 Investors: {len(investors)}")
    if investors:
        for i, investor in enumerate(investors[:10], 1):
            print(f"   {i}. {investor}")
        if len(investors) > 10:
            print(f"   ... and {len(investors) - 10} more")
    
    # Competitors
    competitors = result.get('competitors', [])
    
    print(f"\n🏆 Competitors: {len(competitors)}")
    if competitors:
        for i, competitor in enumerate(competitors[:10], 1):
            print(f"   {i}. {competitor}")
        if len(competitors) > 10:
            print(f"   ... and {len(competitors) - 10} more")
    
    # Save detailed output
    safe_name = company_name.lower().replace(' ', '_')
    output_file = f"pitchbook_output_{safe_name}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n💾 Full data saved to: {output_file}")
    print(f"\n{'='*70}")
    print(f"✅ TEST COMPLETED FOR {company_name}")
    print(f"{'='*70}\n")


async def main():
    """Main test function."""
    print("\n" + "="*70)
    print("🚀 PITCHBOOK SCRAPER - STANDALONE TEST")
    print("="*70)
    print("\n⚠️  Note: PitchBook may block scraping requests.")
    print("   Results depend on PitchBook's anti-bot measures.")
    
    # Get company names from command line or use defaults
    if len(sys.argv) > 1:
        companies = sys.argv[1:]
    else:
        # Default test companies
        companies = ['Stripe', 'OpenAI', 'Anthropic']
        print(f"\nℹ️  No company names provided. Testing with defaults:")
        for company in companies:
            print(f"   - {company}")
        print(f"\n   Usage: python tests/test_pitchbook_standalone.py \"Company Name\" ...")
    
    # Test each company
    for company in companies:
        try:
            await test_pitchbook_scraper(company)
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
