# 81% of AEP's Data Center Backlog Just Evaporated. My Bot Found It First.

*By Luke Jafarieh — Grid Realization Pipeline*

---

**In short:** A public regulatory filing revealed that 24,300 MW of data center demand behind AEP's Ohio grid quietly withdrew after a new tariff forced developers to put money down. The queue went from 30,000 MW to 5,700 MW overnight. Wall Street still hasn't connected the dots.

---

Three weeks ago, a filing hit the Ohio public utility commission docket. Nobody was reading it.

My pipeline was.

It flagged the document at 2:47 AM. By morning I had read it twice.

---

## The Finding

Here is the exact language from the filing, verbatim:

> *"The Columbus data center interconnection cluster has withdrawn 24,300 MW of uncommitted capacity requests following implementation of the take-or-pay tariff. Expected commercial operation dates have been extended by an average of 14 months across the affected queue positions. AEP projects that confirmed contracted load has declined from 30,000 MW to 5,700 MW of bankable demand."*
>
> — American Electric Power, Ohio PUC System Impact Study Update

**What this means in plain English:**

AEP had 30,000 megawatts of data centers in line to connect to its Ohio grid. When regulators forced those developers to financially commit -- pay a deposit or give up their spot -- **81% of them walked.** They were never really committed. They were holding free optionality in the queue.

The 30,000 MW of demand that AEP has been telling investors about? The real number is 5,700 MW.

---

<!-- CHART: Queue Collapse Bar Chart — 30,000 MW → 5,700 MW with 24,300 MW labeled "withdrew" -->

---

## Why This Gets More Dangerous From Here

This is not an AEP-specific problem. The tariff that triggered Ohio's collapse is now spreading across the entire PJM grid -- 13 states, 65 million people, the electricity backbone of the Mid-Atlantic and Midwest.

**The policy timeline:**

1. **Ohio (done):** AEP implements take-or-pay. 81% of the Columbus data center queue withdraws.
2. **Maryland (enacted, 2025-2026):** Two laws passed forcing BGE, Pepco, and Delmarva (all Exelon, $EXC) to create take-or-pay tariffs for loads over 25 MW. Maryland's ratepayer advocate is already in federal court over $1.6 billion in grid upgrades built for data centers that may not show up.
3. **New Jersey (passed legislature June 30, 2026):** 85% commitment required, 10-year term, projects over 50 MW. Pending Governor Sherrill's signature. PSE&G ($PEG) and JCP&L ($FE) are directly exposed.
4. **All 13 PJM governors:** Joint Statement of Principles, January 2026. Data centers pay for their own grid upgrades. Full stop.

---

<!-- CHART: PJM State Status Grid — 13 states, color-coded by tariff status (enacted / passed / pending / not yet) -->

---

## The Specific Stocks to Watch

| Utility | State | Ticker | Signal |
|---|---|---|------|
| American Electric Power | Ohio | $AEP | **Negative.** Queue collapsed 81%. Load growth guidance likely overstated. Watch Q3 earnings. |
| Exelon (BGE/Pepco/Delmarva) | Maryland | $EXC | **Caution.** Tariff enacted. Queue collapse data not yet public. |
| PSEG / PSE&G | New Jersey | $PEG | **Watch.** Bill passes, tariff standards set within 12 months. |
| FirstEnergy / JCP&L | New Jersey | $FE | **Watch.** Same NJ exposure as PEG. |
| PPL Electric | Pennsylvania | $PPL | **Positive (for now).** 9 GW active pipeline, no take-or-pay yet. But Ohio had 30,000 MW and we know how that ended. |

---

## The Information Gap Is the Point

The filing was publicly available the same morning it was submitted. It sat in a government portal, in a docket, behind search filters that most people don't know how to navigate.

Here is the step-by-step information lag:

| Step | What happens | Who knows |
|---|---|---|
| **1** | Filing hits Ohio PUC docket | GRP flags it at 2:47 AM |
| **2** | Regulatory analysts read it | Days to weeks later |
| **3** | Sell-side picks it up | Weeks later, if at all |
| **4** | Management addresses it | Next earnings call |
| **5** | Consensus estimates revise | Months after the filing |

Grid data is informationally rich and operationally inaccessible. That gap is the edge.

---

## What I Built (and How It Found This)

GRP is a Python ETL pipeline I built from scratch. It hits regulatory APIs on a schedule, extracts PDFs, scans for keywords, and runs Z-score anomaly detection on live electricity demand data from the EIA. When enough signal keywords appear in the same document, it fires a flag.

The Ohio filing matched five: *take-or-pay, queue withdrawal, bankable demand, commercial operation date, cost allocation.*

I'm a student. I taught myself Python building this, using Claude as a coding partner to understand what I was writing and debug what wasn't working. No formal CS background. Just a thesis and enough stubbornness to see it through.

The thesis: regulatory filings describe the physical state of the grid in real time. They lead earnings guidance by weeks or months. If you can read them at scale, you know before the market does.

Four standalone scripts showing exactly how GRP works -- no proprietary code, runnable with a free EIA API key:

**[github.com/ljafarieh/grp-public](https://github.com/ljafarieh/grp-public)**

The core loop, simplified:

```python
# 1. Pull live demand from EIA
demand = pull_hourly_demand(ba_code="AEP", days_back=30)

# 2. Flag anomalies with rolling Z-score
spikes = detect_anomalies(demand)   # threshold: 2.0σ over 168-hr window

# 3. Pull new regulatory filings
docs = get_new_documents(participant="American Electric Power")

# 4. Scan each PDF for signal keywords
for doc in docs:
    result = scan_pdf_url(doc["pdf_url"])
    if result.has_signal:
        alert(doc, result)          # 5+ keywords → flag
```

---

## What I'm Watching Next

- **Maryland BGE/Pepco dockets** — tariff is enacted. When does the queue move?
- **New Jersey BPU** — once Sherrill signs, the BPU sets standards within 12 months. First filings from PSE&G and JCP&L will be the tell.
- **AEP Q3 2026 earnings** — does management revise its data center load guidance? That's when this regulatory filing becomes a market event for retail investors.
- **Pennsylvania** — PPL has 9 GW of pipeline. No take-or-pay yet. Ohio's 30,000 MW looked real too.

---

The grid is the biggest infrastructure story of the decade. It plays out in documents nobody reads.

I'm trying to change that.

**Subscribe to get the next one** -- I'll be posting every time GRP flags something worth writing about.

---

*Not financial advice. All sources are fully public: Ohio PUCO, Maryland PSC, NJ BPU, VA SCC, FERC eLibrary, EIA Open Data.*
