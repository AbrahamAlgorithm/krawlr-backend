from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from dotenv import load_dotenv
from app.api.routes import router as auth_router
from app.api.scraping_routes import router as scraping_router

# Load environment variables
load_dotenv()

# Security scheme for Swagger UI
security = HTTPBearer()

app = FastAPI(
    title="Krawlr Backend API",
    description="Company Intelligence Scraping API with AI Enrichment",
    version="1.0.0",
    swagger_ui_parameters={
        "persistAuthorization": True,
    }
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(scraping_router, tags=["Scraping"])

@app.get("/")
async def root():
    return {
        "message": "Krawlr Backend API is running",
        "status": "healthy",
        "version": "1.0.0",
        "docs": "/docs"
    }