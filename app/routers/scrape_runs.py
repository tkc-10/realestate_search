from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import ScrapeRun

router = APIRouter(prefix="/api/scrape-runs", tags=["scrape-runs"])


@router.get("")
def list_runs(
    config_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(ScrapeRun).order_by(desc(ScrapeRun.started_at))
    if config_id:
        q = q.filter(ScrapeRun.search_config_id == config_id)
    runs = q.limit(limit).all()
    return [_serialize(r) for r in runs]


def _serialize(r: ScrapeRun) -> dict:
    config_name = r.search_config.name if r.search_config else ""
    site_name = r.search_config.site.display_name if r.search_config and r.search_config.site else ""
    duration = None
    if r.started_at and r.finished_at:
        duration = int((r.finished_at - r.started_at).total_seconds())
    return {
        "id": r.id,
        "search_config_id": r.search_config_id,
        "config_name": config_name,
        "site_name": site_name,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "duration_seconds": duration,
        "status": r.status,
        "properties_found": r.properties_found,
        "properties_new": r.properties_new,
        "properties_delisted": r.properties_delisted,
        "error_message": r.error_message,
    }
