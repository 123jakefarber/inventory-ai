"""Core stockout-prediction and reorder-recommendation engine.

Uses exponentially-weighted moving average of daily sales velocity, combined
with supplier lead times and a safety-stock buffer, to forecast stockout dates
and suggest reorder quantities.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import (
    Alert,
    Product,
    ProductVariant,
    SalesRecord,
    StockoutPrediction,
    SupplierInfo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
VELOCITY_LOOKBACK_DAYS = 30
VELOCITY_HALF_LIFE_DAYS = 10  # recent days weighted ~2x vs 30 days ago
SAFETY_STOCK_DAYS = 7         # buffer on top of lead time
DEAD_INVENTORY_THRESHOLD_DAYS = 90  # >90 days supply -> dead inventory
CRITICAL_DAYS_THRESHOLD = 14  # <=14 days until stockout -> critical alert

TODAY = date.today


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_daily_velocity(variant_id: int, db: Session) -> float:
    """Return the exponentially-weighted average daily sales over the last 30 days."""
    cutoff = TODAY() - timedelta(days=VELOCITY_LOOKBACK_DAYS)
    records = (
        db.query(SalesRecord)
        .filter(SalesRecord.variant_id == variant_id, SalesRecord.sale_date >= cutoff)
        .all()
    )

    if not records:
        return 0.0

    total_weight = 0.0
    weighted_qty = 0.0
    for rec in records:
        days_ago = (TODAY() - rec.sale_date).days
        weight = math.exp(-math.log(2) * days_ago / VELOCITY_HALF_LIFE_DAYS)
        weighted_qty += rec.quantity * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    weighted_avg_per_record = weighted_qty / total_weight
    sale_days = len({r.sale_date for r in records})
    avg_daily = (weighted_avg_per_record * sale_days) / VELOCITY_LOOKBACK_DAYS
    return round(avg_daily, 2)


def predict_stockout(variant_id: int, db: Session) -> dict:
    """Predict when a variant will stock out."""
    variant = db.query(ProductVariant).get(variant_id)
    if variant is None:
        raise ValueError(f"Variant {variant_id} not found")

    velocity = calculate_daily_velocity(variant_id, db)

    if velocity <= 0:
        return {
            "daily_velocity": 0.0,
            "days_until_stockout": None,
            "predicted_stockout_date": None,
        }

    days = int(variant.current_stock / velocity)
    stockout_date = TODAY() + timedelta(days=days)

    return {
        "daily_velocity": velocity,
        "days_until_stockout": days,
        "predicted_stockout_date": stockout_date,
    }


def generate_reorder_recommendation(variant_id: int, db: Session) -> dict:
    """Recommend reorder quantity and latest order-by date."""
    variant = db.query(ProductVariant).get(variant_id)
    if variant is None:
        raise ValueError(f"Variant {variant_id} not found")

    prediction = predict_stockout(variant_id, db)
    velocity = prediction["daily_velocity"]

    supplier = (
        db.query(SupplierInfo)
        .filter(SupplierInfo.product_id == variant.product_id)
        .first()
    )

    lead_time = supplier.lead_time_days if supplier else 30
    moq = supplier.moq if supplier else 50
    case_pack = supplier.case_pack_size if supplier else 12

    if velocity <= 0:
        return {
            **prediction,
            "recommended_reorder_qty": 0,
            "recommended_order_by_date": None,
            "lead_time_days": lead_time,
        }

    target_days = lead_time + SAFETY_STOCK_DAYS
    target_units = math.ceil(velocity * target_days)

    qty = max(target_units, moq)
    if case_pack > 1:
        qty = math.ceil(qty / case_pack) * case_pack

    stockout_date = prediction["predicted_stockout_date"]
    order_by: Optional[date] = None
    if stockout_date:
        order_by = stockout_date - timedelta(days=lead_time)
        if order_by < TODAY():
            order_by = TODAY()

    return {
        **prediction,
        "recommended_reorder_qty": qty,
        "recommended_order_by_date": order_by,
        "lead_time_days": lead_time,
    }


def detect_dead_inventory(variant_id: int, db: Session) -> Optional[dict]:
    """Flag a variant as dead inventory if it has >90 days of supply at current velocity."""
    variant = db.query(ProductVariant).get(variant_id)
    if variant is None:
        return None

    velocity = calculate_daily_velocity(variant_id, db)

    if velocity <= 0 and variant.current_stock > 0:
        return {
            "variant_id": variant_id,
            "sku": variant.sku,
            "current_stock": variant.current_stock,
            "daily_velocity": 0.0,
            "days_of_supply": None,
            "reason": "No sales in the last 30 days with stock on hand.",
        }

    if velocity > 0:
        days_of_supply = variant.current_stock / velocity
        if days_of_supply > DEAD_INVENTORY_THRESHOLD_DAYS:
            return {
                "variant_id": variant_id,
                "sku": variant.sku,
                "current_stock": variant.current_stock,
                "daily_velocity": velocity,
                "days_of_supply": round(days_of_supply, 1),
                "reason": f"Over {DEAD_INVENTORY_THRESHOLD_DAYS} days of supply at current sell-through rate.",
            }

    return None


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_all_predictions(db: Session, user_id: Optional[int] = None) -> dict:
    """Run predictions for every active variant.

    If user_id is provided, only runs for that user's products.
    Stores results in StockoutPrediction and creates Alert rows.
    Returns a summary dict.
    """
    if user_id is not None:
        # Get variant IDs belonging to this user's products
        user_product_ids = [
            p.id for p in db.query(Product).filter(Product.user_id == user_id).all()
        ]
        variants = (
            db.query(ProductVariant)
            .filter(ProductVariant.product_id.in_(user_product_ids))
            .all()
        )
        variant_ids = [v.id for v in variants]

        # Clear previous predictions and unread alerts for this user's variants only
        if variant_ids:
            db.query(StockoutPrediction).filter(
                StockoutPrediction.variant_id.in_(variant_ids)
            ).delete(synchronize_session=False)
            db.query(Alert).filter(
                Alert.variant_id.in_(variant_ids),
                Alert.is_read == False,  # noqa: E712
            ).delete(synchronize_session=False)
            db.flush()
    else:
        variants = db.query(ProductVariant).all()
        db.query(StockoutPrediction).delete()
        db.query(Alert).filter(Alert.is_read == False).delete()  # noqa: E712
        db.flush()

    stats = {"total": 0, "critical": 0, "reorder": 0, "dead": 0}

    for variant in variants:
        stats["total"] += 1
        rec = generate_reorder_recommendation(variant.id, db)

        pred = StockoutPrediction(
            variant_id=variant.id,
            predicted_stockout_date=rec.get("predicted_stockout_date"),
            recommended_reorder_qty=rec["recommended_reorder_qty"],
            recommended_order_by_date=rec.get("recommended_order_by_date"),
            daily_velocity=rec["daily_velocity"],
            days_until_stockout=rec.get("days_until_stockout"),
        )
        db.add(pred)

        days = rec.get("days_until_stockout")
        if days is not None and days <= CRITICAL_DAYS_THRESHOLD:
            stats["critical"] += 1
            urgency = "URGENT" if days <= 7 else "WARNING"
            db.add(Alert(
                type="stockout",
                variant_id=variant.id,
                message=(
                    f"[{urgency}] {variant.sku} will stock out in ~{days} days "
                    f"({rec['predicted_stockout_date']}). Current stock: {variant.current_stock}."
                ),
            ))

        order_by = rec.get("recommended_order_by_date")
        if order_by and (order_by - TODAY()).days <= 7 and (days is None or days > CRITICAL_DAYS_THRESHOLD):
            stats["reorder"] += 1
            db.add(Alert(
                type="reorder",
                variant_id=variant.id,
                message=(
                    f"Place reorder for {variant.sku} by {order_by} "
                    f"(qty {rec['recommended_reorder_qty']})."
                ),
            ))

        dead = detect_dead_inventory(variant.id, db)
        if dead:
            stats["dead"] += 1
            db.add(Alert(
                type="dead_inventory",
                variant_id=variant.id,
                message=(
                    f"Dead inventory: {variant.sku} — "
                    f"{dead['days_of_supply'] or 'inf'} days of supply. "
                    f"{dead['reason']}"
                ),
            ))

    db.commit()
    logger.info("Prediction run complete: %s", stats)
    return stats
