"""
Standalone test for Company Profile Scraper

Tests the unified profile scraper that combines:
- Company website (About page)
- LinkedIn company profile
- Wikipedia page

Usage:
    python3 tests/test_profile_standalone.py "Company Name" [website_url]
    
Examples:
    python3 tests/test_profile_standalone.py "Stripe"
    python3 tests/test_profile_standalone.py "Apple" "https://www.apple.com"
    python3 tests/test_profile_standalone.py "Tesla"
"""

import sys
import asyncio
import json
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.scraping.profile.company_profile_scraper import get_company_profile, extract_company_name_from_url


async def test_profile_scraper(company_name_or_url: str, website: str | None = None):
    """Test the company profile scraper."""
    
    # Extract company name from URL if provided
    company_name, extracted_website = extract_company_name_from_url(company_name_or_url)
    if not website and extracted_website:
        website = extracted_website
    
    print(f"\n{'='*70}")
    print(f"TESTING COMPANY PROFILE SCRAPER")
    print(f"{'='*70}")
    print(f"Input: {company_name_or_url}")
    print(f"Company: {company_name}")
    if website:
        print(f"Website: {website}")
    print(f"{'='*70}\n")
    
    try:
        # Get unified profile data
        data = await get_company_profile(company_name_or_url, website)
        
        # Display results
        print("\n" + "="*70)
        print("✅ SCRAPING COMPLETE")
        print("="*70)
        
        # Sanitize company name for filename (remove invalid characters)
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', company_name.lower().replace(' ', '_'))
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')  # Remove multiple underscores
        
        # Save to file (clean version without raw_data)
        output_filename = f"profile_{safe_name}.json"
        output_path = project_root / output_filename
        
        # Create clean copy for readability
        clean_data = {k: v for k, v in data.items() if k != 'raw_data'}
        clean_data['metadata'] = data.get('metadata', {})
        
        with open(output_path, "w") as f:
            json.dump(clean_data, f, indent=2)
        
        # Save full data with raw_data to separate file
        full_output_path = project_root / f"profile_{safe_name}_full.json"
        with open(full_output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Data saved to:")
        print(f"   - Clean version: {output_filename}")
        print(f"   - Full version (with raw_data): {full_output_path.name}")
        
        return data
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 tests/test_profile_standalone.py \"Company Name or URL\" [website_url]")
        print("\nExamples:")
        print("  python3 tests/test_profile_standalone.py \"Stripe\"")
        print("  python3 tests/test_profile_standalone.py \"tesla.com\"")
        print("  python3 tests/test_profile_standalone.py \"https://microsoft.org\"")
        print("  python3 tests/test_profile_standalone.py \"https://www.youtube.com/\"")
        print("  python3 tests/test_profile_standalone.py \"Apple\" \"https://www.apple.com\"")
        sys.exit(1)
    
    company_name_or_url = sys.argv[1]
    website = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run the test
    asyncio.run(test_profile_scraper(company_name_or_url, website))


if __name__ == "__main__":
    main()
