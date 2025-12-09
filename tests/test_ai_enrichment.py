"""
Test AI Enrichment with OpenAI
Run this to see how AI cleans and fills missing data
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.ai_enrichment import enrich_company_data

# Sample raw data with issues (like from Google scrape)
SAMPLE_RAW_DATA = {
    "company": {
        "name": "Google",
        "legal_name": None,
        "website": "https://google.com",
        "domain": "google.com",
        "description": "Learn more about Google. Explore our innovative AI products...",
        "tagline": None,
        "logo_url": None,
        "favicon_url": "https://google.com/favicon.ico",
        # MESSY: Should be just 1998
        "founded_year": "September\u00a04, 1998; 27 years ago\u00a0(1998-09-04)[a] in Menlo Park, California, United States",
        "status": "Subsidiary",
        # MESSY: Concatenated without spaces
        "industry": "InternetCloud computingComputer softwareComputer hardwareArtificial intelligenceAdvertising",
        "sector": None,
        "employee_count": "187,000 (2022)",
        "headquarters": "Googleplex, Mountain View, California, U.S."
    },
    "financials": {
        "public_company": True,
        "ticker": "GOOG",
        "exchange": None,
        "cik": "1652044",
        "statements": None,
        "valuation": None  # MISSING: Google has known valuation
    },
    "funding": {
        "total_raised_usd": 0.0,  # WRONG: Google had early funding
        "currency": "USD",
        "round_count": 0,
        "latest_rounds": [],
        "investors": []  # MISSING: Should have early investors
    },
    "people": {
        "founders": [
            {
                "name": "Larry Page",
                "role": "Founder",
                "source": "wikipedia",
                "url": "https://en.wikipedia.org/wiki/Larry_Page",
                "description": "Founder of Google",
                "sources": ["wikipedia"]
            },
            {
                "name": "Sergey Brin",
                "role": "Founder",
                "source": "wikipedia",
                "url": "https://en.wikipedia.org/wiki/Sergey_Brin",
                "description": "Founder of Google",
                "sources": ["wikipedia"]
            }
        ],
        "executives": [],  # MISSING: Should have CEO, CFO, etc.
        "board_members": [],
        "key_people": []
    },
    "products": [],  # MISSING: Google has many products
    "competitors": [],  # MISSING: Should have Microsoft, Meta, etc.
    "news": {
        "total": 10,
        "date_range": {
            "oldest": "2025-04-12",
            "newest": "2025-12-06"
        },
        "articles": []  # Truncated for test
    },
    "online_presence": {
        "site_analysis": {
            "sitemap_pages": 0,
            "key_pages": {}
        },
        "social_media": {},  # MISSING: Should have Twitter, LinkedIn, etc.
        "contact_info": {
            "emails": [],
            "phones": [],
            "addresses": []
        }
    },
    "metadata": {
        "scrape_id": "test-123",
        "scrape_timestamp": "2025-12-08T14:44:38.126498+00:00",
        "scrape_duration_seconds": 138.09,
        "data_quality_score": 45.5,
        "scrapers_status": {
            "profile": "success",
            "website": "success",
            "financial": "success",
            "news": "success",
            "competitors": "success",
            "leadership": "success"
        },
        "refresh_recommended_date": "2025-12-15T14:44:38.126498+00:00"
    }
}


async def main():
    """Test AI enrichment"""
    
    print("=" * 80)
    print("🧪 TESTING AI ENRICHMENT WITH OPENAI")
    print("=" * 80)
    print()
    
    print("📊 ISSUES IN RAW DATA:")
    print(f"   - founded_year: '{SAMPLE_RAW_DATA['company']['founded_year']}'")
    print(f"   - industry: '{SAMPLE_RAW_DATA['company']['industry']}'")
    print(f"   - Missing: valuation, executives, products, competitors, social media")
    print(f"   - Empty investors array")
    print()
    
    print("🤖 Starting AI enrichment with OpenAI GPT-4...")
    print()
    
    # Run enrichment
    enriched = await enrich_company_data(SAMPLE_RAW_DATA)
    
    print()
    print("=" * 80)
    print("✅ ENRICHMENT RESULTS")
    print("=" * 80)
    print()
    
    # Show improvements
    print("📈 IMPROVEMENTS:")
    print()
    
    print(f"1. Founded Year:")
    print(f"   Before: {SAMPLE_RAW_DATA['company']['founded_year']}")
    print(f"   After:  {enriched['company']['founded_year']}")
    print()
    
    print(f"2. Industry:")
    print(f"   Before: {SAMPLE_RAW_DATA['company']['industry']}")
    print(f"   After:  {enriched['company']['industry']}")
    print()
    
    print(f"3. Valuation:")
    print(f"   Before: {SAMPLE_RAW_DATA['financials']['valuation']}")
    print(f"   After:  {enriched['financials']['valuation']}")
    print()
    
    print(f"4. Executives:")
    print(f"   Before: {len(SAMPLE_RAW_DATA['people']['executives'])} executives")
    print(f"   After:  {len(enriched['people']['executives'])} executives")
    if enriched['people']['executives']:
        for exec in enriched['people']['executives'][:3]:
            print(f"           - {exec.get('name')} ({exec.get('role')})")
    print()
    
    print(f"5. Products:")
    print(f"   Before: {len(SAMPLE_RAW_DATA['products'])} products")
    print(f"   After:  {len(enriched['products'])} products")
    if enriched['products']:
        for prod in enriched['products'][:5]:
            prod_name = prod.get('name') if isinstance(prod, dict) else str(prod)
            print(f"           - {prod_name}")
    print()
    
    print(f"6. Competitors:")
    print(f"   Before: {len(SAMPLE_RAW_DATA['competitors'])} competitors")
    print(f"   After:  {len(enriched['competitors'])} competitors")
    if enriched['competitors']:
        for comp in enriched['competitors'][:5]:
            comp_name = comp.get('name') if isinstance(comp, dict) else str(comp)
            print(f"           - {comp_name}")
    print()
    
    print(f"7. Social Media:")
    print(f"   Before: {len(SAMPLE_RAW_DATA['online_presence']['social_media'])} handles")
    print(f"   After:  {len(enriched['online_presence']['social_media'])} handles")
    if enriched['online_presence']['social_media']:
        for platform, handle in list(enriched['online_presence']['social_media'].items())[:5]:
            print(f"           - {platform}: {handle}")
    print()
    
    # Save result
    output_file = "ai_enriched_google.json"
    with open(output_file, 'w') as f:
        json.dump(enriched, f, indent=2)
    
    print(f"💾 Full enriched data saved to: {output_file}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
