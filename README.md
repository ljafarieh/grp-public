# Grid Realization Pipeline — Public Snippets

Code companions to [this Substack post](https://ljafarieh.substack.com) on how I built a system that reads public utility regulatory filings and found an 81% queue washout in AEP's Columbus data center cluster before it showed up anywhere in financial media.

These snippets demonstrate the four core techniques the pipeline uses. They're standalone and runnable with minimal setup. The full pipeline isn't open source, but this is enough to replicate the methodology.

---

## The Project

I'm a self-taught programmer who learned Python by building this. Most of my coding education has happened through trial and error, reading documentation, and working with Claude as a coding partner to debug and understand what I was building. I didn't take a class. I just had a thesis and wanted to see if I could build something to test it.

The thesis: the U.S. electricity grid is the most important infrastructure story of the next decade, and the data that describes it in real time is almost entirely public and almost entirely unread.

Every time a utility company wants to connect a new customer, build a transmission line, or update a demand forecast, they file paperwork with state and federal regulators. These filings describe the physical state of the grid in detail -- who is connecting, how much power they need, when it's expected to come online, and what's being cancelled. None of it gets synthesized. Most of it sits in government portals that are painful to navigate.

**Project Fosbury** is my attempt to change that. The full pipeline -- called the Grid Realization Pipeline (GRP) -- is built to answer a specific question: can public grid data predict stock-moving disclosures from utility companies before those disclosures happen?

The idea is that physical demand signals and regulatory filings lead earnings guidance by weeks or months. A utility's interconnection queue tells you what load growth they're expecting. A system impact study update tells you when that load growth gets revised. If you're reading those filings systematically, you know before the market does.

So far it's working. The AEP Ohio finding below is a real example.

---

## What GRP Does

Public utility regulators -- state PUCs, FERC, and grid operators like PJM -- publish enormous amounts of structured data about the physical electricity grid. System impact studies, interconnection queue updates, demand forecasts, docket filings. All of it is public. Almost none of it is read systematically.

GRP is a pipeline that:
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

Running these four layers together is how GRP detected the AEP Ohio filing -- a system impact study update disclosing that 24,300 MW (81%) of the Columbus data center interconnection queue had withdrawn after a take-or-pay tariff was implemented. The filing was public the day it was submitted. It sat in a government portal. Nobody was reading it systematically.

The gap between regulatory disclosure and market awareness is the edge.

---

*Not financial advice. All data sources are fully public.*
