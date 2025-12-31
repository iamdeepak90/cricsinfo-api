import asyncio
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.http import fetch_text
from app.models.schemas import Match, MatchStatus
from app.sources.parsing import make_uid, date_from_criczop_url


BASE = "https://www.criczop.com"
LIVE_LIST_URL = f"{BASE}/live-cricket-score"
UPCOMING_LIST_URL = f"{BASE}/cricket-schedule"
RESULTS_LIST_URL = f"{BASE}/cricket-match-results"


def _normalize_url(url: str) -> str:
    p = urlparse(url)
    scheme = "https"
    netloc = p.netloc or urlparse(BASE).netloc
    return urlunparse((scheme, netloc, p.path.rstrip("/"), "", "", ""))


def _is_match_url(url: str) -> bool:
    u = url.lower()
    if "dream-11" in u or "team-prediction" in u:
        return False
    if "/live-cricket-score/" in u and (u.endswith("/match-scorecard") or u.endswith("/match-info")):
        return True
    if "/scorecard/" in u:
        return True
    return False


def _urls_from_next_data(html: str) -> Set[str]:
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return set()
    try:
        data = json.loads(script.string)
    except Exception:
        return set()

    found: Set[str] = set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            if "/live-cricket-score/" in x or "/scorecard/" in x:
                url = x if x.startswith("http") else urljoin(BASE, x)
                url = _normalize_url(url)
                if _is_match_url(url):
                    found.add(url)

    walk(data)
    return found


def _urls_from_main_links(html: str) -> Set[str]:
    soup = BeautifulSoup(html, "lxml")
    root = soup.find("main") or soup.body or soup
    urls: Set[str] = set()
    for a in root.find_all("a", href=True):
        href = a["href"]
        url = href if href.startswith("http") else urljoin(BASE, href)
        url = _normalize_url(url)
        if _is_match_url(url):
            urls.add(url)
    return urls


def extract_match_urls(html: str) -> List[str]:
    urls = set()
    urls |= _urls_from_next_data(html)
    urls |= _urls_from_main_links(html)

    if not urls:
        for m in re.finditer(r"/(?:live-cricket-score|scorecard)/[^\"'\s<>]+", html, flags=re.IGNORECASE):
            url = _normalize_url(urljoin(BASE, m.group(0)))
            if _is_match_url(url):
                urls.add(url)

    return sorted(urls)


def parse_heading_title_series(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    h1 = soup.find("h1")
    if not h1:
        return None, None
    heading = h1.get_text(" ", strip=True)
    if "Live Scores:" in heading:
        left, right = heading.split("Live Scores:", 1)
        title = left.replace("#", "").strip().rstrip(":")
        series = right.strip()
        return title, series
    return heading, None


def classify_from_match_page(html: str, soup: BeautifulSoup) -> MatchStatus:
    text = soup.get_text(" ", strip=True).lower()
    if "match yet to start" in text:
        return MatchStatus.UPCOMING
    if "winning-indicator" in html.lower() or "won by" in text or "match drawn" in text or "no result" in text:
        return MatchStatus.RESULT
    if "● live" in text or "\u25cf live" in html.lower():
        return MatchStatus.LIVE
    return MatchStatus.UNKNOWN


def excerpt_top(soup: BeautifulSoup, max_lines: int = 35) -> str:
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    stop_tokens = {"Batting Scorecard", "Bowling Scorecard", "Fall of Wickets"}
    cut = len(lines)
    for i, ln in enumerate(lines):
        if any(t.lower() in ln.lower() for t in stop_tokens):
            cut = i
            break
    lines = lines[:cut]
    return "\n".join(lines[:max_lines])


async def fetch_match_page(url: str) -> Optional[tuple[MatchStatus, Optional[str], Optional[str], str]]:
    try:
        html = await fetch_text(url)
    except Exception:
        return None
    soup = BeautifulSoup(html, "lxml")
    status = classify_from_match_page(html, soup)
    title, series = parse_heading_title_series(soup)
    ex = excerpt_top(soup, max_lines=35)
    return status, title, series, ex


@dataclass
class CriczopLists:
    live_urls: List[str]
    upcoming_urls: List[str]
    result_urls: List[str]


class CriczopSource:
    name = "criczop"

    async def fetch_lists(self) -> CriczopLists:
        live_html = await fetch_text(LIVE_LIST_URL)
        up_html = await fetch_text(UPCOMING_LIST_URL)
        res_html = await fetch_text(RESULTS_LIST_URL)

        live_urls = [u for u in extract_match_urls(live_html) if u.endswith("/match-scorecard") or "/scorecard/" in u]
        upcoming_urls = [u for u in extract_match_urls(up_html) if u.endswith("/match-info")]
        result_urls = [u for u in extract_match_urls(res_html) if u.endswith("/match-scorecard") or "/scorecard/" in u]

        return CriczopLists(
            live_urls=live_urls[: max(settings.MAX_LIVE_VERIFY, 8) * 2],
            upcoming_urls=upcoming_urls[: settings.MAX_UPCOMING],
            result_urls=result_urls[: settings.MAX_RESULTS],
        )

    async def fetch_live_verified(self, candidate_urls: List[str]) -> List[Match]:
        sem = asyncio.Semaphore(settings.MAX_CONCURRENCY)

        async def guarded(url: str):
            async with sem:
                return url, await fetch_match_page(url)

        tasks = [guarded(u) for u in candidate_urls[: settings.MAX_LIVE_VERIFY]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        matches: List[Match] = []
        for item in results:
            if isinstance(item, Exception):
                continue
            url, parsed = item
            if not parsed:
                continue
            status, title, series, ex = parsed
            if status != MatchStatus.LIVE:
                continue

            uid = make_uid(self.name, url)
            start_dt = date_from_criczop_url(url)

            matches.append(
                Match(
                    match_id=uid,
                    source=self.name,
                    url=url,
                    title=title,
                    series=series,
                    status=MatchStatus.LIVE,
                    start_date=start_dt,
                    end_date=start_dt,
                    score_summary=(ex[:500] if ex else None),
                )
            )

        return matches

    async def build_upcoming(self, urls: List[str]) -> List[Match]:
        out: List[Match] = []
        for url in urls[: settings.MAX_UPCOMING]:
            uid = make_uid(self.name, url)
            dt = date_from_criczop_url(url)
            out.append(
                Match(
                    match_id=uid,
                    source=self.name,
                    url=url,
                    status=MatchStatus.UPCOMING,
                    start_date=dt,
                    end_date=dt,
                )
            )
        return out

    async def build_results(self, urls: List[str]) -> List[Match]:
        out: List[Match] = []
        for url in urls[: settings.MAX_RESULTS]:
            uid = make_uid(self.name, url)
            dt = date_from_criczop_url(url)
            out.append(
                Match(
                    match_id=uid,
                    source=self.name,
                    url=url,
                    status=MatchStatus.RESULT,
                    start_date=dt,
                    end_date=dt,
                )
            )
        return out
