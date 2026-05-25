"""スクレイパーの実行と結果をDBに保存するマネージャー"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Property, PropertyHistory, ScrapeRun, SearchConfig
from .scrapers.rakumachi import RakumachiScraper
from .scrapers.kenbiya import KenbiyaScraper
from .scrapers.base import PropertyData

logger = logging.getLogger(__name__)

SCRAPERS = {
    "rakumachi": RakumachiScraper,
    "kenbiya": KenbiyaScraper,
}


def run_scrape(search_config_id: int) -> int:
    """指定した検索設定のスクレイピングを実行。ScrapeRun.id を返す"""
    db = SessionLocal()
    run = ScrapeRun(search_config_id=search_config_id, started_at=datetime.utcnow())
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id

    try:
        config: SearchConfig = db.query(SearchConfig).get(search_config_id)
        if not config:
            raise ValueError(f"SearchConfig {search_config_id} not found")

        site_name = config.site.name
        scraper_cls = SCRAPERS.get(site_name)
        if not scraper_cls:
            raise ValueError(f"Unknown site: {site_name}")

        scraper = scraper_cls()
        found_props = scraper.scrape_all_pages(config.search_url, config.max_pages)

        run.properties_found = len(found_props)
        new_count, delisted_count = _upsert_properties(
            db, found_props, config, run
        )
        run.properties_new = new_count
        run.properties_delisted = delisted_count
        run.status = "success"
        config.last_run_at = datetime.utcnow()

    except Exception as e:
        logger.exception(f"スクレイピングエラー (config={search_config_id}): {e}")
        run.status = "error"
        run.error_message = str(e)

    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.close()

    return run_id


def _upsert_properties(
    db: Session,
    found_props: list[PropertyData],
    config: SearchConfig,
    run: ScrapeRun,
) -> tuple[int, int]:
    """
    スクレイピング結果をDBに反映する。
    - 新規物件: 追加
    - 既存物件: last_seen_at と価格/利回りを更新
    - 今回見つからなかった物件: delistedマーク
    返り値: (新規件数, delisted件数)
    """
    site_id = config.site_id
    now = datetime.utcnow()
    found_ids = {p.external_id for p in found_props}

    # 現在このsearchConfigでactiveな物件を取得
    active_props = (
        db.query(Property)
        .filter(
            Property.search_config_id == config.id,
            Property.status == "active",
        )
        .all()
    )
    active_map = {p.external_id: p for p in active_props}

    new_count = 0

    for prop_data in found_props:
        existing = (
            db.query(Property)
            .filter(
                Property.site_id == site_id,
                Property.external_id == prop_data.external_id,
            )
            .first()
        )

        if existing:
            # 価格/利回りが変わった場合に履歴を追加
            changed = (
                existing.price != prop_data.price
                or existing.gross_yield != prop_data.gross_yield
            )
            existing.last_seen_at = now
            existing.status = "active"
            existing.delisted_at = None
            existing.days_listed = None
            if prop_data.price is not None:
                existing.price = prop_data.price
            if prop_data.price_text:
                existing.price_text = prop_data.price_text
            if prop_data.gross_yield is not None:
                existing.gross_yield = prop_data.gross_yield
            if prop_data.title:
                existing.title = prop_data.title
            if prop_data.location:
                existing.location = prop_data.location
            if prop_data.prefecture:
                existing.prefecture = prop_data.prefecture
            if changed:
                db.add(PropertyHistory(
                    property_id=existing.id,
                    checked_at=now,
                    price=prop_data.price,
                    gross_yield=prop_data.gross_yield,
                    status="active",
                ))
        else:
            new_prop = Property(
                site_id=site_id,
                search_config_id=config.id,
                external_id=prop_data.external_id,
                url=prop_data.url,
                title=prop_data.title,
                price=prop_data.price,
                price_text=prop_data.price_text,
                location=prop_data.location,
                prefecture=prop_data.prefecture,
                property_type=prop_data.property_type,
                gross_yield=prop_data.gross_yield,
                building_age=prop_data.building_age,
                building_area=prop_data.building_area,
                land_area=prop_data.land_area,
                total_units=prop_data.total_units,
                station=prop_data.station,
                image_url=prop_data.image_url,
                description=prop_data.description,
                status="active",
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(new_prop)
            db.flush()
            db.add(PropertyHistory(
                property_id=new_prop.id,
                checked_at=now,
                price=prop_data.price,
                gross_yield=prop_data.gross_yield,
                status="active",
            ))
            new_count += 1

    # 今回見つからなかった物件をdelistedにマーク
    delisted_count = 0
    for ext_id, prop in active_map.items():
        if ext_id not in found_ids:
            first_seen = prop.first_seen_at or now
            prop.status = "delisted"
            prop.delisted_at = now
            prop.days_listed = (now - first_seen).days
            db.add(PropertyHistory(
                property_id=prop.id,
                checked_at=now,
                price=prop.price,
                gross_yield=prop.gross_yield,
                status="delisted",
            ))
            delisted_count += 1

    db.commit()
    return new_count, delisted_count
