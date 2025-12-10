"""
Test script for Unified Orchestrator
Tests the complete company intelligence gathering pipeline
"""
import asyncio
import json
import sys
from app.services.scraping.unified_orchestrator import UnifiedOrchestrator

async def test_unified_orchestrator(url: str):
    """Test the unified orchestrator with a company URL"""
    
    print("=" * 80)
    print("🧪 TESTING UNIFIED ORCHESTRATOR")
    print("=" * 80)
    print(f"📥 Input URL: {url}")
    print("=" * 80)
    print()
    
    orchestrator = UnifiedOrchestrator()
    
    try:
        # Run the orchestrator
        result = await orchestrator.get_complete_company_intelligence(url)
        
        # Save to file
        company_name = result.get('company', {}).get('name', 'unknown')
        filename = f"{company_name.lower().replace(' ', '_')}_unified_output.json"
        
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "=" * 80)
        print("✅ UNIFIED ORCHESTRATOR COMPLETED")
        print("=" * 80)
        
        company = result.get('company', {})
        financials = result.get('financials', {})
        funding = result.get('funding', {})
        people = result.get('people', {})
        competitors = result.get('competitors', [])
        products = result.get('products', [])
        news = result.get('news', {})
        
        print(f"\n🏢 COMPANY:")
        print(f"   Name: {company.get('name')}")
        print(f"   Status: {company.get('status')}")
        print(f"   Industry: {company.get('industry')}")
        print(f"   Founded: {company.get('founded_year')}")
        print(f"   Employees: {company.get('employee_count')}")
        print(f"   HQ: {company.get('headquarters')}")
        
        print(f"\n💰 FINANCIALS:")
        print(f"   Public Company: {financials.get('public_company')}")
        print(f"   Ticker: {financials.get('ticker') or 'N/A'}")
        print(f"   Shares Outstanding: {financials.get('shares_outstanding') or 'N/A'}")
        print(f"   Public Float: {financials.get('public_float') or 'N/A'}")
        print(f"   Financial Statements: {bool(financials.get('statements'))}")
        print(f"   Latest Filings: {len(financials.get('latest_filings', []))}")
        print(f"   Insiders: {len(financials.get('insiders', []))}")
        
        print(f"\n🚀 FUNDING:")
        print(f"   Total Raised: ${funding.get('total_raised_usd'):,.0f}" if funding.get('total_raised_usd') else "   Total Raised: N/A")
        print(f"   Round Count: {funding.get('round_count')}")
        print(f"   Latest Rounds: {len(funding.get('latest_rounds', []))}")
        print(f"   Investors: {len(funding.get('investors', []))}")
        
        print(f"\n👥 PEOPLE:")
        print(f"   Founders: {len(people.get('founders', []))}")
        print(f"   Executives: {len(people.get('executives', []))}")
        print(f"   Board Members: {len(people.get('board_members', []))}")
        print(f"   Key People: {len(people.get('key_people', []))}")
        
        print(f"\n📦 PRODUCTS:")
        print(f"   Total: {len(products)}")
        for i, product in enumerate(products[:3], 1):
            print(f"   {i}. {product.get('name')}")
        
        print(f"\n🏆 COMPETITORS:")
        print(f"   Total: {len(competitors)}")
        for i, comp in enumerate(competitors[:5], 1):
            print(f"   {i}. {comp.get('name')} - {comp.get('website', 'N/A')}")
        
        print(f"\n📰 NEWS:")
        print(f"   Articles: {len(news.get('articles', []))}")
        print(f"   Press Releases: {len(news.get('press_releases', []))}")
        
        print(f"\n📊 METADATA:")
        metadata = result.get('_metadata', {})
        print(f"   Scrape ID: {metadata.get('scrape_id')}")
        print(f"   Duration: {metadata.get('duration_seconds', 0):.2f}s")
        print(f"   Quality Score: {metadata.get('quality_score', 0):.1f}/100")
        print(f"   Success Rate: {metadata.get('scraper_success_rate', 0):.0%}")
        
        print(f"\n📁 Saved to: {filename}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # Default test URL
        url = "https://stripe.com"
    
    asyncio.run(test_unified_orchestrator(url))
