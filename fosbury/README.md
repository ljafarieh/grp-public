# Project Fosbury — PJM Energy-Grid ETL Framework

An informational analytics pipeline that ingests public PJM Interconnection and
EIA electricity-grid data, transforms it into a validated analytical dataset, and
loads it into local SQLite + Parquet storage.

> **This is an informational/analytics tool only.** It does not execute trades,
> provide financial advice, or connect to any brokerage or market-participant
> system.

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│  CLI / run_example.py                                     │
│       │                                                   │
│       ▼                                                   │
│  Pipeline (orchestrator)                                  │
│       │  iterates PipelineStage objects from registry     │
│       │                                                   │
│  ┌────▼──────────┐   ┌──────────────────┐   ┌──────────┐ │
│  │  Extractor    │──▶│  Transformer     │──▶│  Loader  │ │
│  │  (Protocol)   │   │  (Protocol)      │   │ (Proto.) │ │
│  └───────────────┘   └──────────────────┘   └──────────┘ │
│                                                           │
│  Concrete implementations:                                │
│    PjmLmpExtractor        LmpTransformer        SQLite    │
│    PjmConstraintsExtractor ConstraintsTransformer Parquet │
│    EiaDemandExtractor     EiaDemandTransformer            │
└───────────────────────────────────────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| `typing.Protocol` for ETL contracts | Third-party extractors/loaders satisfy the interface without inheriting from Fosbury classes. Duck-typing at call sites, not nominal typing. |
| ABC base classes for concrete implementations | `@abstractmethod` gives a clear compile-time contract; shared retry/logging behaviour lives in the base, not duplicated in each concrete class. |
| Pydantic models as data contracts between stages | Validation errors surface at transformation time with field-level messages — not as `KeyError` deep in the loader. |
| `tenacity` for retry on every I/O boundary | Exponential backoff + jitter on HTTP; linear backoff on file I/O. Both are configurable via `.env`. |
| Plugin registry with `register_stage()` | Adding a new source = one file + one `register_stage()` call. Zero changes to the orchestrator. |
| Dual storage: SQLite + Parquet | SQLite for ad-hoc SQL; date-partitioned Parquet for columnar analytics (DuckDB, Polars, pandas). Same clean dataset writes to both. |
| `pydantic-settings` + `.env` | All config in one place; strict validation at startup, not silent fallbacks scattered through code. |
| Stub mode | `STUB_MODE=true` swaps live HTTP calls for fixture JSON. The full pipeline runs in CI without any API keys. |

---

## File layout

```
fosbury/
├── src/
│   └── fosbury/
│       ├── __init__.py
│       ├── __main__.py          ← CLI entry-point (fosbury / python -m fosbury)
│       ├── registry.py          ← plugin registry + built-in stage registrations
│       ├── core/
│       │   ├── protocols.py     ← Extractor, Transformer, Loader Protocols
│       │   ├── models.py        ← pydantic data contracts (LmpDataset, etc.)
│       │   ├── pipeline.py      ← Pipeline orchestrator
│       │   ├── retry.py         ← http_retry / io_retry decorators
│       │   ├── logging.py       ← structlog configuration
│       │   └── exceptions.py    ← domain exception hierarchy
│       ├── config/
│       │   └── settings.py      ← pydantic-settings Settings class
│       ├── extractors/
│       │   ├── base.py          ← BaseHttpExtractor (stub/live switching, retry)
│       │   ├── pjm_lmp.py       ← PJM 5-min ex-post LMP
│       │   ├── pjm_constraints.py ← PJM binding constraints
│       │   └── eia_demand.py    ← EIA hourly demand
│       ├── transformers/
│       │   ├── base.py          ← BaseTransformer (shared helpers)
│       │   ├── lmp.py
│       │   ├── constraints.py
│       │   └── eia_demand.py
│       └── loaders/
│           ├── sqlite_loader.py ← upsert to SQLite
│           └── parquet_loader.py ← date-partitioned Parquet
├── tests/
│   ├── conftest.py
│   ├── fixtures/                ← JSON stubs for all three sources
│   ├── unit/
│   │   ├── test_pipeline.py
│   │   ├── test_transformers.py
│   │   ├── test_loaders.py
│   │   └── test_retry.py
│   └── integration/
│       └── test_stub_pipeline.py
├── data/
│   ├── sqlite/                  ← fosbury.db written here
│   └── parquet/                 ← date-partitioned Parquet written here
├── run_example.py               ← runnable demo (no credentials needed)
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Quick start

### 1. Install

```bash
cd fosbury/
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set STUB_MODE=true to run without credentials (default)
```

### 3. Run the example

```bash
python run_example.py
```

Or via the CLI:

```bash
fosbury --stub                     # all sources, stub mode
fosbury --stub --source pjm_lmp    # single source
fosbury --log-level DEBUG          # verbose
```

### 4. Run tests

```bash
pytest                                         # all tests
pytest -m "not integration"                    # unit tests only
pytest tests/unit/test_transformers.py -v      # specific file
pytest --cov=fosbury --cov-report=term-missing # coverage
```

---

## Live data

To run against real APIs, edit `.env`:

```dotenv
STUB_MODE=false

# Required for EIA demand data
EIA_API_KEY=your_key_here        # free at https://www.eia.gov/opendata/

# Optional — PJM public LMP/constraints endpoints work without a key.
# Set only if you have a PJM subscription.
PJM_API_KEY=
```

### Where to get API keys

| Source | URL | Cost |
|---|---|---|
| EIA Open Data | https://www.eia.gov/opendata/ | Free |
| PJM Data Miner 2 (public endpoints) | https://dataminer2.pjm.com | Free, no key |
| PJM Data Miner 2 (subscription) | https://www.pjm.com/markets-and-operations/etools/data-miner-2 | Paid |

---

## Adding a new data source

1. **Extractor** — create `src/fosbury/extractors/my_source.py`:

```python
from fosbury.extractors.base import BaseHttpExtractor

class MySourceExtractor(BaseHttpExtractor):
    source_key = "my_source"

    def _live_extract(self):
        return self._get_json("https://api.example.com/data")
```

2. **Transformer** — create `src/fosbury/transformers/my_source.py`:

```python
from fosbury.transformers.base import BaseTransformer

class MySourceTransformer(BaseTransformer):
    def transform(self, raw):
        # validate and return a pydantic dataset model
        ...
```

3. **Fixture** — add `tests/fixtures/my_source.json` (sample API response).

4. **Register** — add to the bottom of `src/fosbury/registry.py`:

```python
def _build_my_source(settings):
    from fosbury.extractors.my_source import MySourceExtractor
    from fosbury.transformers.my_source import MySourceTransformer
    from fosbury.loaders.sqlite_loader import SqliteLoader
    from fosbury.loaders.parquet_loader import ParquetLoader
    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="my_source",
        extractor=MySourceExtractor(settings),
        transformer=MySourceTransformer(),
        loaders=[SqliteLoader(settings.sqlite_path), ParquetLoader(settings.parquet_dir)],
    )

register_stage("my_source", _build_my_source, "My new source")
```

No other files change.

---

## Querying the output

### SQLite

```bash
sqlite3 data/sqlite/fosbury.db
```

```sql
-- Highest-congestion intervals
SELECT timestamp_utc, pnode_name, lmp_congestion
FROM lmp
ORDER BY CAST(lmp_congestion AS REAL) DESC
LIMIT 10;

-- Most-binding constraints by shadow price
SELECT constraint_name, MAX(CAST(shadow_price AS REAL)) AS max_shadow
FROM constraints
GROUP BY constraint_name
ORDER BY max_shadow DESC;
```

### Parquet (DuckDB)

```python
import duckdb
conn = duckdb.connect()
df = conn.execute(
    "SELECT * FROM read_parquet('data/parquet/lmp/**/*.parquet') "
    "WHERE lmp_congestion < -5 ORDER BY lmp_congestion"
).df()
```
