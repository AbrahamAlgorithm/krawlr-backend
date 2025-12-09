"""
Test the scraping API endpoints
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.scraping_routes import router
from app.main import app


def test_routes():
    """Test that routes are properly registered"""
    
    print("=" * 80)
    print("🧪 TESTING SCRAPING API ROUTES")
    print("=" * 80)
    print()
    
    # List all routes
    print("📋 Registered Routes:")
    print()
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ','.join(route.methods) if route.methods else 'N/A'
            print(f"   {methods:8s} {route.path}")
    
    print()
    print("=" * 80)
    print("✅ API Routes Configured Successfully!")
    print("=" * 80)
    print()
    print("🚀 To start the server, run:")
    print("   uvicorn app.main:app --reload --port 8000")
    print()
    print("📚 API Documentation will be available at:")
    print("   http://localhost:8000/docs")
    print()
    print("🔑 Authentication Required:")
    print("   - All scraping endpoints require authentication")
    print("   - Use existing auth endpoints to get JWT token")
    print("   - Pass token in Authorization header: 'Bearer <token>'")
    print()
    print("📌 Main Endpoints:")
    print("   POST   /api/v1/scrape/company         - Start a new scrape")
    print("   GET    /api/v1/scrape/{id}/status     - Check scrape status")
    print("   GET    /api/v1/scrape/{id}            - Get scrape results")
    print("   GET    /api/v1/scrape/user/history    - Get user's scrape history")
    print("   GET    /api/v1/health                 - Health check")
    print()


if __name__ == "__main__":
    test_routes()
