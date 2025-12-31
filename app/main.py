from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.live_score import router as live_score_router

app = FastAPI(
    title="Live Score API (Criczop / ESPN Scraper)",
    version="1.1.0",
)

# Optional CORS (handy for frontend usage)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(live_score_router, prefix="")

@app.get("/healthz")
def healthz():
    return {"ok": True}
