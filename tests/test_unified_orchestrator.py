"""
Test script for Unified Orchestrator

Usage:
    python3 tests/test_unified_orchestrator.py <website_url> [company_name]
    
Examples:
    python3 tests/test_unified_orchestrator.py "https://stripe.com"
    python3 tests/test_unified_orchestrator.py "https://openai.com"
    python3 tests/test_unified_orchestrator.py "https://github.com"
    python3 tests/test_unified_orchestrator.py "pxxl.app" "PXXL"
"""

import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.unified_orchestrator import (
    get_complete_company_intelligence,
    SecurityValidator,
    CompanyNameExtractor
)


def print_section(title: str, data: any, max_items: int = 5):
    """Pretty print a section of data"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")
    
    if isinstance(data, dict):
        for key, value in list(data.items())[:max_items]:
            if isinstance(value, (dict, list)):
                print(f"  {key}: {type(value).__name__} with {len(value)} items")
            else:
                print(f"  {key}: {value}")
        
        if len(data) > max_items:
            print(f"  ... and {len(data) - max_items} more fields")
    
    elif isinstance(data, list):
        print(f"  Total items: {len(data)}")
        for i, item in enumerate(data[:max_items]):
            if isinstance(item, dict):
                name = item.get('name') or item.get('title') or f"Item {i+1}"
                print(f"  - {name}")
            else:
                print(f"  - {item}")
        
        if len(data) > max_items:
            print(f"  ... and {len(data) - max_items} more items")
    
    else:
        print(f"  {data}")


def test_security_validator():
    """Test security validation"""
    print("\n" + "="*80)
    print("TESTING SECURITY VALIDATOR")
    print("="*80)
    
    test_cases = [
        ("https://stripe.com", True, "Valid HTTPS URL"),
        ("http://google.com", True, "Valid HTTP URL"),
        ("https://localhost", False, "Blocked localhost"),
        ("https://127.0.0.1", False, "Blocked IP"),
        ("https://192.168.1.1", False, "Blocked private IP"),
        ("ftp://example.com", False, "Invalid protocol"),
        ("javascript:alert('xss')", False, "XSS attempt"),
        ("https://example.com/../../../etc/passwd", False, "Path traversal"),
    ]
    
    for url, expected_valid, description in test_cases:
        is_valid, error = SecurityValidator.validate_url(url)
        status = "✅" if is_valid == expected_valid else "❌"
        print(f"{status} {description}: {url}")
        if not is_valid:
            print(f"   Error: {error}")


def test_name_extraction():
    """Test company name extraction"""
    print("\n" + "="*80)
    print("TESTING COMPANY NAME EXTRACTION")
    print("="*80)
    
    test_cases = [
        ("https://stripe.com", "Stripe"),
        ("https://www.google.com", "Google"),
        ("https://openai.com", "OpenAI"),
        ("https://github.com", "GitHub"),
        ("https://pxxl.app", "Pxxl"),
        ("https://api.stripe.com", "Stripe"),
        ("https://www.facebook.com", "Facebook"),
    ]
    
    for url, expected_name in test_cases:
        extracted = CompanyNameExtractor.extract_from_url(url)
        status = "✅" if extracted.lower() == expected_name.lower() else "⚠️"
        print(f"{status} {url} -> {extracted} (expected: {expected_name})")


async def test_orchestrator(website_url: str, company_name: str = None):
    """Test complete orchestrator"""
    print("\n" + "="*80)
    print(f"TESTING UNIFIED ORCHESTRATOR")
    print(f"URL: {website_url}")
    if company_name:
        print(f"Company Name: {company_name}")
    print("="*80)
    
    try:
        # Run orchestrator
        print("\n⏳ Gathering company intelligence (this may take 1-3 minutes)...\n")
        
        result = await get_complete_company_intelligence(
            website_url=website_url,
            company_name=company_name,
            timeout=180  # 3 minutes
        )
        
        # Print results
        print("\n" + "🎉"*40)
        print("SUCCESS! Company intelligence gathered")
        print("🎉"*40)
        
        # Company info
        print_section("COMPANY INFORMATION", result.get('company', {}))
        
        # Financials
        financials = result.get('financials', {})
        if financials.get('public_company'):
            income_stmt = financials.get('income_statement') or {}
            balance = financials.get('balance_sheet') or {}
            print_section("FINANCIALS (Public Company)", {
                'ticker': financials.get('ticker'),
                'exchange': financials.get('exchange'),
                'latest_revenue': income_stmt.get('revenue', {}).get('FY 2024') if isinstance(income_stmt, dict) else None,
                'total_assets': balance.get('total_assets', {}).get('FY 2024') if isinstance(balance, dict) else None,
            })
        
        # Funding
        funding = result.get('funding', {})
        if funding.get('total_raised_usd'):
            print_section("FUNDING (Private Company)", {
                'total_raised': f"${funding.get('total_raised_usd'):,}",
                'round_count': funding.get('round_count'),
                'investor_count': len(funding.get('investors', [])),
            })
        
        # People
        people = result.get('people', {})
        print(f"\n{'='*80}")
        print(f"  PEOPLE")
        print(f"{'='*80}")
        print(f"  Founders: {len(people.get('founders', []))}")
        print(f"  Executives: {len(people.get('executives', []))}")
        print(f"  Board Members: {len(people.get('board_members', []))}")
        
        # Products
        products = result.get('products', [])
        print_section("PRODUCTS & SERVICES", products, max_items=3)
        
        # Competitors
        competitors = result.get('competitors', [])
        print_section("COMPETITORS", competitors, max_items=3)
        
        # News
        news = result.get('news', {})
        print_section("NEWS & PRESS", {
            'total_articles': news.get('total'),
            'date_range': news.get('date_range'),
            'recent_articles': len(news.get('articles', []))
        })
        
        # Online Presence
        online = result.get('online_presence', {})
        print_section("ONLINE PRESENCE", {
            'sitemap_pages': online.get('site_analysis', {}).get('sitemap_pages'),
            'social_accounts': len(online.get('social_media', {})),
            'emails': len(online.get('contact_info', {}).get('emails', [])),
            'phones': len(online.get('contact_info', {}).get('phones', [])),
        })
        
        # Metadata
        metadata = result.get('metadata', {})
        print(f"\n{'='*80}")
        print(f"  METADATA & QUALITY")
        print(f"{'='*80}")
        print(f"  Scrape ID: {metadata.get('scrape_id')}")
        print(f"  Duration: {metadata.get('scrape_duration_seconds')}s")
        print(f"  Data Quality Score: {metadata.get('data_quality_score')}/100")
        print(f"  Timestamp: {metadata.get('scrape_timestamp')}")
        
        # Scraper status
        print(f"\n  Scraper Status:")
        for scraper, status in metadata.get('scrapers_status', {}).items():
            icon = "✅" if status == "success" else "❌"
            print(f"    {icon} {scraper}: {status}")
        
        # Save to file
        output_file = f"unified_intelligence_{result['company']['name'].lower().replace(' ', '_')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\n💾 Full results saved to: {output_file}")
        
        return result
        
    except ValueError as e:
        print(f"\n❌ VALIDATION ERROR: {e}")
        return None
    
    except TimeoutError as e:
        print(f"\n⏱️ TIMEOUT ERROR: {e}")
        return None
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Main test function"""
    # Run security tests
    test_security_validator()
    
    # Run name extraction tests
    test_name_extraction()
    
    # Get URL from command line
    if len(sys.argv) < 2:
        print("\n❌ Error: Please provide a website URL")
        print("\nUsage:")
        print("  python3 tests/test_unified_orchestrator.py <website_url> [company_name]")
        print("\nExamples:")
        print("  python3 tests/test_unified_orchestrator.py 'https://stripe.com'")
        print("  python3 tests/test_unified_orchestrator.py 'https://openai.com'")
        print("  python3 tests/test_unified_orchestrator.py 'pxxl.app' 'PXXL'")
        sys.exit(1)
    
    website_url = sys.argv[1]
    company_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run orchestrator test
    await test_orchestrator(website_url, company_name)


if __name__ == "__main__":
    asyncio.run(main())
