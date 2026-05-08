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



## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs available at: http://localhost:8000/docs
