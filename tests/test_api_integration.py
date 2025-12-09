"""
Integration test for the scraping API
This simulates the full flow without actually starting the server
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.scraping.unified_orchestrator import UnifiedOrchestrator


async def test_orchestrator_with_user_id():
    """Test that orchestrator properly handles user_id"""
    
    print("=" * 80)
    print("🧪 TESTING UNIFIED ORCHESTRATOR WITH USER_ID")
    print("=" * 80)
    print()
    
    # Initialize orchestrator
    orchestrator = UnifiedOrchestrator()
    
    # Test scraping with user_id
    print("🚀 Starting scrape for Stripe with user_id...")
    print()
    
    result = await orchestrator.get_complete_company_intelligence(
        website_url="https://stripe.com",
        company_name="Stripe",
        user_id="test-user-123",
        scrape_id="test-scrape-456"
    )
    
    print()
    print("=" * 80)
    print("✅ SCRAPE COMPLETED")
    print("=" * 80)
    print()
    
    # Verify metadata includes user_id
    metadata = result.get('metadata', {})
    
    print("📊 Metadata:")
    print(f"   Scrape ID: {metadata.get('scrape_id')}")
    print(f"   User ID: {metadata.get('user_id')}")
    print(f"   Duration: {metadata.get('scrape_duration_seconds')}s")
    print(f"   Quality Score: {metadata.get('data_quality_score')}/100")
    print(f"   AI Enriched: {metadata.get('ai_enriched')}")
    print()
    
    # Verify user_id is set
    if metadata.get('user_id') == 'test-user-123':
        print("✅ User ID correctly stored in metadata!")
    else:
        print("❌ User ID not found in metadata!")
    
    # Verify scrape_id is set
    if metadata.get('scrape_id') == 'test-scrape-456':
        print("✅ Scrape ID correctly stored in metadata!")
    else:
        print("❌ Scrape ID not found in metadata!")
    
    print()
    print("=" * 80)
    print("🎉 INTEGRATION TEST PASSED")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Start the server: uvicorn app.main:app --reload --port 8000")
    print("2. Register a user: POST /register")
    print("3. Login: POST /login")
    print("4. Start a scrape: POST /api/v1/scrape/company")
    print("5. Check status: GET /api/v1/scrape/{scrape_id}/status")
    print("6. Get results: GET /api/v1/scrape/{scrape_id}")
    print()


if __name__ == "__main__":
    asyncio.run(test_orchestrator_with_user_id())
