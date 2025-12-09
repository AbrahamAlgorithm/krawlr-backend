"""
Standalone test for Website Content Scraper

Tests comprehensive website scraping including:
- Sitemap & page structure
- Products & services
- Contact info & social media

Usage:
    python3 tests/test_website_content_standalone.py "URL" [max_pages]
    
Examples:
    python3 tests/test_website_content_standalone.py "https://stripe.com"
    python3 tests/test_website_content_standalone.py "tesla.com" 100
    python3 tests/test_website_content_standalone.py "https://www.youtube.com/" 50
"""

import sys
import asyncio
import json
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.scraping.content.website_content_scraper import scrape_website_content
from app.services.scraping.profile.company_profile_scraper import extract_company_name_from_url


async def test_website_content_scraper(url: str, max_pages: int = 200):
    """Test the website content scraper."""
    
    # Extract company name for filename
    company_name, _ = extract_company_name_from_url(url)
    
    print(f"\n{'='*70}")
    print(f"TESTING WEBSITE CONTENT SCRAPER")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Max pages: {max_pages}")
    print(f"{'='*70}\n")
    
    try:
        # Scrape website content
        data = await scrape_website_content(url, max_pages)
        
        print("\n" + "="*70)
        print("✅ SCRAPING COMPLETE")
        print("="*70)
        
        # Sanitize company name for filename
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', company_name.lower().replace(' ', '_'))
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        
        # Save clean version (without some verbose data)
        output_filename = f"website_content_{safe_name}.json"
        output_path = project_root / output_filename
        
        # Create clean copy
        clean_data = {
            "url": data["url"],
            "domain": data["domain"],
            "structure": {
                "total_pages_found": data["structure"]["total_pages_found"],
                "sitemap_urls_count": len(data["structure"]["sitemap_urls"]),
                "sitemap_urls_sample": data["structure"]["sitemap_urls"][:10],  # First 10
                "robots_txt": data["structure"]["robots_txt"],
                "internal_links_count": len(data["structure"]["internal_links"]),
                "internal_links_sample": data["structure"]["internal_links"][:10],  # First 10
                "key_pages": data["structure"]["key_pages"],
            },
            "identity": data["identity"],
            "products_services": data["products_services"],
            "contact_info": data["contact_info"],
            "structured_data": data["structured_data"],
            "metadata": data["metadata"],
        }
        
        with open(output_path, "w") as f:
            json.dump(clean_data, f, indent=2)
        
        # Save full data with all URLs
        full_output_path = project_root / f"website_content_{safe_name}_full.json"
        with open(full_output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Data saved to:")
        print(f"   - Clean version: {output_filename}")
        print(f"   - Full version (all URLs): {full_output_path.name}")
        
        return data
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 tests/test_website_content_standalone.py \"URL\" [max_pages]")
        print("\nExamples:")
        print("  python3 tests/test_website_content_standalone.py \"https://stripe.com\"")
        print("  python3 tests/test_website_content_standalone.py \"tesla.com\" 100")
        print("  python3 tests/test_website_content_standalone.py \"https://www.youtube.com/\" 50")
        sys.exit(1)
    
    url = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    
    # Run the test
    asyncio.run(test_website_content_scraper(url, max_pages))


if __name__ == "__main__":
    main()
