# Krawlr API - Quick Start Guide

## 🚀 Starting the Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

Server will run at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

---

## 🔑 Authentication

All scraping endpoints require authentication. You must have a user account and JWT token.

### 1. Register a User

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "securepassword123"
  }'
```

### 2. Login to Get Token

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "...",
  "user": {
    "id": "user123",
    "email": "test@example.com",
    "name": "Test User"
  }
}
```

---

## 📊 Scraping Endpoints

### Start a New Scrape

```bash
curl -X POST http://localhost:8000/api/v1/scrape/company \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "url": "https://stripe.com",
    "company_name": "Stripe"
  }'
```

Response:
```json
{
  "scrape_id": "abc123-def456-ghi789",
  "status": "pending",
  "url": "https://stripe.com",
  "company_name": "Stripe",
  "message": "Scraping job started successfully...",
  "estimated_completion_seconds": 120
}
```

### Check Scrape Status

```bash
curl -X GET http://localhost:8000/api/v1/scrape/abc123-def456-ghi789/status \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "scrape_id": "abc123-def456-ghi789",
  "user_id": "user123",
  "status": "processing",
  "progress": 75,
  "url": "https://stripe.com",
  "company_name": "Stripe",
  "created_at": "2025-12-08T10:30:00Z",
  "updated_at": "2025-12-08T10:31:30Z",
  "data_quality_score": null
}
```

### Get Scrape Results

```bash
curl -X GET http://localhost:8000/api/v1/scrape/abc123-def456-ghi789 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response: Full company intelligence JSON with:
- Company profile
- Financial data
- Funding information
- Leadership team
- Products
- Competitors
- News mentions
- Online presence
- **AI-enriched and cleaned data**

### Get User's Scrape History

```bash
curl -X GET http://localhost:8000/api/v1/scrape/user/history?limit=20 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 🏥 Health Check

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-08T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "firestore": "healthy",
    "orchestrator": "healthy",
    "ai_enrichment": "healthy"
  }
}
```

---

## 📋 Scrape Status Values

- **`pending`**: Job is queued, not started yet
- **`processing`**: Currently scraping (check `progress` field 0-100)
- **`completed`**: Scraping finished successfully
- **`failed`**: Scraping encountered an error (check `error` field)

---

## 🎯 What Gets Scraped

The API scrapes and enriches data from multiple sources:

1. **Profile Data**: Wikipedia, Crunchbase, company website
2. **Website Analysis**: Content, structure, key pages
3. **Financial Data**: SEC EDGAR (public companies)
4. **Funding**: Crunchbase, news articles
5. **Leadership**: LinkedIn, Crunchbase, company pages
6. **Competitors**: Multiple sources
7. **News**: Recent mentions and articles
8. **AI Enrichment**: Cleans formatting, fills missing data, validates information

---

## ⚡ Performance

- **Average scrape time**: 120-140 seconds
- **Concurrent scrapers**: 6 running simultaneously
- **AI enrichment**: ~10-15 seconds additional
- **Data quality score**: 0-100 (tracked in metadata)

---

## 🔒 Security Features

- JWT-based authentication
- User-scoped data (users only see their own scrapes)
- URL validation and sanitization
- Rate limiting (planned)
- API key support (planned)

---

## 📚 API Documentation

Visit `http://localhost:8000/docs` for:
- Interactive API documentation
- Try out endpoints directly
- View request/response schemas
- Authentication setup

---

## 🐛 Troubleshooting

**Authentication Error**:
```
401 Unauthorized - User ID not found in authentication token
```
→ Make sure you're passing a valid JWT token in the `Authorization: Bearer <token>` header

**Scrape Not Found**:
```
404 Not Found - Scraping job not found
```
→ Check the `scrape_id` is correct

**Permission Denied**:
```
403 Forbidden - You don't have permission to access this scraping job
```
→ You can only access your own scrapes

**Job Not Completed**:
```
409 Conflict - Scraping job is not completed yet
```
→ Use the `/status` endpoint to check progress first
