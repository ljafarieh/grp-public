# Grid Realization Pipeline — Public Snippets

Code companions to [this Substack post](https://yoursubstack.com) on how I built an agentic system that reads public utility regulatory filings and found an 81% queue washout in AEP's Columbus data center cluster before the market did.

These snippets demonstrate the four core techniques the pipeline uses. They're standalone and runnable with minimal setup. The full pipeline isn't open source, but this is enough to replicate the methodology.

---

## What This Is

Public utility regulators — state PUCs, FERC, and grid operators like PJM — publish enormous amounts of structured data about the physical electricity grid. System impact studies, interconnection queue updates, demand forecasts, docket filings. All of it is public. Almost none of it is read systematically.

GRP (Grid Realization Pipeline) is an agentic ETL system that:
1. Pulls live electricity demand data from the U.S. Energy Information Administration API
2. Detects anomalies in that demand using Z-score statistics
3. Scrapes public regulatory dockets for relevant filings
4. Extracts and scans PDF text for signal keywords

Each snippet below corresponds to one of those four layers.

---

## Snippets

| File | What it demonstrates |
|---|---|
| [`01_eia_demand_pull.py`](01_eia_demand_pull.py) | Pulling live hourly electricity demand by utility from the EIA Open Data API |
| [`02_zscore_anomaly.py`](02_zscore_anomaly.py) | Detecting demand spikes using rolling Z-score statistics |
| [`03_regulatory_scraper.py`](03_regulatory_scraper.py) | Hitting a public state regulatory API to pull docket filings |
| [`04_pdf_signal_scanner.py`](04_pdf_signal_scanner.py) | Extracting text from regulatory PDFs and scanning for signal keywords |

---

## Setup

```bash
pip install httpx pandas pdfplumber
```

For snippet 1 you'll need a free EIA API key: [eia.gov/opendata](https://www.eia.gov/opendata/)

---

## The Finding

Running these four layers together is how GRP detected the AEP Ohio filing — a system impact study update disclosing that 24,300 MW (81%) of the Columbus data center interconnection queue had withdrawn after a take-or-pay tariff was implemented. The filing was public the day it was submitted. It sat in a government portal. Nobody was reading it systematically.

The gap between regulatory disclosure and market awareness is the edge.

---

*Not financial advice. All data sources are fully public.*
