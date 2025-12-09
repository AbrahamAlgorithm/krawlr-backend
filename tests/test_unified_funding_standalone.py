#!/usr/bin/env python3
"""
Standalone test script for the unified funding scraper.
Tests the combined EDGAR + PitchBook scraper.

Usage:
    python3 tests/test_unified_funding_standalone.py "Company Name"
    
Examples:
    python3 tests/test_unified_funding_standalone.py "Apple"
    python3 tests/test_unified_funding_standalone.py "Stripe"
    python3 tests/test_unified_funding_standalone.py "GitHub"
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.scraping.financial.funding_scraper import get_unified_funding_data


async def main():
    """Test the unified funding scraper."""
    
    # Get company name from command line
    if len(sys.argv) < 2:
        print("❌ Error: Company name required")
        print("\nUsage:")
        print("  python3 tests/test_unified_funding_standalone.py 'Company Name'")
        print("\nExamples:")
        print("  python3 tests/test_unified_funding_standalone.py 'Apple'")
        print("  python3 tests/test_unified_funding_standalone.py 'Stripe'")
        print("  python3 tests/test_unified_funding_standalone.py 'GitHub'")
        sys.exit(1)
    
    company_name = sys.argv[1]
    
    # Run the unified scraper
    print(f"\n🚀 Testing Unified Funding Scraper")
    print(f"📊 Company: {company_name}\n")
    
    try:
        # Get unified data
        data = await get_unified_funding_data(company_name)
        
        # Save to file (create clean copy without raw_data for readability)
        output_filename = f"unified_funding_{company_name.lower().replace(' ', '_')}.json"
        output_path = project_root / output_filename
        
        # Create a clean copy without massive raw_data
        clean_data = {k: v for k, v in data.items() if k != 'raw_data'}
        clean_data['metadata'] = data.get('metadata', {})
        
        with open(output_path, "w") as f:
            json.dump(clean_data, f, indent=2)
        
        # Also save full data with raw_data to separate file
        full_output_path = project_root / f"unified_funding_{company_name.lower().replace(' ', '_')}_full.json"
        with open(full_output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Data saved to:")
        print(f"   - Clean version: {output_filename}")
        print(f"   - Full version (with raw_data): {full_output_path.name}")
        
        # Print key metrics
        print(f"\n{'='*70}")
        print(f"KEY METRICS")
        print(f"{'='*70}")
        
        identity = data["identity"]
        financials = data["financials"]
        funding = data["funding"]
        
        if identity.get("ticker"):
            print(f"📈 Ticker: {identity['ticker']}")
        
        if financials.get("revenue"):
            print(f"💰 Revenue: {financials['revenue']}")
        
        if financials.get("net_income"):
            print(f"💵 Net Income: {financials['net_income']}")
        
        if funding.get("total_raised"):
            print(f"🚀 Total Raised: {funding['total_raised']}")
        
        if funding.get("funding_rounds"):
            print(f"📊 Funding Rounds: {len(funding['funding_rounds'])}")
        
        if funding.get("investors"):
            print(f"👥 Investors: {len(funding['investors'])}")
        
        print(f"{'='*70}")
        
        # Exit with success
        print(f"\n✅ Test completed successfully!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
