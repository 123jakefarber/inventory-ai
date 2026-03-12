"""Realistic mock data for an apparel brand selling via Square.

The data is designed so that a demo will surface:
 - Imminent stockout warnings  (Hoodie M, Joggers L)
 - Reorder recommendations     (Hoodie L, Crewneck M)
 - Dead / overstocked inventory (Baseball Hat, Hoodie XXL)
 - Healthy items for contrast   (Joggers M, Crewneck L)
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from typing import List

from sqlalchemy.orm import Session

from database import (
    Alert,
    Product,
    ProductVariant,
    SalesRecord,
    StockoutPrediction,
    SupplierInfo,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TODAY = date.today()
HISTORY_DAYS = 90

# ---------------------------------------------------------------------------
# Product definitions
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        "name": "Classic Hoodie",
        "category": "Tops",
        "variants": [
            {"sku": "HOOD-BLK-S", "size": "S", "color": "Black", "stock": 45, "price": 68.00, "base_daily": 1.2},
            {"sku": "HOOD-BLK-M", "size": "M", "color": "Black", "stock": 8, "price": 68.00, "base_daily": 2.8},   # LOW - stockout soon
            {"sku": "HOOD-BLK-L", "size": "L", "color": "Black", "stock": 22, "price": 68.00, "base_daily": 2.5},
            {"sku": "HOOD-BLK-XL", "size": "XL", "color": "Black", "stock": 35, "price": 68.00, "base_daily": 1.5},
            {"sku": "HOOD-BLK-XXL", "size": "XXL", "color": "Black", "stock": 110, "price": 68.00, "base_daily": 0.15},  # DEAD
        ],
        "supplier": {
            "supplier_name": "Coastal Apparel Co.",
            "lead_time_days": 35,
            "moq": 50,
            "case_pack_size": 10,
        },
    },
    {
        "name": "Essential Joggers",
        "category": "Bottoms",
        "variants": [
            {"sku": "JOG-GRY-S", "size": "S", "color": "Heather Grey", "stock": 30, "price": 55.00, "base_daily": 0.9},
            {"sku": "JOG-GRY-M", "size": "M", "color": "Heather Grey", "stock": 52, "price": 55.00, "base_daily": 1.8},
            {"sku": "JOG-GRY-L", "size": "L", "color": "Heather Grey", "stock": 6, "price": 55.00, "base_daily": 2.1},   # LOW
            {"sku": "JOG-GRY-XL", "size": "XL", "color": "Heather Grey", "stock": 40, "price": 55.00, "base_daily": 1.0},
        ],
        "supplier": {
            "supplier_name": "Coastal Apparel Co.",
            "lead_time_days": 30,
            "moq": 60,
            "case_pack_size": 12,
        },
    },
    {
        "name": "Logo Baseball Hat",
        "category": "Accessories",
        "variants": [
            {"sku": "HAT-NAV-OS", "size": "One Size", "color": "Navy", "stock": 175, "price": 32.00, "base_daily": 0.2},  # DEAD
        ],
        "supplier": {
            "supplier_name": "ProStitch Headwear",
            "lead_time_days": 25,
            "moq": 144,
            "case_pack_size": 24,
        },
    },
    {
        "name": "Heavyweight Crewneck",
        "category": "Tops",
        "variants": [
            {"sku": "CREW-OAT-S", "size": "S", "color": "Oatmeal", "stock": 28, "price": 62.00, "base_daily": 0.8},
            {"sku": "CREW-OAT-M", "size": "M", "color": "Oatmeal", "stock": 18, "price": 62.00, "base_daily": 2.0},
            {"sku": "CREW-OAT-L", "size": "L", "color": "Oatmeal", "stock": 55, "price": 62.00, "base_daily": 1.7},
            {"sku": "CREW-OAT-XL", "size": "XL", "color": "Oatmeal", "stock": 42, "price": 62.00, "base_daily": 1.0},
            {"sku": "CREW-OAT-XXL", "size": "XXL", "color": "Oatmeal", "stock": 65, "price": 62.00, "base_daily": 0.3},
        ],
        "supplier": {
            "supplier_name": "Heritage Textile Group",
            "lead_time_days": 40,
            "moq": 40,
            "case_pack_size": 10,
        },
    },
]


# ---------------------------------------------------------------------------
# Sales generation helpers
# ---------------------------------------------------------------------------

def _seasonality_factor(d: date) -> float:
    """Return a multiplier (0.7 – 1.3) based on month — heavier sales in fall/winter."""
    month = d.month
    factors = {
        1: 1.15, 2: 1.05, 3: 0.90, 4: 0.80, 5: 0.75, 6: 0.70,
        7: 0.70, 8: 0.75, 9: 0.90, 10: 1.10, 11: 1.25, 12: 1.30,
    }
    return factors.get(month, 1.0)


def _day_of_week_factor(d: date) -> float:
    """Weekends sell ~20 % more, Tuesdays are slowest."""
    dow = d.weekday()  # 0=Mon ... 6=Sun
    factors = [0.95, 0.85, 0.95, 1.0, 1.10, 1.20, 1.15]
    return factors[dow]


def _generate_sales(variant_base_daily: float, days: int = HISTORY_DAYS) -> List[dict]:
    """Return a list of {date, quantity} dicts spanning *days* into the past."""
    records: List[dict] = []
    for offset in range(days, 0, -1):
        d = TODAY - timedelta(days=offset)
        lam = variant_base_daily * _seasonality_factor(d) * _day_of_week_factor(d)
        qty = max(0, int(random.gauss(lam, lam * 0.35)))
        if qty > 0:
            records.append({"sale_date": d, "quantity": qty})
    return records


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_database(db: Session, user_id: int) -> None:
    """Populate the database with mock products, variants, sales, and supplier info.

    Scoped to a specific user. Idempotent — checks whether user already has products.
    """
    existing = db.query(Product).filter(Product.user_id == user_id).first()
    if existing is not None:
        return  # Already seeded for this user

    random.seed(42)  # Reproducible data

    for product_def in PRODUCTS:
        product = Product(
            user_id=user_id,
            name=product_def["name"],
            category=product_def["category"],
            square_id=f"SQ-{product_def['name'][:4].upper()}-MOCK",
        )
        db.add(product)
        db.flush()  # Get product.id

        # Supplier
        sup = product_def["supplier"]
        supplier = SupplierInfo(product_id=product.id, **sup)
        db.add(supplier)

        # Variants + sales
        for v_def in product_def["variants"]:
            variant = ProductVariant(
                product_id=product.id,
                sku=v_def["sku"],
                size=v_def["size"],
                color=v_def["color"],
                current_stock=v_def["stock"],
                price=v_def["price"],
            )
            db.add(variant)
            db.flush()

            sales = _generate_sales(v_def["base_daily"])
            for s in sales:
                db.add(SalesRecord(variant_id=variant.id, quantity=s["quantity"], sale_date=s["sale_date"]))

    db.commit()
