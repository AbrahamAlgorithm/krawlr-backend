# Pub/Sub Queue System - Deployment Guide

## 🚀 High-Performance Async Architecture

Your application now uses **Google Cloud Pub/Sub** for massive speed and scalability:

- ✅ **Instant API responses** (< 1 second) - jobs queued immediately
- ✅ **Horizontal scaling** - run multiple workers in parallel
- ✅ **Guaranteed delivery** - jobs never lost, automatic retries
- ✅ **Real-time progress** - live updates via progress topic
- ✅ **Webhooks** - notify your systems when scrapes complete

## 📋 Architecture Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /api/v1/scrape/company
       ▼
┌─────────────────┐
│   FastAPI API   │ ◄── Returns job_id instantly
└────────┬────────┘
         │ Publishes to Pub/Sub
         ▼
   ┌──────────────┐
   │ scrape-jobs  │ ◄── Pub/Sub Topic
   │    Queue     │
   └──────┬───────┘
          │
    ┌─────┴─────┬─────────┬─────────┐
    ▼           ▼         ▼         ▼
┌────────┐  ┌────────┐ ┌────────┐ ┌────────┐
│Worker 1│  │Worker 2│ │Worker 3│ │Worker N│  ◄── Scale to N workers
└────┬───┘  └────┬───┘ └────┬───┘ └────┬───┘
     │           │          │          │
     └───────────┴──────────┴──────────┘
                 │
                 ▼
         ┌───────────────┐
         │   Firestore   │ ◄── Job status + Results
         └───────────────┘
                 │
                 ▼
    ┌────────────────────────┐
    │  scrape-completed      │ ◄── Pub/Sub Topic
    │       Topic            │
    └────────┬───────────────┘
             │
             ▼
    ┌─────────────────┐
    │ Webhook Service │ ◄── Sends HTTP webhooks
    └─────────────────┘
```

## 🛠️ Setup Instructions

### 1. Install Dependencies

```bash
pip install google-cloud-pubsub
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Google Cloud Project
GCP_PROJECT_ID=your-project-id

# Pub/Sub Topics (optional - defaults provided)
PUBSUB_SCRAPE_JOBS_TOPIC=scrape-jobs
PUBSUB_SCRAPE_COMPLETED_TOPIC=scrape-completed
PUBSUB_SCRAPE_PROGRESS_TOPIC=scrape-progress
```

### 3. Setup Pub/Sub Infrastructure

Run once to create topics and subscriptions:

```bash
python setup_pubsub.py
```

### 4. Start Services

**Terminal 1 - API Server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Worker (Process scrape jobs):**
```bash
python worker.py
```

**Terminal 3 - Webhook Service (Send notifications):**
```bash
python webhook_service.py
```

## 📊 How It Works

### Submit Scrape Job (Client)

```bash
POST /api/v1/scrape/company
Authorization: Bearer YOUR_TOKEN

{
  "url": "https://stripe.com"
}

Response (< 1 second):
{
  "scrape_id": "abc-123-def",
  "status": "queued",
  "message": "Job queued successfully!"
}
```

### Check Status (Poll every 2-3 seconds)

```bash
GET /api/v1/scrape/status/abc-123-def

Response:
{
  "job_id": "abc-123-def",
  "status": "processing",
  "progress_percent": 50,
  "current_stage": "financial",
  "duration_seconds": 45
}
```

### Get Results (When complete)

```bash
GET /api/v1/scrape/abc-123-def

Response:
{
  "company": {...},
  "financials": {...},
  "funding": {...},
  ...
}
```

## 🔥 Production Deployment

### Docker Compose (Recommended)

```yaml
version: '3.8'

services:
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    environment:
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
    volumes:
      - ./credentials.json:/app/credentials.json
  
  worker:
    build: .
    command: python worker.py
    deploy:
      replicas: 3  # Scale workers
    environment:
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
    volumes:
      - ./credentials.json:/app/credentials.json
  
  webhook:
    build: .
    command: python webhook_service.py
    environment:
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
    volumes:
      - ./credentials.json:/app/credentials.json
```

Start with:
```bash
docker-compose up -d --scale worker=5
```

### Kubernetes (For massive scale)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scrape-worker
spec:
  replicas: 10  # Scale to 10+ workers
  selector:
    matchLabels:
      app: scrape-worker
  template:
    metadata:
      labels:
        app: scrape-worker
    spec:
      containers:
      - name: worker
        image: gcr.io/YOUR_PROJECT/krawlr-worker:latest
        command: ["python", "worker.py"]
        env:
        - name: GCP_PROJECT_ID
          value: "your-project-id"
        resources:
          requests:
            cpu: "1"
            memory: "2Gi"
          limits:
            cpu: "2"
            memory: "4Gi"
```

## 📈 Performance Metrics

### Before Pub/Sub (FastAPI BackgroundTasks)
- ⏱️ API response: 60-120 seconds (blocked)
- 🔄 Concurrency: Limited by server workers
- 💥 Failures: Jobs lost on server restart
- 📊 Scale: Vertical only (bigger server)

### After Pub/Sub
- ⚡ API response: < 1 second (queued)
- 🔄 Concurrency: Unlimited (N workers)
- ✅ Failures: Automatic retry + durability
- 📊 Scale: Horizontal (add more workers)

### Example Throughput

**Single worker:**
- 90 seconds per scrape
- ~40 scrapes/hour
- ~960 scrapes/day

**10 workers:**
- 90 seconds per scrape (parallel)
- ~400 scrapes/hour
- ~9,600 scrapes/day

**100 workers:**
- ~4,000 scrapes/hour
- ~96,000 scrapes/day

## 🔧 Monitoring

### Check Queue Depth

```bash
gcloud pubsub topics list
gcloud pubsub subscriptions list
```

### View Worker Logs

```bash
# Local
tail -f worker.log

# Docker
docker logs -f worker-1

# Kubernetes
kubectl logs -f deployment/scrape-worker
```

### Cloud Monitoring (GCP)

- Pub/Sub metrics: https://console.cloud.google.com/cloudpubsub
- Set alerts for:
  - Queue depth > 100 (scale up workers)
  - Old unacked messages (worker issues)
  - Failed delivery attempts (investigate errors)

## 🎯 Auto-Scaling

### Cloud Run (Serverless Workers)

Deploy workers as Cloud Run service with:
- Min instances: 0 (cost-effective)
- Max instances: 100 (massive scale)
- Pub/Sub trigger: Auto-scales based on queue

```bash
gcloud run deploy scrape-worker \
  --image gcr.io/YOUR_PROJECT/worker:latest \
  --memory 2Gi \
  --timeout 600s \
  --min-instances 0 \
  --max-instances 100 \
  --set-env-vars GCP_PROJECT_ID=your-project
```

## 🔒 Security

1. **Service Account**: Create dedicated service account with Pub/Sub permissions
2. **IAM Roles**:
   - `roles/pubsub.publisher` (API server)
   - `roles/pubsub.subscriber` (Workers, webhook service)
3. **Firestore Rules**: Ensure workers can read/write job data
4. **Webhook Signatures**: Add HMAC signatures to webhooks for verification

## 🐛 Troubleshooting

### Jobs not processing
- Check worker is running: `ps aux | grep worker.py`
- Check Pub/Sub subscription exists
- Verify service account permissions

### Slow processing
- Scale up workers: `docker-compose up -d --scale worker=10`
- Check worker logs for errors
- Monitor Cloud Logging

### Messages stuck in queue
- Check ack deadline (default: 600 seconds = 10 minutes)
- Investigate worker errors
- May need to purge and resubmit

## 📚 API Reference

### Job Status Values

- `queued`: In Pub/Sub queue, waiting for worker
- `processing`: Worker is scraping
- `completed`: Success, result available
- `failed`: Error occurred
- `retrying`: Failed but will retry

### Progress Stages

- `starting`: Worker picked up job
- `profile`: Scraping company profile
- `website`: Analyzing website
- `financial`: Fetching financial data
- `news`: Gathering news
- `enrichment`: AI processing
- `saving`: Storing results
- `completed`: Done

## 🎉 Benefits Summary

✅ **10-100x faster** API responses
✅ **Unlimited** concurrent scrapes
✅ **Guaranteed** job completion
✅ **Auto-retry** on failures
✅ **Real-time** progress tracking
✅ **Webhook** notifications
✅ **Horizontal** scaling
✅ **Cost-effective** (pay per use)

---

**Ready to scale!** 🚀
