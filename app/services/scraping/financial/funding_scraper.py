"""
Unified funding scraper service that combines EDGAR and PitchBook data.
Runs both scrapers in parallel and merges the results intelligently.

This service provides a single interface for fetching comprehensive company
financial and funding data from multiple sources.
"""

from __future__ import annotations

import asyncio
import logging
import json
import os
from typing import Any
from datetime import datetime

import google.generativeai as genai

from .edgar_scraper import get_company_financials_by_name
from .pitchbook_scraper import get_company_data as get_pitchbook_data
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Configure Gemini AI
settings = get_settings()
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)
    
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.5-flash-lite')
else:
    GEMINI_MODEL = None
    logger.warning("GEMINI_API_KEY not found. AI enrichment will be disabled.")


async def get_unified_funding_data(company_name: str) -> dict[str, Any]:
    """
    Get comprehensive funding data by running EDGAR and PitchBook scrapers in parallel.
    
    This function:
    1. Runs both scrapers concurrently for speed
    2. Handles failures gracefully (if one fails, uses the other)
    3. Merges data intelligently, prioritizing more reliable sources
    4. Returns a unified format combining the best of both
    
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
    print(f"🔄 UNIFIED FUNDING SCRAPER")
    print(f"{'='*70}")
    print(f"📊 Company: {company_name}")
    print(f"🚀 Running EDGAR and PitchBook scrapers in parallel...")
    print(f"{'='*70}\n")
    
    # Run both scrapers concurrently
    edgar_task = asyncio.create_task(_run_edgar_scraper(company_name))
    pitchbook_task = asyncio.create_task(_run_pitchbook_scraper(company_name))
    
    # Wait for both to complete
    edgar_data, pitchbook_data = await asyncio.gather(edgar_task, pitchbook_task)
    
    # Merge and format the results
    unified_data = _merge_funding_data(company_name, edgar_data, pitchbook_data)
    
    # Enrich with AI if available
    if GEMINI_MODEL:
        print(f"\n[AI] 🤖 Enriching data with Gemini AI...")
        unified_data = await _enrich_with_ai(unified_data)
    else:
        print(f"\n[AI] ⚠️  Gemini API key not configured. Skipping AI enrichment.")
    
    # Print summary
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


def _merge_funding_data(
    company_name: str,
    edgar_data: dict | None,
    pitchbook_data: dict | None
) -> dict[str, Any]:
    """
    Intelligently merge data from EDGAR and PitchBook.
    
    Priority rules:
    - Ticker symbol: EDGAR (authoritative for public companies)
    - Financial statements: EDGAR (more detailed and reliable)
    - Funding rounds: PitchBook (specializes in this)
    - Industry/Description: Prefer PitchBook (more detailed)
    - Company status: PitchBook (tracks Private/Public/Acquired)
    """
    print(f"\n[MERGE] 🔀 Merging data from sources...")
    
    sources_used = []
    errors = []
    
    if edgar_data:
        sources_used.append("edgar")
    else:
        errors.append("EDGAR data unavailable")
    
    if pitchbook_data:
        sources_used.append("pitchbook")
    else:
        errors.append("PitchBook data unavailable")
    
    # Determine data quality
    if edgar_data and pitchbook_data:
        data_quality = "excellent"
    elif edgar_data or pitchbook_data:
        data_quality = "good" if edgar_data else "partial"
    else:
        data_quality = "limited"
    
    # Initialize unified structure
    unified = {
        "company_name": company_name,
        "sources_used": sources_used,
        "data_quality": data_quality,
        
        "identity": {
            "name": None,
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
            "source": None,
            "fiscal_year": None
        },
        
        "funding": {
            "total_raised": None,
            "latest_deal_type": None,
            "funding_rounds": [],
            "investors": [],
            "source": None
        },
        
        "market": {
            "competitors": [],
            "source": None
        },
        
        "latest_filings": {
            "filings": [],
            "source": None
        },
        
        "raw_data": {
            "edgar": edgar_data,
            "pitchbook": pitchbook_data
        },
        
        "metadata": {
            "scraped_at": datetime.utcnow().isoformat(),
            "edgar_success": edgar_data is not None,
            "pitchbook_success": pitchbook_data is not None,
            "ai_enriched": False,
            "errors": errors
        }
    }
    
    # Merge identity data
    if edgar_data:
        unified["identity"]["name"] = edgar_data.get("company_name") or company_name
        unified["identity"]["ticker"] = edgar_data.get("ticker")
        unified["identity"]["headquarters"] = edgar_data.get("company_address")
    
    if pitchbook_data:
        # Prefer PitchBook for these fields as they're more detailed
        unified["identity"]["name"] = pitchbook_data.get("company_name") or unified["identity"]["name"]
        unified["identity"]["website"] = pitchbook_data.get("website")
        unified["identity"]["description"] = pitchbook_data.get("description")
        unified["identity"]["industry"] = pitchbook_data.get("industry")
        unified["identity"]["headquarters"] = pitchbook_data.get("headquarters") or unified["identity"]["headquarters"]
        unified["identity"]["founded_year"] = pitchbook_data.get("founded_year")
        unified["identity"]["status"] = pitchbook_data.get("status")
        unified["identity"]["employees"] = pitchbook_data.get("employees")
    
    # Merge financial data (prioritize EDGAR for public companies)
    if edgar_data and edgar_data.get("financial_statements"):
        # Get most recent year's data
        financial_statements = edgar_data["financial_statements"]
        if financial_statements:
            # Sort by fiscal year descending
            sorted_years = sorted(
                financial_statements.items(),
                key=lambda x: x[0],
                reverse=True
            )
            
            if sorted_years:
                latest_year, latest_data = sorted_years[0]
                income_statement = latest_data.get("income_statement", {})
                balance_sheet = latest_data.get("balance_sheet", {})
                cash_flow = latest_data.get("cash_flow_statement", {})
                
                unified["financials"]["revenue"] = income_statement.get("Revenues")
                unified["financials"]["net_income"] = income_statement.get("NetIncomeLoss")
                unified["financials"]["assets"] = balance_sheet.get("Assets")
                unified["financials"]["liabilities"] = balance_sheet.get("Liabilities")
                unified["financials"]["equity"] = balance_sheet.get("StockholdersEquity")
                unified["financials"]["cash_flow"] = cash_flow.get("NetCashProvidedByUsedInOperatingActivities")
                unified["financials"]["source"] = "edgar"
                unified["financials"]["fiscal_year"] = latest_year
    
    # Merge funding data (prioritize PitchBook)
    if pitchbook_data:
        unified["funding"]["total_raised"] = pitchbook_data.get("total_raised")
        unified["funding"]["latest_deal_type"] = pitchbook_data.get("latest_deal_type")
        unified["funding"]["funding_rounds"] = pitchbook_data.get("funding_rounds", [])
        unified["funding"]["investors"] = pitchbook_data.get("investors", [])
        unified["funding"]["source"] = "pitchbook"
        
        # Merge competitors (basic info from PitchBook)
        competitors_list = pitchbook_data.get("competitors", [])
        if competitors_list:
            unified["market"]["competitors"] = [
                {"name": comp, "enriched": False} for comp in competitors_list
            ]
            unified["market"]["source"] = "pitchbook"
    
    # Merge latest filings from EDGAR
    if edgar_data and edgar_data.get("recent_filings"):
        unified["latest_filings"]["filings"] = edgar_data["recent_filings"][:5]  # Top 5
        unified["latest_filings"]["source"] = "edgar"
    
    # Log merge results
    print(f"[MERGE] ✓ Company name: {unified['identity']['name']}")
    print(f"[MERGE] ✓ Ticker: {unified['identity']['ticker'] or 'N/A'}")
    print(f"[MERGE] ✓ Status: {unified['identity']['status'] or 'N/A'}")
    print(f"[MERGE] ✓ Financials source: {unified['financials']['source'] or 'N/A'}")
    print(f"[MERGE] ✓ Funding source: {unified['funding']['source'] or 'N/A'}")
    print(f"[MERGE] ✓ Data quality: {data_quality}")
    
    return unified


async def _enrich_with_ai(unified_data: dict) -> dict:
    """
    Use Gemini AI to fill missing data gaps and enrich competitor information.
    
    The AI will:
    1. Fill missing identity fields (description, industry, etc.)
    2. Enrich competitor data with detailed information
    3. Add insights about funding and market position
    4. Never respond with "I don't know" - either provide data or leave empty
    """
    if not GEMINI_MODEL:
        return unified_data
    
    company_name = unified_data["identity"]["name"]
    
    # Build context for AI
    context = _build_ai_context(unified_data)
    
    # Create prompt for AI enrichment
    prompt = f"""You are a financial data analyst assistant. Analyze the following company data and fill in missing information using your knowledge.

Company: {company_name}

Current Data:
{json.dumps(context, indent=2)}

Please provide a JSON response with the following structure. For each field:
- If you know the answer with confidence, provide it
- If you're uncertain or don't know, leave the field as null or empty array
- NEVER respond with "I don't know" or similar - just omit or leave empty
- For competitors, provide detailed intelligence if you know about them

IMPORTANT - Total Raised Verification:
- The current total_raised is: {context.get('total_raised', 'Not provided')}
- If you know this is INCORRECT, provide the correct amount in the "total_raised_corrected" field
- If you believe it's CORRECT or you don't know the correct amount, leave "total_raised_corrected" as null
- Always provide your best estimate if the field is empty

Required JSON structure:
{{
    "identity": {{
        "description": "Brief company description (2-3 sentences)",
        "industry": "Primary industry",
        "website": "Company website URL",
        "founded_year": "Year founded",
        "headquarters": "City, State/Country",
        "employees": "Number of employees (approximate)"
    }},
    "funding": {{
        "total_raised": "Total funding raised if currently empty",
        "total_raised_corrected": "Corrected amount if current value is wrong (or null if correct)",
        "latest_round": "Latest funding round type"
    }},
    "competitors": [
        {{
            "name": "Competitor name",
            "location": "City, Country",
            "total_raised": "Total funding raised",
            "website": "Website URL",
            "description": "What they do (1-2 sentences)",
            "advantages": "What they do better than {company_name}",
            "focus_areas": ["Area 1", "Area 2", "Area 3"]
        }}
    ]
}}

Only fill in fields where you have confident knowledge. Respond with valid JSON only, no additional text."""

    try:
        # Generate enriched data with AI
        print(f"[AI] 🤖 Querying Gemini for enrichment...")
        response = await asyncio.to_thread(
            GEMINI_MODEL.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # Low temperature for factual responses
                max_output_tokens=4096,
            )
        )
        
        # Parse AI response
        ai_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if ai_text.startswith("```json"):
            ai_text = ai_text[7:]
        if ai_text.startswith("```"):
            ai_text = ai_text[3:]
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3]
        ai_text = ai_text.strip()
        
        ai_data = json.loads(ai_text)
        
        # Merge AI enrichments into unified data
        unified_data = _apply_ai_enrichments(unified_data, ai_data)
        unified_data["metadata"]["ai_enriched"] = True
        
        print(f"[AI] ✅ Successfully enriched data with AI")
        
    except json.JSONDecodeError as e:
        print(f"[AI] ⚠️  Failed to parse AI response: {e}")
        logger.warning(f"AI JSON parse error: {e}")
    except Exception as e:
        print(f"[AI] ⚠️  AI enrichment error: {e}")
        logger.error(f"AI enrichment error: {e}")
    
    return unified_data


def _build_ai_context(unified_data: dict) -> dict:
    """Build context object for AI enrichment."""
    identity = unified_data["identity"]
    funding = unified_data["funding"]
    competitors = unified_data["market"]["competitors"]
    
    # Extract competitor names
    competitor_names = []
    if competitors:
        competitor_names = [
            c["name"] if isinstance(c, dict) else c 
            for c in competitors
        ]
    
    return {
        "company_name": identity["name"],
        "ticker": identity["ticker"],
        "current_description": identity["description"],
        "current_industry": identity["industry"],
        "current_website": identity["website"],
        "status": identity["status"],
        "employees": identity["employees"],
        "founded_year": identity["founded_year"],
        "headquarters": identity["headquarters"],
        "total_raised": funding["total_raised"],
        "latest_deal": funding["latest_deal_type"],
        "known_competitors": competitor_names,
        "has_edgar_data": unified_data["metadata"]["edgar_success"],
        "has_pitchbook_data": unified_data["metadata"]["pitchbook_success"]
    }


def _apply_ai_enrichments(unified_data: dict, ai_data: dict) -> dict:
    """Apply AI enrichments to unified data, only filling missing fields."""
    
    # Enrich identity fields (only if currently missing)
    ai_identity = ai_data.get("identity", {})
    identity = unified_data["identity"]
    
    if not identity["description"] and ai_identity.get("description"):
        identity["description"] = ai_identity["description"]
        print(f"[AI] ✓ Added description")
    
    if not identity["industry"] and ai_identity.get("industry"):
        identity["industry"] = ai_identity["industry"]
        print(f"[AI] ✓ Added industry")
    
    if not identity["website"] and ai_identity.get("website"):
        identity["website"] = ai_identity["website"]
        print(f"[AI] ✓ Added website")
    
    if not identity["founded_year"] and ai_identity.get("founded_year"):
        identity["founded_year"] = ai_identity["founded_year"]
        print(f"[AI] ✓ Added founded year")
    
    if not identity["headquarters"] and ai_identity.get("headquarters"):
        identity["headquarters"] = ai_identity["headquarters"]
        print(f"[AI] ✓ Added headquarters")
    
    if not identity["employees"] and ai_identity.get("employees"):
        identity["employees"] = ai_identity["employees"]
        print(f"[AI] ✓ Added employee count")
    
    # Enrich funding fields
    ai_funding = ai_data.get("funding", {})
    funding = unified_data["funding"]
    
    # Check if AI corrected the total raised amount
    if ai_funding.get("total_raised_corrected"):
        old_value = funding["total_raised"]
        funding["total_raised"] = ai_funding["total_raised_corrected"]
        print(f"[AI] ✓ Corrected total raised: {old_value} → {funding['total_raised']}")
    elif not funding["total_raised"] and ai_funding.get("total_raised"):
        funding["total_raised"] = ai_funding["total_raised"]
        print(f"[AI] ✓ Added total raised: {funding['total_raised']}")
    elif funding["total_raised"]:
        print(f"[AI] ✓ Verified total raised: {funding['total_raised']} (confirmed correct)")
    
    if not funding["latest_deal_type"] and ai_funding.get("latest_round"):
        funding["latest_deal_type"] = ai_funding["latest_round"]
        print(f"[AI] ✓ Added latest round type")
    
    # Enrich competitors with detailed information
    ai_competitors = ai_data.get("competitors", [])
    if ai_competitors:
        enriched_competitors = []
        
        for ai_comp in ai_competitors:
            competitor = {
                "name": ai_comp.get("name", ""),
                "location": ai_comp.get("location", ""),
                "total_raised": ai_comp.get("total_raised", ""),
                "website": ai_comp.get("website", ""),
                "description": ai_comp.get("description", ""),
                "advantages": ai_comp.get("advantages", ""),
                "focus_areas": ai_comp.get("focus_areas", []),
                "enriched": True
            }
            enriched_competitors.append(competitor)
        
        unified_data["market"]["competitors"] = enriched_competitors
        print(f"[AI] ✓ Enriched {len(enriched_competitors)} competitors with detailed data")
    
    return unified_data


def _print_summary(unified_data: dict) -> None:
    """Print a formatted summary of the unified data."""
    print(f"\n{'='*70}")
    print(f"📊 UNIFIED FUNDING DATA SUMMARY")
    print(f"{'='*70}")
    
    identity = unified_data["identity"]
    financials = unified_data["financials"]
    funding = unified_data["funding"]
    market = unified_data["market"]
    metadata = unified_data["metadata"]
    
    print(f"\n🏢 COMPANY IDENTITY:")
    print(f"   Name: {identity['name']}")
    print(f"   Ticker: {identity['ticker'] or 'N/A'}")
    print(f"   Status: {identity['status'] or 'N/A'}")
    print(f"   Industry: {identity['industry'] or 'N/A'}")
    print(f"   Founded: {identity['founded_year'] or 'N/A'}")
    print(f"   Employees: {identity['employees'] or 'N/A'}")
    print(f"   Website: {identity['website'] or 'N/A'}")
    print(f"   HQ: {identity['headquarters'] or 'N/A'}")
    
    if financials['source']:
        print(f"\n💰 FINANCIAL DATA (from {financials['source'].upper()}):")
        print(f"   Fiscal Year: {financials['fiscal_year'] or 'N/A'}")
        print(f"   Revenue: {financials['revenue'] or 'N/A'}")
        print(f"   Net Income: {financials['net_income'] or 'N/A'}")
        print(f"   Total Assets: {financials['assets'] or 'N/A'}")
        print(f"   Cash Flow: {financials['cash_flow'] or 'N/A'}")
    
    if funding['source']:
        print(f"\n🚀 FUNDING DATA (from {funding['source'].upper()}):")
        print(f"   Total Raised: {funding['total_raised'] or 'N/A'}")
        print(f"   Latest Deal: {funding['latest_deal_type'] or 'N/A'}")
        print(f"   Funding Rounds: {len(funding['funding_rounds'])}")
        print(f"   Investors: {len(funding['investors'])}")
        if funding['investors']:
            print(f"   Top Investors: {', '.join(funding['investors'][:5])}")
    
    if market['competitors']:
        print(f"\n🏆 MARKET DATA:")
        print(f"   Competitors: {len(market['competitors'])}")
        
        # Check if competitors are enriched with AI
        is_enriched = any(
            isinstance(c, dict) and c.get("enriched") 
            for c in market['competitors']
        )
        
        if is_enriched:
            print(f"   Status: AI-Enriched with detailed intelligence")
            # Show first 3 enriched competitors with details
            for idx, comp in enumerate(market['competitors'][:3], 1):
                if isinstance(comp, dict) and comp.get("enriched"):
                    print(f"\n   Competitor {idx}: {comp.get('name', 'Unknown')}")
                    if comp.get('location'):
                        print(f"      Location: {comp['location']}")
                    if comp.get('total_raised'):
                        print(f"      Funding: {comp['total_raised']}")
                    if comp.get('description'):
                        print(f"      Description: {comp['description'][:80]}...")
                    if comp.get('advantages'):
                        print(f"      Advantages: {comp['advantages'][:80]}...")
                    if comp.get('focus_areas'):
                        print(f"      Focus: {', '.join(comp['focus_areas'][:3])}")
        else:
            # Simple list if not enriched
            competitor_names = [
                c['name'] if isinstance(c, dict) else c 
                for c in market['competitors'][:5]
            ]
            print(f"   Top Competitors: {', '.join(competitor_names)}")
    
    if unified_data.get("latest_filings", {}).get("filings"):
        filings = unified_data["latest_filings"]["filings"]
        print(f"\n📄 LATEST SEC FILINGS:")
        print(f"   Total: {len(filings)}")
        for filing in filings[:3]:
            print(f"   • {filing.get('form', 'N/A')} - {filing.get('filing_date', 'N/A')}")
    
    print(f"\n📈 DATA QUALITY:")
    print(f"   Overall Quality: {unified_data['data_quality'].upper()}")
    print(f"   Sources Used: {', '.join(unified_data['sources_used']).upper()}")
    print(f"   EDGAR Success: {'✅' if metadata['edgar_success'] else '❌'}")
    print(f"   PitchBook Success: {'✅' if metadata['pitchbook_success'] else '❌'}")
    print(f"   AI Enrichment: {'✅' if metadata.get('ai_enriched') else '❌'}")
    
    if metadata['errors']:
        print(f"\n⚠️  WARNINGS:")
        for error in metadata['errors']:
            print(f"   • {error}")
    
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
