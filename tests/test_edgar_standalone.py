"""
Standalone test script for EDGAR scraper.
Tests the SEC EDGAR financial data extraction.

Usage:
    python tests/test_edgar_standalone.py
    python tests/test_edgar_standalone.py "Apple"
    python tests/test_edgar_standalone.py "Microsoft Corporation" "Tesla Inc"
    python tests/test_edgar_standalone.py AAPL TSLA --ticker
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.edgar_scraper import (
    get_company_financials,
    get_company_financials_by_name,
    resolve_company_ticker,
    get_company_insiders,
    prepare_revenue_chart_data
)


async def test_ticker_resolution(company_name: str):
    """Test ticker resolution from company name."""
    print(f"\n{'='*70}")
    print(f"🔍 TESTING TICKER RESOLUTION")
    print(f"{'='*70}\n")
    print(f"Company Name: {company_name}\n")
    
    ticker_info = await resolve_company_ticker(company_name)
    
    if not ticker_info:
        print(f"❌ Could not resolve ticker for: {company_name}\n")
        return None
    
    print(f"✅ TICKER RESOLVED:")
    print(f"   Ticker: {ticker_info['ticker']}")
    print(f"   Company: {ticker_info['company_name']}")
    print(f"   Exchange: {ticker_info['exchange']}")
    print(f"   Method: {ticker_info['method']}\n")
    
    return ticker_info['ticker']


async def test_edgar_scraper(input_value: str, is_ticker: bool = False):
    """Test EDGAR scraper with company name or ticker."""
    print(f"\n{'='*70}")
    print(f"🧪 TESTING EDGAR SCRAPER")
    print(f"{'='*70}\n")
    
    if is_ticker:
        print(f"Input Type: TICKER")
        print(f"Ticker: {input_value}\n")
        result = await get_company_financials(input_value)
        ticker = input_value
    else:
        print(f"Input Type: COMPANY NAME")
        print(f"Company: {input_value}\n")
        
        # First resolve the ticker
        ticker = await test_ticker_resolution(input_value)
        if not ticker:
            return
        
        # Then fetch financials
        print(f"{'='*70}")
        print(f"📊 FETCHING FINANCIAL DATA")
        print(f"{'='*70}\n")
        result = await get_company_financials(ticker)
    
    if not result:
        print(f"❌ No data found\n")
        return
    
    print(f"\n{'='*70}")
    print(f"📈 RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    # Basic company info
    print(f"🏢 Company: {result.get('name', 'N/A')}")
    print(f"🎫 Ticker: {result.get('ticker', 'N/A')}")
    print(f"🔢 CIK: {result.get('cik', 'N/A')}")
    print(f"🏭 SIC: {result.get('sic', 'N/A')}")
    print(f"📍 Address: {result.get('business_address', 'N/A')}")
    print(f"📊 Has Facts API Data: {result.get('has_facts', False)}")
    
    # Key metrics
    if result.get('shares_outstanding'):
        print(f"\n💹 Key Metrics:")
        print(f"   - Shares Outstanding: {result.get('shares_outstanding')}")
        print(f"   - Public Float: {result.get('public_float', 'N/A')}")
    
    # Financial statements
    print(f"\n📄 Financial Statements:")
    has_income = bool(result.get('income_statement_md'))
    has_balance = bool(result.get('balance_sheet_md'))
    has_cashflow = bool(result.get('cash_flow_md'))
    
    print(f"   - Income Statement: {'✅ Available' if has_income else '❌ Not Available'}")
    if has_income:
        periods = result.get('income_periods', [])
        print(f"     Periods: {len(periods)} years - {periods}")
        
    print(f"   - Balance Sheet: {'✅ Available' if has_balance else '❌ Not Available'}")
    if has_balance:
        periods = result.get('balance_periods', [])
        print(f"     Periods: {len(periods)} years - {periods}")
        
    print(f"   - Cash Flow: {'✅ Available' if has_cashflow else '❌ Not Available'}")
    if has_cashflow:
        periods = result.get('cashflow_periods', [])
        print(f"     Periods: {len(periods)} years - {periods}")
    
    # Latest filings
    filings = result.get('latest_filings', [])
    print(f"\n📁 Latest SEC Filings: {len(filings)}")
    for i, filing in enumerate(filings[:5], 1):
        print(f"   {i}. {filing['form']} - {filing['filing_date']}")
        print(f"      URL: {filing['url']}")
        content_len = len(filing.get('content', '')) if filing.get('content') else 0
        print(f"      Content: {content_len:,} characters")
    
    # Chart data
    if has_income:
        print(f"\n📊 Testing Chart Data Preparation...")
        chart_data = prepare_revenue_chart_data(result)
        if chart_data:
            print(f"   ✅ Chart data prepared successfully")
            print(f"   Periods: {chart_data['labels']}")
            print(f"   Revenue (billions): {chart_data['revenue']}")
            if any(chart_data['gross_profit']):
                print(f"   Gross Profit (billions): {chart_data['gross_profit']}")
            if any(chart_data['net_income']):
                print(f"   Net Income (billions): {chart_data['net_income']}")
    
    # Test insider data
    print(f"\n👥 Testing Insider Data Retrieval...")
    insiders = await get_company_insiders(ticker)
    if insiders:
        print(f"   ✅ Found {len(insiders)} insiders from Form 4 filings")
        print(f"\n   Top Executives:")
        for insider in insiders[:10]:
            print(f"      • {insider['insider']} - {insider['position']}")
    else:
        print(f"   ⚠️  No Form 4 filings found (last 6 months)")
    
    # Save detailed output
    safe_name = ticker.replace('/', '_')
    output_file = f"edgar_output_{safe_name}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n💾 Full data saved to: {output_file}")
    print(f"\n{'='*70}")
    print(f"✅ TEST COMPLETED")
    print(f"{'='*70}\n")


async def main():
    """Main test function."""
    print("\n" + "="*70)
    print("🚀 EDGAR SCRAPER - STANDALONE TEST")
    print("="*70)
    
    # Parse arguments
    is_ticker_mode = '--ticker' in sys.argv
    if is_ticker_mode:
        sys.argv.remove('--ticker')
    
    # Get inputs from command line or use defaults
    if len(sys.argv) > 1:
        inputs = sys.argv[1:]
    else:
        if is_ticker_mode:
            inputs = ['AAPL', 'TSLA', 'MSFT']
            print(f"\nℹ️  No tickers provided. Testing with defaults: {', '.join(inputs)}")
        else:
            inputs = ['Apple', 'Tesla', 'Microsoft']
            print(f"\nℹ️  No companies provided. Testing with defaults: {', '.join(inputs)}")
        
        print(f"   Usage:")
        print(f"     python tests/test_edgar_standalone.py \"Company Name\"")
        print(f"     python tests/test_edgar_standalone.py TICKER --ticker")
    
    # Test each input
    for input_value in inputs:
        try:
            await test_edgar_scraper(input_value, is_ticker=is_ticker_mode)
            await asyncio.sleep(1)  # Rate limiting
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error testing {input_value}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
