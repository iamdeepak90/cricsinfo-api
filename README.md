# Live Score API (FastAPI + BeautifulSoup)

A robust live-score scraper API that prefers ESPNcricinfo RSS feed and falls back to HTML scraping.

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

Render will run:

```
gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT
```

## Notes

- Scraping can be rate-limited; basic TTL caching is included.
- Output fields are best-effort and may vary by source availability.
