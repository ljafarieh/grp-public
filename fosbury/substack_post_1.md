# I Built a Bot That Reads Utility Filings. It Found Something the Market Missed.

*By Luke Jafarieh*

---

Everyone knows AI needs a lot of power. What fewer people talk about is what happens when the companies promising to deliver that power quietly admit they can't.

That's what I found. Not from the Wall Street Journal or CNBC. From a pipeline I built that scrapes public regulatory filings that almost nobody reads.

---

## The Setup

Utility companies are legally required to file paperwork with state and federal regulators every time something meaningful changes on the grid. New power line approved, data center applying to connect, queue of projects getting studied: all of it goes into public dockets run by state public utility commissions and FERC (the Federal Energy Regulatory Commission).

These filings are completely public. They're buried in government portals that are painful to navigate, written in language that makes most people's eyes glaze over.

So I built something to read them automatically.

It's called the Grid Realization Pipeline, or GRP. It hits regulatory APIs on a schedule, extracts PDFs, scans for keywords, runs anomaly detection on actual electricity demand data from the EIA (the U.S. Energy Information Administration), and flags anything that looks meaningful. The whole thing runs in Python, stores events in SQLite, and sends alerts when something hits.

I'm not a hedge fund. I'm a student who thought physical grid data was underanalyzed and wanted to see what was actually in there.

---

## What It Found

A few weeks ago, GRP pulled a system impact study update from Ohio's public utility commission. Filed by American Electric Power, one of the largest utilities in the country (ticker $AEP).

The relevant excerpt, verbatim:

> *"The Columbus data center interconnection cluster has withdrawn 24,300 MW of uncommitted capacity requests following implementation of the take-or-pay tariff. Expected commercial operation dates have been extended by an average of 14 months across the affected queue positions. AEP projects that confirmed contracted load has declined from 30,000 MW to 5,700 MW of bankable demand."*

Let me translate that.

AEP had 30,000 megawatts of data centers lined up wanting to connect to its grid in Columbus, Ohio. They put a new rule in place called a take-or-pay tariff: if you want a spot in line, you have to financially commit to actually using the power you're asking for. You can't just hold a reservation.

When that rule kicked in, 24,300 MW -- **81% of the queue** -- walked away overnight. The data centers that weren't actually committed disappeared. What looked like 30,000 MW of real demand turned out to be mostly speculative. The actual bankable demand was 5,700 MW.

And the projects that stayed got pushed back an average of 14 months on their expected in-service dates.

---

## Why This Matters

### For AEP

AEP has been telling investors a story about data center demand driving major load growth in Ohio. That story was real, but the queue numbers backing it up were inflated by developers who never seriously intended to build. Once the tariff forced everyone to show their hand, the real figure came out at about one-fifth of what was in the queue.

That's a significant revision to AEP's near-term earnings story. It doesn't mean the stock craters tomorrow; markets are complicated and AEP has other growth drivers. But the load growth thesis for Columbus took a major hit, and it came out in a regulatory filing that wasn't getting read.

### For the broader sector

This isn't just an AEP problem. Take-or-pay tariffs are spreading across the entire PJM grid, which covers 13 states and 65 million people across the Mid-Atlantic and Midwest.

Maryland passed two laws in 2025 and 2026 forcing utilities (mainly Exelon's BGE and Pepco) to create take-or-pay tariffs for data centers over 25 MW. New Jersey passed a bill on June 30, 2026 requiring an 85% take-or-pay commitment over 10 years for data centers over 50 MW, pending the Governor's signature. All 13 PJM state governors signed a joint statement in January 2026 saying data centers need to pay for their own grid upgrades.

The question becomes: when Maryland's tariff takes full effect and New Jersey's follows, do we see the same 80% queue collapse that happened in Ohio?

If yes, that's a bad sign for Exelon ($EXC) and PSEG ($PEG). Not because data centers aren't coming, but because the pipeline numbers in their investor materials are probably just as inflated as AEP's were.

### For the macro picture

The AI infrastructure narrative assumes demand is real. Every GPU cluster needs power, every hyperscaler is racing to build: that part is true. But the way interconnection queues work, any developer -- even one with no real intention of building -- can file for a grid connection and hold that spot. Until recently it was basically free optionality.

Take-or-pay tariffs force the market to tell the truth. Ohio told the truth and 81% of the queue evaporated.

If that ratio holds in other states, the "data center demand is going to double the grid" story is built on numbers that are meaningfully overstated. The real demand is still enormous. But the speculative layer sitting on top of it is thick.

That has implications beyond individual utility stocks. It matters for capacity auction prices in PJM, which hit record highs partly on data center demand projections. It matters for transmission infrastructure spending plans. It matters for the natural gas peaker plants being kept online specifically to serve expected data center load that may not show up.

---

## The Policy Layer

What's interesting to me is that this isn't a market failure being corrected by the market. Regulators stepped in with a specific policy tool -- the take-or-pay tariff -- and the tool is working exactly as designed.

Maryland's ratepayer advocate filed a FERC complaint in May 2026 saying Maryland residents are on the hook for $1.6 billion in transmission upgrades built for data centers that may or may not materialize. That complaint is the political pressure driving more aggressive tariff design in other states.

The sequence plays out like this: ratepayers feel the cost, legislators act, regulators implement take-or-pay, the speculative queue collapses, actual committed demand becomes visible, utilities revise their load growth forecasts.

Nationally we're probably at step 3. Ohio got to step 4. Maryland and New Jersey are about to find out what their step 4 looks like.

---

## How GRP Found It

The filing was public the day it hit the Ohio PUC docket. It sat in a government database that requires you to know what you're looking for, navigate the portal, download the PDF, and actually read it.

GRP does all of that automatically. It monitors active dockets, pulls new documents as they're filed, extracts the text, and checks it against keywords including "queue withdrawal," "take-or-pay," "commercial operation date," and "bankable demand." When enough of those appear in the same document, it fires a flag.

The idea behind the project: public grid data is informationally rich but operationally inaccessible. The people who could act on it mostly don't have the infrastructure to read it at scale. The people who build that kind of infrastructure mostly don't think to point it at utility filings.

That gap is the edge.

---

## The Code (Simplified)

I'm not open-sourcing the full pipeline, but I posted four standalone scripts on GitHub that show exactly how each layer works. You can run all of them with `pip install httpx pandas pdfplumber` and a free EIA API key.

**[github.com/yourusername/grp-public](https://github.com/yourusername/grp-public)**

Here's how the four pieces fit together:

**Layer 1 -- Pull live demand from EIA**

The EIA Open Data API publishes hourly electricity demand for every balancing authority in the country. One API call returns JSON, and you can see how many megawatts AEP's customers are consuming right now.

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

**Layer 2 -- Flag statistical anomalies**

A rolling 7-day Z-score flags demand readings more than 2 standard deviations above the recent average. When a utility's load spikes abnormally, it often comes before a public announcement about a new large customer connecting.

```python
df["rolling_mean"] = df["value_mwh"].rolling(window=168).mean()
df["rolling_std"]  = df["value_mwh"].rolling(window=168).std()
df["zscore"]       = (df["value_mwh"] - df["rolling_mean"]) / df["rolling_std"]

spikes = df[df["zscore"] >= 2.0]
```

**Layer 3 -- Hit the regulatory API**

Most state utility commission portals have a JavaScript frontend that calls a JSON API underneath. Reverse-engineer the network requests and you can query it directly with no browser needed. Here's Virginia's SCC:

```python
cases = httpx.get(
    "https://www.scc.virginia.gov/DocketSearchAPI/breeze/"
    "CASES_ESTABDATE/GetCasesEstDateByParticipant",
    params={"Participant": "Dominion"},
    headers={"X-Requested-With": "XMLHttpRequest"},
).json()

docs = httpx.get(
    "https://www.scc.virginia.gov/DocketSearchAPI/breeze/"
    "CaseDetails/GetDocuments",
    params={
        "$filter": f"MATTER_NO eq {matter_no}",
        "$select": "Document_Name,Date_Filed,DocID,FileName",
    },
).json()
```

**Layer 4 -- Scan the PDF**

Download the PDF, extract the text with pdfplumber, run keyword matching. Two or more signal keywords in the same document triggers a flag.

```python
with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)

keywords_found = [kw for kw in SIGNAL_KEYWORDS if kw.lower() in text.lower()]

if len(keywords_found) >= 2:
    print("SIGNAL:", keywords_found)
```

The Ohio filing matched: `"take-or-pay"`, `"queue withdrawal"`, `"bankable demand"`, `"commercial operation date"`, and `"cost allocation"`. Five keywords, well above the threshold.

Full standalone scripts with comments are at the GitHub link above.

---

## What I'm Watching Next

- **Maryland BGE/Pepco dockets** -- when the large-load tariff finalizes, does the queue move?
- **New Jersey BPU** -- once Governor Sherrill signs the bill, the BPU has 12 months to set tariff standards. I'll be watching what PSE&G and JCP&L file when those standards drop.
- **AEP Q3 2026 earnings** -- does management revise its data center load growth guidance? That's when this filing becomes a market event.
- **Pennsylvania** -- PPL has 9 GW of active data center pipeline and no take-or-pay tariff yet. If Pennsylvania moves, PPL is the next test case. Right now that 9 GW looks real. But Ohio's 30,000 MW looked real too.

---

The grid is the most important infrastructure story of the decade and it plays out in documents nobody reads. I'm trying to change that.

More to come.

---

*Not financial advice. GRP is a research tool. All data sourced from public regulatory filings: Ohio PUCO, Maryland PSC, PA PUC, VA SCC, and FERC eLibrary.*
