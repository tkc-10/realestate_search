from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SearchConfig, Site
from ..scheduler import refresh_jobs
from ..scraper_manager import run_scrape

router = APIRouter(prefix="/searches", tags=["searches"])


@router.post("/create")
def create_search(
    request: Request,
    name: str = Form(...),
    site_id: int = Form(...),
    search_url: str = Form(...),
    interval_hours: int = Form(6),
    max_pages: int = Form(5),
    db: Session = Depends(get_db),
):
    config = SearchConfig(
        name=name,
        site_id=site_id,
        search_url=search_url,
        interval_hours=interval_hours,
        max_pages=max_pages,
        is_active=True,
    )
    db.add(config)
    db.commit()
    refresh_jobs()
    return RedirectResponse("/searches", status_code=303)


@router.post("/{config_id}/toggle")
def toggle_search(config_id: int, db: Session = Depends(get_db)):
    config = db.query(SearchConfig).get(config_id)
    if not config:
        raise HTTPException(404)
    config.is_active = not config.is_active
    db.commit()
    refresh_jobs()
    return RedirectResponse("/searches", status_code=303)


@router.post("/{config_id}/delete")
def delete_search(config_id: int, db: Session = Depends(get_db)):
    config = db.query(SearchConfig).get(config_id)
    if not config:
        raise HTTPException(404)
    db.delete(config)
    db.commit()
    refresh_jobs()
    return RedirectResponse("/searches", status_code=303)


@router.post("/{config_id}/run")
def manual_run(config_id: int, db: Session = Depends(get_db)):
    config = db.query(SearchConfig).get(config_id)
    if not config:
        raise HTTPException(404)
    import threading
    threading.Thread(target=run_scrape, args=(config_id,), daemon=True).start()
    return RedirectResponse(f"/searches?running={config_id}", status_code=303)
