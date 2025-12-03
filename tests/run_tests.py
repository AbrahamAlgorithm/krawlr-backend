#!/usr/bin/env python3
"""
Interactive test runner for all Krawlr scrapers.
Provides a menu-driven interface to test different scrapers.
"""

import subprocess
import sys


def print_header():
    """Print the header."""
    print("\n" + "="*70)
    print("🚀 KRAWLR SCRAPER TEST RUNNER")
    print("="*70)


def print_menu():
    """Print the test menu."""
    print("\n📋 Available Tests:")
    print("  1. EDGAR Scraper (SEC Financial Data)")
    print("  2. PitchBook Scraper (Private Company Data)")
    print("  3. Website Scraper (General Web Scraping)")
    print("  4. Unified Funding Scraper (EDGAR + PitchBook) ⭐ NEW")
    print("  5. Exit")
    print()


def run_edgar_test():
    """Run EDGAR scraper test."""
    print("\n" + "="*70)
    print("🏛️  EDGAR SCRAPER TEST")
    print("="*70)
    company = input("\n📊 Enter company name (e.g., Apple, Microsoft): ").strip()
    
    if not company:
        print("❌ Company name required")
        return
    
    print(f"\n🚀 Running EDGAR scraper for: {company}")
    cmd = ["python3", "tests/test_edgar_standalone.py", company]
    subprocess.run(cmd)


def run_pitchbook_test():
    """Run PitchBook scraper test."""
    print("\n" + "="*70)
    print("💼 PITCHBOOK SCRAPER TEST")
    print("="*70)
    company = input("\n📊 Enter company name (e.g., Stripe, GitHub, Airbnb): ").strip()
    
    if not company:
        print("❌ Company name required")
        return
    
    print(f"\n🚀 Running PitchBook scraper for: {company}")
    cmd = ["python3", "tests/test_pitchbook_standalone.py", company]
    subprocess.run(cmd)


def run_website_test():
    """Run website scraper test."""
    print("\n" + "="*70)
    print("🌐 WEBSITE SCRAPER TEST")
    print("="*70)
    url = input("\n🔗 Enter website URL (e.g., https://example.com): ").strip()
    
    if not url:
        print("❌ URL required")
        return
    
    print(f"\n🚀 Running website scraper for: {url}")
    cmd = ["python3", "tests/test_website_standalone.py", url]
    subprocess.run(cmd)


def run_unified_funding_test():
    """Run unified funding scraper test."""
    print("\n" + "="*70)
    print("🎯 UNIFIED FUNDING SCRAPER TEST (EDGAR + PitchBook)")
    print("="*70)
    print("\nℹ️  This test runs both EDGAR and PitchBook scrapers in parallel")
    print("   and combines the results intelligently.")
    print("\n💡 Tips:")
    print("   • Public companies (e.g., Apple, Microsoft) - EDGAR data")
    print("   • Private companies (e.g., Stripe, GitHub) - PitchBook data")
    print("   • Best results: Recently IPO'd companies (both sources)")
    
    company = input("\n📊 Enter company name: ").strip()
    
    if not company:
        print("❌ Company name required")
        return
    
    print(f"\n🚀 Running unified funding scraper for: {company}")
    cmd = ["python3", "tests/test_unified_funding_standalone.py", company]
    subprocess.run(cmd)


def main():
    """Main test runner loop."""
    while True:
        print_header()
        print_menu()
        
        try:
            choice = input("👉 Select test (1-5): ").strip()
            
            if choice == "1":
                run_edgar_test()
            elif choice == "2":
                run_pitchbook_test()
            elif choice == "3":
                run_website_test()
            elif choice == "4":
                run_unified_funding_test()
            elif choice == "5":
                print("\n👋 Goodbye!")
                sys.exit(0)
            else:
                print("\n❌ Invalid choice. Please select 1-5.")
            
            # Wait for user before showing menu again
            input("\n⏎  Press Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            input("\n⏎  Press Enter to continue...")


if __name__ == "__main__":
    main()
