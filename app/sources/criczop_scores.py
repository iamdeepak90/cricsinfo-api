import re
from datetime import date
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.core.http import fetch_text
from app.models.schemas import Match, MatchStatus
from app.sources.parsing import make_uid


BASE = "https://www.criczop.com"

SEED_PAGES = [
    f"{BASE}/",  # home contains direct Scorecard/Commentary links for many matches
    f"{BASE}/live-cricket-score",
    f"{BASE}/cricket-schedule",
    f"{BASE}/cricket-match-results",
]

MONTHS_FULL = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _normalize_url(url: str) -> str:
    """Drop query/fragment and force https."""
    p = urlparse(url)
    scheme = "https"
    netloc = p.netloc or urlparse(BASE).netloc
    return urlunparse((scheme, netloc, p.path.rstrip("/"), "", "", ""))


def _is_candidate_match_url(url: str) -> bool:
    u = url.lower()
    if "dream-11" in u or "team-prediction" in u:
        return False
    if "/live-cricket-score/" in u and (u.endswith("/match-scorecard") or u.endswith("/match-info")):
        return True
    if "/scorecard/" in u:
        return True
    return False


def _extract_candidate_urls(html: str) -> Set[str]:
    urls: Set[str] = set()

    # 1) HTML anchors
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href:
            continue
        full = href if href.startswith("http") else urljoin(BASE, href)
        full = _normalize_url(full)
        if _is_candidate_match_url(full):
            urls.add(full)

    # 2) Regex fallback (handles URLs embedded in JSON/JS)
    for m in re.finditer(r"/(?:live-cricket-score|scorecard)/[^\"'\s<>]+", html, flags=re.IGNORECASE):
        full = _normalize_url(urljoin(BASE, m.group(0)))
        if _is_candidate_match_url(full):
            urls.add(full)

    return urls


def _date_from_url(url: str) -> Optional[date]:
    """Parse '/...-31-december-2025/...' style dates."""
    p = urlparse(url)
    path = p.path.lower()
    m = re.search(r"-(\d{1,2})-(january|february|march|april|may|june|july|august|september|october|november|december)-(\d{4})(?:/|$)", path)
    if not m:
        return None
    d = int(m.group(1))
    mon = MONTHS_FULL.get(m.group(2))
    y = int(m.group(3))
    if not mon:
        return None
    try:
        return date(y, mon, d)
    except ValueError:
        return None


def _parse_heading(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    """Return (title, series) from the H1 heading if present."""
    h1 = soup.find("h1")
    if not h1:
        return None, None
    heading = h1.get_text(" ", strip=True)
    if "Live Scores:" in heading:
        left, right = heading.split("Live Scores:", 1)
        # left often contains "Team A vs. Team B, Match X"
        title = left.replace("#", "").strip().rstrip(":")
        series = right.strip()
        return title, series
    return heading, None


def _detect_status(html: str, soup: BeautifulSoup) -> MatchStatus:
    # Live pages show a bullet + "Live" in the header area (seen on indexed pages).
    if "● live" in soup.get_text(" ", strip=True).lower() or "\u25cf live" in html.lower():
        return MatchStatus.LIVE
    # Completed pages often carry a "winning-indicator" image.
    if "winning-indicator" in html.lower():
        return MatchStatus.RESULT
    return MatchStatus.UNKNOWN


def _extract_top_excerpt(soup: BeautifulSoup, max_lines: int = 24) -> str:
    """A short, human readable summary from the top of the page."""
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Stop before the big scorecard tables if present
    stop_tokens = {"Batting Scorecard", "Bowling Scorecard", "Fall of Wickets"}
    cut = len(lines)
    for i, ln in enumerate(lines):
        if any(t.lower() in ln.lower() for t in stop_tokens):
            cut = i
            break
    lines = lines[:cut]

    # Remove common nav tokens
    ignore_exact = {
        "INFO", "SCORECARD", "SQUADS", "COMMENTARY", "POINTS TABLE",
        "Schedule", "Logout",
    }
    filtered = [ln for ln in lines if ln not in ignore_exact and not ln.endswith("┃ Info")]
    return "\n".join(filtered[:max_lines])


class CriczopScoresSource:
    """Scrape Criczop match pages.

    Criczop exposes direct match pages like:
      - /live-cricket-score/<slug>/match-scorecard
      - /live-cricket-score/<slug>/match-info
      - /scorecard/<slug>-<id>-<series>
    We first scrape a few seed pages to discover match URLs, then (best-effort)
    fetch each match page to classify LIVE/RESULT and extract a small summary.
    """

    name = "criczop"

    async def fetch_match_detail_excerpt(self, match_url: str) -> str:
        """Return a short excerpt for the detail endpoint."""
        html = await fetch_text(match_url)
        soup = BeautifulSoup(html, "lxml")
        return _extract_top_excerpt(soup, max_lines=60)

    async def fetch_matches(self) -> List[Match]:
        # Discover match URLs from seed pages
        candidate_urls: Set[str] = set()
        for seed in SEED_PAGES:
            try:
                html = await fetch_text(seed)
            except Exception:
                continue
            candidate_urls |= _extract_candidate_urls(html)

        if not candidate_urls:
            return []

        # Limit work (the list is already refreshed/cached at service level)
        urls = sorted(candidate_urls)[:160]

        # Only deep-fetch pages near "now" to keep list latency reasonable.
        # (Render free tiers can be sensitive to long cold-start requests.)
        today = date.today()

        matches: List[Match] = []
        for url in urls:
            uid = make_uid(self.name, url)
            start_dt = _date_from_url(url)

            # Guess without fetching first (match-info => UPCOMING)
            status = MatchStatus.UPCOMING if url.lower().endswith("/match-info") else MatchStatus.UNKNOWN
            title = None
            series = None
            score_summary = None
            result_summary = None

            should_fetch = False
            if url.lower().endswith("/match-scorecard") or "/scorecard/" in url.lower():
                # If we can parse a date from the URL, only fetch near today.
                if start_dt is None:
                    should_fetch = True
                else:
                    should_fetch = (today - start_dt).days <= 2 and (start_dt - today).days <= 7
            elif url.lower().endswith("/match-info"):
                should_fetch = start_dt is None or (start_dt - today).days <= 14

            if should_fetch:
                try:
                    html = await fetch_text(url)
                    soup = BeautifulSoup(html, "lxml")
                    title, series = _parse_heading(soup)
                    status = _detect_status(html, soup) if status == MatchStatus.UNKNOWN else status

                    excerpt = _extract_top_excerpt(soup)
                    if status == MatchStatus.LIVE:
                        score_summary = excerpt[:400] if excerpt else None
                    elif status == MatchStatus.RESULT:
                        result_summary = excerpt[:280] if excerpt else None
                except Exception:
                    pass

            matches.append(
                Match(
                    match_id=uid,
                    source=self.name,
                    url=url,
                    series=series,
                    title=title,
                    description=None,
                    status=status,
                    start_date=start_dt,
                    end_date=start_dt,
                    score_summary=score_summary,
                    result_summary=result_summary,
                )
            )

        # Deduplicate by our uid
        uniq = {m.match_id: m for m in matches}
        return list(uniq.values())
