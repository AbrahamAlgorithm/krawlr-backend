# Unified Company Intelligence API - JSON Schema

## Overview
This document defines the structure of the unified JSON response that combines all scraping services into one comprehensive company intelligence report.

## Top-Level Structure

```json
{
  "company": {},           // Basic company information
  "financials": {},        // Financial data, funding, valuation
  "people": {},            // Founders, executives, leadership
  "products_services": {}, // Products, services, offerings
  "competitors": {},       // Competitor analysis
  "news_press": {},        // Recent news and press releases
  "online_presence": {},   // Website, social media, contact info
  "metadata": {}           // Scraping metadata and quality scores
}
```

---

## 1. Company Section

**Purpose**: Core company identity and basic information

```json
{
  "company": {
    "name": string,                    // Primary company name
    "legal_name": string | null,       // Legal entity name
    "website": string | null,          // Primary website URL
    "domain": string | null,           // Primary domain
    "description": string | null,      // Company description (1-2 paragraphs)
    "tagline": string | null,          // Short tagline/slogan
    "logo_url": string | null,         // Logo image URL
    "favicon_url": string | null,      // Favicon URL
    "founded": string | null,          // Founding year (YYYY format)
    "status": string | null,           // "Private" | "Public" | "Acquired" | "Closed"
    "industry": string | null,         // Primary industry
    "sector": string | null,           // Broader sector
    "employee_count": number | null,   // Approximate employee count
    "headquarters": {
      "address": string | null,
      "city": string | null,
      "state": string | null,
      "country": string | null,
      "postal_code": string | null
    }
  }
}
```

**Data Sources**: Wikipedia, Website, PitchBook, LinkedIn

---

## 2. Financials Section

**Purpose**: Financial data, funding, valuation, public filings

```json
{
  "financials": {
    "status": "public" | "private",
    "ticker": string | null,           // Stock ticker (if public)
    "exchange": string | null,         // Stock exchange (NYSE, NASDAQ, etc.)
    "cik": string | null,              // SEC CIK number
    "public_company": boolean,
    
    // For Private Companies
    "funding": {
      "total_raised": string | null,         // "$9.5B"
      "total_raised_usd": number | null,     // 9500000000
      "currency": "USD" | string,
      "funding_rounds": number,
      "latest_round": {
        "type": string | null,               // "Series C", "Secondary"
        "date": string | null,               // ISO date
        "amount": string | null,
        "valuation": string | null,
        "lead_investors": string[]
      },
      "investors": {
        "total": number,
        "featured": [
          {
            "name": string,
            "type": string,                  // "Venture Capital", "Angel"
            "rounds": string[]
          }
        ]
      }
    },
    
    // For Public Companies
    "public_financials": {
      "market_cap": number | null,
      "shares_outstanding": number | null,
      "public_float": number | null,
      "fiscal_year_end": string | null,
      
      "income_statement": {
        "periods": string[],               // ["2021", "2022", "2023"]
        "revenue": number[],               // Annual revenue
        "gross_profit": number[],
        "operating_income": number[],
        "net_income": number[],
        "currency": "USD"
      },
      
      "balance_sheet": {
        "periods": string[],
        "total_assets": number[],
        "total_liabilities": number[],
        "shareholders_equity": number[],
        "currency": "USD"
      },
      
      "cash_flow": {
        "periods": string[],
        "operating_cash_flow": number[],
        "investing_cash_flow": number[],
        "financing_cash_flow": number[],
        "free_cash_flow": number[],
        "currency": "USD"
      },
      
      "recent_filings": [
        {
          "type": "10-K" | "10-Q" | "8-K",
          "date": string,
          "url": string,
          "description": string
        }
      ]
    } | null,
    
    "valuation": {
      "current": string | null,        // "$50B"
      "currency": "USD",
      "date": string | null,           // ISO date
      "source": string | null          // "Latest funding round" | "Market cap"
    }
  }
}
```

**Data Sources**: EDGAR (public), PitchBook (private), Crunchbase

---

## 3. People Section

**Purpose**: Founders, executives, leadership team, board members

```json
{
  "people": {
    "founders": [
      {
        "name": string,
        "role": string,                    // "Co-founder & CEO"
        "bio": string | null,              // Short biography
        "linkedin_url": string | null,
        "twitter_url": string | null,
        "image_url": string | null,
        "sources": string[]                // ["wikipedia", "crunchbase"]
      }
    ],
    
    "executives": [
      {
        "name": string,
        "role": string,                    // "CEO", "CFO", "CTO"
        "department": string | null,       // "Executive", "Finance", "Technology"
        "bio": string | null,
        "linkedin_url": string | null,
        "image_url": string | null,
        "sources": string[]
      }
    ],
    
    "leadership_count": number,            // Total leadership team size
    
    "board_members": [
      {
        "name": string,
        "role": string,                    // "Board Member", "Chairman"
        "bio": string | null,
        "sources": string[]
      }
    ]
  }
}
```

**Data Sources**: Wikipedia, Website team pages, LinkedIn, Crunchbase

---

## 4. Products & Services Section

**Purpose**: Company offerings, features, pricing

```json
{
  "products_services": {
    "total_count": number,
    
    "categories": [
      {
        "category": string,              // "Payments", "Infrastructure"
        
        "products": [
          {
            "name": string,
            "description": string | null,
            "url": string | null,
            "features": string[],
            "pricing": string | null,    // "Free tier + usage-based"
            "target_audience": string | null,
            "source": string             // "website" | "docs"
          }
        ]
      }
    ]
  }
}
```

**Data Sources**: Company website, documentation, product pages

---

## 5. Competitors Section

**Purpose**: Competitive landscape analysis

```json
{
  "competitors": {
    "total_count": number,
    
    "direct_competitors": [
      {
        "name": string,
        "domain": string | null,
        "similarity_score": number,        // 0-100
        "description": string | null,
        "url": string | null,
        "founded": string | null,
        "funding": string | null,
        "status": string | null,           // "Private" | "Public"
        "ticker": string | null,
        "employee_count": number | null,
        "sources": string[],
        "relationship": string | null      // Brief explanation
      }
    ],
    
    "adjacent_competitors": [
      {
        "name": string,
        "domain": string | null,
        "similarity_score": number,
        "description": string | null,
        "relationship": string             // Why they're adjacent
      }
    ]
  }
}
```

**Data Sources**: Google, Owler, website comparison pages, Wikipedia

---

## 6. News & Press Section

**Purpose**: Recent news, press releases, trending topics

```json
{
  "news_press": {
    "total_articles": number,
    
    "date_range": {
      "oldest": string,                  // ISO date
      "newest": string                   // ISO date
    },
    
    "recent_news": [
      {
        "title": string,
        "summary": string | null,
        "url": string,
        "source": string,                // "TechCrunch", "Reuters"
        "published_date": string,        // ISO date
        "type": "news" | "press_release" | "blog",
        "sentiment": "positive" | "neutral" | "negative" | null,
        "credibility_score": number,     // 0-10
        "topics": string[]               // ["acquisition", "funding"]
      }
    ],
    
    "press_releases": [
      {
        "title": string,
        "url": string,
        "published_date": string,
        "type": "press_release",
        "summary": string | null
      }
    ],
    
    "trending_topics": string[]          // Most common topics
  }
}
```

**Data Sources**: Google News, company newsroom, press release sites

---

## 7. Online Presence Section

**Purpose**: Digital footprint, social media, contact information

```json
{
  "online_presence": {
    "website": {
      "url": string,
      "domain": string,
      "sitemap_pages": number | null,
      "key_pages": {
        "about": string | null,
        "careers": string | null,
        "contact": string | null,
        "pricing": string | null,
        "blog": string | null,
        "docs": string | null
      },
      "technologies": string[],          // Tech stack
      "analytics": string[]              // Analytics tools detected
    },
    
    "social_media": {
      "twitter": {
        "url": string | null,
        "handle": string | null,
        "followers": number | null,
        "verified": boolean | null
      },
      "linkedin": {
        "url": string | null,
        "followers": number | null
      },
      "github": {
        "url": string | null,
        "repositories": number | null,
        "stars": number | null
      },
      "youtube": {
        "url": string | null,
        "subscribers": number | null
      },
      "facebook": {
        "url": string | null,
        "followers": number | null
      },
      "instagram": {
        "url": string | null,
        "followers": number | null
      }
    },
    
    "contact_info": {
      "emails": [
        {
          "type": "support" | "sales" | "press" | "general",
          "email": string
        }
      ],
      "phones": [
        {
          "type": "support" | "sales" | "main",
          "number": string,
          "country": string
        }
      ],
      "addresses": [
        {
          "type": "headquarters" | "office" | "regional",
          "street": string | null,
          "city": string | null,
          "state": string | null,
          "country": string,
          "postal_code": string | null
        }
      ]
    }
  }
}
```

**Data Sources**: Company website, sitemap, social media profiles

---

## 8. Metadata Section

**Purpose**: Scraping information, data quality, sources

```json
{
  "metadata": {
    "scrape_id": string,                 // Unique identifier
    "scrape_timestamp": string,          // ISO timestamp
    "scrape_duration_seconds": number,
    "data_quality_score": number,        // 0-100 overall quality
    
    "completeness": {
      "company_info": number,            // 0-100
      "financials": number,
      "people": number,
      "products": number,
      "competitors": number,
      "news": number,
      "online_presence": number
    },
    
    "sources_used": [
      {
        "source": string,                // "wikipedia", "pitchbook"
        "data_points": number,           // Number of fields populated
        "success": boolean,
        "error": string | null           // Error message if failed
      }
    ],
    
    "api_version": string,               // "1.0.0"
    "warnings": string[],                // Any warnings or limitations
    "refresh_recommended_date": string   // ISO date - when to refresh
  }
}
```

---

## Data Quality Scoring

**Score Calculation** (0-100):
- **Company Info**: 20 points max (name, description, founded, etc.)
- **Financials**: 20 points max (funding or public data)
- **People**: 15 points max (founders, executives found)
- **Products**: 15 points max (product catalog completeness)
- **Competitors**: 10 points max (competitor list quality)
- **News**: 10 points max (recent articles found)
- **Online Presence**: 10 points max (social media, contact info)

**Score Ranges**:
- **90-100**: Excellent - Comprehensive data from multiple sources
- **70-89**: Good - Most key data points available
- **50-69**: Fair - Basic information available, gaps exist
- **Below 50**: Poor - Significant data gaps, consider manual research

---

## Usage Notes

1. **Null Values**: Fields return `null` when data is unavailable
2. **Empty Arrays**: Return `[]` when no items found (not null)
3. **Currency**: All monetary values include currency field
4. **Dates**: ISO 8601 format (YYYY-MM-DD or full timestamp)
5. **URLs**: Always include protocol (https://)
6. **Sources**: Array shows which scrapers contributed data
7. **Scores**: 0-100 scale for consistency (similarity, quality, credibility)

---

## Example Minimal Response

For a company with limited data:

```json
{
  "company": {
    "name": "Small Startup Inc",
    "website": "https://smallstartup.com",
    "description": "Early stage startup",
    "founded": "2024",
    "status": "Private",
    "industry": null,
    "employee_count": null,
    "headquarters": {}
  },
  "financials": {
    "status": "private",
    "public_company": false,
    "funding": null,
    "valuation": null
  },
  "people": {
    "founders": [],
    "executives": [],
    "leadership_count": 0,
    "board_members": []
  },
  "products_services": {
    "total_count": 0,
    "categories": []
  },
  "competitors": {
    "total_count": 0,
    "direct_competitors": [],
    "adjacent_competitors": []
  },
  "news_press": {
    "total_articles": 0,
    "recent_news": [],
    "press_releases": []
  },
  "online_presence": {
    "website": {
      "url": "https://smallstartup.com",
      "domain": "smallstartup.com"
    },
    "social_media": {},
    "contact_info": {}
  },
  "metadata": {
    "scrape_timestamp": "2025-12-05T10:30:00Z",
    "data_quality_score": 25,
    "warnings": ["Limited public data available"]
  }
}
```
