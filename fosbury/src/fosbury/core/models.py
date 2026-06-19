"""Shared pydantic data models that travel between ETL stages.

These are the *data contracts* of the pipeline.  Every extractor returns raw
dicts/lists; every transformer validates them into these models before handing
them to the loader.  Using pydantic means validation errors are caught at
transformation time with field-level messages, not as cryptic KeyErrors deep
in the loader.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# LMP (Locational Marginal Price) models
# ---------------------------------------------------------------------------


class LmpRecord(BaseModel):
    """A single LMP observation for one pricing node at one timestamp.

    Prices are stored as ``Decimal`` to avoid floating-point drift when summing
    over many records.
    """

    timestamp_utc: datetime
    pnode_id: int
    pnode_name: str
    lmp_total: Decimal
    lmp_congestion: Decimal
    lmp_marginal_loss: Decimal
    lmp_energy: Decimal
    voltage_level: str | None = None

    @field_validator("timestamp_utc", mode="before")
    @classmethod
    def parse_timestamp(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(str(v))

    @field_validator("lmp_total", "lmp_congestion", "lmp_marginal_loss", "lmp_energy", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


class LmpDataset(BaseModel):
    """Collection of LMP records produced by one extractor run."""

    source: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    records: list[LmpRecord]

    @property
    def row_count(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# Grid constraint / congestion models
# ---------------------------------------------------------------------------


class ConstraintRecord(BaseModel):
    """A single binding transmission constraint observation."""

    timestamp_utc: datetime
    constraint_name: str
    contingency: str
    shadow_price: Decimal
    mw_flow: Decimal
    mw_limit: Decimal
    pct_loading: Decimal | None = None

    @field_validator("timestamp_utc", mode="before")
    @classmethod
    def parse_timestamp(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(str(v))

    @field_validator("shadow_price", "mw_flow", "mw_limit", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


class ConstraintDataset(BaseModel):
    """Collection of constraint records produced by one extractor run."""

    source: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    records: list[ConstraintRecord]

    @property
    def row_count(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# EIA electricity demand models
# ---------------------------------------------------------------------------


class DemandRecord(BaseModel):
    """Hourly electricity demand from the EIA API."""

    timestamp_utc: datetime
    respondent: str        # EIA balancing-authority code, e.g. "PJM"
    respondent_name: str
    value_mwh: Decimal
    type_name: str         # e.g. "Demand", "Net generation"

    @field_validator("timestamp_utc", mode="before")
    @classmethod
    def parse_timestamp(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        raw = str(v).replace("T", " ")
        return datetime.fromisoformat(raw)

    @field_validator("value_mwh", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))


class DemandDataset(BaseModel):
    """Collection of demand records produced by one extractor run."""

    source: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    records: list[DemandRecord]

    @property
    def row_count(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# Pipeline run-result model (returned by Pipeline.run)
# ---------------------------------------------------------------------------


class StageResult(BaseModel):
    """Summary of one completed ETL stage (one source_key)."""

    source_key: str
    success: bool
    rows_loaded: int = 0
    elapsed_s: float = 0.0
    error: str | None = None
