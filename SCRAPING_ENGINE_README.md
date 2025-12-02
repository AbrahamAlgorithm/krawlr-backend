# Krawlr Scraping Engine

Complete web-scraping engine for extracting comprehensive company digital footprints from a single website URL.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  POST /scrape          → Start scraping job                  │
│  GET /scrape/{job_id}  → Check job status                    │
│  GET /company/{domain} → Get cached company data             │
│                                                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Scraping Orchestrator  │
        │  (Background Task)      │
        └────────────────────────┘
                     │
        ┌────────────┴───────────────┐
        │                            │
        ▼                            ▼
┌──────────────┐            ┌──────────────┐
│   Scrapers   │            │  Firestore   │
└──────────────┘            │   Storage    │
        │                   └──────────────┘
        │
        ├─→ Website Scraper (Identity)
        │   ├─ Homepage scraping
        │   ├─ Sitemap discovery
        │   ├─ Internal link crawling
        │   ├─ Product extraction
        │   └─ Contact info extraction
        │
        ├─→ Google Search Scraper
        │   ├─ Founder/Management (LinkedIn)
        │   ├─ Funding information
        │   ├─ Competitors (related:)
        │   └─ News mentions
        │
        └─→ SEC EDGAR Scraper
            ├─ Company CIK lookup
            ├─ 10-K/10-Q filings
            └─ Financial data extraction
```

## Features

### 1. Identity Scraper (`website_scraper.py`)

Extracts complete company identity from website:

- **Logo & Branding**
  - Logo URL (from JSON-LD, OpenGraph, `<img>` tags)
  - Favicon URL
  
- **Company Information**
  - Company name (from JSON-LD, OpenGraph, meta tags, domain)
  - Description (OpenGraph, meta description, JSON-LD)
  - JSON-LD structured data
  - OpenGraph metadata

- **Social Media Links**
  - Twitter/X
  - LinkedIn
  - Facebook
  - Instagram
  - YouTube
  - GitHub
  - TikTok

- **Contact Information**
  - Email addresses (filtered for validity)
  - Phone numbers
  - Physical addresses
  - Google Maps links

- **Site Structure**
  - Sitemap URLs (from sitemap.xml, robots.txt)
  - Internal links (up to 200 pages)
  - Key pages (About, Products, Contact, Careers, Team)

- **Products & Services**
  - Product names and descriptions
  - Product features (from lists)
  - Product URLs
  - PDF brochures and documentation
  - JSON-LD Product schemas

### 2. Founder & Management Scraper (`google_search_scraper.py`)

Searches Google for executives using:
```
site:linkedin.com/in "<company name>" founder OR CEO
```

Extracts:
- Full name
- Job title (Founder, CEO, Co-founder, etc.)
- LinkedIn profile URL
- Brief bio/description

### 3. Financial Scraper (`edgar_scraper.py`)

Scrapes SEC EDGAR for public companies:

- Company CIK (Central Index Key) lookup
- Recent 10-K and 10-Q filings
- Financial metrics:
  - Revenue
  - Net income
  - Total assets
  - Total liabilities
  - Shareholders' equity

### 4. Funding Scraper (`google_search_scraper.py`)

Searches Google for funding information:
```
"<company name>" (funding OR raised OR "Series A" OR investment)
```

Extracts:
- Funding amount ($XX million/billion)
- Round type (Seed, Series A/B/C, IPO)
- Investor names
- Article source and description

### 5. Competitor Scraper (`google_search_scraper.py`)

Uses Google's `related:` operator:
```
related:targetwebsite.com
```

Extracts:
- Competitor name
- Website URL
- Brief description

### 6. News Scraper (`google_search_scraper.py`)

Searches Google News for recent mentions:
```
"<company name>"
```

Extracts:
- Article title
- Publication source
- Article URL
- Summary/description

## Data Structure

All scraping results are stored in Firestore with the following schema:

```json
{
  "identity": {
    "url": "https://example.com",
    "domain": "example.com",
    "company_name": "Example Corp",
    "logo_url": "https://example.com/logo.png",
    "favicon_url": "https://example.com/favicon.ico",
    "description": "Company description...",
    "social_links": {
      "twitter": "https://twitter.com/example",
      "linkedin": "https://linkedin.com/company/example"
    },
    "contact_info": {
      "emails": ["contact@example.com"],
      "phones": ["+1-555-0100"],
      "addresses": ["123 Main St, City, State 12345"],
      "google_maps_links": ["https://maps.google.com/..."]
    },
    "sitemap_urls": ["https://example.com/page1", "..."],
    "internal_links": ["https://example.com/about", "..."],
    "key_pages": {
      "about": "https://example.com/about",
      "products": "https://example.com/products",
      "contact": "https://example.com/contact"
    },
    "products": [
      {
        "name": "Product Name",
        "description": "Product description...",
        "url": "https://example.com/product",
        "features": ["Feature 1", "Feature 2"],
        "brochures": [{"url": "https://example.com/doc.pdf", "title": "..."}]
      }
    ],
    "pdf_documents": [
      {"url": "https://example.com/whitepaper.pdf", "title": "..."}
    ],
    "json_ld_data": [...],
    "opengraph_data": {...}
  },
  "founders": [
    {
      "name": "John Doe",
      "job_title": "Co-founder & CEO",
      "profile_url": "https://linkedin.com/in/johndoe",
      "description": "Brief bio..."
    }
  ],
  "financials": {
    "cik": "0001234567",
    "ticker": "EXPL",
    "filings": [
      {
        "type": "10-K",
        "filing_date": "2024-02-15",
        "document_url": "https://sec.gov/..."
      }
    ],
    "financials": {
      "revenue": "$1.2 billion",
      "net_income": "$300 million",
      "total_assets": "$5 billion"
    }
  },
  "funding": [
    {
      "title": "Company raises $50M Series B",
      "url": "https://techcrunch.com/...",
      "amount": "$50 million",
      "round_type": "Series B",
      "description": "..."
    }
  ],
  "investors": [...],
  "competitors": [
    {
      "name": "Competitor Inc",
      "url": "https://competitor.com",
      "description": "..."
    }
  ],
  "news": [
    {
      "title": "Company launches new product",
      "source": "TechCrunch",
      "url": "https://techcrunch.com/...",
      "description": "..."
    }
  ],
  "sitemap": [...],
  "pages": [...]
}
```

## Usage

### API Endpoints

#### 1. Start Scraping Job

```http
POST /scrape
Authorization: Bearer <firebase_id_token>
Content-Type: application/json

{
  "url": "https://stripe.com"
}
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://stripe.com",
  "domain": "stripe.com",
  "status": "pending",
  "message": "Scraping job started. Use job_id to check progress at GET /scrape/{job_id}"
}
```

#### 2. Check Job Status

```http
GET /scrape/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <firebase_id_token>
```

Response (in progress):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://stripe.com",
  "status": "in_progress",
  "progress": 65,
  "created_at": "2024-12-01T10:00:00Z",
  "updated_at": "2024-12-01T10:02:30Z"
}
```

Response (completed):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://stripe.com",
  "status": "completed",
  "progress": 100,
  "result": {
    "identity": {...},
    "founders": [...],
    "financials": {...},
    ...
  },
  "completed_at": "2024-12-01T10:05:00Z"
}
```

#### 3. Get Cached Company Data

```http
GET /company/stripe.com
Authorization: Bearer <firebase_id_token>
```

Returns the complete scraped data for the domain (if previously scraped).

### Python Usage

```python
from app.services.scraping.orchestrator import scraping_orchestrator

# Start scraping job
job_id = await scraping_orchestrator.start_scraping_job(
    url="https://stripe.com",
    user_id="user123"
)

# Check status
status = await scraping_orchestrator.get_job_status(job_id)

# Get cached data
data = await scraping_orchestrator.get_cached_company_data("stripe.com")
```

### Individual Scraper Usage

```python
# Identity scraper
from app.services.scraping.website_scraper import website_scraper
identity = await website_scraper.scrape("https://stripe.com", max_pages=200)

# Founder scraper
from app.services.scraping.google_search_scraper import google_search_scraper
founders = await google_search_scraper.search_founders("Stripe", limit=10)

# Financial scraper
from app.services.scraping.edgar_scraper import sec_edgar_scraper
financials = await sec_edgar_scraper.scrape_financials("Apple", ticker="AAPL")

# Funding scraper
funding = await google_search_scraper.search_funding("OpenAI", limit=10)

# Competitor scraper
competitors = await google_search_scraper.search_competitors("stripe.com", limit=10)

# News scraper
news = await google_search_scraper.search_news("Tesla", limit=15)
```

## Testing

Run the comprehensive test suite:

```bash
python test_scrapers.py
```

This will test:
1. Identity scraper
2. Founder scraper
3. Financial scraper (SEC EDGAR)
4. Funding scraper
5. Competitor scraper
6. News scraper
7. Full orchestration

Results are saved to `test_scraping_output.json`.

## Configuration

### Rate Limiting

- HTTP requests: 10 requests/second (via `aiolimiter`)
- Google Search: 1 second delay between requests
- SEC EDGAR: 0.5 second delay between requests (required by SEC)

### Limits

- Maximum pages to crawl: 200 (configurable)
- Maximum sitemap URLs: 1000
- Maximum product pages: 20
- Email limit: 10 per page
- Phone limit: 10 per page

### Caching

- Company data cached for 24 hours in Firestore
- Cached data returned immediately if available
- Reduces redundant scraping

## Error Handling

- All scrapers have graceful fallbacks
- Failed scrapers don't block others
- Jobs marked as "failed" with error message
- Retries with exponential backoff for HTTP requests

## Dependencies

```
fastapi==0.121.2
httpx==0.28.1
beautifulsoup4==4.14.2
aiolimiter==1.2.1
google-cloud-firestore
advertools==0.17.1
```

## Files Structure

```
app/
├── services/
│   ├── scraping/
│   │   ├── website_scraper.py      # Identity scraping
│   │   ├── google_search_scraper.py # Google-based scrapers
│   │   ├── edgar_scraper.py        # SEC financial scraping
│   │   ├── orchestrator.py         # Coordinates all scrapers
│   │   └── firestore_service.py    # Data persistence
│   └── utils/
│       ├── http_client.py          # HTTP client with rate limiting
│       ├── parser.py               # HTML parsing utilities
│       ├── validators.py           # URL validation
│       └── sitemap_utils.py        # Sitemap handling
├── api/
│   └── routes.py                   # API endpoints
└── core/
    └── auth.py                     # Firebase authentication

tests/
└── test_scrapers.py                # Comprehensive test suite
```

## Future Enhancements

1. **AI Enhancement**: Use Gemini AI to enrich scraped data
2. **Screenshot Capture**: Capture website screenshots
3. **Technology Detection**: Identify tech stack (Wappalyzer-style)
4. **Email Verification**: Verify extracted emails are valid
5. **Social Media Stats**: Extract follower counts, engagement
6. **Advanced Financial Parsing**: XBRL parsing for detailed financials
7. **Webhook Notifications**: Notify when scraping completes
8. **Scheduled Re-scraping**: Automatic updates for tracked companies
9. **Batch Scraping**: Scrape multiple companies in parallel
10. **Export Formats**: CSV, Excel, PDF reports

## License

Proprietary - Krawlr Project
