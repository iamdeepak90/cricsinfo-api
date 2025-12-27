import httpx
from app.core.config import settings

def default_headers() -> dict[str, str]:
    return {
        "User-Agent": settings.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

async def fetch_text(url: str) -> str:
    timeout = httpx.Timeout(settings.FETCH_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, headers=default_headers(), follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text
