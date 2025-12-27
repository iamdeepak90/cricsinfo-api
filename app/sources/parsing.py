import re
from datetime import date
from typing import Optional, Tuple

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

def extract_match_id_from_url(url: str) -> Optional[int]:
    # Cricinfo classic: /ci/engine/match/1455614.html
    m = re.search(r"/match/(\d+)\.html", url)
    if m:
        return int(m.group(1))

    # Cricinfo new: ...-1455614 or /full-scorecard-1455614
    m = re.search(r"[-/](\d{6,10})(?:[/?]|$)", url)
    if m:
        return int(m.group(1))

    # ESPN: /game/1455614/
    m = re.search(r"/game/(\d+)(?:/|$)", url)
    if m:
        return int(m.group(1))

    return None

def parse_date_range(text: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Handles:
      - "Dec 27 2025"
      - "Dec 26-30 2025"
      - "Dec 26-27 2025"
      - "Dec 26-27, 2025"
    Best-effort only.
    """
    text = text.replace("\u00a0", " ").strip()

    # e.g. "Dec 26-30 2025" (no comma)
    m = re.search(r"\b([A-Z][a-z]{2})\s+(\d{1,2})(?:-(\d{1,2}))?(?:,)?\s+(\d{4})\b", text)
    if m:
        mon_s, d1, d2, y = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        mon = MONTHS.get(mon_s)
        if not mon:
            return None, None
        start = date(y, mon, d1)
        end = date(y, mon, int(d2)) if d2 else start
        return start, end

    # e.g. "December 27, 2025" (rare)
    m = re.search(r"\b([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\b", text)
    if m:
        mon_name, d, y = m.group(1)[:3], int(m.group(2)), int(m.group(3))
        mon = MONTHS.get(mon_name)
        if mon:
            dt = date(y, mon, d)
            return dt, dt

    return None, None

def classify_status(block_text: str) -> str:
    t = block_text.lower()

    if any(x in t for x in ["won by", "match drawn", "abandoned", "no result", "tied", "stumps -", "result"]):
        return "RESULT"

    if "starts at" in t or ("start" in t and "local time" in t):
        return "UPCOMING"

    # score-like patterns
    score_patterns = [
        r"\b\d+/\d+\b",            # 26/1
        r"\b\d+\s*&\s*\d+\b",      # 152 & 132
        r"\(\d+(\.\d+)?/\d+\s*ov", # (3.1/20 ov)
        r"\bday\s+\d+\b",          # Day 2
        r"\binnings\b",
        r"\btea\b|\blunch\b",
    ]
    if any(re.search(p, block_text, re.IGNORECASE) for p in score_patterns) and "starts at" not in t:
        return "LIVE"

    return "UNKNOWN"
