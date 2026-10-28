import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="shopper")  # shopper | merchant | admin
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(253), unique=True)
    domain_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verify_token: Mapped[str] = mapped_column(String(64), default=lambda: uuid.uuid4().hex)
    country: Mapped[str] = mapped_column(String(2), default="pk")
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    plan: Mapped[str] = mapped_column(String(20), default="free")
    kind: Mapped[str] = mapped_column(String(10), default="store")  # store | social
    allow_training: Mapped[bool] = mapped_column(Boolean, default=False)  # opt-in: our try-on model may learn from photos
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    keys: Mapped[list["ApiKey"]] = relationship(back_populates="merchant", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(60), default="default")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    merchant: Mapped[Merchant] = relationship(back_populates="keys")


class CatalogItem(Base):
    """A product in Saasta's own index: partner uploads, crawled store pages, or social sellers."""

    __tablename__ = "catalog_items"
    __table_args__ = (Index("ix_catalog_source_ext", "domain", "external_id", unique=True),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    source: Mapped[str] = mapped_column(String(10), default="partner", index=True)  # partner | crawl | social
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(253), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(2048))
    image_url: Mapped[str] = mapped_column(String(2048))
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    category: Mapped[str | None] = mapped_column(String(40), index=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    rating: Mapped[float | None] = mapped_column(Float)
    reviews: Mapped[int | None] = mapped_column(Integer)
    phash: Mapped[str | None] = mapped_column(String(32))
    color_hist: Mapped[bytes | None] = mapped_column(LargeBinary)
    vec: Mapped[bytes | None] = mapped_column(LargeBinary)  # float16 unit vector from our fashion model
    color: Mapped[str | None] = mapped_column(String(20))
    allow_training: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, index=True)


class CrawlSite(Base):
    """A store domain our crawler indexes (public product pages only, robots.txt respected)."""

    __tablename__ = "crawl_sites"
    domain: Mapped[str] = mapped_column(String(253), primary_key=True)
    kind: Mapped[str | None] = mapped_column(String(12))  # shopify | sitemap
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    error: Mapped[str | None] = mapped_column(String(300))
    products: Mapped[int] = mapped_column(Integer, default=0)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Search(Base):
    __tablename__ = "searches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    merchant_id: Mapped[str | None] = mapped_column(String(32), index=True)  # set when via widget
    kind: Mapped[str] = mapped_column(String(10))  # image | video | url | text
    query_text: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(12), default="queued")  # queued|running|done|failed
    error: Mapped[str | None] = mapped_column(String(300))
    country: Mapped[str] = mapped_column(String(2), default="pk")
    media_key: Mapped[str | None] = mapped_column(String(80))
    result: Mapped[dict | None] = mapped_column(JSON)
    category: Mapped[str | None] = mapped_column(String(40), index=True)
    best_price: Mapped[float | None] = mapped_column(Float)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Click(Base):
    __tablename__ = "clicks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    search_id: Mapped[str | None] = mapped_column(String(32), index=True)
    merchant_id: Mapped[str | None] = mapped_column(String(32), index=True)
    url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str] = mapped_column(String(253), index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Watch(Base):
    """Price-drop watch on a product the shopper found."""

    __tablename__ = "watches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(2048))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    target_price: Mapped[float | None] = mapped_column(Float)
    last_price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    history: Mapped[list | None] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Board(Base):
    """Saved look board (shareable)."""

    __tablename__ = "boards"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    public: Mapped[bool] = mapped_column(Boolean, default=False)
    items: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TryOn(Base):
    __tablename__ = "tryons"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="queued")
    category: Mapped[str] = mapped_column(String(20))
    output_key: Mapped[str | None] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
