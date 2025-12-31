from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional, Dict, List

from app.core.cache import cache
from app.core.config import settings
from app.models.schemas import Match, MatchListResponse, MatchDetailResponse, MatchStatus
from app.sources.criczop import CriczopSource, fetch_match_page

def _tz(tz_name: Optional[str]) -> ZoneInfo:
    return ZoneInfo(tz_name or settings.TZ)

def _today(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()

def _is_today(m: Match, today: date) -> bool:
    if m.start_date:
        return m.start_date == today
    return True

class ScoresService:
    def __init__(self):
        self.criczop = CriczopSource()

    async def get_match_list(self, timezone: Optional[str] = None) -> MatchListResponse:
        tz = _tz(timezone)
        today = _today(tz)

        cache_key = f"list:{tz.key}:{today.isoformat()}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        lists = await self.criczop.fetch_lists()

        live = await self.criczop.fetch_live_verified(lists.live_urls)
        upcoming = await self.criczop.build_upcoming(lists.upcoming_urls)
        results = await self.criczop.build_results(lists.result_urls)

        url_map: Dict[int, str] = {}
        for m in (live + upcoming + results):
            url_map[m.match_id] = m.url
        cache.set(f"urlmap:{tz.key}", url_map, ttl_seconds=3600)

        live_today = [m for m in live if _is_today(m, today)]

        mode = "mixed"
        items: List[Match] = []

        if live_today:
            mode = "live"
            items = live_today + [m for m in upcoming if _is_today(m, today)] + [m for m in results if _is_today(m, today)]
        else:
            upcoming_today = [m for m in upcoming if _is_today(m, today)]
            if upcoming_today:
                mode = "upcoming"
                items = upcoming_today
            else:
                mode = "mixed"
                items = results[:5] + upcoming[:5]

        resp = MatchListResponse(
            mode=mode,
            timezone=tz.key,
            generated_at=datetime.now(tz),
            items=items,
            live=live_today,
            upcoming=upcoming,
            results=results,
        )
        cache.set(cache_key, resp, ttl_seconds=settings.LIST_CACHE_TTL_SECONDS)
        return resp

    async def get_match_detail(self, match_id: int, timezone: Optional[str] = None) -> Optional[MatchDetailResponse]:
        tz = _tz(timezone)
        cache_key = f"detail:{tz.key}:{match_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        url_map = cache.get(f"urlmap:{tz.key}") or {}
        match_url = url_map.get(match_id)
        if not match_url:
            await self.get_match_list(timezone=tz.key)
            url_map = cache.get(f"urlmap:{tz.key}") or {}
            match_url = url_map.get(match_id)

        if not match_url:
            return None

        parsed = await fetch_match_page(match_url)
        if parsed:
            status, title, series, ex = parsed
        else:
            status, title, series, ex = MatchStatus.UNKNOWN, None, None, ""

        match = Match(
            match_id=match_id,
            source="criczop",
            url=match_url,
            status=status,
            title=title,
            series=series,
            score_summary=ex[:600] if status == MatchStatus.LIVE else None,
            result_summary=ex[:400] if status == MatchStatus.RESULT else None,
        )

        resp = MatchDetailResponse(
            match=match,
            fetched_at=datetime.now(tz),
            timezone=tz.key,
            raw_text_excerpt=ex[:1200] if ex else None,
        )
        cache.set(cache_key, resp, ttl_seconds=settings.DETAIL_CACHE_TTL_SECONDS)
        return resp
