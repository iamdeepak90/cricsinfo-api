import re
import zlib
from datetime import date
from typing import Optional

MONTHS_FULL = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

def make_uid(source: str, url: str) -> int:
    return zlib.crc32(f"{source}|{url}".encode("utf-8")) & 0xFFFFFFFF

def date_from_criczop_url(url: str) -> Optional[date]:
    url = url.lower()
    m = re.search(
        r"-(\d{1,2})-(january|february|march|april|may|june|july|august|september|october|november|december)-(\d{4})(?:/|$)",
        url,
    )
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
