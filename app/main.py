from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.live_score import router as live_score_router

app = FastAPI(
    title="Live Score API (Criczop Scraper)",
    version="2.0.0",
)

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
