import asyncio
from app.services.scraping.website_scraper import website_scraper

async def test():
    # Test with Google
    result = await website_scraper.scrape("https://linkedin.com")
    
    print("\n" + "="*50)
    print("SCRAPING RESULTS")
    print("="*50)
    print(f"Company: {result.get('company_name')}")
    print(f"Logo: {result.get('logo_url')}")
    print(f"Description: {result.get('description')}")
    
    print(f"\nSocial Links:")
    for platform, url in result.get('social_links', {}).items():
        print(f"  {platform}: {url}")
    
    print(f"\nContact Info:")
    print(f"  Emails: {result.get('contact_info', {}).get('emails')}")
    print(f"  Phones: {result.get('contact_info', {}).get('phones')}")
    
    print(f"\nKey Pages Found: {list(result.get('key_pages', {}).keys())}")
    
    # NEW: Show first 50 sitemap URLs
    print(f"\nSitemap URLs (showing first 50 of {len(result.get('sitemap_urls', []))}):")
    for url in result.get('sitemap_urls', [])[:50]:
        print(f"  - {url}")
    
    print(f"\nProducts: {len(result.get('products', []))} found")
    if result.get('products'):
        for product in result.get('products', [])[:5]:  # Show first 5
            print(f"  - {product['name']}: {product.get('description', 'No description')[:100]}")

if __name__ == "__main__":
    asyncio.run(test())