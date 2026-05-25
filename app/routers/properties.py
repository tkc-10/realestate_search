from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import Property, Site

router = APIRouter(prefix="/api/properties", tags=["properties"])


@router.get("")
def list_properties(
    site_id: int | None = Query(None),
    status: str | None = Query(None),
    prefecture: str | None = Query(None),
    property_type: str | None = Query(None),
    min_yield: float | None = Query(None),
    max_yield: float | None = Query(None),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None),
    sort: str = Query("first_seen_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Property)

    if site_id:
        q = q.filter(Property.site_id == site_id)
    if status:
        q = q.filter(Property.status == status)
    if prefecture:
        q = q.filter(Property.prefecture == prefecture)
    if property_type:
        q = q.filter(Property.property_type == property_type)
    if min_yield is not None:
        q = q.filter(Property.gross_yield >= min_yield)
    if max_yield is not None:
        q = q.filter(Property.gross_yield <= max_yield)
    if min_price is not None:
        q = q.filter(Property.price >= min_price)
    if max_price is not None:
        q = q.filter(Property.price <= max_price)

    total = q.count()

    sort_col = getattr(Property, sort, Property.first_seen_at)
    if order == "asc":
        q = q.order_by(sort_col)
    else:
        q = q.order_by(desc(sort_col))

    props = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [_serialize(p) for p in props],
    }


@router.get("/{prop_id}")
def get_property(prop_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).get(prop_id)
    if not prop:
        from fastapi import HTTPException
        raise HTTPException(404)
    return {
        **_serialize(prop),
        "history": [
            {
                "checked_at": h.checked_at.isoformat() if h.checked_at else None,
                "price": h.price,
                "gross_yield": h.gross_yield,
                "status": h.status,
            }
            for h in prop.history
        ],
    }


def _serialize(p: Property) -> dict:
    return {
        "id": p.id,
        "site_id": p.site_id,
        "site_name": p.site.display_name if p.site else "",
        "external_id": p.external_id,
        "url": p.url,
        "title": p.title,
        "price": p.price,
        "price_text": p.price_text,
        "location": p.location,
        "prefecture": p.prefecture,
        "property_type": p.property_type,
        "gross_yield": p.gross_yield,
        "building_age": p.building_age,
        "building_area": p.building_area,
        "land_area": p.land_area,
        "total_units": p.total_units,
        "station": p.station,
        "image_url": p.image_url,
        "status": p.status,
        "first_seen_at": p.first_seen_at.isoformat() if p.first_seen_at else None,
        "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
        "delisted_at": p.delisted_at.isoformat() if p.delisted_at else None,
        "days_listed": p.days_listed,
    }
