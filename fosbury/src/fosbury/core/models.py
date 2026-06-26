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
    respondent: str        # EIA balancing-authority code, e.g. "DOM"
    respondent_name: str
    value_mwh: Decimal
    type_name: str         # e.g. "Demand", "Net generation"
    ticker: str = ""       # NYSE/NASDAQ ticker of the BA owner; "" if non-traded
    company_name: str = "" # Full name of the publicly traded parent company

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
# Grid Realization Pipeline — regulatory event models
# ---------------------------------------------------------------------------

# Valid categories from the GRP universal schema
DATA_TYPES = {"QUEUE_MILESTONE", "REGULATORY_PROTEST", "EQUIPMENT_DELAY"}


class GridEvent(BaseModel):
    """A single normalised regulatory or grid event from any scraper.

    The ``event_id`` is a SHA-256 hash of (source_url + raw_text_blob[:200])
    so the same filing never produces duplicate rows even across re-runs.
    """

    event_id: str
    iso_region: str                  # e.g. "PJM", "ERCOT"
    state_jurisdiction: str          # e.g. "VA", "OH", "PA", "FEDERAL"
    entity_target: str               # corporate name, e.g. "Dominion Energy"
    data_type: str                   # one of DATA_TYPES
    raw_text_blob: str               # cleaned excerpt ≤ 2000 chars
    metric_delta: int = 0            # quantified delay in calendar days
    keywords_matched: list[str] = Field(default_factory=list)
    source_url: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    alert_sent: bool = False

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v: str) -> str:
        if v not in DATA_TYPES:
            raise ValueError(f"data_type must be one of {DATA_TYPES}, got '{v}'")
        return v

    @field_validator("scraped_at", mode="before")
    @classmethod
    def parse_scraped_at(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(str(v))

    @field_validator("raw_text_blob")
    @classmethod
    def truncate_blob(cls, v: str) -> str:
        return v[:2000]


class GridEventDataset(BaseModel):
    """Collection of GridEvent records from one scraper run."""

    source: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    records: list[GridEvent]

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
