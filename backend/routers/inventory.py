"""API endpoints for inventory, predictions, alerts, and the dashboard."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import Alert, Product, ProductVariant, StockoutPrediction, SupplierInfo, User, get_db
from services.auth_service import get_current_user
from services.prediction_engine import run_all_predictions

router = APIRouter(prefix="/api", tags=["inventory"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_product_ids(db: Session, user_id: int) -> List[int]:
    """Return product IDs belonging to a user."""
    return [p.id for p in db.query(Product).filter(Product.user_id == user_id).all()]


def _user_variant_ids(db: Session, user_id: int) -> List[int]:
    """Return variant IDs belonging to a user's products."""
    product_ids = _user_product_ids(db, user_id)
    if not product_ids:
        return []
    return [
        v.id for v in db.query(ProductVariant)
        .filter(ProductVariant.product_id.in_(product_ids))
        .all()
    ]


def _variant_to_dict(v: ProductVariant) -> Dict[str, Any]:
    return {
        "id": v.id,
        "product_id": v.product_id,
        "product_name": v.product.name if v.product else None,
        "category": v.product.category if v.product else None,
        "sku": v.sku,
        "size": v.size,
        "color": v.color,
        "current_stock": v.current_stock,
        "price": v.price,
    }


def _prediction_to_dict(p: StockoutPrediction, v: ProductVariant) -> Dict[str, Any]:
    return {
        "id": p.id,
        "variant_id": p.variant_id,
        "sku": v.sku,
        "product_name": v.product.name if v.product else None,
        "size": v.size,
        "color": v.color,
        "current_stock": v.current_stock,
        "daily_velocity": p.daily_velocity,
        "days_until_stockout": p.days_until_stockout,
        "predicted_stockout_date": p.predicted_stockout_date.isoformat() if p.predicted_stockout_date else None,
        "recommended_reorder_qty": p.recommended_reorder_qty,
        "recommended_order_by_date": p.recommended_order_by_date.isoformat() if p.recommended_order_by_date else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _alert_to_dict(a: Alert) -> Dict[str, Any]:
    return {
        "id": a.id,
        "type": a.type,
        "variant_id": a.variant_id,
        "sku": a.variant.sku if a.variant else None,
        "product_name": a.variant.product.name if a.variant and a.variant.product else None,
        "message": a.message,
        "is_read": a.is_read,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@router.get("/inventory")
def list_inventory(
    category: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return all products with their variants and current stock levels."""
    query = db.query(Product).filter(Product.user_id == user.id)
    if category:
        query = query.filter(Product.category == category)
    products = query.all()

    results = []
    for p in products:
        supplier = db.query(SupplierInfo).filter(SupplierInfo.product_id == p.id).first()
        results.append({
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "square_id": p.square_id,
            "supplier": {
                "name": supplier.supplier_name,
                "lead_time_days": supplier.lead_time_days,
                "moq": supplier.moq,
                "case_pack_size": supplier.case_pack_size,
            } if supplier else None,
            "variants": [_variant_to_dict(v) for v in p.variants],
            "total_stock": sum(v.current_stock for v in p.variants),
        })

    return {"products": results, "count": len(results)}


@router.get("/inventory/{variant_id}")
def get_variant(
    variant_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return details for a single product variant."""
    variant = db.query(ProductVariant).get(variant_id)
    if not variant or variant.product.user_id != user.id:
        raise HTTPException(status_code=404, detail="Variant not found")

    prediction = (
        db.query(StockoutPrediction)
        .filter(StockoutPrediction.variant_id == variant_id)
        .order_by(StockoutPrediction.created_at.desc())
        .first()
    )

    data = _variant_to_dict(variant)
    data["prediction"] = _prediction_to_dict(prediction, variant) if prediction else None
    return data


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

@router.get("/predictions")
def list_predictions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return all current stockout predictions, sorted by urgency."""
    variant_ids = _user_variant_ids(db, user.id)
    if not variant_ids:
        return {"predictions": [], "count": 0}

    rows = (
        db.query(StockoutPrediction, ProductVariant)
        .join(ProductVariant, StockoutPrediction.variant_id == ProductVariant.id)
        .filter(StockoutPrediction.variant_id.in_(variant_ids))
        .order_by(StockoutPrediction.days_until_stockout.asc().nullslast())
        .all()
    )
    predictions = [_prediction_to_dict(p, v) for p, v in rows]
    return {"predictions": predictions, "count": len(predictions)}


@router.get("/predictions/summary")
def predictions_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Dashboard-ready summary of prediction state."""
    variant_ids = _user_variant_ids(db, user.id)
    if not variant_ids:
        return {"critical": 0, "warning": 0, "healthy": 0, "unread_alerts": 0, "actions_needed_today": 0}

    critical = (
        db.query(StockoutPrediction)
        .filter(StockoutPrediction.variant_id.in_(variant_ids), StockoutPrediction.days_until_stockout <= 14)
        .count()
    )
    warning = (
        db.query(StockoutPrediction)
        .filter(
            StockoutPrediction.variant_id.in_(variant_ids),
            StockoutPrediction.days_until_stockout > 14,
            StockoutPrediction.days_until_stockout <= 30,
        )
        .count()
    )
    healthy = (
        db.query(StockoutPrediction)
        .filter(
            StockoutPrediction.variant_id.in_(variant_ids),
            (StockoutPrediction.days_until_stockout > 30)
            | (StockoutPrediction.days_until_stockout == None),  # noqa: E711
        )
        .count()
    )
    unread_alerts = (
        db.query(Alert)
        .filter(Alert.variant_id.in_(variant_ids), Alert.is_read == False)  # noqa: E712
        .count()
    )

    return {
        "critical": critical,
        "warning": warning,
        "healthy": healthy,
        "unread_alerts": unread_alerts,
        "actions_needed_today": critical,
    }


@router.post("/predictions/refresh")
def refresh_predictions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger a full prediction recalculation."""
    stats = run_all_predictions(db, user.id)
    return {"status": "ok", "stats": stats}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts")
def list_alerts(
    type: Optional[str] = Query(None, description="Filter by alert type: stockout, reorder, dead_inventory"),
    is_read: Optional[bool] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return alerts, optionally filtered by type and read status."""
    variant_ids = _user_variant_ids(db, user.id)
    if not variant_ids:
        return {"alerts": [], "count": 0}

    query = db.query(Alert).filter(Alert.variant_id.in_(variant_ids))
    if type:
        query = query.filter(Alert.type == type)
    if is_read is not None:
        query = query.filter(Alert.is_read == is_read)
    alerts = query.order_by(Alert.created_at.desc()).all()
    return {"alerts": [_alert_to_dict(a) for a in alerts], "count": len(alerts)}


@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a single alert as read."""
    alert = db.query(Alert).get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    # Verify ownership
    variant = db.query(ProductVariant).get(alert.variant_id)
    if not variant or variant.product.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"status": "ok", "alert": _alert_to_dict(alert)}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Combined dashboard payload."""
    products = db.query(Product).filter(Product.user_id == user.id).all()
    product_ids = [p.id for p in products]

    if not product_ids:
        return {
            "inventory_summary": {"total_products": 0, "total_variants": 0, "total_units_in_stock": 0},
            "prediction_summary": {"critical": 0, "warning": 0, "healthy": 0, "unread_alerts": 0, "actions_needed_today": 0},
            "critical_alerts": [],
            "reorder_actions": [],
        }

    variants = db.query(ProductVariant).filter(ProductVariant.product_id.in_(product_ids)).all()
    variant_ids = [v.id for v in variants]
    total_stock = sum(v.current_stock for v in variants)

    summary = predictions_summary(user=user, db=db)

    critical_alerts = (
        db.query(Alert)
        .filter(Alert.variant_id.in_(variant_ids), Alert.type == "stockout", Alert.is_read == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .limit(5)
        .all()
    )

    reorder_actions = (
        db.query(Alert)
        .filter(Alert.variant_id.in_(variant_ids), Alert.type == "reorder", Alert.is_read == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "inventory_summary": {
            "total_products": len(products),
            "total_variants": len(variants),
            "total_units_in_stock": total_stock,
        },
        "prediction_summary": summary,
        "critical_alerts": [_alert_to_dict(a) for a in critical_alerts],
        "reorder_actions": [_alert_to_dict(a) for a in reorder_actions],
    }


# ---------------------------------------------------------------------------
# Square sync (per-user)
# ---------------------------------------------------------------------------

@router.post("/square/sync")
async def square_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger a full sync from Square for the current user."""
    from database import SquareConnection
    from services.square_service import SquareService

    conn = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
    if not conn:
        return {"status": "not_connected", "message": "Connect your Square account first."}

    svc = SquareService(access_token=conn.access_token, location_id=conn.location_id or "")
    sync_result = await svc.full_sync(db, user.id)

    stats = run_all_predictions(db, user.id)
    return {"status": "ok", "sync": sync_result, "predictions": stats}
