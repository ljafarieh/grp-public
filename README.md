# AI-Compute Buildout Research Pipeline

A modular Python tool for tracking and analyzing publicly traded companies
exposed to the AI-compute infrastructure buildout — power generation, grid
equipment, semiconductors, data-center real estate, critical minerals, and
uranium fuel.

---

## ⚠️ NOT FINANCIAL ADVICE

This tool is a **research and observation instrument**. Every output is
framed as an observation or a testable hypothesis with a stated confidence
level and the evidence behind it. Nothing here is a buy, sell, or hold
recommendation. Inclusion of any ticker in the universe is a **research
choice**, not an endorsement of any company or security.

---

## Thesis background

The analytical spine is the macro thesis from Leopold Aschenbrenner's
June 2024 essay *Situational Awareness: The Decade Ahead*. The tool treats
it as **a hypothesis to grade against reality**, not received wisdom:

> Frontier-AI compute is scaling by orders of magnitude, driving enormous
> capital into data centers. The binding physical constraint becomes electric
> power, so value accrues to the "picks and shovels" of the buildout —
> compute/semiconductors, power generation, grid/electrical equipment,
> cooling, and critical-mineral inputs.

This is one analyst's view, published ~2 years ago, and it is contested.
The tool lets you build a scorecard: has the thesis-aligned basket actually
outperformed? Are the predicted bottlenecks showing up in the data?

---

## Architecture

```
pipeline-project/
├── config/
│   └── universe.yaml       # Tagged ticker universe — edit this to change scope
├── ingestion/
│   ├── adapter.py          # Swappable data-source interface (yfinance today)
│   └── ingest.py           # Fetch OHLCV → merge → parquet cache
├── cache/                  # Local parquet files, one per ticker (.gitignored)
├── reports/                # Generated markdown reports (.gitignored)
├── run_pipeline.py         # Single entry point
├── .env.example            # API key template (never commit .env)
└── requirements.txt
```

**Three-tier decoupling:**
- `ingestion/` — knows about data sources and the cache; knows nothing about analysis
- `analysis/` *(Phase 1+)* — reads from cache; knows nothing about data sources or UI
- `reporting/` *(Phase 3+)* — reads analysis outputs; knows nothing about data sources

**Data source:** `yfinance` (Yahoo Finance, unofficial). Isolated behind
`DataSourceAdapter` in `adapter.py` — swapping to Polygon, Alpaca, or stooq
only requires adding a new subclass there.

**Cache:** one parquet file per ticker in `cache/`. Ingestion is incremental:
re-runs fetch only the missing date range, so they are fast and deterministic.

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Copy env template — no keys needed for Phase 0
cp .env.example .env

# 3. Run the pipeline
python run_pipeline.py
```

The first run fetches ~1 year of OHLCV history for all tickers and prints a
sanity-check table. Subsequent runs fetch only new trading days.

---

## Universe

Tickers are defined in [`config/universe.yaml`](config/universe.yaml).
Each entry has:

| Field | Description |
|---|---|
| `name` | Full company/fund name |
| `sector` | Broad GICS sector |
| `thesis_role` | Role in the AI-buildout supply chain (see below) |
| `notes` | Research rationale — why this ticker is in scope |

**Thesis roles:**

| Tag | What it represents |
|---|---|
| `compute_semis` | Chip design, fabrication, EDA |
| `power_generation` | Electricity generation (gas, nuclear, renewables) |
| `grid_transmission` | Transmission construction and engineering |
| `electrical_equipment` | Switchgear, transformers, UPS |
| `datacenter_reit` | Physical data-center ownership |
| `critical_minerals` | Rare earths, specialty metals |
| `uranium_fuel` | Uranium mining and enrichment |
| `benchmark` | Comparison indices (SPY, QQQ, XLU, XLE) |

To add a ticker, append it to `universe.yaml` with the appropriate tag.

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| 0 | ✅ Done | Scaffold, config, adapter, OHLCV ingestion, sanity check |
| 1 | Pending | Move detection (volatility-adjusted), news pull, cautious attribution |
| 2 | Pending | Correlations, lead-lag, sector rotation, thesis scorecard |
| 3 | Pending | Markdown reports + optional Streamlit dashboard |
| 4 | Pending | Lookahead-bias check, out-of-sample validation, multiple-testing report |

---

## Epistemic principles

- **No lookahead bias** — any backtested claim uses only data available at prediction time.
- **Multiple-comparisons honesty** — scanning many relationships surfaces spurious patterns. The tool reports how many tests were run and treats uncorrected findings as candidates, not facts.
- **Confidence on every claim** — low / medium / high, with stated reasoning.
- **Correlation ≠ causation** — respected in all attribution language.
- **Noise is a valid answer** — a report that concludes "nothing significant today" is correct and useful.
