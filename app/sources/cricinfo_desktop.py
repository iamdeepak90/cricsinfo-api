import re
from bs4 import BeautifulSoup
from typing import List, Optional

from app.core.http import fetch_text
from app.models.schemas import Match, MatchStatus
from app.sources.parsing import make_uid, parse_date_range, classify_status

DESKTOP_URL = "https://www.espncricinfo.com/ci/engine/match/scores/desktop.html"

class CricinfoDesktopSource:
    name = "cricinfo_desktop"

    def _pick_container(self, a_tag) -> Optional[object]:
        # Try to find a reasonable parent container (row/div) for this match link.
        node = a_tag
        for _ in range(6):
            if not node:
                break
            txt = node.get_text(" ", strip=True) if hasattr(node, "get_text") else ""
            if 40 <= len(txt) <= 600:
                return node
            node = node.parent
        return a_tag.parent

    async def fetch_matches(self) -> List[Match]:
        try:
            html = await fetch_text(DESKTOP_URL)
        except Exception:
            return []

        soup = BeautifulSoup(html, "lxml")
        matches: List[Match] = []

        # classic links: /ci/engine/match/1455614.html
        for a in soup.select('a[href*="/ci/engine/match/"]'):
            href = a.get("href", "")
            url = href if href.startswith("http") else f"https://www.espncricinfo.com{href}"
            match_id = make_uid(self.name, url)

            container = self._pick_container(a)
            block_text = container.get_text(" ", strip=True) if container else a.get_text(" ", strip=True)

            status_s = classify_status(block_text)
            start, end = parse_date_range(block_text)

            score_like = None
            m = re.search(r"(\d+/\d+.*?ov\)?)", block_text)
            if m:
                score_like = m.group(1)

            matches.append(
                Match(
                    match_id=match_id,
                    source=self.name,
                    url=url,
                    description=block_text[:260],
                    status=MatchStatus(status_s),
                    start_date=start,
                    end_date=end,
                    score_summary=score_like,
                )
            )

        return matches
