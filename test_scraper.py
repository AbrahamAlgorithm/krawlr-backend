#!/usr/bin/env python3
"""
Test script for unified funding scraper.
Usage: python test_scraper.py <company_name_or_url>

Examples:
    python test_scraper.py "Walmart"
    python test_scraper.py "Apple Inc"
    python test_scraper.py "https://www.tesla.com"
    python test_scraper.py walmart.com
"""

import asyncio
import json
import sys
from urllib.parse import urlparse
from app.services.scraping.financial.funding_scraper import get_unified_funding_data


def extract_company_name(input_str: str) -> str:
    """
    Extract company name from URL or use input directly.
    
    Examples:
        "https://www.walmart.com" -> "Walmart"
        "walmart.com" -> "Walmart"
        "Walmart Inc" -> "Walmart Inc"
    """
    # Check if it looks like a URL
    if "://" in input_str or input_str.endswith((".com", ".org", ".net", ".io")):
        parsed = urlparse(input_str if "://" in input_str else f"https://{input_str}")
        domain = parsed.netloc or parsed.path
        # Remove www. and extract company name
        company = domain.replace("www.", "").split(".")[0]
        return company.capitalize()
    
    # Otherwise, use as-is
    return input_str


async def test_scraper(company_input: str):
    """Test the unified scraper with a company name or URL."""
    company_name = extract_company_name(company_input)
    
    print(f"\n{'='*70}")
    print(f"🧪 TESTING UNIFIED SCRAPER")
    print(f"{'='*70}")
    print(f"📥 Input: {company_input}")
    print(f"🏢 Company: {company_name}")
    print(f"{'='*70}\n")
    
    try:
        # Run the scraper
        result = await get_unified_funding_data(company_name)
        
        if result:
            # Save to file
            filename = f"{company_name.lower().replace(' ', '_')}_output.json"
            with open(filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            # Print summary
            print(f"\n{'='*70}")
            print(f"✅ SCRAPING RESULTS")
            print(f"{'='*70}")
            
            identity = result.get('identity', {})
            print(f"\n🏢 COMPANY IDENTITY:")
            print(f"   Name: {identity.get('name')}")
            print(f"   Ticker: {identity.get('ticker', 'N/A')}")
            print(f"   Industry: {identity.get('industry', 'N/A')}")
            print(f"   Status: {identity.get('status', 'N/A')}")
            print(f"   Founded: {identity.get('founded_year', 'N/A')}")
            print(f"   Employees: {identity.get('employees', 'N/A')}")
            print(f"   Website: {identity.get('website', 'N/A')}")
            
            if identity.get('description'):
                desc = identity['description'][:150] + "..." if len(identity['description']) > 150 else identity['description']
                print(f"   Description: {desc}")
            
            financials = result.get('financials', {})
            if financials.get('revenue') or len(financials.get('income_statement', [])) > 0:
                print(f"\n💰 FINANCIAL DATA:")
                print(f"   Fiscal Year: {financials.get('fiscal_year', 'N/A')}")
                print(f"   Revenue: {financials.get('revenue', 'N/A')}")
                print(f"   Net Income: {financials.get('net_income', 'N/A')}")
                print(f"   Cash Flow: {financials.get('cash_flow', 'N/A')}")
                print(f"   Statements: {len(financials.get('income_statement', []))} income, {len(financials.get('balance_sheet', []))} balance, {len(financials.get('cash_flow_statement', []))} cash flow")
            
            funding = result.get('funding', {})
            print(f"\n🚀 FUNDING DATA:")
            print(f"   Total Raised: {funding.get('total_raised', 'N/A')}")
            print(f"   Latest Deal: {funding.get('latest_deal_type', 'N/A')}")
            print(f"   Funding Rounds: {len(funding.get('funding_rounds', []))}")
            print(f"   Investors: {len(funding.get('investors', []))}")
            
            key_metrics = result.get('key_metrics', {})
            if key_metrics.get('shares_outstanding'):
                print(f"\n📈 KEY METRICS:")
                print(f"   Shares Outstanding: {key_metrics.get('shares_outstanding', 'N/A')}")
                print(f"   Public Float: {key_metrics.get('public_float', 'N/A')}")
            
            insiders = result.get('insiders', [])
            if insiders:
                print(f"\n👥 INSIDERS: {len(insiders)}")
                for insider in insiders[:3]:
                    print(f"   • {insider.get('insider', 'N/A')} - {insider.get('position', 'N/A')}")
            
            filings = result.get('latest_filings', [])
            if filings:
                print(f"\n📄 LATEST SEC FILINGS: {len(filings)}")
                for filing in filings[:3]:
                    print(f"   • {filing.get('form', 'N/A')} - {filing.get('filing_date', 'N/A')}")
            
            competitors = result.get('competitors', [])
            if competitors:
                print(f"\n🏆 COMPETITORS: {len(competitors)}")
                for comp in competitors[:3]:
                    print(f"\n   {comp.get('name', 'Unknown')}")
                    if comp.get('location'):
                        print(f"      📍 {comp['location']}")
                    if comp.get('website'):
                        print(f"      🌐 {comp['website']}")
                    if comp.get('description'):
                        desc = comp['description'][:100] + "..." if len(comp.get('description', '')) > 100 else comp.get('description', '')
                        print(f"      📝 {desc}")
            
            print(f"\n{'='*70}")
            print(f"✅ COMPLETED!")
            print(f"📁 Saved to: {filename}")
            print(f"{'='*70}\n")
            
        else:
            print(f"\n❌ No data returned from scraper")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_scraper.py <company_name_or_url>")
        print("\nExamples:")
        print("  python test_scraper.py 'Walmart'")
        print("  python test_scraper.py 'Apple Inc'")
        print("  python test_scraper.py 'https://www.tesla.com'")
        print("  python test_scraper.py walmart.com")
        sys.exit(1)
    
    company_input = sys.argv[1]
    asyncio.run(test_scraper(company_input))


if __name__ == "__main__":
    main()
