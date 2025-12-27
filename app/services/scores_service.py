from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

from app.core.cache import cache
from app.core.config import settings
from app.models.schemas import (
    Match,
    MatchListResponse,
    MatchDetailResponse,
    MatchStatus,
)
from app.sources.cricinfo_rss import CricinfoRSSSource
from app.sources.cricinfo_desktop import CricinfoDesktopSource
from app.sources.espn_scores import ESPNScoreboardSource

def _tz(tz_name: Optional[str]) -> ZoneInfo:
    return ZoneInfo(tz_name or settings.TZ)

def _today(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()

def _is_today_match(m: Match, today: date) -> bool:
    if m.start_date and m.end_date:
        return m.start_date <= today <= m.end_date
    if m.start_date:
        return m.start_date == today
    return True  # unknown -> allow in "today bucket" heuristically

def _merge(old: Match, new: Match) -> Match:
    # Prefer fields that are present, and prefer non-UNKNOWN status
    data = old.model_dump()
    nd = new.model_dump()
    for k, v in nd.items():
        if v is None:
            continue
        if k == "status":
            if data.get("status") == MatchStatus.UNKNOWN and v != MatchStatus.UNKNOWN:
                data[k] = v
        else:
            if data.get(k) is None or (isinstance(data.get(k), str) and not data.get(k)):
                data[k] = v
    # Always keep a URL that works (new might be better)
    data["url"] = nd.get("url") or data["url"]
    data["source"] = nd.get("source") or data["source"]
    return Match(**data)

class ScoresService:
    def __init__(self):
        self.rss = CricinfoRSSSource()
        self.desktop = CricinfoDesktopSource()
        self.espn = ESPNScoreboardSource()

    async def _fetch_all_sources(self) -> List[Match]:
        # Try multiple sources and merge
        sources = [self.rss, self.desktop, self.espn]
        merged: Dict[int, Match] = {}

        for src in sources:
            try:
                matches = await src.fetch_matches()
            except Exception:
                matches = []
            for m in matches:
                if m.match_id in merged:
                    merged[m.match_id] = _merge(merged[m.match_id], m)
                else:
                    merged[m.match_id] = m

        return list(merged.values())

    async def get_match_list(self, timezone: Optional[str] = None) -> MatchListResponse:
        tz = _tz(timezone)
        today = _today(tz)

        cache_key = f"list:{tz.key}:{today.isoformat()}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        all_matches = await self._fetch_all_sources()

        # Save match_id -> url for detail endpoint
        url_map = {m.match_id: m.url for m in all_matches if m.url}
        cache.set(f"urlmap:{tz.key}", url_map, ttl_seconds=3600)

        today_matches = [m for m in all_matches if _is_today_match(m, today)]
        live = [m for m in today_matches if m.status == MatchStatus.LIVE]
        upcoming = [m for m in today_matches if m.status == MatchStatus.UPCOMING]
        results_today = [m for m in today_matches if m.status == MatchStatus.RESULT]

        # Determine "no match today"
        has_any_today = len(today_matches) > 0

        # If no match today: pick 5 recent results + 5 upcoming from all_matches
        recent: List[Match] = []
        future: List[Match] = []

        if not has_any_today:
            past = [m for m in all_matches if (m.end_date and m.end_date < today) or (m.start_date and m.start_date < today and m.status == MatchStatus.RESULT)]
            past_sorted = sorted(past, key=lambda x: (x.end_date or x.start_date or date(1970,1,1)), reverse=True)
            recent = past_sorted[:5]

            fut = [m for m in all_matches if (m.start_date and m.start_date > today) or (m.status == MatchStatus.UPCOMING)]
            fut_sorted = sorted(fut, key=lambda x: (x.start_date or date(9999,1,1)))
            future = fut_sorted[:5]

            items = recent + future
            mode = "mixed"

        else:
            # Ordering rules:
            # 1) If live exists: show live first, then upcoming, then results
            # 2) If no live but upcoming exists: show upcoming (then results)
            # 3) Else show whatever we have
            if live:
                items = live + upcoming + results_today
                mode = "live"
            elif upcoming:
                items = upcoming + results_today
                mode = "upcoming"
            else:
                items = results_today
                mode = "mixed"

        resp = MatchListResponse(
            mode=mode,
            timezone=tz.key,
            generated_at=datetime.now(tz),
            items=items,
            live=live,
            upcoming=upcoming if has_any_today else future,
            recent=recent,
        )

        cache.set(cache_key, resp, ttl_seconds=settings.LIST_CACHE_TTL_SECONDS)
        return resp

    async def get_match_detail(self, match_id: int, timezone: Optional[str] = None) -> Optional[MatchDetailResponse]:
        tz = _tz(timezone)
        cache_key = f"detail:{tz.key}:{match_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # Resolve match url (best-effort)
        url_map = cache.get(f"urlmap:{tz.key}") or {}
        match_url = url_map.get(match_id)

        # If url not known, refresh list once and try again
        if not match_url:
            _ = await self.get_match_list(timezone=tz.key)
            url_map = cache.get(f"urlmap:{tz.key}") or {}
            match_url = url_map.get(match_id)

        if not match_url:
            return None

        # Build a minimal Match object (you can expand scraping later)
        match = Match(match_id=match_id, source="resolved", url=match_url)

        excerpt = None
        try:
            excerpt = await self.espn.fetch_match_detail_excerpt(match_url)
        except Exception:
            excerpt = None

        resp = MatchDetailResponse(
            match=match,
            fetched_at=datetime.now(tz),
            timezone=tz.key,
            raw_text_excerpt=excerpt,
        )
        cache.set(cache_key, resp, ttl_seconds=settings.DETAIL_CACHE_TTL_SECONDS)
        return resp
