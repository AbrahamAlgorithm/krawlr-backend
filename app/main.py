from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Krawlr Backend API")

app.include_router(router, tags=["Authentication"])

@app.get("/")
async def root():
    return {"message": "Krawlr Backend API is running", "status": "healthy"}