# SnackStad Backend

FastAPI backend for the SnackStad AI concession agent system.

## Endpoints

| Method | Path | Agent |
|--------|------|-------|
| POST | /fan/location | Location Agent |
| POST | /queues/score | Queue Scout |
| POST | /inventory/check | Inventory Agent |
| POST | /order/suggest | Order Agent |
| POST | /route/calculate | Route Agent |
| POST | /edge/handle | Edge Case Handler |

## Deploy to Railway (5 minutes)

1. Go to https://railway.app and sign in with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select this repo
4. Railway auto-detects the Procfile and deploys
5. Click your deployment → "Settings" → copy the public URL
6. Replace `https://placeholder.aiamzing.com` with your URL in all Orchestrate tool JSONs

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs available at: http://localhost:8000/docs
