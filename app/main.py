from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes import router

# Load environment variables
load_dotenv()

app = FastAPI(title="Krawlr Backend API")

app.include_router(router, tags=["Authentication"])

@app.get("/")
async def root():
    return {"message": "Krawlr Backend API is running", "status": "healthy"}