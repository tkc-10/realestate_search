from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Property, Site, ScrapeRun

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Property).count()
    active = db.query(Property).filter(Property.status == "active").count()
    delisted = db.query(Property).filter(Property.status == "delisted").count()

    # 平均掲載日数（delisted物件）
    avg_days = (
        db.query(func.avg(Property.days_listed))
        .filter(Property.status == "delisted", Property.days_listed != None)
        .scalar()
    )

    # サイト別集計
    by_site = (
        db.query(Site.display_name, func.count(Property.id))
        .join(Property, Property.site_id == Site.id)
        .group_by(Site.id)
        .all()
    )

    # 直近7日間のdelist件数
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_delisted = (
        db.query(Property)
        .filter(Property.status == "delisted", Property.delisted_at >= week_ago)
        .count()
    )

    # 最終スクレイピング
    last_run = (
        db.query(ScrapeRun)
        .filter(ScrapeRun.status == "success")
        .order_by(ScrapeRun.finished_at.desc())
        .first()
    )

    # 都道府県別
    by_prefecture = (
        db.query(Property.prefecture, func.count(Property.id))
        .filter(Property.prefecture != None, Property.prefecture != "")
        .group_by(Property.prefecture)
        .order_by(func.count(Property.id).desc())
        .limit(10)
        .all()
    )

    # 物件種別
    by_type = (
        db.query(Property.property_type, func.count(Property.id))
        .filter(Property.property_type != None, Property.property_type != "")
        .group_by(Property.property_type)
        .order_by(func.count(Property.id).desc())
        .all()
    )

    # 掲載日数分布（delisted）
    days_dist = _days_distribution(db)

    return {
        "total": total,
        "active": active,
        "delisted": delisted,
        "avg_days_listed": round(float(avg_days), 1) if avg_days else None,
        "recent_delisted_7d": recent_delisted,
        "by_site": [{"name": n, "count": c} for n, c in by_site],
        "by_prefecture": [{"prefecture": p, "count": c} for p, c in by_prefecture],
        "by_type": [{"type": t, "count": c} for t, c in by_type],
        "days_distribution": days_dist,
        "last_run_at": last_run.finished_at.isoformat() if last_run else None,
    }


def _days_distribution(db: Session) -> list[dict]:
    """掲載日数の分布（0-7, 8-14, 15-30, 31-60, 61+）"""
    buckets = [
        ("〜7日", 0, 7),
        ("8〜14日", 8, 14),
        ("15〜30日", 15, 30),
        ("31〜60日", 31, 60),
        ("61日〜", 61, 99999),
    ]
    result = []
    for label, lo, hi in buckets:
        count = (
            db.query(Property)
            .filter(
                Property.status == "delisted",
                Property.days_listed >= lo,
                Property.days_listed <= hi,
            )
            .count()
        )
        result.append({"label": label, "count": count})
    return result
