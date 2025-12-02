#!/usr/bin/env python3
"""
Interactive test runner for Krawlr scrapers.
Makes it easy to test each scraper without remembering commands.

Usage:
    python3 run_tests.py
"""

import asyncio
import sys
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
END = '\033[0m'


def print_header(text):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{END}")
    print(f"{BOLD}{BLUE}{text}{END}")
    print(f"{BOLD}{BLUE}{'='*70}{END}\n")


def print_menu():
    """Print the main menu."""
    print_header("🧪 KRAWLR SCRAPER TEST RUNNER")
    
    print(f"{BOLD}Choose a scraper to test:{END}\n")
    print(f"  {GREEN}1.{END} 📊 EDGAR Scraper (Financial Data)")
    print(f"     Test with public company ticker (e.g., AAPL, TSLA)")
    print()
    print(f"  {GREEN}2.{END} 🌐 Website Scraper (Company Identity)")
    print(f"     Test with any company website (e.g., stripe.com)")
    print()
    print(f"  {GREEN}3.{END} 🔍 Google Search Scraper (Market Intelligence)")
    print(f"     Test with company name (e.g., \"Stripe\")")
    print()
    print(f"  {GREEN}4.{END} 🚀 Full Integration Test")
    print(f"     Test all scrapers together with orchestrator")
    print()
    print(f"  {RED}0.{END} Exit")
    print()


def get_user_input(prompt, default=None):
    """Get input from user with optional default."""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


async def test_edgar():
    """Run EDGAR scraper test."""
    print_header("📊 EDGAR SCRAPER TEST")
    
    print("Examples: AAPL, TSLA, MSFT, GOOGL, AMZN, META, NVDA\n")
    ticker = get_user_input("Enter stock ticker", "AAPL")
    
    print(f"\n{YELLOW}Running EDGAR test for {ticker}...{END}\n")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "tests/test_edgar_standalone.py", ticker],
        cwd=Path(__file__).parent
    )
    
    if result.returncode == 0:
        print(f"\n{GREEN}✅ Test completed! Check edgar_output_{ticker}.json for full results{END}")
    else:
        print(f"\n{RED}❌ Test failed with exit code {result.returncode}{END}")


async def test_website():
    """Run website scraper test."""
    print_header("🌐 WEBSITE SCRAPER TEST")
    
    print("Examples: stripe.com, openai.com, shopify.com, airbnb.com\n")
    url = get_user_input("Enter website URL", "stripe.com")
    
    # Add https:// if not present
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    print(f"\n{YELLOW}Running website test for {url}...{END}\n")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "tests/test_website_standalone.py", url],
        cwd=Path(__file__).parent
    )
    
    if result.returncode == 0:
        domain = url.replace('https://', '').replace('http://', '').split('/')[0]
        print(f"\n{GREEN}✅ Test completed! Check website_output_{domain}.json for full results{END}")
    else:
        print(f"\n{RED}❌ Test failed with exit code {result.returncode}{END}")


async def test_google_search():
    """Run Google search scraper test."""
    print_header("🔍 GOOGLE SEARCH SCRAPER TEST")
    
    print("Examples: Stripe, OpenAI, Anthropic, Databricks, Rippling\n")
    print(f"{YELLOW}⚠️  Note: Google may block requests if run too frequently{END}\n")
    
    company = get_user_input("Enter company name", "Stripe")
    
    print(f"\n{YELLOW}Running Google search test for {company}...{END}\n")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "tests/test_google_search_standalone.py", company],
        cwd=Path(__file__).parent
    )
    
    if result.returncode == 0:
        safe_name = company.lower().replace(' ', '_')
        print(f"\n{GREEN}✅ Test completed! Check google_search_output_{safe_name}.json for full results{END}")
    else:
        print(f"\n{RED}❌ Test failed with exit code {result.returncode}{END}")


async def test_full_integration():
    """Run full integration test."""
    print_header("🚀 FULL INTEGRATION TEST")
    
    print("This will test all scrapers together with the orchestrator.")
    print("It takes several minutes to complete.\n")
    
    confirm = get_user_input("Continue? (y/n)", "y")
    
    if confirm.lower() != 'y':
        print("Test cancelled.")
        return
    
    print(f"\n{YELLOW}Running full integration test...{END}\n")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "test_scrapers.py"],
        cwd=Path(__file__).parent
    )
    
    if result.returncode == 0:
        print(f"\n{GREEN}✅ All tests completed!{END}")
    else:
        print(f"\n{RED}❌ Some tests failed with exit code {result.returncode}{END}")


async def main():
    """Main interactive loop."""
    while True:
        print_menu()
        
        choice = get_user_input("Enter your choice (0-4)", "1")
        
        if choice == "0":
            print(f"\n{GREEN}Goodbye!{END}\n")
            break
        elif choice == "1":
            await test_edgar()
        elif choice == "2":
            await test_website()
        elif choice == "3":
            await test_google_search()
        elif choice == "4":
            await test_full_integration()
        else:
            print(f"\n{RED}Invalid choice. Please enter 0-4.{END}\n")
        
        # Ask if user wants to continue
        print()
        continue_choice = get_user_input("Run another test? (y/n)", "y")
        if continue_choice.lower() != 'y':
            print(f"\n{GREEN}Goodbye!{END}\n")
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Test interrupted by user{END}\n")
        sys.exit(0)
