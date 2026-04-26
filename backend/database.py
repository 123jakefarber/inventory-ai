"""SQLAlchemy database setup and ORM models."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from config import DATABASE_URL


# ---------------------------------------------------------------------------
# Engine & session
# ---------------------------------------------------------------------------
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    __allow_unmapped__ = True


# ---------------------------------------------------------------------------
# Dependency for FastAPI
# ---------------------------------------------------------------------------
def get_db():
    """Yield a database session, ensuring it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String(255), nullable=False)
    business_name: Optional[str] = Column(String(255), nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    products: List["Product"] = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    square_connection: Optional["SquareConnection"] = relationship("SquareConnection", back_populates="user", uselist=False, cascade="all, delete-orphan")


class SquareConnection(Base):
    __tablename__ = "square_connections"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token: str = Column(String(512), nullable=False)
    refresh_token: str = Column(String(512), nullable=False)
    token_expires_at: Optional[datetime] = Column(DateTime, nullable=True)
    merchant_id: Optional[str] = Column(String(64), nullable=True)
    location_id: Optional[str] = Column(String(64), nullable=True)
    connected_at: datetime = Column(DateTime, server_default=func.now())

    user: "User" = relationship("User", back_populates="square_connection")


class Product(Base):
    __tablename__ = "products"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    square_id: Optional[str] = Column(String(64), nullable=True)
    name: str = Column(String(255), nullable=False)
    category: str = Column(String(128), nullable=False, default="")
    image_url: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    user: "User" = relationship("User", back_populates="products")
    variants: List["ProductVariant"] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    supplier_info: Optional["SupplierInfo"] = relationship("SupplierInfo", back_populates="product", uselist=False, cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: int = Column(Integer, primary_key=True, index=True)
    product_id: int = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku: str = Column(String(64), nullable=False)
    size: str = Column(String(32), nullable=False, default="One Size")
    color: str = Column(String(64), nullable=False, default="Default")
    current_stock: int = Column(Integer, nullable=False, default=0)
    price: float = Column(Float, nullable=False, default=0.0)

    product: "Product" = relationship("Product", back_populates="variants")
    sales_records: List["SalesRecord"] = relationship("SalesRecord", back_populates="variant", cascade="all, delete-orphan")
    predictions: List["StockoutPrediction"] = relationship("StockoutPrediction", back_populates="variant", cascade="all, delete-orphan")
    alerts: List["Alert"] = relationship("Alert", back_populates="variant", cascade="all, delete-orphan")


class SalesRecord(Base):
    __tablename__ = "sales_records"

    id: int = Column(Integer, primary_key=True, index=True)
    variant_id: int = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    quantity: int = Column(Integer, nullable=False, default=1)
    sale_date: date = Column(Date, nullable=False)

    variant: "ProductVariant" = relationship("ProductVariant", back_populates="sales_records")


class SupplierInfo(Base):
    __tablename__ = "supplier_info"

    id: int = Column(Integer, primary_key=True, index=True)
    product_id: int = Column(Integer, ForeignKey("products.id"), nullable=False, unique=True)
    supplier_name: str = Column(String(255), nullable=False)
    lead_time_days: int = Column(Integer, nullable=False, default=30)
    moq: int = Column(Integer, nullable=False, default=50)
    case_pack_size: int = Column(Integer, nullable=False, default=12)

    product: "Product" = relationship("Product", back_populates="supplier_info")


class StockoutPrediction(Base):
    __tablename__ = "stockout_predictions"

    id: int = Column(Integer, primary_key=True, index=True)
    variant_id: int = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    predicted_stockout_date: Optional[date] = Column(Date, nullable=True)
    recommended_reorder_qty: int = Column(Integer, nullable=False, default=0)
    recommended_order_by_date: Optional[date] = Column(Date, nullable=True)
    daily_velocity: float = Column(Float, nullable=False, default=0.0)
    days_until_stockout: Optional[int] = Column(Integer, nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    variant: "ProductVariant" = relationship("ProductVariant", back_populates="predictions")


class Alert(Base):
    __tablename__ = "alerts"

    id: int = Column(Integer, primary_key=True, index=True)
    type: str = Column(String(32), nullable=False)  # stockout | dead_inventory | reorder
    variant_id: int = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    message: str = Column(Text, nullable=False)
    is_read: bool = Column(Boolean, nullable=False, default=False)
    created_at: datetime = Column(DateTime, server_default=func.now())

    variant: "ProductVariant" = relationship("ProductVariant", back_populates="alerts")


# ---------------------------------------------------------------------------
# Table creation helper
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
