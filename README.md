# Live Score API (Criczop only)

FastAPI service that scrapes Criczop schedule pages and verifies LIVE matches by checking the match page itself.

## Endpoints

- `GET /healthz`
- `GET /live-score`
- `GET /live-score/{match_id}`

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Deploy to Render

This repo includes `render.yaml` and a `Dockerfile`.

1. Push to GitHub
2. Render → New → Blueprint → pick the repo
3. Deploy
