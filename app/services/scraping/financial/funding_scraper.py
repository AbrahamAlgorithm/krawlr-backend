"""
Unified funding scraper service with smart routing.

Routing Logic:
- Public companies → EDGAR (SEC filings)
- Private companies → PitchBook (funding data)

No merging - routes to the appropriate scraper based on company status.
"""

from __future__ import annotations

import asyncio
import logging
import json
import os
from typing import Any
from datetime import datetime

from openai import AsyncOpenAI

from .edgar_scraper import get_company_financials_by_name, is_private_unicorn
from .pitchbook_scraper import get_company_data as get_pitchbook_data
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Configure OpenAI
settings = get_settings()
openai_client = None
if settings.openai_api_key:
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
else:
    logger.warning("OPENAI_API_KEY not found. AI enrichment will be disabled.")


async def get_unified_funding_data(company_name: str) -> dict[str, Any]:
    """
    Get comprehensive funding data using smart routing.
    
    Routing Logic:
    1. Check if company is private unicorn or public company
    2. If private → Use PitchBook scraper
    3. If public → Use EDGAR scraper
    4. Enrich with AI for competitors and missing identity fields
    
    Args:
        company_name: Company name to search for
        
    Returns:
        Dictionary containing:
        {
            "company_name": str,
            "sources_used": list[str],  # ["edgar", "pitchbook"] or subset
            "data_quality": str,  # "excellent", "good", "partial", "limited"
            
            # Company Identity
            "identity": {
                "name": str,
                "ticker": str | None,  # From EDGAR
                "website": str | None,
                "description": str | None,
                "industry": str | None,
                "headquarters": str | None,
                "founded_year": str | None,
                "status": str | None,  # Private/Public/Acquired
                "employees": str | None
            },
            
            # Financial Data (primarily from EDGAR for public companies)
            "financials": {
                "revenue": str | None,
                "net_income": str | None,
                "assets": str | None,
                "liabilities": str | None,
                "equity": str | None,
                "cash_flow": str | None,
                "source": str,  # "edgar" or "pitchbook"
                "fiscal_year": str | None
            },
            
            # Funding Data (primarily from PitchBook)
            "funding": {
                "total_raised": str | None,
                "latest_deal_type": str | None,
                "funding_rounds": list[dict],
                "investors": list[str],
                "source": str  # "pitchbook" or "edgar"
            },
            
            # Market Data
            "market": {
                "competitors": list[str],
                "source": str
            },
            
            # Raw data from each source (for debugging/advanced use)
            "raw_data": {
                "edgar": dict | None,
                "pitchbook": dict | None
            },
            
            # Metadata
            "metadata": {
                "scraped_at": str,
                "edgar_success": bool,
                "pitchbook_success": bool,
                "errors": list[str]
            }
        }
    """
    print(f"\n{'='*70}")
    print(f"🔄 SMART ROUTING SCRAPER")
    print(f"{'='*70}")
    print(f"📊 Company: {company_name}")
    print(f"{'='*70}\n")
    
    # STEP 1: Determine if company is private or public
    print(f"[ROUTER] 🔍 Determining company status...")
    
    # Check if it's a known private unicorn
    unicorn_info = is_private_unicorn(company_name)
    
    if unicorn_info:
        # PRIVATE COMPANY → Use PitchBook
        print(f"[ROUTER] 🦄 Private unicorn detected: {unicorn_info['name']}")
        print(f"[ROUTER] → Routing to PitchBook scraper\n")
        
        pitchbook_data = await _run_pitchbook_scraper(company_name)
        unified_data = _format_pitchbook_data(company_name, pitchbook_data)
        
    else:
        # Try to find public company ticker
        print(f"[ROUTER] 🔍 Checking for public company ticker...")
        from .edgar_scraper import resolve_company_ticker
        ticker_info = await resolve_company_ticker(company_name)
        
        if ticker_info and ticker_info.get('ticker'):
            # PUBLIC COMPANY → Use EDGAR
            print(f"[ROUTER] 🏛️  Public company detected: {ticker_info['company_name']}")
            print(f"[ROUTER] → Routing to EDGAR scraper\n")
            
            edgar_data = await _run_edgar_scraper(company_name)
            unified_data = _format_edgar_data(company_name, edgar_data)
            
        else:
            # No ticker found, likely PRIVATE → Use PitchBook
            print(f"[ROUTER] 🔒 No public ticker found")
            print(f"[ROUTER] → Routing to PitchBook scraper (likely private)\n")
            
            pitchbook_data = await _run_pitchbook_scraper(company_name)
            unified_data = _format_pitchbook_data(company_name, pitchbook_data)
    
    # STEP 2: Enrich with AI if available
    if openai_client:
        print(f"\n[AI] 🤖 Enriching data with OpenAI...")
        unified_data = await _enrich_with_ai(unified_data)
    else:
        print(f"\n[AI] ⚠️  OpenAI API key not configured. Skipping AI enrichment.")
    
    # STEP 3: Print summary
    _print_summary(unified_data)
    
    return unified_data


async def _run_edgar_scraper(company_name: str) -> dict | None:
    """Run EDGAR scraper and handle errors."""
    print(f"[EDGAR] 🏛️  Starting EDGAR scraper...")
    try:
        data = await get_company_financials_by_name(company_name)
        if data and "error" not in data:
            print(f"[EDGAR] ✅ Successfully retrieved data")
            return data
        else:
            error_msg = data.get("error", "Unknown error") if data else "No data returned"
            print(f"[EDGAR] ⚠️  Failed: {error_msg}")
            logger.warning(f"EDGAR scraper failed for {company_name}: {error_msg}")
            return None
    except Exception as e:
        print(f"[EDGAR] ❌ Error: {e}")
        logger.error(f"EDGAR scraper error for {company_name}: {e}")
        return None


async def _run_pitchbook_scraper(company_name: str) -> dict | None:
    """Run PitchBook scraper and handle errors."""
    print(f"[PITCHBOOK] 💼 Starting PitchBook scraper...")
    try:
        data = await get_pitchbook_data(company_name)
        if data and "error" not in data:
            print(f"[PITCHBOOK] ✅ Successfully retrieved data")
            return data
        else:
            error_msg = data.get("error", "Unknown error") if data else "No data returned"
            print(f"[PITCHBOOK] ⚠️  Failed: {error_msg}")
            logger.warning(f"PitchBook scraper failed for {company_name}: {error_msg}")
            return None
    except Exception as e:
        print(f"[PITCHBOOK] ❌ Error: {e}")
        logger.error(f"PitchBook scraper error for {company_name}: {e}")
        return None


def _format_edgar_data(company_name: str, edgar_data: dict | None) -> dict[str, Any]:
    """
    Format EDGAR data into unified structure.
    For PUBLIC companies only.
    """
    print(f"\n[FORMAT] 📋 Formatting EDGAR data...")
    
    if not edgar_data:
        return _create_empty_structure(company_name)
    
    unified = {
        "company_name": company_name,
        
        "identity": {
            "name": edgar_data.get("name") or company_name,
            "ticker": edgar_data.get("ticker"),
            "website": edgar_data.get("website"),
            "description": None,
            "industry": None,
            "headquarters": edgar_data.get("business_address"),
            "founded_year": None,
            "status": "Public",  # EDGAR = Public companies
            "employees": None
        },
        
        "financials": {
            "revenue": None,
            "net_income": None,
            "assets": None,
            "liabilities": None,
            "equity": None,
            "cash_flow": None,
            "fiscal_year": None,
            "income_statement": edgar_data.get("income_statement", []),
            "balance_sheet": edgar_data.get("balance_sheet", []),
            "cash_flow_statement": edgar_data.get("cash_flow", [])
        },
        
        "funding": {
            "total_raised": None,  # Public companies don't have "raised" data
            "latest_deal_type": "IPO" if edgar_data.get("ticker") else None,
            "funding_rounds": [],
            "investors": []
        },
        
        "key_metrics": {
            "shares_outstanding": edgar_data.get("shares_outstanding"),
            "public_float": edgar_data.get("public_float")
        },
        
        "latest_filings": edgar_data.get("latest_filings", [])[:5],
        "insiders": edgar_data.get("insiders", []),
        "products": [],
        "competitors": [],
        
        "_internal": {
            "data_source": "edgar",
            "is_public": True,
            "needs_ai_enrichment": True
        }
    }
    
    # Extract latest financial metrics
    income_statement = edgar_data.get("income_statement", [])
    balance_sheet = edgar_data.get("balance_sheet", [])
    cash_flow = edgar_data.get("cash_flow", [])
    
    if income_statement and len(income_statement) > 0:
        first_metric = income_statement[0] if income_statement else {}
        years = [k for k in first_metric.keys() if k != "metric"]
        if years:
            latest_year = max(years)
            unified["financials"]["fiscal_year"] = latest_year
            
            for item in income_statement:
                metric = item.get("metric", "").lower()
                value = item.get(latest_year)
                if "revenue" in metric or "sales" in metric:
                    unified["financials"]["revenue"] = value
                elif "net income" in metric:
                    unified["financials"]["net_income"] = value
            
            for item in cash_flow:
                metric = item.get("metric", "").lower()
                value = item.get(latest_year)
                if "operating" in metric and "cash" in metric:
                    unified["financials"]["cash_flow"] = value
    
    print(f"[FORMAT] ✓ EDGAR data formatted for public company")
    return unified


def _format_pitchbook_data(company_name: str, pitchbook_data: dict | None) -> dict[str, Any]:
    """
    Format PitchBook data into unified structure.
    For PRIVATE companies only.
    """
    print(f"\n[FORMAT] 📋 Formatting PitchBook data...")
    
    if not pitchbook_data:
        return _create_empty_structure(company_name)
    
    unified = {
        "company_name": company_name,
        
        "identity": {
            "name": pitchbook_data.get("company_name") or company_name,
            "ticker": None,  # Private companies don't have tickers
            "website": pitchbook_data.get("website"),
            "description": pitchbook_data.get("description"),
            "industry": pitchbook_data.get("industry"),
            "headquarters": pitchbook_data.get("headquarters"),
            "founded_year": pitchbook_data.get("founded_year"),
            "status": pitchbook_data.get("status", "Private"),
            "employees": pitchbook_data.get("employees")
        },
        
        "financials": {
            "revenue": None,  # PitchBook doesn't provide detailed financials
            "net_income": None,
            "assets": None,
            "liabilities": None,
            "equity": None,
            "cash_flow": None,
            "fiscal_year": None,
            "income_statement": [],
            "balance_sheet": [],
            "cash_flow_statement": []
        },
        
        "funding": {
            "total_raised": pitchbook_data.get("total_raised"),
            "latest_deal_type": pitchbook_data.get("latest_deal_type"),
            "funding_rounds": pitchbook_data.get("funding_rounds", []),
            "investors": pitchbook_data.get("investors", [])
        },
        
        "key_metrics": {
            "shares_outstanding": None,
            "public_float": None
        },
        
        "latest_filings": [],
        "insiders": [],
        "products": [],
        "competitors": [{"name": comp} for comp in pitchbook_data.get("competitors", [])],
        
        "_internal": {
            "data_source": "pitchbook",
            "is_public": False,
            "needs_ai_enrichment": True
        }
    }
    
    print(f"[FORMAT] ✓ PitchBook data formatted for private company")
    return unified


def _create_empty_structure(company_name: str) -> dict[str, Any]:
    """Create empty unified structure when no data is available."""
    return {
        "company_name": company_name,
        "identity": {
            "name": company_name,
            "ticker": None,
            "website": None,
            "description": None,
            "industry": None,
            "headquarters": None,
            "founded_year": None,
            "status": None,
            "employees": None
        },
        "financials": {
            "revenue": None,
            "net_income": None,
            "assets": None,
            "liabilities": None,
            "equity": None,
            "cash_flow": None,
            "fiscal_year": None,
            "income_statement": [],
            "balance_sheet": [],
            "cash_flow_statement": []
        },
        "funding": {
            "total_raised": None,
            "latest_deal_type": None,
            "funding_rounds": [],
            "investors": []
        },
        "key_metrics": {
            "shares_outstanding": None,
            "public_float": None
        },
        "latest_filings": [],
        "insiders": [],
        "products": [],
        "competitors": [],
        "_internal": {
            "data_source": "none",
            "is_public": None,
            "needs_ai_enrichment": True
        }
    }


# Remove old merge function (no longer needed)
async def _enrich_with_ai(unified_data: dict) -> dict:
    """
    Use OpenAI to enrich data based on EDGAR structure.
    AI fills ONLY missing fields (identity, competitors).
    AI does NOT touch financial or funding data from EDGAR.
    """
    if not openai_client:
        return unified_data
    
    company_name = unified_data["identity"]["name"]
    
    # Enhanced prompt with EDGAR structure understanding
    prompt = f"""You are a Product Research Analyst AI assistant with deep knowledge of SEC filings and EDGAR data.

Your task is to enrich company data for: **{company_name}**

EDGAR DATA STRUCTURE (for your reference):
- EDGAR provides: ticker, business_address, shares_outstanding, public_float
- EDGAR provides: income_statement, balance_sheet, cash_flow_statement (arrays of financial data)
- EDGAR provides: latest_filings (SEC forms like 10-K, 10-Q, 8-K)
- EDGAR provides: insiders (executives with positions)

CURRENT DATA AVAILABLE FROM EDGAR:
{json.dumps(unified_data, indent=2, default=str)}

INSTRUCTIONS:

1. **Identity & Basics** (fill ONLY if empty from EDGAR):
   - description: Company overview (2-3 sentences about what they do)
   - industry: Primary industry/sector
   - website: Full website URL (e.g., www.company.com)
   - founded_year: Year founded (YYYY format)
   - status: Public/Private/Acquired (if EDGAR has ticker, usually Public)
   - employees: Number or range
   - If EDGAR already has headquarters/ticker, keep it as-is

2. **Products** (ALWAYS provide 3-7 main products/services):
   - Research {company_name}'s actual product portfolio
   - Include name, category, and detailed description for each product
   - Format: {{"name": "Product Name", "category": "Category", "description": "What it does and who uses it"}}
   - Focus on flagship products and main revenue drivers

3. **Competitor Intelligence** (ALWAYS provide 3-5 competitors):
   - Provide competitor name, location, website, description
   - Add strategic analysis: advantages over {company_name}, focus_areas
   - Format focus_areas as array of 3-5 key strategic areas
   - DO NOT include "total_raised" for competitors

4. **What NOT to touch** (EDGAR provides these):
   - DO NOT modify financials (revenue, net_income, cash_flow, etc.)
   - DO NOT modify funding data (EDGAR doesn't have this, leave empty)
   - DO NOT modify key_metrics (shares_outstanding, public_float from EDGAR)
   - DO NOT modify insiders (from EDGAR SEC filings)
   - DO NOT modify latest_filings (SEC forms from EDGAR)

REQUIRED OUTPUT JSON STRUCTURE:
{{
    "identity": {{
        "description": "Company description (only if missing)",
        "industry": "Industry/sector (only if missing)",
        "website": "Website URL (only if missing)",
        "founded_year": "YYYY (only if missing)",
        "employees": "Number or range (only if missing)",
        "status": "Public/Private (only if missing)"
    }},
    "products": [
        {{
            "name": "Product Name",
            "category": "Product Category",
            "description": "Detailed description of what it does and who it serves"
        }}
    ],
    "competitors": [
        {{
            "name": "Competitor name",
            "location": "City, State/Country",
            "website": "https://www.competitor.com",
            "description": "What they do (2-3 sentences)",
            "advantages": "Key competitive advantages vs {company_name}",
            "focus_areas": ["Area 1", "Area 2", "Area 3"]
        }}
    ]
}}

RESPOND WITH VALID JSON ONLY. Provide 3-7 products and 3-5 competitors minimum."""

    try:
        # Generate enriched data with AI
        print(f"[AI] 🤖 Analyzing competitors and identity with Product Research Analyst AI...")
        response = await openai_client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Product Research Analyst AI with deep knowledge of SEC filings and EDGAR data. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=8192,
            response_format={"type": "json_object"}
        )
        
        # Parse response
        ai_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if ai_text.startswith("```json"):
            ai_text = ai_text[7:]
        if ai_text.startswith("```"):
            ai_text = ai_text[3:]
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3]
        ai_text = ai_text.strip()
        
        ai_data = json.loads(ai_text)
        
        # Apply AI enrichments - ONLY for competitors and basic identity
        unified_data = _apply_ai_enrichments(unified_data, ai_data)
        
        print(f"[AI] ✅ Successfully enriched competitors and identity fields")
        
    except json.JSONDecodeError as e:
        print(f"[AI] ⚠️  Failed to parse AI response: {e}")
        logger.warning(f"AI JSON parse error: {e}")
    except Exception as e:
        print(f"[AI] ⚠️  AI enrichment error: {e}")
        logger.error(f"AI enrichment error: {e}")
    
    return unified_data


def _apply_ai_enrichments(unified_data: dict, ai_data: dict) -> dict:
    """
    Apply AI enrichments - ONLY for competitors and basic identity fields.
    Does NOT touch financial or funding data.
    """
    
    # 1. IDENTITY ENRICHMENT - Fill ONLY empty fields
    ai_identity = ai_data.get("identity", {})
    identity = unified_data["identity"]
    
    fields_filled = []
    
    for field in ["description", "industry", "website", "founded_year", "headquarters", "employees", "status"]:
        if not identity.get(field) and ai_identity.get(field):
            identity[field] = ai_identity[field]
            fields_filled.append(field)
    
    if fields_filled:
        print(f"[AI] ✓ Filled identity fields: {', '.join(fields_filled)}")
    
    # 2. PRODUCTS ENRICHMENT - Main product portfolio
    ai_products = ai_data.get("products", [])
    if ai_products:
        enriched_products = []
        
        for ai_prod in ai_products:
            product = {
                "name": ai_prod.get("name", ""),
                "category": ai_prod.get("category", ""),
                "description": ai_prod.get("description", "")
            }
            enriched_products.append(product)
        
        unified_data["products"] = enriched_products
        print(f"[AI] ✓ Added {len(enriched_products)} products to portfolio")
    
    # 3. COMPETITOR ENRICHMENT - Comprehensive intelligence (NO total_raised)
    ai_competitors = ai_data.get("competitors", [])
    if ai_competitors:
        enriched_competitors = []
        
        for ai_comp in ai_competitors:
            competitor = {
                "name": ai_comp.get("name", ""),
                "location": ai_comp.get("location", ""),
                "website": ai_comp.get("website", ""),
                "description": ai_comp.get("description", ""),
                "advantages": ai_comp.get("advantages", ""),
                "focus_areas": ai_comp.get("focus_areas", [])
            }
            enriched_competitors.append(competitor)
        
        unified_data["competitors"] = enriched_competitors
        print(f"[AI] ✓ Enriched {len(enriched_competitors)} competitors with strategic intelligence")
    
    return unified_data


def _print_summary(unified_data: dict) -> None:
    """Print a formatted summary of the unified data."""
    print(f"\n{'='*70}")
    print(f"📊 UNIFIED FUNDING DATA SUMMARY")
    print(f"{'='*70}")
    
    identity = unified_data["identity"]
    financials = unified_data["financials"]
    funding = unified_data["funding"]
    competitors = unified_data["competitors"]
    
    print(f"\n🏢 COMPANY IDENTITY:")
    print(f"   Name: {identity['name']}")
    print(f"   Ticker: {identity['ticker'] or 'N/A'}")
    print(f"   Status: {identity['status'] or 'N/A'}")
    print(f"   Industry: {identity['industry'] or 'N/A'}")
    print(f"   Founded: {identity['founded_year'] or 'N/A'}")
    print(f"   Employees: {identity['employees'] or 'N/A'}")
    print(f"   Website: {identity['website'] or 'N/A'}")
    print(f"   HQ: {identity['headquarters'] or 'N/A'}")
    
    if financials.get('revenue') or len(financials.get('income_statement', [])) > 0:
        print(f"\n💰 FINANCIAL DATA:")
        print(f"   Fiscal Year: {financials.get('fiscal_year') or 'N/A'}")
        print(f"   Revenue: {financials.get('revenue') or 'N/A'}")
        print(f"   Net Income: {financials.get('net_income') or 'N/A'}")
        print(f"   Total Assets: {financials.get('assets') or 'N/A'}")
        print(f"   Cash Flow: {financials.get('cash_flow') or 'N/A'}")
        print(f"   Statements: {len(financials.get('income_statement', []))} income, {len(financials.get('balance_sheet', []))} balance, {len(financials.get('cash_flow_statement', []))} cash flow rows")
    
    if funding.get('total_raised') or len(funding.get('funding_rounds', [])) > 0:
        print(f"\n🚀 FUNDING DATA:")
        print(f"   Total Raised: {funding.get('total_raised') or 'N/A'}")
        print(f"   Latest Deal: {funding.get('latest_deal_type') or 'N/A'}")
        print(f"   Funding Rounds: {len(funding.get('funding_rounds', []))}")
        print(f"   Investors: {len(funding.get('investors', []))}")
        if funding.get('investors'):
            print(f"   Top Investors: {', '.join(funding['investors'][:5])}")
    
    if unified_data.get("key_metrics", {}).get("shares_outstanding"):
        print(f"\n📈 KEY METRICS:")
        metrics = unified_data["key_metrics"]
        print(f"   Shares Outstanding: {metrics.get('shares_outstanding') or 'N/A'}")
        print(f"   Public Float: {metrics.get('public_float') or 'N/A'}")
    
    if unified_data.get("insiders") and len(unified_data["insiders"]) > 0:
        insiders = unified_data["insiders"]
        print(f"\n👥 INSIDERS:")
        print(f"   Executives: {len(insiders)}")
        for exec in insiders[:3]:
            print(f"      • {exec.get('insider', 'N/A')} - {exec.get('position', 'N/A')}")
    
    if unified_data.get("products") and len(unified_data["products"]) > 0:
        products = unified_data["products"]
        print(f"\n🎯 PRODUCTS:")
        print(f"   Total: {len(products)}")
        for idx, prod in enumerate(products[:5], 1):
            print(f"\n   {idx}. {prod.get('name', 'Unknown')}")
            if prod.get('category'):
                print(f"      📦 Category: {prod['category']}")
            if prod.get('description'):
                desc = prod['description'][:120] + "..." if len(prod.get('description', '')) > 120 else prod.get('description', '')
                print(f"      📝 {desc}")
    
    if unified_data.get("latest_filings") and len(unified_data["latest_filings"]) > 0:
        filings = unified_data["latest_filings"]
        print(f"\n📄 LATEST SEC FILINGS:")
        print(f"   Total: {len(filings)}")
        for filing in filings[:3]:
            print(f"   • {filing.get('form', 'N/A')} - {filing.get('filing_date', 'N/A')}")
    
    if competitors:
        print(f"\n🏆 COMPETITORS:")
        print(f"   Total: {len(competitors)}")
        
        # Show enriched competitors with details
        for idx, comp in enumerate(competitors[:3], 1):
            print(f"\n   {idx}. {comp.get('name', 'Unknown')}")
            if comp.get('location'):
                print(f"      📍 {comp['location']}")
            if comp.get('website'):
                print(f"      🌐 {comp['website']}")
            if comp.get('description'):
                desc = comp['description'][:100] + "..." if len(comp.get('description', '')) > 100 else comp.get('description', '')
                print(f"      📝 {desc}")
            if comp.get('advantages'):
                adv = comp['advantages'][:100] + "..." if len(comp.get('advantages', '')) > 100 else comp.get('advantages', '')
                print(f"      💡 {adv}")
            if comp.get('focus_areas'):
                print(f"      🎯 {', '.join(comp['focus_areas'][:3])}")
    
    print(f"\n{'='*70}")
    print(f"✅ UNIFIED SCRAPING COMPLETED")
    print(f"{'='*70}\n")


# Singleton instance for compatibility
class UnifiedFundingScraper:
    """Unified funding scraper service."""
    
    async def get_company_data(self, company_name: str) -> dict:
        """
        Get unified funding data for a company.
        
        Args:
            company_name: Company name to search for
            
        Returns:
            Dictionary with unified data from EDGAR and PitchBook
        """
        return await get_unified_funding_data(company_name)


# Create singleton instance
unified_funding_scraper = UnifiedFundingScraper()
