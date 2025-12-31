from bs4 import BeautifulSoup
from typing import List
from app.core.http import fetch_text
from app.models.schemas import Match, MatchStatus
from app.sources.parsing import make_uid, parse_date_range, classify_status

RSS_URLS = [
    "https://www.espncricinfo.com/rss/livescores.xml",
    "https://static.cricinfo.com/rss/livescores.xml",
]

class CricinfoRSSSource:
    name = "cricinfo_rss"

    async def fetch_matches(self) -> List[Match]:
        xml = None
        for url in RSS_URLS:
            try:
                xml = await fetch_text(url)
                if xml:
                    break
            except Exception:
                continue

        if not xml:
            return []

        soup = BeautifulSoup(xml, "xml")
        matches: List[Match] = []

        for item in soup.find_all("item"):
            title = (item.title.text or "").strip() if item.title else None
            link = (item.link.text or "").strip() if item.link else None
            desc = (item.description.text or "").strip() if item.description else None

            if not link:
                continue

            match_id = make_uid(self.name, link)

            block_text = " ".join([x for x in [title, desc] if x])
            status_s = classify_status(block_text)

            start, end = parse_date_range(block_text)

            matches.append(
                Match(
                    match_id=match_id,
                    source=self.name,
                    url=link,
                    title=title,
                    description=desc,
                    status=MatchStatus(status_s),
                    start_date=start,
                    end_date=end,
                    score_summary=title,
                )
            )

        return matches
