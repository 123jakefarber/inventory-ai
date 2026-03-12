"""Square API client — syncs catalog, inventory counts, and orders into the local DB.

Supports both per-user OAuth tokens (multi-tenant) and mock fallback mode.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

import config
from database import Product, ProductVariant, SalesRecord, SupplierInfo

logger = logging.getLogger(__name__)

# Default supplier info for products synced from Square
DEFAULT_LEAD_TIME_DAYS = 30
DEFAULT_MOQ = 50
DEFAULT_CASE_PACK_SIZE = 12
DEFAULT_SUPPLIER_NAME = "Unknown Supplier"


class SquareService:
    """Thin wrapper around the Square Catalog, Inventory & Orders APIs."""

    def __init__(self, access_token: str = "", location_id: str = "") -> None:
        self._access_token: str = access_token
        self._base_url: str = config.SQUARE_BASE_URL
        self._location_id: str = location_id
        self._use_mock: bool = not self._access_token
        self._headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Square-Version": "2024-12-18",
        }

    @property
    def is_live(self) -> bool:
        return not self._use_mock

    # ------------------------------------------------------------------
    # High-level sync methods
    # ------------------------------------------------------------------

    async def sync_catalog(self, db: Session, user_id: int) -> Dict[str, int]:
        """Pull all ITEM catalog objects from Square and upsert into local DB."""
        if self._use_mock:
            logger.info("[MOCK] Catalog sync skipped — using local mock data.")
            return {"created": 0, "updated": 0}

        items = await self._list_catalog_items()
        created = 0
        updated = 0

        for item in items:
            item_data = item.get("item_data", {})
            square_id = item["id"]
            name = item_data.get("name", "Unnamed Product")
            category = ""

            if item_data.get("reporting_category"):
                cat_obj = item_data["reporting_category"]
                category = cat_obj.get("name", "")
            elif item_data.get("categories"):
                category = item_data["categories"][0].get("name", "")

            product = db.query(Product).filter(
                Product.square_id == square_id, Product.user_id == user_id
            ).first()
            if product is None:
                product = Product(user_id=user_id, square_id=square_id, name=name, category=category)
                db.add(product)
                db.flush()
                db.add(SupplierInfo(
                    product_id=product.id,
                    supplier_name=DEFAULT_SUPPLIER_NAME,
                    lead_time_days=DEFAULT_LEAD_TIME_DAYS,
                    moq=DEFAULT_MOQ,
                    case_pack_size=DEFAULT_CASE_PACK_SIZE,
                ))
                created += 1
            else:
                product.name = name
                if category:
                    product.category = category
                updated += 1

            for variation in item_data.get("variations", []):
                var_data = variation.get("item_variation_data", {})
                var_square_id = variation["id"]
                sku = var_data.get("sku") or var_square_id
                var_name = var_data.get("name", "Default")
                size = _parse_size(var_name)

                price_money = var_data.get("price_money", {})
                price = price_money.get("amount", 0) / 100.0

                existing_var = db.query(ProductVariant).filter(ProductVariant.sku == sku).first()
                if existing_var is None:
                    db.add(ProductVariant(
                        product_id=product.id,
                        sku=sku,
                        size=size,
                        color=var_name if size == "One Size" else "Default",
                        current_stock=0,
                        price=price,
                    ))
                else:
                    existing_var.price = price
                    existing_var.product_id = product.id

        db.commit()
        logger.info("Catalog sync complete: created=%d, updated=%d", created, updated)
        return {"created": created, "updated": updated}

    async def sync_inventory(self, db: Session) -> Dict[str, int]:
        """Pull inventory counts from Square and update local variant stock levels."""
        if self._use_mock:
            return {"synced": 0, "skipped": 0}

        counts = await self._batch_retrieve_inventory_counts()
        synced = 0
        skipped = 0

        for count in counts:
            catalog_object_id = count.get("catalog_object_id", "")
            quantity_str = count.get("quantity", "0")
            state = count.get("state", "")

            if state != "IN_STOCK":
                skipped += 1
                continue

            try:
                quantity = int(float(quantity_str))
            except (ValueError, TypeError):
                quantity = 0

            variant = db.query(ProductVariant).filter(ProductVariant.sku == catalog_object_id).first()
            if variant is None:
                skipped += 1
                continue

            variant.current_stock = quantity
            synced += 1

        db.commit()
        return {"synced": synced, "skipped": skipped}

    async def sync_orders(self, db: Session, days: int = 90) -> Dict[str, int]:
        """Pull orders from Square for the last N days and create SalesRecords."""
        if self._use_mock:
            return {"new_records": 0, "orders_processed": 0}

        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        orders = await self._search_orders(start_date, end_date)

        new_records = 0
        orders_processed = 0

        for order in orders:
            orders_processed += 1
            created_at = order.get("created_at", "")
            order_date = date.fromisoformat(created_at[:10]) if created_at else end_date

            for line_item in order.get("line_items", []):
                catalog_object_id = line_item.get("catalog_object_id", "")
                quantity_str = line_item.get("quantity", "1")

                try:
                    quantity = int(float(quantity_str))
                except (ValueError, TypeError):
                    quantity = 1

                if not catalog_object_id:
                    continue

                variant = db.query(ProductVariant).filter(ProductVariant.sku == catalog_object_id).first()
                if variant is None:
                    continue

                existing = (
                    db.query(SalesRecord)
                    .filter(SalesRecord.variant_id == variant.id, SalesRecord.sale_date == order_date)
                    .first()
                )
                if existing:
                    existing.quantity += quantity
                else:
                    db.add(SalesRecord(variant_id=variant.id, quantity=quantity, sale_date=order_date))
                new_records += 1

        db.commit()
        return {"new_records": new_records, "orders_processed": orders_processed}

    async def full_sync(self, db: Session, user_id: int = 0) -> Dict[str, Any]:
        """Run a complete sync: catalog -> inventory -> orders."""
        logger.info("Starting full Square sync...")
        catalog_stats = await self.sync_catalog(db, user_id)
        inventory_stats = await self.sync_inventory(db)
        orders_stats = await self.sync_orders(db)
        result = {
            "catalog": catalog_stats,
            "inventory": inventory_stats,
            "orders": orders_stats,
        }
        logger.info("Full sync complete: %s", result)
        return result

    # ------------------------------------------------------------------
    # Square API calls (paginated)
    # ------------------------------------------------------------------

    async def _list_catalog_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: Dict[str, str] = {"types": "ITEM"}
                if cursor:
                    params["cursor"] = cursor
                response = await client.get(
                    f"{self._base_url}/v2/catalog/list",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                items.extend(data.get("objects", []))
                cursor = data.get("cursor")
                if not cursor:
                    break
        return items

    async def _batch_retrieve_inventory_counts(self) -> List[Dict[str, Any]]:
        counts: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        if not self._location_id:
            logger.warning("Location ID not set — cannot sync inventory")
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                body: Dict[str, Any] = {"location_ids": [self._location_id]}
                if cursor:
                    body["cursor"] = cursor
                response = await client.post(
                    f"{self._base_url}/v2/inventory/counts/batch-retrieve",
                    headers=self._headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                counts.extend(data.get("counts", []))
                cursor = data.get("cursor")
                if not cursor:
                    break
        return counts

    async def _search_orders(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        orders: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        if not self._location_id:
            logger.warning("Location ID not set — cannot sync orders")
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                body: Dict[str, Any] = {
                    "location_ids": [self._location_id],
                    "query": {
                        "filter": {
                            "state_filter": {"states": ["COMPLETED"]},
                            "date_time_filter": {
                                "created_at": {
                                    "start_at": f"{start_date}T00:00:00Z",
                                    "end_at": f"{end_date}T23:59:59Z",
                                }
                            },
                        },
                        "sort": {"sort_field": "CREATED_AT", "sort_order": "ASC"},
                    },
                }
                if cursor:
                    body["cursor"] = cursor
                response = await client.post(
                    f"{self._base_url}/v2/orders/search",
                    headers=self._headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                orders.extend(data.get("orders", []))
                cursor = data.get("cursor")
                if not cursor:
                    break
        return orders

    # ------------------------------------------------------------------
    # Location helper
    # ------------------------------------------------------------------

    async def list_locations(self) -> List[Dict[str, Any]]:
        if self._use_mock:
            return [{"id": "MOCK", "name": "Mock Location", "status": "ACTIVE"}]

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/v2/locations",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json().get("locations", [])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_SIZE_MAP = {
    "xs": "XS", "extra small": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "extra large": "XL", "x-large": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL",
    "3xl": "3XL", "xxxl": "3XL",
    "os": "One Size", "one size": "One Size", "onesize": "One Size",
}


def _parse_size(name: str) -> str:
    """Try to extract a standard size from a variant name."""
    lower = name.strip().lower()
    if lower in _SIZE_MAP:
        return _SIZE_MAP[lower]
    for token in lower.split():
        if token in _SIZE_MAP:
            return _SIZE_MAP[token]
    return name
