import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .database import engine, get_db, SessionLocal
from .models import Base, Site, SearchConfig, Property, ScrapeRun
from .scheduler import start_scheduler, stop_scheduler
from .routers import properties, searches, scrape_runs, stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

TEMPLATES_DIR = "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_sites()
    start_scheduler()
    yield
    stop_scheduler()


def _seed_sites():
    db = SessionLocal()
    try:
        if not db.query(Site).first():
            db.add_all([
                Site(name="rakumachi", display_name="楽待", base_url="https://www.rakumachi.jp"),
                Site(name="kenbiya", display_name="健美家", base_url="https://www.kenbiya.com"),
            ])
            db.commit()
    finally:
        db.close()


app = FastAPI(title="不動産投資物件トラッカー", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# APIルーター
app.include_router(properties.router)
app.include_router(searches.router)
app.include_router(scrape_runs.router)
app.include_router(stats.router)


# ------- ページルーター -------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total = db.query(Property).count()
    active = db.query(Property).filter(Property.status == "active").count()
    delisted = db.query(Property).filter(Property.status == "delisted").count()
    recent_runs = (
        db.query(ScrapeRun)
        .order_by(desc(ScrapeRun.started_at))
        .limit(5)
        .all()
    )
    sites = db.query(Site).all()
    return templates.TemplateResponse(request, "index.html", {
        "total": total,
        "active": active,
        "delisted": delisted,
        "recent_runs": recent_runs,
        "sites": sites,
    })


@app.get("/searches", response_class=HTMLResponse)
async def searches_page(request: Request, db: Session = Depends(get_db)):
    configs = db.query(SearchConfig).order_by(SearchConfig.id).all()
    sites = db.query(Site).all()
    running = request.query_params.get("running")
    return templates.TemplateResponse(request, "searches.html", {
        "configs": configs,
        "sites": sites,
        "running": running,
    })


@app.get("/properties", response_class=HTMLResponse)
async def properties_page(request: Request, db: Session = Depends(get_db)):
    sites = db.query(Site).all()
    prefectures = (
        db.query(Property.prefecture)
        .filter(Property.prefecture != None, Property.prefecture != "")
        .distinct()
        .order_by(Property.prefecture)
        .all()
    )
    property_types = (
        db.query(Property.property_type)
        .filter(Property.property_type != None, Property.property_type != "")
        .distinct()
        .order_by(Property.property_type)
        .all()
    )
    return templates.TemplateResponse(request, "properties.html", {
        "sites": sites,
        "prefectures": [r[0] for r in prefectures],
        "property_types": [r[0] for r in property_types],
    })


@app.get("/properties/{prop_id}", response_class=HTMLResponse)
async def property_detail_page(prop_id: int, request: Request, db: Session = Depends(get_db)):
    prop = db.query(Property).get(prop_id)
    if not prop:
        return RedirectResponse("/properties")
    return templates.TemplateResponse(request, "property_detail.html", {
        "prop": prop,
    })


@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request, db: Session = Depends(get_db)):
    sites = db.query(Site).all()
    return templates.TemplateResponse(request, "analysis.html", {
        "sites": sites,
    })


@app.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, db: Session = Depends(get_db)):
    configs = db.query(SearchConfig).order_by(SearchConfig.id).all()
    return templates.TemplateResponse(request, "scrape_runs.html", {
        "configs": configs,
    })
