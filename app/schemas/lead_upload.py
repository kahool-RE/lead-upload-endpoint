from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LeadUploadRowError(BaseModel):
    row_number: int
    message: str
    listing_id: str | None = None
    address: str | None = None
    rule_outcome: Literal['rejected', 'low_priority'] = 'rejected'
    reasons: list[str] = Field(default_factory=list)


class LeadUploadLeadPreview(BaseModel):
    external_listing_id: str | None = None
    status: str | None = None
    address: str
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    county: str | None = None
    price: float | None = None
    bedrooms: float | None = None
    bathrooms: float | None = None
    square_footage: int | None = None
    lot_size: float | None = None
    year_built: int | None = None
    property_type: str | None = None
    owner_name: str | None = None
    owner_occupied: bool | None = None
    contact_name: str | None = None
    best_phone: str | None = None
    best_email: str | None = None
    list_agent_name: str | None = None
    list_agent_email: str | None = None
    list_agent_phone: str | None = None
    listing_office_name: str | None = None
    mls_number: str | None = None
    source: str | None = None
    source_url: str | None = None
    processed_at: datetime | None = None
    days_on_market: int | None = None
    apn: str | None = None
    remarks: str | None = None
    score: int
    priority: Literal['high', 'low']
    rule_outcome: Literal['accepted', 'low_priority']
    rule_reasons: list[str] = Field(default_factory=list)
    dedupe_key: str


class LeadUploadResponse(BaseModel):
    ok: bool = True
    mode: Literal['dry_run', 'commit']
    filename: str
    total_rows: int
    accepted_rows: int
    low_priority_rows: int = 0
    rejected_rows: int
    inserted: int = 0
    updated: int = 0
    skipped_duplicates: int = 0
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    preview: list[LeadUploadLeadPreview] = Field(default_factory=list)
    errors: list[LeadUploadRowError] = Field(default_factory=list)
    scoring_rules: dict[str, int] = Field(default_factory=dict)
    filter_rules: list[str] = Field(default_factory=list)
