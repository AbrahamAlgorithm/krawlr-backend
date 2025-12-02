# 🧪 Quick Testing Guide

This guide shows how to test each scraper individually with real data.

## Prerequisites

Make sure you're in the project directory and have activated the virtual environment:

```bash
cd /Users/AbrahamAlgorithm/Krawlr/krawlr-backend
source venv/bin/activate  # or source .venv/bin/activate
```

---

## 1. 📊 Test EDGAR Scraper (Financial Data)

Extract financial statements and SEC filings for public companies.

### Quick Test:
```bash
python3 tests/test_edgar_standalone.py AAPL
```

### Test Multiple Companies:
```bash
python3 tests/test_edgar_standalone.py AAPL TSLA MSFT GOOGL
```

### What You Get:
- 5 years of financial statements (income, balance sheet, cash flow)
- Recent SEC filings (10-K, 10-Q, 8-K) with full text
- Company insiders from Form 4 filings
- Revenue chart data ready for visualization
- **Output:** `edgar_output_{TICKER}.json`

### Example Companies to Test:
- `AAPL` - Apple Inc.
- `TSLA` - Tesla
- `MSFT` - Microsoft
- `GOOGL` - Google/Alphabet
- `AMZN` - Amazon
- `META` - Meta/Facebook
- `NVDA` - NVIDIA

---

## 2. 🌐 Test Website Scraper (Company Identity)

Extract comprehensive data from any company website.

### Quick Test:
```bash
python3 tests/test_website_standalone.py https://stripe.com
```

### Test Without https:// Prefix:
```bash
python3 tests/test_website_standalone.py stripe.com
```

### Test Multiple Websites:
```bash
python3 tests/test_website_standalone.py https://stripe.com https://openai.com https://shopify.com
```

### What You Get:
- Company name, logo, favicon, description
- Contact info (emails, phones, addresses)
- Social media links
- Products/services catalog
- PDF documents
- Site structure (sitemap, internal links)
- Structured data (JSON-LD, OpenGraph)
- **Output:** `website_output_{DOMAIN}.json`

### Example Websites to Test:
- `https://stripe.com` - Payment processing
- `https://openai.com` - AI company
- `https://shopify.com` - E-commerce platform
- `https://airbnb.com` - Travel/hospitality
- `https://figma.com` - Design tool
- `https://notion.so` - Productivity app

---

## 3. 🔍 Test Google Search Scraper (Market Intelligence)

Search for founders, funding, competitors, and news.

### Quick Test:
```bash
python3 tests/test_google_search_standalone.py "Stripe"
```

### Test Multiple Companies:
```bash
python3 tests/test_google_search_standalone.py "Stripe" "OpenAI" "Shopify"
```

### What You Get:
- Founder/executive LinkedIn profiles
- Funding announcements and amounts
- Competitor companies
- Recent news articles
- **Output:** `google_search_output_{COMPANY}.json`

### Example Companies to Test:
- `"Stripe"` - Payment company
- `"OpenAI"` - AI research
- `"Anthropic"` - AI safety
- `"Databricks"` - Data analytics
- `"Rippling"` - HR software

### ⚠️ Note:
Google may block requests if you run too many tests quickly. Wait a few minutes between test runs if you see errors.

---

## 🎯 Quick Examples

### Test a Public Tech Company (Complete Profile):
```bash
# 1. Get financial data
python3 tests/test_edgar_standalone.py TSLA

# 2. Get website identity
python3 tests/test_website_standalone.py https://tesla.com

# 3. Get market intelligence
python3 tests/test_google_search_standalone.py "Tesla"
```

### Test a Startup (No Financial Data):
```bash
# 1. Get website identity
python3 tests/test_website_standalone.py https://replicate.com

# 2. Get market intelligence
python3 tests/test_google_search_standalone.py "Replicate"
```

### Test an E-commerce Company:
```bash
# 1. Financial data
python3 tests/test_edgar_standalone.py SHOP

# 2. Website data
python3 tests/test_website_standalone.py https://shopify.com

# 3. Market intelligence
python3 tests/test_google_search_standalone.py "Shopify"
```

---

## 📁 Output Files

All tests save detailed JSON output in the current directory:

- `edgar_output_AAPL.json` - Full financial data
- `website_output_stripe.com.json` - Complete website extraction
- `google_search_output_stripe.json` - All search results

You can inspect these files to see the exact data structure returned by each scraper.

---

## 🔧 Troubleshooting

### "Command not found: python"
Use `python3` instead:
```bash
python3 tests/test_edgar_standalone.py AAPL
```

### EDGAR: "edgartools not available"
Install the library:
```bash
pip install edgartools
```

### Website: Connection timeouts
Some sites have aggressive rate limiting. This is normal. Try:
- Testing a different website
- Waiting a few minutes
- Reducing `max_pages` parameter

### Google: No results found
Google may be blocking requests. Try:
- Waiting 5-10 minutes between tests
- Testing different companies
- Using a VPN if issues persist

---

## 🚀 Full Integration Test

To test all scrapers together (as they run in production):

```bash
python3 test_scrapers.py
```

This runs the complete orchestration with multiple companies.

---

## 📚 More Information

See `tests/README.md` for detailed documentation on each test script.
