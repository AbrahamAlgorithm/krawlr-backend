"""
AI Enrichment Service using OpenAI
Cleans, formats, and fills missing data in scraped company intelligence
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime

from openai import AsyncOpenAI
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


async def enrich_company_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use OpenAI to enrich and clean company data.
    
    This function:
    1. Fills in missing fields (nulls, empty strings, empty arrays)
    2. Formats messy data (dates, numbers, addresses)
    3. Validates and corrects information
    4. Adds missing details using AI knowledge
    
    Args:
        raw_data: Raw scraped company intelligence data
        
    Returns:
        Enriched and cleaned company data
    """
    if not client:
        logger.warning("OpenAI API key not configured. Skipping AI enrichment.")
        return raw_data
    
    logger.info(f"🤖 Starting AI enrichment for: {raw_data.get('company', {}).get('name', 'Unknown')}")
    
    try:
        # Prepare the data summary for AI
        data_summary = _prepare_data_summary(raw_data)
        
        # Build the enrichment prompt
        prompt = _build_enrichment_prompt(raw_data, data_summary)
        
        # Call OpenAI API
        logger.info("📡 Sending request to OpenAI GPT-4...")
        response = await client.chat.completions.create(
            model="gpt-4o",  # Using GPT-4 Optimized for best results
            messages=[
                {
                    "role": "system",
                    "content": """You are a business intelligence data enrichment specialist. Your job is to:
1. Fill in missing data fields using your knowledge
2. Clean and format messy data (dates, numbers, addresses)
3. Validate and correct information
4. Never make up data - only fill in what you're confident about
5. Always return valid JSON matching the exact schema provided
6. For dates, use ISO format (YYYY-MM-DD) or just year (YYYY)
7. For numbers, use proper numeric types (not strings)
8. For arrays, ensure they're not empty if data is available
9. Clean up formatting issues (unicode characters, extra spaces, etc.)"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more factual responses
            response_format={"type": "json_object"}
        )
        
        # Parse the AI response
        enriched_json = response.choices[0].message.content
        enriched_data = json.loads(enriched_json)
        
        logger.info("✅ AI enrichment completed successfully")
        
        # Log what was improved
        _log_improvements(raw_data, enriched_data)
        
        return enriched_data
        
    except Exception as e:
        logger.error(f"❌ AI enrichment failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        # Return original data if enrichment fails
        return raw_data


def _prepare_data_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a summary of what data is missing or needs improvement."""
    summary = {
        "company_name": data.get("company", {}).get("name"),
        "missing_fields": [],
        "messy_fields": [],
        "empty_arrays": []
    }
    
    # Check company section
    company = data.get("company", {})
    for field, value in company.items():
        if value is None or value == "":
            summary["missing_fields"].append(f"company.{field}")
        elif isinstance(value, str) and len(value) > 100 and ("\u00a0" in value or "[" in value):
            summary["messy_fields"].append(f"company.{field}")
    
    # Check for empty arrays
    if not data.get("people", {}).get("founders"):
        summary["empty_arrays"].append("people.founders")
    if not data.get("people", {}).get("executives"):
        summary["empty_arrays"].append("people.executives")
    if not data.get("products"):
        summary["empty_arrays"].append("products")
    if not data.get("competitors"):
        summary["empty_arrays"].append("competitors")
    
    # Check funding
    funding = data.get("funding", {})
    if funding.get("total_raised_usd") == 0:
        summary["missing_fields"].append("funding.total_raised_usd")
    if not funding.get("investors"):
        summary["empty_arrays"].append("funding.investors")
    
    # Check financials
    financials = data.get("financials", {})
    if not financials.get("valuation"):
        summary["missing_fields"].append("financials.valuation")
    
    # Check online presence
    online = data.get("online_presence", {})
    if not online.get("social_media"):
        summary["missing_fields"].append("online_presence.social_media")
    if not online.get("contact_info", {}).get("emails"):
        summary["empty_arrays"].append("online_presence.contact_info.emails")
    
    return summary


def _build_enrichment_prompt(data: Dict[str, Any], summary: Dict[str, Any]) -> str:
    """Build the enrichment prompt for OpenAI."""
    
    company_name = summary["company_name"]
    
    prompt = f"""I have scraped company intelligence data for "{company_name}" that needs cleaning and enrichment.

**YOUR TASK:**
1. Fill in missing fields (currently null or empty)
2. Clean messy formatting (especially dates, addresses, industry labels)
3. Add missing social media handles if you know them
4. Format numbers properly (founded_year should be just YYYY, not full text)
5. Add valuation data if publicly known
6. Add investors, founders, executives if known
7. Keep all existing good data unchanged
8. Return the COMPLETE enriched JSON (all sections included)

**ISSUES FOUND:**
- Missing fields: {', '.join(summary['missing_fields'][:10])}
- Messy formatting: {', '.join(summary['messy_fields'][:5])}
- Empty arrays: {', '.join(summary['empty_arrays'][:10])}

**CURRENT DATA:**
```json
{json.dumps(data, indent=2)}
```

**INSTRUCTIONS:**
- For "founded_year": extract just the year as integer (e.g., 1998 not "September 4, 1998; 27 years ago...")
- For "industry": clean up concatenated text (e.g., "InternetCloud computing" → "Internet, Cloud Computing")
- For social_media: add handles if you know them (twitter, linkedin, facebook, etc.)
- For empty founders/executives: add if publicly known
- For valuation: add if company has known valuation
- For investors: add major investors if known
- For competitors: add 3-5 main competitors if missing
- For contact_info: format properly (clean emails, phones)
- Keep metadata section unchanged
- Remove unicode artifacts (\u00a0, etc.)

**IMPORTANT:**
- Return valid JSON only
- Include ALL sections from original data
- Don't remove any existing good data
- Only add data you're confident about
- Use proper data types (numbers as numbers, not strings)

Return the complete enriched JSON now:"""
    
    return prompt


def _log_improvements(original: Dict[str, Any], enriched: Dict[str, Any]) -> None:
    """Log what improvements were made by AI."""
    improvements = []
    
    # Check company fields
    orig_company = original.get("company", {})
    enr_company = enriched.get("company", {})
    
    if orig_company.get("founded_year") != enr_company.get("founded_year"):
        improvements.append(f"✓ Cleaned founded_year: '{orig_company.get('founded_year')}' → '{enr_company.get('founded_year')}'")
    
    if orig_company.get("industry") != enr_company.get("industry"):
        improvements.append(f"✓ Cleaned industry formatting")
    
    # Check if arrays were filled
    if not original.get("people", {}).get("founders") and enriched.get("people", {}).get("founders"):
        count = len(enriched["people"]["founders"])
        improvements.append(f"✓ Added {count} founders")
    
    if not original.get("competitors") and enriched.get("competitors"):
        count = len(enriched["competitors"])
        improvements.append(f"✓ Added {count} competitors")
    
    if not original.get("products") and enriched.get("products"):
        count = len(enriched["products"])
        improvements.append(f"✓ Added {count} products")
    
    # Check funding
    orig_funding = original.get("funding", {}).get("total_raised_usd", 0)
    enr_funding = enriched.get("funding", {}).get("total_raised_usd", 0)
    if orig_funding == 0 and enr_funding > 0:
        improvements.append(f"✓ Added funding: ${enr_funding:,}")
    
    # Check valuation
    if not original.get("financials", {}).get("valuation") and enriched.get("financials", {}).get("valuation"):
        improvements.append(f"✓ Added valuation data")
    
    # Check social media
    orig_social = len(original.get("online_presence", {}).get("social_media", {}))
    enr_social = len(enriched.get("online_presence", {}).get("social_media", {}))
    if enr_social > orig_social:
        improvements.append(f"✓ Added {enr_social - orig_social} social media handles")
    
    # Log improvements
    if improvements:
        logger.info("📊 AI Improvements:")
        for improvement in improvements:
            logger.info(f"   {improvement}")
    else:
        logger.info("   No significant changes made (data was already clean)")


# Public API
__all__ = ['enrich_company_data']
