#!/usr/bin/env python3
"""
Comprehensive test script for Krawlr scraping engine.
Tests all scraping modules individually and together.
"""

import asyncio
import json
from app.services.scraping.website_scraper import website_scraper
from app.services.scraping.google_search_scraper import google_search_scraper
from app.services.scraping.edgar_scraper import sec_edgar_scraper
from app.services.scraping.orchestrator import scraping_orchestrator

async def test_identity_scraper():
    """Test website identity scraping."""
    print("\n" + "="*70)
    print("TEST 1: Identity Scraper")
    print("="*70)
    
    test_url = "https://stripe.com"
    print(f"\n🧪 Testing identity scraping for: {test_url}\n")
    
    result = await website_scraper.scrape(test_url, max_pages=50)
    
    print("\n📊 Results Summary:")
    print(f"  Company Name: {result.get('company_name')}")
    print(f"  Logo URL: {result.get('logo_url')}")
    print(f"  Favicon URL: {result.get('favicon_url')}")
    print(f"  Description: {result.get('description', '')[:100]}...")
    print(f"  Social Links: {list(result.get('social_links', {}).keys())}")
    print(f"  Emails: {len(result.get('contact_info', {}).get('emails', []))}")
    print(f"  Phones: {len(result.get('contact_info', {}).get('phones', []))}")
    print(f"  Addresses: {len(result.get('contact_info', {}).get('addresses', []))}")
    print(f"  Google Maps: {len(result.get('contact_info', {}).get('google_maps_links', []))}")
    print(f"  Sitemap URLs: {len(result.get('sitemap_urls', []))}")
    print(f"  Internal Links: {len(result.get('internal_links', []))}")
    print(f"  Products: {len(result.get('products', []))}")
    print(f"  PDF Documents: {len(result.get('pdf_documents', []))}")
    print(f"  JSON-LD Schemas: {len(result.get('json_ld_data', []))}")
    
    print("\n✅ Identity scraper test completed")
    return result

async def test_founder_scraper():
    """Test founder/management scraping."""
    print("\n" + "="*70)
    print("TEST 2: Founder & Management Scraper")
    print("="*70)
    
    company_name = "Stripe"
    print(f"\n🧪 Testing founder search for: {company_name}\n")
    
    founders = await google_search_scraper.search_founders(company_name, limit=5)
    
    print("\n📊 Found Founders/Executives:")
    for i, founder in enumerate(founders, 1):
        print(f"\n  {i}. {founder.get('name')}")
        print(f"     Title: {founder.get('job_title')}")
        print(f"     LinkedIn: {founder.get('profile_url')}")
        if founder.get('description'):
            print(f"     Bio: {founder.get('description')[:100]}...")
    
    print("\n✅ Founder scraper test completed")
    return founders

async def test_financial_scraper():
    """Test SEC EDGAR financial scraping."""
    print("\n" + "="*70)
    print("TEST 3: Financial Scraper (SEC EDGAR)")
    print("="*70)
    
    company_name = "Apple"
    ticker = "AAPL"
    print(f"\n🧪 Testing financial data scraping for: {company_name} ({ticker})\n")
    
    financials = await sec_edgar_scraper.scrape_financials(company_name, ticker)
    
    print("\n📊 Financial Data:")
    print(f"  CIK: {financials.get('cik')}")
    print(f"  Filings Found: {len(financials.get('filings', []))}")
    
    if financials.get('filings'):
        latest = financials['filings'][0]
        print(f"\n  Latest Filing:")
        print(f"    Type: {latest.get('type')}")
        print(f"    Date: {latest.get('filing_date')}")
        print(f"    URL: {latest.get('document_url')}")
    
    if financials.get('financials'):
        print(f"\n  Financial Metrics:")
        for key, value in financials['financials'].items():
            if value:
                print(f"    {key.replace('_', ' ').title()}: {value}")
    
    print("\n✅ Financial scraper test completed")
    return financials

async def test_funding_scraper():
    """Test funding information scraping."""
    print("\n" + "="*70)
    print("TEST 4: Funding Scraper")
    print("="*70)
    
    company_name = "OpenAI"
    print(f"\n🧪 Testing funding search for: {company_name}\n")
    
    funding = await google_search_scraper.search_funding(company_name, limit=5)
    
    print("\n📊 Funding Information:")
    for i, item in enumerate(funding, 1):
        print(f"\n  {i}. {item.get('title')}")
        if item.get('amount'):
            print(f"     Amount: {item.get('amount')}")
        if item.get('round_type'):
            print(f"     Round: {item.get('round_type')}")
        print(f"     Source: {item.get('url')}")
        print(f"     Details: {item.get('description', '')[:150]}...")
    
    print("\n✅ Funding scraper test completed")
    return funding

async def test_competitor_scraper():
    """Test competitor scraping."""
    print("\n" + "="*70)
    print("TEST 5: Competitor Scraper")
    print("="*70)
    
    domain = "stripe.com"
    print(f"\n🧪 Testing competitor search for: {domain}\n")
    
    competitors = await google_search_scraper.search_competitors(domain, limit=5)
    
    print("\n📊 Competitors Found:")
    for i, comp in enumerate(competitors, 1):
        print(f"\n  {i}. {comp.get('name')}")
        print(f"     URL: {comp.get('url')}")
        print(f"     Description: {comp.get('description', '')[:150]}...")
    
    print("\n✅ Competitor scraper test completed")
    return competitors

async def test_news_scraper():
    """Test news scraping."""
    print("\n" + "="*70)
    print("TEST 6: News Scraper")
    print("="*70)
    
    company_name = "Tesla"
    print(f"\n🧪 Testing news search for: {company_name}\n")
    
    news = await google_search_scraper.search_news(company_name, limit=5)
    
    print("\n📊 Recent News:")
    for i, article in enumerate(news, 1):
        print(f"\n  {i}. {article.get('title')}")
        print(f"     Source: {article.get('source', 'Unknown')}")
        print(f"     URL: {article.get('url')}")
        print(f"     Summary: {article.get('description', '')[:150]}...")
    
    print("\n✅ News scraper test completed")
    return news

async def test_full_orchestration():
    """Test the full orchestration of all scrapers."""
    print("\n" + "="*70)
    print("TEST 7: Full Orchestration (without Firestore)")
    print("="*70)
    
    test_url = "https://shopify.com"
    print(f"\n🧪 Running full scraping pipeline for: {test_url}")
    print("Note: This will take several minutes...\n")
    
    # Note: We can't actually run the full orchestrator without starting a job
    # because it updates Firestore. Instead, we'll run the scrapers manually.
    
    from app.services.utils.validators import extract_domain
    domain = extract_domain(test_url)
    
    # Identity
    print("\n[1/5] Scraping identity...")
    identity = await website_scraper.scrape(test_url, max_pages=100)
    company_name = identity.get('company_name', domain)
    
    # Founders
    print("\n[2/5] Searching founders...")
    founders = await google_search_scraper.search_founders(company_name, limit=5)
    
    # Financials
    print("\n[3/5] Checking SEC filings...")
    financials = await sec_edgar_scraper.scrape_financials(company_name)
    
    # Funding
    print("\n[4/5] Searching funding info...")
    funding = await google_search_scraper.search_funding(company_name, limit=5)
    
    # Competitors & News
    print("\n[5/5] Finding competitors and news...")
    competitors = await google_search_scraper.search_competitors(domain, limit=5)
    news = await google_search_scraper.search_news(company_name, limit=5)
    
    # Compile results
    result = {
        'identity': identity,
        'founders': founders,
        'financials': financials,
        'funding': funding,
        'competitors': competitors,
        'news': news
    }
    
    print("\n" + "="*70)
    print("📊 FULL SCRAPING RESULTS SUMMARY")
    print("="*70)
    print(f"\nCompany: {company_name}")
    print(f"Domain: {domain}")
    print(f"\n✅ Identity Data:")
    print(f"   - Products: {len(identity.get('products', []))}")
    print(f"   - Social Links: {len(identity.get('social_links', {}))}")
    print(f"   - Emails: {len(identity.get('contact_info', {}).get('emails', []))}")
    print(f"   - Pages Crawled: {len(identity.get('sitemap_urls', [])) + len(identity.get('internal_links', []))}")
    print(f"\n👥 Founders: {len(founders)}")
    print(f"💰 Financial Filings: {len(financials.get('filings', []))}")
    print(f"💸 Funding Mentions: {len(funding)}")
    print(f"🏢 Competitors: {len(competitors)}")
    print(f"📰 News Articles: {len(news)}")
    
    # Save to file
    with open('test_scraping_output.json', 'w') as f:
        # Convert sets to lists for JSON serialization
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n💾 Full results saved to: test_scraping_output.json")
    print("\n✅ Full orchestration test completed")
    
    return result

async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🚀 KRAWLR SCRAPING ENGINE - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    # Run individual scraper tests
    await test_identity_scraper()
    await asyncio.sleep(2)  # Rate limiting
    
    await test_founder_scraper()
    await asyncio.sleep(2)
    
    await test_financial_scraper()
    await asyncio.sleep(2)
    
    await test_funding_scraper()
    await asyncio.sleep(2)
    
    await test_competitor_scraper()
    await asyncio.sleep(2)
    
    await test_news_scraper()
    await asyncio.sleep(2)
    
    # Run full orchestration test
    await test_full_orchestration()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
