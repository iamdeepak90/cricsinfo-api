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
    title: Optional[str] = None
    description: Optional[str] = None
    status: MatchStatus = MatchStatus.UNKNOWN

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    score_summary: Optional[str] = None
    result_summary: Optional[str] = None
    note: Optional[str] = None

class MatchListResponse(BaseModel):
    mode: str
    timezone: str
    generated_at: datetime
    items: List[Match]

    live: List[Match] = []
    upcoming: List[Match] = []
    results: List[Match] = []

class MatchDetailResponse(BaseModel):
    match: Match
    fetched_at: datetime
    timezone: str
    raw_text_excerpt: Optional[str] = None
