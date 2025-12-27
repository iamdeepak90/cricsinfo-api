from fastapi import APIRouter, Query, HTTPException
from app.services.scores_service import ScoresService
from app.models.schemas import MatchListResponse, MatchDetailResponse

router = APIRouter(tags=["live-score"])
service = ScoresService()

@router.get("/live-score", response_model=MatchListResponse)
async def live_score(timezone: str = Query(default=None, description="IANA timezone e.g. Asia/Kolkata")):
    return await service.get_match_list(timezone=timezone)

@router.get("/live-score/{match_id}", response_model=MatchDetailResponse)
async def live_score_detail(match_id: int, timezone: str = Query(default=None)):
    detail = await service.get_match_detail(match_id=match_id, timezone=timezone)
    if not detail:
        raise HTTPException(status_code=404, detail="Match not found (try fetching /live-score first).")
    return detail
