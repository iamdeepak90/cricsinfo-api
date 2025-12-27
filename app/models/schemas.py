from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date

class MatchStatus(str, Enum):
    LIVE = "LIVE"
    UPCOMING = "UPCOMING"
    RESULT = "RESULT"
    UNKNOWN = "UNKNOWN"

class Match(BaseModel):
    match_id: int
    source: str
    url: str

    series: Optional[str] = None
    title: Optional[str] = None           # e.g. "Australia vs England"
    description: Optional[str] = None     # e.g. "4th Test, at Melbourne..."
    status: MatchStatus = MatchStatus.UNKNOWN

    # Parsed dates (best-effort)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # Summaries
    score_summary: Optional[str] = None   # e.g. "ENG 110 & 76/2* ..."
    result_summary: Optional[str] = None  # e.g. "England won by 4 wkts"
    note: Optional[str] = None            # e.g. "Starts at 09:30 local time"

class MatchListResponse(BaseModel):
    mode: str  # "live" | "upcoming" | "mixed"
    timezone: str
    generated_at: datetime
    items: List[Match]

    live: List[Match] = []
    upcoming: List[Match] = []
    recent: List[Match] = []

class MatchDetailResponse(BaseModel):
    match: Match
    fetched_at: datetime
    timezone: str
    # You can expand this later (innings, batsmen, etc.)
    raw_text_excerpt: Optional[str] = None
