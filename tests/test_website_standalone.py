"""
Standalone test script for Website Identity scraper.
Tests comprehensive website data extraction.

Usage:
    python tests/test_website_standalone.py
    python tests/test_website_standalone.py https://stripe.com
    python tests/test_website_standalone.py https://stripe.com https://shopify.com
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.website_scraper import website_scraper


async def test_website_scraper(url: str):
    """Test website scraper with a specific URL."""
    print(f"\n{'='*70}")
    print(f"🧪 TESTING WEBSITE SCRAPER FOR: {url}")
    print(f"{'='*70}\n")
    
    # Scrape the website
    print(f"🌐 Starting comprehensive website scrape...\n")
    result = await website_scraper.scrape(url, max_pages=50)
    
    if not result:
        print(f"❌ No data extracted from {url}")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 RESULTS SUMMARY")
    print(f"{'='*70}\n")
    
    # Basic identity
    print(f"🏢 Company Information:")
    print(f"   - Name: {result.get('company_name', 'N/A')}")
    print(f"   - Domain: {result.get('domain', 'N/A')}")
    print(f"   - Description: {result.get('description', 'N/A')[:100]}...")
    
    # Visual identity
    print(f"\n🎨 Visual Identity:")
    print(f"   - Logo: {result.get('logo_url', 'N/A')}")
    print(f"   - Favicon: {result.get('favicon_url', 'N/A')}")
    
    # Contact information
    emails = result.get('emails', [])
    phones = result.get('phones', [])
    addresses = result.get('addresses', [])
    
    print(f"\n📞 Contact Information:")
    print(f"   - Emails: {len(emails)}")
    if emails:
        for email in emails[:3]:
            print(f"      • {email}")
    
    print(f"   - Phones: {len(phones)}")
    if phones:
        for phone in phones[:3]:
            print(f"      • {phone}")
    
    print(f"   - Addresses: {len(addresses)}")
    if addresses:
        for address in addresses[:3]:
            print(f"      • {address}")
    
    # Social links
    social = result.get('social_links', {})
    print(f"\n🔗 Social Media:")
    print(f"   - Platforms: {len(social)}")
    for platform, link in social.items():
        print(f"      • {platform}: {link}")
    
    # Site structure
    sitemap_urls = result.get('sitemap_urls', [])
    internal_links = result.get('internal_links', [])
    
    print(f"\n🗺️  Site Structure:")
    print(f"   - Sitemap URLs: {len(sitemap_urls)}")
    print(f"   - Internal Links: {len(internal_links)}")
    
    # Products and services
    products = result.get('products', [])
    print(f"\n📦 Products/Services: {len(products)}")
    if products:
        for i, product in enumerate(products[:5], 1):
            print(f"   {i}. {product.get('name', 'N/A')}")
            print(f"      URL: {product.get('url', 'N/A')}")
            if product.get('description'):
                desc = product['description'][:100]
                print(f"      Description: {desc}...")
    
    # PDF documents
    pdfs = result.get('pdf_links', [])
    print(f"\n📄 PDF Documents: {len(pdfs)}")
    if pdfs:
        for i, pdf in enumerate(pdfs[:5], 1):
            print(f"   {i}. {pdf}")
    
    # Structured data
    json_ld = result.get('json_ld', [])
    opengraph = result.get('opengraph', {})
    
    print(f"\n📊 Structured Data:")
    print(f"   - JSON-LD schemas: {len(json_ld)}")
    if json_ld:
        for schema in json_ld[:3]:
            schema_type = schema.get('@type', 'Unknown')
            print(f"      • {schema_type}")
    
    print(f"   - OpenGraph tags: {len(opengraph)}")
    if opengraph:
        for key, value in list(opengraph.items())[:5]:
            print(f"      • {key}: {str(value)[:50]}")
    
    # Google Maps locations
    google_maps = result.get('google_maps_links', [])
    print(f"\n📍 Google Maps Locations: {len(google_maps)}")
    if google_maps:
        for i, location in enumerate(google_maps[:3], 1):
            print(f"   {i}. {location}")
    
    # Save detailed output
    domain = result.get('domain', 'unknown')
    output_file = f"website_output_{domain}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n💾 Full data saved to: {output_file}")
    print(f"\n{'='*70}")
    print(f"✅ TEST COMPLETED FOR {url}")
    print(f"{'='*70}\n")


async def main():
    """Main test function."""
    print("\n" + "="*70)
    print("🚀 WEBSITE IDENTITY SCRAPER - STANDALONE TEST")
    print("="*70)
    
    # Get URLs from command line or use defaults
    if len(sys.argv) > 1:
        urls = sys.argv[1:]
    else:
        # Default test URLs
        urls = ['https://stripe.com', 'https://openai.com']
        print(f"\nℹ️  No URLs provided. Testing with defaults:")
        for url in urls:
            print(f"   - {url}")
        print(f"\n   Usage: python tests/test_website_standalone.py URL1 URL2 ...")
    
    # Test each URL
    for url in urls:
        try:
            # Ensure URL has scheme
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            await test_website_scraper(url)
            await asyncio.sleep(2)  # Rate limiting
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error testing {url}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
