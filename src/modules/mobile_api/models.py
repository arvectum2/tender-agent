from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class MobileDeviceAccess(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mobile_device_access"

    device_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_mobile_device_access_revoked", "is_revoked", "updated_at"),
    )


class MobileDeviceRegistration(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mobile_device_registrations"

    device_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    apns_token: Mapped[str] = mapped_column(String(256), nullable=False)
    apns_environment: Mapped[str] = mapped_column(String(16), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_mobile_device_registration_enabled", "is_enabled", "updated_at"),
    )


class MobilePushDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mobile_push_deliveries"

    delivery_key: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("mobile_device_registrations.device_id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    deal_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    apns_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("delivery_key", name="uq_mobile_push_delivery_key"),
        Index("ix_mobile_push_delivery_status", "status", "created_at"),
        Index("ix_mobile_push_delivery_device", "device_id", "created_at"),
    )
