from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    dom: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_occupied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    outreach_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="new", server_default="new", index=True
    )
    do_not_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)

    message_events = relationship(
        "MessageEvent",
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MessageEvent.id",
    )

    __table_args__ = (
        Index("ix_leads_address_city_state_zip", "address", "city", "state", "zip"),
        Index("ix_leads_outreach_status_score", "outreach_status", "score"),
    )
