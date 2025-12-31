import re
from bs4 import BeautifulSoup
from typing import List, Optional

from app.core.http import fetch_text
from app.models.schemas import Match, MatchStatus
from app.sources.parsing import make_uid, parse_date_range, classify_status

SCORES_URLS = [
    "https://www.espn.com/cricket/scores",
    "https://www.espn.in/cricket/scores",
    "https://www.espn.co.uk/cricket/scores",
]

class ESPNScoreboardSource:
    name = "espn_scores"

    def _find_match_card(self, a_tag) -> Optional[object]:
        node = a_tag
        for _ in range(7):
            if not node:
                break
            txt = node.get_text(" ", strip=True) if hasattr(node, "get_text") else ""
            if 60 <= len(txt) <= 900:
                return node
            node = node.parent
        return a_tag.parent

    async def fetch_matches(self) -> List[Match]:
        html = None
        for url in SCORES_URLS:
            try:
                html = await fetch_text(url)
                if html:
                    break
            except Exception:
                continue

        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        matches: List[Match] = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/cricket/series/" not in href or "/game/" not in href:
                continue

            full_url = href if href.startswith("http") else f"https://www.espn.com{href}"
            # Exposed as API `match_id` (stable across providers)
            match_id = make_uid(self.name, full_url)

            card = self._find_match_card(a)
            block_text = card.get_text(" ", strip=True) if card else a.get_text(" ", strip=True)

            status_s = classify_status(block_text)
            start, end = parse_date_range(block_text)

            result_summary = None
            m = re.search(r"([A-Za-z].*?\bwon by\b.*?$)", block_text, re.IGNORECASE)
            if m:
                result_summary = m.group(1).strip()

            score_summary = a.get_text(" ", strip=True)[:220]

            matches.append(
                Match(
                    match_id=match_id,
                    source=self.name,
                    url=full_url,
                    description=block_text[:260],
                    status=MatchStatus(status_s),
                    start_date=start,
                    end_date=end,
                    score_summary=score_summary,
                    result_summary=result_summary,
                )
            )

        uniq = {m.match_id: m for m in matches}
        return list(uniq.values())

    async def fetch_match_detail_excerpt(self, match_url: str) -> str:
        html = await fetch_text(match_url)
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        return "\n".join(text.splitlines()[:40])
