"""SEC EDGAR financial data extraction service with enhanced Company Facts API."""

from __future__ import annotations

import logging
from typing import Any
import re
import os

# PRIVATE COMPANY ALLOWLIST - Known unicorns that should NEVER match to public tickers
PRIVATE_COMPANY_ALLOWLIST = {
    "stripe": {"domain": "stripe.com", "valuation": "$65B+", "name": "Stripe, Inc."},
    "canva": {"domain": "canva.com", "valuation": "$32B+", "name": "Canva Pty Ltd"},
    "spacex": {"domain": "spacex.com", "valuation": "$180B+", "name": "Space Exploration Technologies Corp."},
    "databricks": {"domain": "databricks.com", "valuation": "$43B+", "name": "Databricks, Inc."},
    "bytedance": {"domain": "bytedance.com", "valuation": "$225B+", "name": "ByteDance Ltd."},
    "shein": {"domain": "shein.com", "valuation": "$66B+", "name": "Shein"},
    "revolut": {"domain": "revolut.com", "valuation": "$33B+", "name": "Revolut Ltd"},
    "klarna": {"domain": "klarna.com", "valuation": "$6.7B+", "name": "Klarna Bank AB"},
    "instacart": {"domain": "instacart.com", "valuation": "$39B+", "name": "Maplebear Inc. (Instacart)"},
    "epic games": {"domain": "epicgames.com", "valuation": "$32B+", "name": "Epic Games, Inc."},
    "openai": {"domain": "openai.com", "valuation": "$157B+", "name": "OpenAI, Inc."},
    "anthropic": {"domain": "anthropic.com", "valuation": "$18B+", "name": "Anthropic PBC"},
    "xai": {"domain": "x.ai", "valuation": "$50B+", "name": "xAI"},
    "figure ai": {"domain": "figure.ai", "valuation": "$2.6B+", "name": "Figure AI, Inc."},
    "chime": {"domain": "chime.com", "valuation": "$25B+", "name": "Chime Financial, Inc."},
    "discord": {"domain": "discord.com", "valuation": "$15B+", "name": "Discord Inc."},
    "notion": {"domain": "notion.so", "valuation": "$10B+", "name": "Notion Labs Inc."},
    "plaid": {"domain": "plaid.com", "valuation": "$13.4B+", "name": "Plaid Inc."},
}


def is_private_unicorn(company_name: str) -> dict | None:
    """
    Check if company is a known private unicorn that should skip ticker lookup.
    
    Args:
        company_name: Company name to check
        
    Returns:
        Company info dict if matched, None otherwise
    """
    company_lower = company_name.lower().strip()
    
    for key, info in PRIVATE_COMPANY_ALLOWLIST.items():
        if key in company_lower or company_lower in key:
            print(f"[EDGAR] 🦄 Matched private unicorn: {info['name']}")
            print(f"[EDGAR] ⚠️  Skipping ticker lookup to avoid false matches")
            return info
    
    return None


async def verify_company_domain(ticker: str, expected_domain: str) -> bool:
    """
    Verify that a ticker's company domain matches the expected domain.
    This prevents matching wrong companies with similar names.
    
    Args:
        ticker: Stock ticker symbol
        expected_domain: Expected company domain (e.g., "canva.com")
        
    Returns:
        True if domains match, False otherwise
    """
    try:
        import httpx
        from urllib.parse import urlparse
        
        # Get company info from Yahoo Finance
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        params = {
            'modules': 'assetProfile'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Extract company website
            profile = data.get('quoteSummary', {}).get('result', [{}])[0].get('assetProfile', {})
            company_website = profile.get('website', '')
            
            if not company_website:
                print(f"[EDGAR] ⚠️  No website found for ticker {ticker}")
                return False
            
            # Extract domains
            actual_domain = urlparse(company_website).netloc.replace('www.', '')
            expected_clean = expected_domain.replace('www.', '')
            
            match = actual_domain.lower() == expected_clean.lower()
            
            if match:
                print(f"[EDGAR] ✓ Domain verified: {actual_domain} matches {expected_clean}")
            else:
                print(f"[EDGAR] ✗ Domain mismatch: {actual_domain} != {expected_clean}")
                print(f"[EDGAR] ⚠️  Rejecting ticker {ticker} - wrong company!")
            
            return match
            
    except Exception as e:
        print(f"[EDGAR] ⚠️  Domain verification failed: {e}")
        # On error, be conservative and reject
        return False


async def verify_has_sec_filings(ticker: str) -> bool:
    """
    Verify that a ticker actually has SEC filings (i.e., is a real public US company).
    This prevents routing private companies or foreign stocks to EDGAR.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        True if company has SEC filings, False otherwise
    """
    try:
        import httpx
        
        print(f"[EDGAR] 🔍 Verifying SEC filings for ticker: {ticker}")
        
        # Try to get company facts from SEC API
        # First need to resolve ticker to CIK
        cik_url = f"https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            'action': 'getcompany',
            'ticker': ticker,
            'count': 1,
            'output': 'json'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; CompanyResearch/1.0; +http://example.com)'
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to get CIK for this ticker
            response = await client.get(cik_url, params=params, headers=headers, follow_redirects=True)
            
            # If we get a 404 or error, no SEC filings exist
            if response.status_code == 404:
                print(f"[EDGAR] ✗ No SEC filings found for {ticker} - likely not a US public company")
                return False
            
            if response.status_code != 200:
                print(f"[EDGAR] ⚠️  Could not verify SEC filings (status {response.status_code})")
                # Be conservative - if we can't verify, assume it might be public
                return True
            
            # Check if we got actual company data
            try:
                data = response.text
                # Check for indicators that this is a real company with filings
                if 'No matching' in data or 'No companies' in data or len(data) < 100:
                    print(f"[EDGAR] ✗ No SEC filings found for {ticker}")
                    return False
                
                print(f"[EDGAR] ✓ Confirmed SEC filings exist for {ticker}")
                return True
                
            except Exception:
                # If we can't parse, assume it might be valid
                return True
            
    except Exception as e:
        print(f"[EDGAR] ⚠️  SEC filing verification failed: {e}")
        # On error, be conservative and assume might be public
        return True



def strip_ansi_codes(text: str) -> str:
    """
    Remove ANSI escape codes (colors, formatting) from text.
    Makes the output cleaner for JSON storage and display.
    """
    if not text:
        return text
    # Remove ANSI escape sequences (colors, bold, etc.)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def format_financials_for_frontend(statement_data: dict, periods: list) -> list:
    """
    Convert financial statement data into frontend-friendly format.
    
    Args:
        statement_data: Dictionary with metric labels as keys and their data as values
        periods: List of period labels (e.g., ['FY 2024', 'FY 2023', ...])
    
    Returns:
        List of dictionaries, each containing a metric and its values across periods
        Example: [{"metric": "Total Revenue", "2024": 637959000000, "2023": 574785000000, ...}]
    """
    if not statement_data or not periods:
        return []
    
    formatted_financials = []
    
    for label, item_data in statement_data.items():
        values = item_data.get('values', {})
        if not values:
            continue
        
        # Create the metric row
        metric_row = {"metric": label}
        
        # Add values for each period (extract year from "FY 2024" -> "2024")
        for period in periods:
            year = period.replace('FY ', '').strip()
            if period in values:
                metric_row[year] = values[period]
        
        formatted_financials.append(metric_row)
    
    return formatted_financials


try:
    from edgar import Company, set_identity
    print("[EDGAR] Successfully imported edgartools")
    
    # CRITICAL: Set identity IMMEDIATELY when module loads (SEC requirement)
    # This must happen BEFORE any Company() calls
    try:
        from app.core.config import get_settings
        settings = get_settings()
        identity = settings.edgar_identity or "Krawlr scraper contact@krawlr.com"
        print(f"[EDGAR] Setting identity from settings: {identity}")
    except Exception as e:
        identity = os.getenv("EDGAR_IDENTITY", "Krawlr scraper contact@krawlr.com")
        print(f"[EDGAR] Setting identity from env: {identity}")
    
    set_identity(identity)
    print(f"[EDGAR] ✓ Identity set globally: {identity}")
    
except ImportError as e:
    print(f"[EDGAR] Failed to import edgartools: {e}")
    Company = None
    set_identity = None

logger = logging.getLogger(__name__)


async def resolve_company_ticker(company_name: str) -> dict | None:
    """
    Resolve a company name to its ticker symbol using multiple strategies.
    Includes domain verification and private unicorn detection.
    
    Args:
        company_name: Company name (e.g., "Apple", "Microsoft Corporation")
        
    Returns:
        Dictionary with ticker and metadata, or None if private unicorn
    """
    print(f"[EDGAR] Resolving ticker for: {company_name}")
    
    # GUARD 1: Check if this is a known private unicorn
    unicorn_info = is_private_unicorn(company_name)
    if unicorn_info:
        # Return special marker to indicate this is private
        return {
            'ticker': None,
            'company_name': unicorn_info['name'],
            'is_private_unicorn': True,
            'domain': unicorn_info['domain'],
            'valuation': unicorn_info['valuation'],
            'method': 'private_unicorn_allowlist'
        }
    
    # Strategy 1: Try CSV lookup first (fastest)
    ticker_info = await _lookup_ticker_from_csv(company_name)
    if ticker_info:
        # Verify this ticker actually has SEC filings
        has_filings = await verify_has_sec_filings(ticker_info['ticker'])
        if not has_filings:
            print(f"[EDGAR] ✗ Rejecting CSV match - no SEC filings (likely private/foreign)")
            return None
        
        print(f"[EDGAR] ✓ Found via CSV: {ticker_info['ticker']}")
        return ticker_info
    
    # Strategy 2: Try Yahoo Finance search (most reliable)
    ticker_info = await _search_yahoo_finance(company_name)
    if ticker_info:
        # Verify this ticker actually has SEC filings
        has_filings = await verify_has_sec_filings(ticker_info['ticker'])
        if not has_filings:
            print(f"[EDGAR] ✗ Rejecting Yahoo match - no SEC filings (likely private/foreign)")
            return None
        
        print(f"[EDGAR] ✓ Found via Yahoo Finance: {ticker_info['ticker']}")
        return ticker_info
    
    # Strategy 3: Try SEC EDGAR CIK search
    ticker_info = await _search_edgar_cik(company_name)
    if ticker_info:
        print(f"[EDGAR] ✓ Found via EDGAR CIK: {ticker_info['ticker']}")
        return ticker_info
    
    print(f"[EDGAR] ✗ Could not resolve ticker for: {company_name}")
    return None


async def _lookup_ticker_from_csv(company_name: str) -> dict | None:
    """
    Look up ticker from local tickers.csv file.
    Uses fuzzy matching to handle variations in company names.
    """
    try:
        import csv
        import os
        from difflib import SequenceMatcher
        
        data_path = os.path.join(os.path.dirname(__file__), '../../data/tickers.csv')
        
        if not os.path.exists(data_path):
            print(f"[EDGAR] tickers.csv not found at: {data_path}")
            return None
        
        company_lower = company_name.lower().strip()
        # Remove common suffixes for better matching
        company_clean = re.sub(r'\b(inc|corp|corporation|company|co|ltd|limited)\b\.?', '', company_lower).strip()
        
        best_match = None
        best_score = 0.0
        
        with open(data_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                csv_name = row['company_name'].lower().strip()
                csv_name_clean = re.sub(r'\b(inc|corp|corporation|company|co|ltd|limited)\b\.?', '', csv_name).strip()
                
                # Exact match (highest priority)
                if company_clean == csv_name_clean or company_lower == csv_name:
                    return {
                        'ticker': row['ticker'],
                        'company_name': row['company_name'],
                        'exchange': row.get('exchange', 'Unknown'),
                        'method': 'csv_lookup'
                    }
                
                # Fuzzy match
                score = SequenceMatcher(None, company_clean, csv_name_clean).ratio()
                if score > best_score and score > 0.8:  # 80% similarity threshold
                    best_score = score
                    best_match = {
                        'ticker': row['ticker'],
                        'company_name': row['company_name'],
                        'exchange': row.get('exchange', 'Unknown'),
                        'method': 'csv_lookup'
                    }
        
        if best_match:
            print(f"[EDGAR] CSV fuzzy match: {best_match['company_name']} (score: {best_score:.2f})")
        
        return best_match
        
    except Exception as e:
        print(f"[EDGAR] Error reading tickers.csv: {e}")
        return None


async def _search_yahoo_finance(company_name: str) -> dict | None:
    """
    Search for ticker using Yahoo Finance API.
    This is the most reliable method for finding current tickers.
    """
    try:
        import httpx
        
        # Yahoo Finance query API
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            'q': company_name,
            'quotesCount': 5,
            'newsCount': 0,
            'enableFuzzyQuery': False,
            'quotesQueryId': 'tss_match_phrase_query'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            quotes = data.get('quotes', [])
            if not quotes:
                return None
            
            # Get the first equity result (not ETF, index, etc.)
            for quote in quotes:
                if quote.get('quoteType') == 'EQUITY':
                    return {
                        'ticker': quote['symbol'],
                        'company_name': quote.get('longname') or quote.get('shortname'),
                        'exchange': quote.get('exchDisp', 'Unknown'),
                        'method': 'yahoo_finance'
                    }
            
            # If no equity found, return first result anyway
            first = quotes[0]
            return {
                'ticker': first['symbol'],
                'company_name': first.get('longname') or first.get('shortname'),
                'exchange': first.get('exchDisp', 'Unknown'),
                'method': 'yahoo_finance'
            }
    
    except Exception as e:
        print(f"[EDGAR] Yahoo Finance search failed: {e}")
        return None


async def _search_edgar_cik(company_name: str) -> dict | None:
    """
    Search SEC EDGAR CIK (Central Index Key) database.
    Official SEC data but slower and less user-friendly.
    """
    try:
        import httpx
        
        # SEC EDGAR company tickers JSON
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {
            'User-Agent': 'Krawlr scraper contact@krawlr.com',
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Search through the data
            company_lower = company_name.lower().strip()
            company_clean = re.sub(r'\b(inc|corp|corporation|company|co|ltd|limited)\b\.?', '', company_lower).strip()
            
            best_match = None
            best_score = 0.0
            
            for item in data.values():
                edgar_name = item['title'].lower().strip()
                edgar_clean = re.sub(r'\b(inc|corp|corporation|company|co|ltd|limited)\b\.?', '', edgar_name).strip()
                
                # Exact match
                if company_clean == edgar_clean or company_lower == edgar_name:
                    return {
                        'ticker': item['ticker'],
                        'company_name': item['title'],
                        'exchange': 'SEC',
                        'cik': str(item['cik_str']).zfill(10),
                        'method': 'edgar_search'
                    }
                
                # Fuzzy match
                from difflib import SequenceMatcher
                score = SequenceMatcher(None, company_clean, edgar_clean).ratio()
                if score > best_score and score > 0.85:
                    best_score = score
                    best_match = {
                        'ticker': item['ticker'],
                        'company_name': item['title'],
                        'exchange': 'SEC',
                        'cik': str(item['cik_str']).zfill(10),
                        'method': 'edgar_search'
                    }
            
            return best_match
    
    except Exception as e:
        print(f"[EDGAR] EDGAR CIK search failed: {e}")
        return None


def initialize_edgar(email: str) -> None:
    """Initialize EDGAR with user identity (required by SEC)."""
    if set_identity:
        set_identity(email)
        logger.info("EDGAR identity set")
    else:
        logger.warning("edgartools not available")


async def get_company_financials_by_name(company_name: str) -> dict | None:
    """
    Fetch comprehensive financial data from SEC EDGAR using company name.
    Automatically resolves the company name to a ticker symbol.
    Handles private unicorns by returning minimal data structure.
    
    Args:
        company_name: Company name (e.g., "Apple", "Microsoft Corporation")
        
    Returns:
        Dictionary containing comprehensive company data or private company marker
    """
    print(f"[EDGAR] Fetching financials for company: {company_name}")
    
    # Resolve company name to ticker
    ticker_info = await resolve_company_ticker(company_name)
    
    if not ticker_info:
        print(f"[EDGAR] ✗ Could not find ticker for: {company_name}")
        return {
            'error': 'Company ticker not found',
            'company_name': company_name,
            'suggestion': 'Try using the exact company name or ticker symbol'
        }
    
    # Check if this is a private unicorn
    if ticker_info.get('is_private_unicorn'):
        print(f"[EDGAR] 🦄 Private unicorn detected: {ticker_info['company_name']}")
        print(f"[EDGAR] ℹ️  Returning minimal structure - AI will enrich")
        return {
            'name': ticker_info['company_name'],
            'ticker': None,
            'is_private': True,
            'website': f"https://{ticker_info['domain']}",
            'estimated_valuation': ticker_info['valuation'],
            'source': 'private_unicorn_allowlist',
            'note': 'This is a private company. Financial data from SEC filings not available.',
            # Empty structures for AI to fill
            'income_statement': [],
            'balance_sheet': [],
            'cash_flow': [],
            'latest_filings': [],
            'insiders': []
        }
    
    ticker = ticker_info['ticker']
    print(f"[EDGAR] ✓ Resolved to ticker: {ticker} ({ticker_info['company_name']})")
    
    # Fetch financial data using ticker
    result = await get_company_financials(ticker)
    
    if result:
        # Add ticker resolution metadata
        result['ticker_resolution'] = ticker_info
    
    return result


async def get_company_financials(ticker: str) -> dict | None:
    """
    Fetch comprehensive financial data from SEC EDGAR for a given ticker.
    Uses the enhanced Company Facts API to retrieve financial statements, metrics, and filings.
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        
    Returns:
        Dictionary containing comprehensive company data including:
        - Basic info: ticker, name, cik, sic, business_address
        - Key metrics: shares_outstanding, public_float
        - Financial statements: income_statement, balance_sheet, cash_flow (as markdown)
        - Latest filings: list of recent filings with form, date, accession, url, content
    """
    print(f"[EDGAR] get_company_financials called for ticker: {ticker}")
    try:
        print("[EDGAR] Attempting to import edgartools...")
        from edgar import Company, set_identity
        print("[EDGAR] ✓ Successfully imported edgartools")
        
        # Identity is already set globally at module import
        print(f"[EDGAR] ℹ️  Identity already set at module level")
        
        print(f"[EDGAR] Fetching comprehensive company data for ticker: {ticker}")
        company = Company(ticker)
        print(f"[EDGAR] Company object created: {company.name}")
        
        # Extract basic company information
        company_info = {
            "ticker": ticker,
            "name": company.name if hasattr(company, 'name') else None,
            "cik": None,
            "sic": None,
            "business_address": None,
            "shares_outstanding": None,
            "public_float": None,
            "has_facts": False,
            "income_statement": [],
            "balance_sheet": [],
            "cash_flow": [],
            "key_metrics": {},
            "latest_filings": [],
            "insiders": []
        }
        
        # Get CIK
        if hasattr(company, 'cik'):
            cik_value = company.cik
            company_info["cik"] = str(cik_value)
            print(f"[EDGAR] CIK: {company_info['cik']}")
        
        # Get SIC
        if hasattr(company, 'sic'):
            sic_value = company.sic
            company_info["sic"] = str(sic_value) if sic_value else None
            print(f"[EDGAR] SIC: {company_info['sic']}")
        
        # Get business address
        if hasattr(company, 'business_address'):
            business_address = company.business_address
            if callable(business_address):
                business_address = business_address()
            company_info["business_address"] = str(business_address) if business_address else None
            print(f"[EDGAR] Business Address: {company_info['business_address']}")
        
        # Check if facts are available
        if hasattr(company, 'facts') and company.facts:
            print(f"[EDGAR] ✓ Facts API data available")
            company_info["has_facts"] = True
            
            # Get key metrics
            try:
                if hasattr(company, 'shares_outstanding'):
                    shares = company.shares_outstanding
                    if shares:
                        company_info["shares_outstanding"] = f"{shares:,.0f}"
                        print(f"[EDGAR] Shares Outstanding: {company_info['shares_outstanding']}")
            except Exception as e:
                print(f"[EDGAR] Error getting shares_outstanding: {e}")
            
            try:
                if hasattr(company, 'public_float'):
                    public_float = company.public_float
                    if public_float:
                        company_info["public_float"] = f"${public_float:,.0f}"
                        print(f"[EDGAR] Public Float: {company_info['public_float']}")
            except Exception as e:
                print(f"[EDGAR] Error getting public_float: {e}")
            
            # Get multi-year financial statements (5 years of data)
            print("[EDGAR] Fetching multi-year financial statements (5 years)...")
            
            # Income Statement - 5 years
            try:
                income_stmt = company.income_statement(periods=5, annual=True)
                if income_stmt:
                    print(f"[EDGAR] ✓ Income statement retrieved - {len(income_stmt.periods)} periods")
                    llm_context = income_stmt.to_llm_context(include_metadata=True)
                    
                    # Build temporary data structure for formatting
                    temp_data = {}
                    for item in income_stmt.iter_with_values():
                        temp_data[item.label] = {
                            'concept': item.concept,
                            'values': item.values,
                            'is_total': getattr(item, 'is_total', False)
                        }
                    
                    # Format for frontend consumption (no duplicate data stored)
                    company_info["income_statement"] = format_financials_for_frontend(
                        temp_data,
                        income_stmt.periods
                    )
                    
                    company_info["key_metrics"].update({
                        "income_statement_periods": len(income_stmt.periods),
                        **llm_context.get('key_metrics', {})
                    })
                    print(f"[EDGAR] Income statement: {len(income_stmt.periods)} periods, {len(temp_data)} line items")
            except Exception as e:
                print(f"[EDGAR] Error getting income statement: {e}")
            
            # Balance Sheet - 5 years
            try:
                balance_sheet = company.balance_sheet(periods=5, annual=True)
                if balance_sheet:
                    print(f"[EDGAR] ✓ Balance sheet retrieved - {len(balance_sheet.periods)} periods")
                    bs_context = balance_sheet.to_llm_context(include_metadata=True)
                    
                    # Build temporary data structure for formatting
                    temp_data = {}
                    for item in balance_sheet.iter_with_values():
                        temp_data[item.label] = {
                            'concept': item.concept,
                            'values': item.values,
                            'is_total': getattr(item, 'is_total', False)
                        }
                    
                    # Format for frontend consumption (no duplicate data stored)
                    company_info["balance_sheet"] = format_financials_for_frontend(
                        temp_data,
                        balance_sheet.periods
                    )
                    
                    company_info["key_metrics"].update({
                        "balance_sheet_periods": len(balance_sheet.periods),
                        **{f"bs_{k}": v for k, v in bs_context.get('key_metrics', {}).items()}
                    })
                    print(f"[EDGAR] Balance sheet: {len(balance_sheet.periods)} periods, {len(temp_data)} line items")
            except Exception as e:
                print(f"[EDGAR] Error getting balance sheet: {e}")
            
            # Cash Flow Statement - 5 years
            try:
                cash_flow = company.cash_flow(periods=5, annual=True)
                if cash_flow:
                    print(f"[EDGAR] ✓ Cash flow statement retrieved - {len(cash_flow.periods)} periods")
                    cf_context = cash_flow.to_llm_context(include_metadata=True)
                    
                    # Build temporary data structure for formatting
                    temp_data = {}
                    for item in cash_flow.iter_with_values():
                        temp_data[item.label] = {
                            'concept': item.concept,
                            'values': item.values,
                            'is_total': getattr(item, 'is_total', False)
                        }
                    
                    # Format for frontend consumption (no duplicate data stored)
                    company_info["cash_flow"] = format_financials_for_frontend(
                        temp_data,
                        cash_flow.periods
                    )
                    
                    company_info["key_metrics"].update({
                        "cash_flow_periods": len(cash_flow.periods),
                        **{f"cf_{k}": v for k, v in cf_context.get('key_metrics', {}).items()}
                    })
                    print(f"[EDGAR] Cash flow: {len(cash_flow.periods)} periods, {len(temp_data)} line items")
            except Exception as e:
                print(f"[EDGAR] Error getting cash flow: {e}")
        else:
            print("[EDGAR] ⚠️  No Facts API data available for this company")
        
        # Fetch latest filings with comprehensive metadata
        print("[EDGAR] Fetching recent filings with exhibits and metadata...")
        try:
            filings = company.get_filings(form=['10-K', '10-Q', '8-K'])
            
            if filings is not None:
                
                filing_count = 0
                for filing in filings:
                    if filing_count >= 5:
                        break
                    
                    try:
                        # Basic filing information
                        filing_data = {
                            "form": filing.form,
                            "filing_date": str(filing.filing_date),
                            "report_date": str(filing.report_date) if hasattr(filing, 'report_date') and filing.report_date else None,
                            "accession_number": filing.accession_no,
                            
                            # URLs
                            "url": filing.homepage_url,
                            "text_url": getattr(filing, 'text_url', None),
                            
                            # Documents
                            "primary_document": getattr(filing, 'primary_document', None),
                            
                            # SEC Metadata
                            "acceptance_datetime": str(filing.acceptance_datetime) if hasattr(filing, 'acceptance_datetime') and filing.acceptance_datetime else None,
                            "file_number": getattr(filing, 'file_number', None),
                            "film_number": getattr(filing, 'film_number', None),
                            
                            # 8-K specific items (why the filing was submitted)
                            "items": getattr(filing, 'items', None),
                            
                            # Technical details
                            "is_xbrl": getattr(filing, 'is_xbrl', False),
                            
                            # Exhibits and attachments
                            "exhibits": [],
                            "attachments": []
                        }
                        
                        # Extract exhibits/attachments if available
                        try:
                            if hasattr(filing, 'attachments') and filing.attachments:
                                for doc in filing.attachments:
                                    attachment_info = {
                                        "description": getattr(doc, 'description', None),
                                        "document": getattr(doc, 'document', None),
                                        "url": getattr(doc, 'url', None) if hasattr(doc, 'url') else None
                                    }
                                    
                                    # Categorize as exhibit or attachment based on description
                                    desc = str(attachment_info.get('description', '')).upper()
                                    
                                    if 'EX-' in desc or 'EXHIBIT' in desc:
                                        filing_data["exhibits"].append(attachment_info)
                                    else:
                                        filing_data["attachments"].append(attachment_info)
                        except Exception as attach_error:
                            print(f"[EDGAR] Warning: Could not extract attachments for {filing.form}: {attach_error}")
                        
                        company_info["latest_filings"].append(filing_data)
                        filing_count += 1
                        
                    except Exception as e:
                        print(f"[EDGAR] Error processing filing: {e}")
                        continue
            
            print(f"[EDGAR] Total filings retrieved: {len(company_info['latest_filings'])}")
            
        except Exception as e:
            print(f"[EDGAR] Error fetching filings: {e}")
            company_info["latest_filings"] = []
        
        # Fetch insiders data (Form 4 filings from last 6 months)
        print("[EDGAR] Fetching company insiders...")
        try:
            insiders_result = await get_company_insiders(ticker)
            company_info["insiders"] = insiders_result if insiders_result else []
            print(f"[EDGAR] Found {len(company_info['insiders'])} unique insiders")
        except Exception as e:
            print(f"[EDGAR] Error fetching insiders: {e}")
            company_info["insiders"] = []
            
        return company_info
        
    except Exception as e:
        print(f"[EDGAR] Error fetching EDGAR data for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return None


# Keep old function name for backward compatibility
async def identify_company_ticker(company_name: str) -> str | None:
    """
    Legacy function - use resolve_company_ticker() instead.
    Returns just the ticker string for backward compatibility.
    """
    ticker_info = await resolve_company_ticker(company_name)
    return ticker_info['ticker'] if ticker_info else None


async def get_company_insiders(ticker: str) -> list[dict] | None:
    """Get list of company insiders from Form 4 filings (past 6 months)."""
    try:
        from edgar import Company
        from datetime import datetime, timedelta
        
        try:
            from app.core.config import get_settings
            settings = get_settings()
            if settings.edgar_identity:
                from edgar import set_identity
                set_identity(settings.edgar_identity)
        except Exception:
            import os
            identity = os.getenv("EDGAR_IDENTITY", "Krawlr scraper contact@krawlr.com")
            from edgar import set_identity
            set_identity(identity)
        
        print(f"[EDGAR] Fetching insiders for ticker: {ticker}")
        
        date_range = (datetime.now() - timedelta(days=6*30)).strftime('%Y-%m-%d:')
        company = Company(ticker)
        filings = company.get_filings(form='4', filing_date=date_range)
        
        if not filings:
            return []
        
        insiders_data = []
        processed_count = 0
        
        for filing in filings:
            try:
                form4 = filing.obj()
                if not form4:
                    continue
                
                summary = form4.get_ownership_summary()
                if not summary:
                    continue
                
                df = summary.to_dataframe()
                if df is not None and not df.empty:
                    if 'Insider' in df.columns and 'Position' in df.columns:
                        for _, row in df[['Insider', 'Position']].iterrows():
                            insiders_data.append({
                                'insider': str(row['Insider']),
                                'position': str(row['Position'])
                            })
                        processed_count += 1
                
                if processed_count >= 20:
                    break
                    
            except Exception:
                continue
        
        # Remove duplicates
        seen = set()
        unique_insiders = []
        for insider_dict in insiders_data:
            key = (insider_dict['insider'], insider_dict['position'])
            if key not in seen:
                seen.add(key)
                unique_insiders.append(insider_dict)
        
        # Sort by position importance
        def position_priority(insider):
            position = insider['position'].lower()
            if 'chief executive officer' in position or position == 'ceo':
                return 0
            elif 'president' in position:
                return 1
            elif 'chief financial officer' in position or 'cfo' in position:
                return 2
            elif 'chief' in position and 'officer' in position:
                return 3
            elif 'svp' in position or 'senior vice president' in position:
                return 4
            elif 'vice president' in position or position.startswith('vp'):
                return 5
            elif 'director' in position:
                return 6
            else:
                return 7
        
        unique_insiders.sort(key=lambda x: (position_priority(x), x['position'], x['insider']))
        
        print(f"[EDGAR] Found {len(unique_insiders)} unique insiders")
        return unique_insiders
        
    except Exception as e:
        logger.error(f"Error fetching insiders for {ticker}: {e}")
        return None


def prepare_revenue_chart_data(financial_data: dict) -> dict | None:
    """Extract chart-ready data for Revenue, Gross Profit, and Net Income visualization."""
    try:
        income_data = financial_data.get("income_statement_data", {})
        periods = financial_data.get("income_periods", [])
        
        if not income_data or not periods:
            return None
        
        revenue_values = None
        gross_profit_values = None
        net_income_values = None
        
        for label, item_data in income_data.items():
            concept = item_data.get('concept', '')
            values = item_data.get('values', {})
            
            if not revenue_values and ('Revenue' in label or 'us-gaap_Revenues' in concept or 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax' in concept):
                revenue_values = values
            
            if not gross_profit_values and ('Gross Profit' in label or 'us-gaap_GrossProfit' in concept):
                gross_profit_values = values
            
            if not net_income_values and ('Net Income' in label or 'us-gaap_NetIncomeLoss' in concept):
                net_income_values = values
        
        if not revenue_values:
            return None
        
        chart_data = {
            "labels": [],
            "revenue": [],
            "gross_profit": [],
            "net_income": [],
            "periods": periods[::-1]
        }
        
        import pandas as pd
        for period in periods[::-1]:
            try:
                fy_label = pd.to_datetime(period).strftime('FY%y')
                chart_data["labels"].append(fy_label)
            except:
                chart_data["labels"].append(period[-4:])
        
        for period in periods[::-1]:
            rev_val = revenue_values.get(period, 0)
            chart_data["revenue"].append(round(rev_val / 1e9, 2) if rev_val else 0)
            
            gp_val = gross_profit_values.get(period, 0) if gross_profit_values else 0
            chart_data["gross_profit"].append(round(gp_val / 1e9, 2) if gp_val else 0)
            
            ni_val = net_income_values.get(period, 0) if net_income_values else 0
            chart_data["net_income"].append(round(ni_val / 1e9, 2) if ni_val else 0)
        
        return chart_data
        
    except Exception as e:
        print(f"[EDGAR] Error preparing chart data: {e}")
        return None


# Singleton instance for backward compatibility with orchestrator
class SECEdgarScraper:
    """Legacy wrapper for backward compatibility."""
    
    async def scrape_financials(self, company_name: str, ticker: str | None = None) -> dict:
        """
        Wrapper method for backward compatibility with orchestrator.
        Now uses company name as primary input.
        """
        # If ticker provided, use it directly
        if ticker:
            result = await get_company_financials(ticker)
            if result:
                return result
        
        # Otherwise use company name
        result = await get_company_financials_by_name(company_name)
        return result if result else {
            'company_name': company_name,
            'ticker': ticker,
            'error': 'Company not found or ticker could not be identified'
        }

# Create singleton instance
sec_edgar_scraper = SECEdgarScraper()

