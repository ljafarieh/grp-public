# I Built a Bot That Reads Utility Filings. It Found Something the Market Missed.

*By Luke Jafarieh*

---

Everyone knows AI needs a lot of power. What fewer people talk about is what happens when the companies promising to deliver that power quietly admit they can't.

That's what I found. And I found it not by reading the Wall Street Journal or watching CNBC — I found it because a pipeline I built scrapes public regulatory filings that almost nobody reads.

---

## The Setup

Utility companies are legally required to file paperwork with state and federal regulators every time something meaningful changes on the grid. When a power line gets approved, when a new data center applies to connect, when a queue of projects gets studied — all of it goes into public dockets run by state public utility commissions and FERC (the Federal Energy Regulatory Commission).

These filings are completely public. They're just buried in government portals that are painful to navigate and written in a language that makes most people's eyes glaze over.

So I built something to read them automatically.

It's called the Grid Realization Pipeline — GRP. It's an agentic system that hits these regulatory APIs on a schedule, extracts PDFs, scans for signal keywords, runs anomaly detection on actual electricity demand data from the EIA (the U.S. Energy Information Administration), and flags anything that looks meaningful. The whole thing runs in Python, stores events in SQLite, and sends alerts when something hits.

I'm not a hedge fund. I'm just someone who thought physical grid data was underanalyzed and wanted to see what was actually in there.

---

## What It Found

A few weeks ago, GRP pulled a system impact study update from Ohio's public utility commission. It was filed by American Electric Power — AEP, one of the largest utilities in the country, ticker $AEP.

Here's the relevant excerpt, verbatim:

> *"The Columbus data center interconnection cluster has withdrawn 24,300 MW of uncommitted capacity requests following implementation of the take-or-pay tariff. Expected commercial operation dates have been extended by an average of 14 months across the affected queue positions. AEP projects that confirmed contracted load has declined from 30,000 MW to 5,700 MW of bankable demand."*

Let me translate that.

AEP had 30,000 megawatts of data centers lined up wanting to connect to its grid in Columbus, Ohio. They implemented a new rule — called a take-or-pay tariff — that said: if you want a spot in line, you have to financially commit to actually using the power you're asking for. You can't just hold a reservation.

When that rule went into effect, 24,300 MW — **81% of the queue** — disappeared overnight. The data centers that weren't actually committed walked away. What looked like a pipeline of 30,000 MW of new load turned out to be mostly speculative. The real, bankable demand was only 5,700 MW.

On top of that, the remaining projects got pushed back by an average of 14 months on their expected in-service dates.

---

## Why This Matters

### For AEP specifically

AEP has been telling investors a story about data center demand driving major load growth in Ohio. That story was real — but the queue numbers that backstopped it were inflated by speculators who never intended to actually build. Now that the take-or-pay tariff forced everyone to show their hand, the real number is about one-fifth of what was in the queue.

That's a material revision to AEP's near-term earnings narrative. It doesn't necessarily mean the stock goes down tomorrow — markets are weird and AEP has other growth drivers. But the load growth thesis for Columbus just took a major hit, and it came out in a regulatory filing most people weren't reading.

### For the broader sector

This isn't just an AEP story. Take-or-pay tariffs for large load customers are spreading across the entire PJM grid — which covers 13 states and serves 65 million people across the Mid-Atlantic and Midwest.

Maryland enacted two laws in 2025 and 2026 forcing utilities (mainly Exelon's BGE and Pepco) to create take-or-pay tariffs for data centers over 25 MW. New Jersey just passed a bill on June 30, 2026 requiring an 85% take-or-pay commitment over 10 years for data centers over 50 MW — pending the Governor's signature. All 13 PJM state governors signed a joint statement in January 2026 saying data centers need to pay for their own grid upgrades.

The question is: when Maryland's tariff takes effect and New Jersey's follows, do we see the same 80% queue collapse that happened in Ohio?

If yes, that's a bad signal for Exelon ($EXC) and PSEG ($PEG) — not because data centers aren't coming, but because the pipeline numbers their investor materials have been citing are probably just as inflated as AEP's were.

### For the macro picture

Here's the bigger point that I think is underappreciated.

The AI infrastructure narrative assumes demand is real. Every GPU cluster needs power. Every hyperscaler is racing to build. That part is true. But the way interconnection queues work, any developer — even one with no serious intention of building — can file for a grid connection and hold that spot. Until recently, it was basically free optionality.

Take-or-pay tariffs are the mechanism that forces the market to tell the truth. And when Ohio told the truth, 81% of the queue wasn't real.

If that ratio holds across other states, the "data center demand is going to double the grid" narrative is built on numbers that are significantly overstated. Not all of it — the real demand is still massive — but the speculative layer on top of it is thick.

That has implications beyond individual utility stocks. It matters for capacity auction prices in PJM (which hit record highs partly on data center demand projections). It matters for transmission infrastructure capex plans. It matters for the natural gas peaker plants being kept online specifically to serve expected data center load.

---

## The Policy Layer

What's interesting to me is that this isn't a market failure being corrected by the market. It's regulators stepping in with a specific policy instrument — the take-or-pay tariff — and the instrument is working exactly as intended.

Maryland's ratepayer advocate filed a FERC complaint in May 2026 saying Maryland residents are on the hook for $1.6 billion in transmission upgrades built for data centers that may or may not materialize. That complaint is the political force driving more aggressive tariff design.

The pattern is: ratepayers feel the cost → legislators act → regulators implement take-or-pay → speculative queue collapses → actual committed demand becomes visible → utilities revise their load growth forecasts.

We're probably at step 3 nationally. Ohio got to step 4. Maryland and New Jersey are about to find out what their step 4 looks like.

---

## How GRP Found It Before Anyone Else

The filing was public the day it was submitted to the Ohio PUC. It sat in a docket database that requires you to know what you're looking for, navigate a government portal, download a PDF, and actually read it.

GRP does all of that automatically. It monitors the active dockets, pulls new documents as they're filed, extracts the text, and runs it against a keyword list that includes things like "queue withdrawal," "take-or-pay," "commercial operation date," and "bankable demand." When enough of those appear in the same document, it flags it as a signal.

That's the thesis behind the whole project: public grid data is informationally rich but operationally inaccessible. Most of the people who could act on it don't have the infrastructure to read it at scale. Most of the people who build that infrastructure don't think to look at utility filings.

The gap is the edge.

---

## The Code (Simplified)

I'm not open-sourcing the full pipeline, but I posted four standalone snippets on GitHub that show exactly how each layer works. You can run all of them with `pip install httpx pandas pdfplumber` and a free EIA API key.

**[→ github.com/yourusername/grp-public](https://github.com/yourusername/grp-public)**

Here's the gist of how the four pieces fit together:

**Layer 1 — Pull live demand from EIA**

The EIA Open Data API publishes hourly electricity demand for every balancing authority in the country. One API call, JSON back, and you know how many megawatts AEP's customers are consuming right now.

```python
resp = httpx.get(
    "https://api.eia.gov/v2/electricity/rto/region-data/data/",
    params={
        "api_key":               EIA_API_KEY,
        "facets[respondent][]":  "AEP",
        "facets[type][]":        "D",   # D = demand
        "frequency":             "hourly",
    }
)
rows = resp.json()["response"]["data"]
```

**Layer 2 — Flag statistical anomalies**

A rolling 7-day Z-score flags demand readings that are more than 2 standard deviations above the recent average. When a utility's load spikes abnormally, it often precedes a public announcement about a new large customer connecting.

```python
df["rolling_mean"] = df["value_mwh"].rolling(window=168).mean()
df["rolling_std"]  = df["value_mwh"].rolling(window=168).std()
df["zscore"]       = (df["value_mwh"] - df["rolling_mean"]) / df["rolling_std"]

spikes = df[df["zscore"] >= 2.0]
```

**Layer 3 — Hit the regulatory API**

Most state utility commission portals have a JavaScript frontend that calls a JSON API under the hood. Reverse-engineer the network requests and you can query it directly — no browser needed. Here's Virginia's SCC:

```python
cases = httpx.get(
    "https://www.scc.virginia.gov/DocketSearchAPI/breeze/"
    "CASES_ESTABDATE/GetCasesEstDateByParticipant",
    params={"Participant": "Dominion"},
    headers={"X-Requested-With": "XMLHttpRequest"},
).json()

# Then fetch documents for a specific case
docs = httpx.get(
    "https://www.scc.virginia.gov/DocketSearchAPI/breeze/"
    "CaseDetails/GetDocuments",
    params={
        "$filter": f"MATTER_NO eq {matter_no}",
        "$select": "Document_Name,Date_Filed,DocID,FileName",
    },
).json()
```

**Layer 4 — Scan the PDF**

Download the PDF, extract the text with pdfplumber, run keyword matching. Two or more signal keywords in the same document triggers a flag.

```python
with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)

keywords_found = [kw for kw in SIGNAL_KEYWORDS if kw.lower() in text.lower()]

if len(keywords_found) >= 2:
    print("SIGNAL:", keywords_found)
```

That's the whole detection loop. The Ohio filing hit on: `"take-or-pay"`, `"queue withdrawal"`, `"bankable demand"`, `"commercial operation date"`, and `"cost allocation"` — five keywords, well above the threshold.

Full standalone snippets, with comments, at the GitHub link above.

---

## What I'm Watching Next

- **Maryland BGE/Pepco dockets** — when the large-load tariff finalizes, does the queue move?
- **New Jersey BPU** — Governor Sherrill signs the bill, then BPU has 12 months to set standards. I'll be watching what PSE&G and JCP&L file when those standards drop.
- **AEP's Q3 2026 earnings call** — does management revise data center load growth guidance? That's the moment this filing becomes a market event.
- **Pennsylvania** — PPL has 9 GW of active data center pipeline and no take-or-pay tariff yet. If Pennsylvania moves, PPL is the next test case. Right now that 9 GW looks real — but Ohio's 30,000 MW looked real too.

---

The grid is the most important infrastructure story of the decade and it plays out in documents that nobody reads. I'm trying to change that.

More to come.

---

*This is not financial advice. GRP is a research tool. All data sourced from public regulatory filings: Ohio PUCO, Maryland PSC, PA PUC, VA SCC, and FERC eLibrary.*
