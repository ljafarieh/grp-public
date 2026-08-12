"""GRP Daily Digest — run this after the pipeline to read today's findings.

Usage:
    python daily_digest.py          # today's events
    python daily_digest.py 2026-08-10  # specific date
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta


DB_PATH = "data/sqlite/fosbury.db"

# ---------------------------------------------------------------------------
# Interpretation layer — plain English explanation for each event
# ---------------------------------------------------------------------------

def _interpret(entity: str, data_type: str, keywords: list[str], blob: str, mw: int) -> str:
    """Return 2-3 sentences explaining what the finding means and why it matters."""

    kw_set = {k.lower() for k in keywords}
    entity_l = entity.lower()

    # --- AI / HPC companies -------------------------------------------------
    if any(x in entity_l for x in ["core scientific", "corz"]):
        if "interconnect" in kw_set or "notice to proceed" in kw_set:
            return (
                f"Core Scientific disclosed a grid interconnection development"
                f"{f' involving {mw:,} MW' if mw else ''}. "
                "For CORZ, every confirmed MW of interconnected capacity is a billable asset — "
                "they lease power to hyperscalers at a premium over spot prices. "
                "New interconnection approvals expand the revenue base directly."
            )
        if "hyperscaler" in kw_set or "power purchase agreement" in kw_set:
            return (
                "Core Scientific disclosed a new hyperscaler or power purchase agreement. "
                "These contracts are the main driver of CORZ's HPC revenue — locking in a "
                "customer at a fixed rate de-risks earnings and typically causes analyst upgrades."
            )

    if any(x in entity_l for x in ["keel", "bitfarms"]):
        if "panther creek" in kw_set or "sharon" in kw_set or "scrubgrass" in kw_set:
            return (
                "KEEL disclosed an update on its Pennsylvania sites (Panther Creek, Sharon, or Scrubgrass). "
                "These are the sites with established PJM interconnections that KEEL is converting from "
                "Bitcoin mining to AI data center hosting. Any change in status here directly affects "
                "how quickly they can sign hyperscaler leases."
            )
        if "interconnect" in kw_set or "pjm" in kw_set:
            return (
                f"KEEL filed a disclosure referencing its PJM grid position"
                f"{f' — {mw:,} MW mentioned' if mw else ''}. "
                "KEEL holds one of the few pre-approved large-scale interconnections in PJM Pennsylvania. "
                "Given the 2041 queue backlog, this position is increasingly valuable to hyperscalers "
                "who cannot get new capacity approved in time."
            )

    if "iren" in entity_l:
        return (
            f"IREN filed an update{f' referencing {mw:,} MW' if mw else ''} related to grid or interconnection. "
            "IREN is one of the former Bitcoin miners with approved PJM positions pivoting to AI/HPC. "
            "Watch for NTP issuances or ISA executions — those are the signals that a site "
            "has passed the point of no return and capital is committed."
        )

    if any(x in entity_l for x in ["cipher", "cifr"]):
        return (
            f"Cipher Mining disclosed a grid or capacity development{f' — {mw:,} MW referenced' if mw else ''}. "
            "Cipher is earlier in the AI/HPC pivot than CORZ or KEEL but holds Bitcoin mining "
            "infrastructure that could be repurposed. This is worth tracking as a potential "
            "acquisition target or pivot story."
        )

    if any(x in entity_l for x in ["applied digital", "apld"]):
        return (
            f"Applied Digital disclosed a power or interconnection development{f' — {mw:,} MW' if mw else ''}. "
            "APLD builds AI data centers and cloud infrastructure, competing directly in the "
            "same market as CORZ's HPC hosting business. Filings about power capacity "
            "signal their ability to sign new contracts."
        )

    if any(x in entity_l for x in ["terawulf", "wulf"]):
        return (
            f"TeraWulf filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "WULF operates nuclear-powered Bitcoin mining and is pivoting toward AI compute. "
            "Their nuclear power source gives them a carbon-free selling point that "
            "hyperscalers with sustainability mandates specifically seek out."
        )

    if any(x in entity_l for x in ["riot", "marathon", "cleanspark", "mara", "clsk", "bit digital", "btbt"]):
        return (
            f"{entity} filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "This is a large Bitcoin miner that has not yet fully pivoted to AI/HPC. "
            "Watch for language about data center hosting, hyperscaler agreements, or "
            "grid interconnection upgrades — those are signs the pivot is underway."
        )

    # --- Utilities ----------------------------------------------------------
    if "ppl" in entity_l:
        if "data center tariff" in kw_set or "large load tariff" in kw_set or "load commitment" in kw_set:
            return (
                "PPL filed a disclosure related to its large-load or data center tariff proceedings. "
                "The outcome of Pennsylvania's M-2025-3054271 docket directly determines whether "
                "PPL can charge data centers a take-or-pay tariff — guaranteed revenue whether or "
                "not the data center uses the power. A favorable ruling is a direct earnings upgrade for PPL."
            )
        if "interconnect" in kw_set or "transmission" in kw_set:
            return (
                f"PPL disclosed a transmission or interconnection development{f' — {mw:,} MW referenced' if mw else ''}. "
                "PPL is the primary utility serving Pennsylvania's growing data center load. "
                "More interconnection activity means more mandated transmission investment, "
                "which flows directly into PPL's regulated rate base and allowed earnings."
            )

    if "dominion" in entity_l:
        return (
            f"Dominion Energy filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "Dominion serves the Virginia data center corridor and has 70,000 MW of large-load "
            "requests in its queue per the Verrus filing. Any disclosure about queue processing, "
            "transmission investment, or co-location policy directly affects how fast "
            "that backlog clears — and how much capital Dominion must deploy."
        )

    if any(x in entity_l for x in ["american electric power", "aep"]):
        return (
            f"AEP disclosed a grid or capacity development{f' — {mw:,} MW referenced' if mw else ''}. "
            "AEP serves Ohio, which is showing 9.3% annual peak load growth — the highest in PJM. "
            "That growth requires significant transmission investment that AEP must fund, "
            "translating into higher rate base and regulated earnings over the next 3-5 years."
        )

    if "firstenergy" in entity_l or "fe" == entity_l:
        return (
            f"FirstEnergy filed a disclosure{f' — {mw:,} MW referenced' if mw else ''}. "
            "FirstEnergy serves Pennsylvania and Ohio, two of the highest load-growth states in PJM. "
            "They filed testimony in the PA large-load tariff proceeding, which means the outcome "
            "of that docket affects their revenue model directly alongside PPL."
        )

    if any(x in entity_l for x in ["exelon", "exc"]):
        return (
            f"Exelon filed a disclosure{f' — {mw:,} MW referenced' if mw else ''}. "
            "Exelon owns regulated utilities across PJM (ComEd, BGE, PECO, Pepco) and is "
            "the parent of the wires serving Maryland and DC's data center corridor. "
            "Interconnection disclosures signal where they are being forced to invest."
        )

    if "pseg" in entity_l:
        return (
            f"PSEG filed a disclosure{f' — {mw:,} MW referenced' if mw else ''}. "
            "PSEG serves New Jersey, which showed 308 MW of large-load adjustments in PJM's "
            "official forecast. They also own nuclear generation in PJM, so they benefit "
            "from both the transmission build and capacity scarcity pricing."
        )

    if "dte" in entity_l:
        return (
            f"DTE Energy filed a disclosure{f' — {mw:,} MW referenced' if mw else ''}. "
            "DTE serves Michigan inside PJM territory. Watch for large-load interconnection "
            "filings as data center demand spreads from Virginia and Pennsylvania into "
            "adjacent PJM states."
        )

    # --- Nuclear / Generation -----------------------------------------------
    if "constellation" in entity_l:
        if "co-location" in kw_set or "colocation" in kw_set:
            return (
                f"Constellation disclosed a nuclear co-location development{f' — {mw:,} MW' if mw else ''}. "
                "Constellation has already signed a co-location deal with Microsoft at its "
                "Crane Clean Energy Center. Additional co-location agreements would add "
                "contracted revenue on top of capacity market payments — a double earnings catalyst."
            )
        return (
            f"Constellation filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "As the largest nuclear operator in PJM, Constellation collects full capacity "
            "payments at the current price-cap level ($329-333/MW-day) with no fuel cost risk. "
            "Any disclosure about nuclear output, co-location, or capacity position is relevant "
            "to their earnings trajectory."
        )

    if "vistra" in entity_l:
        return (
            f"Vistra filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "Vistra owns nuclear and gas generation in PJM and has an active data center "
            "co-location deal with Amazon. Two consecutive price-cap capacity auctions "
            "are a direct tailwind for their generation earnings."
        )

    if "talen" in entity_l:
        return (
            f"Talen Energy filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "Talen owns the Susquehanna nuclear plant in Pennsylvania and has the Amazon "
            "Cumulus co-location deal already signed. Any update here affects the "
            "template other utilities and generators use for co-location deals going forward."
        )

    if "nrg" in entity_l:
        return (
            f"NRG Energy filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "NRG holds dispatchable gas and nuclear generation in PJM. Price-cap capacity "
            "auctions mean NRG earns scarcity rents on existing plants with no new capex. "
            "Watch for data center power agreements — NRG has been exploring direct supply deals."
        )

    if "entergy" in entity_l:
        return (
            f"Entergy filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "Entergy operates nuclear plants and transmission in parts of the eastern US. "
            "Monitor for any PJM-adjacent load growth disclosures or nuclear co-location "
            "language, which would signal they are pursuing the same strategy as Constellation."
        )

    if "cameco" in entity_l:
        return (
            f"Cameco filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "Cameco is the world's largest uranium producer. As nuclear co-location deals "
            "increase demand for long-term nuclear output, demand for uranium fuel rises. "
            "Cameco benefits upstream from every new nuclear power agreement signed."
        )

    if "ge vernova" in entity_l or "gev" in entity_l:
        return (
            f"GE Vernova filed a disclosure{f' referencing {mw:,} MW' if mw else ''}. "
            "GE Vernova makes the transformers, switchgear, and grid equipment that utilities "
            "must order to serve new large loads. Every MW of new interconnection approved "
            "in PJM eventually becomes a purchase order for grid hardware — GEV's backlog "
            "is a direct function of how fast the queue clears."
        )

    # --- Regulatory filings (VA SCC, PA PUC, etc.) --------------------------
    if data_type == "REGULATORY_PROTEST":
        if "co-location" in kw_set or "behind-the-meter" in kw_set:
            return (
                f"A regulatory filing by {entity} touched on nuclear co-location or "
                "behind-the-meter arrangements. These proceedings determine whether "
                "data centers can take power directly from a generator without going "
                "through the grid — a policy that, if approved broadly, reshapes "
                "how utilities price and deliver large loads."
            )
        if "ratepayer" in kw_set or "cost allocation" in kw_set:
            return (
                f"{entity} filed in a proceeding about who pays for grid upgrades "
                "needed to serve large loads. If regulators decide data centers pay "
                "the full cost, utilities like PPL lock in new revenue. If existing "
                "ratepayers absorb it, utilities still build — but data center margins compress."
            )

    if data_type == "LARGE_LOAD_FORECAST":
        return (
            f"PJM's official load forecast for {entity}'s service territory was updated"
            f"{f', showing {mw:,} MW of new large-load requests' if mw else ''}. "
            "This is PJM formally acknowledging that data center demand in this region "
            "is real and must be planned around — it forces the utility to file for "
            "new transmission investment, which feeds directly into regulated earnings."
        )

    if data_type == "CAPACITY_SCARCITY":
        return (
            f"The PJM capacity auction for {entity}'s region cleared at the price cap. "
            "This means there was not enough generation supply to meet demand at normal prices. "
            "Generator owners — especially nuclear operators like Constellation and Talen — "
            "collect the maximum allowed payment per MW, with no additional capital required."
        )

    if data_type == "QUEUE_MILESTONE":
        return (
            f"{entity} disclosed a grid queue development{f' — {mw:,} MW referenced' if mw else ''}. "
            "Queue milestones (ISA executed, NTP issued, under construction) signal that "
            "a project has moved past the study phase and capital is being committed. "
            "For AI/HPC companies, this is the moment a site becomes leaseable to hyperscalers."
        )

    if data_type == "DISCOVERY":
        return (
            f"The pipeline's discovery scanner surfaced {entity} as a potential new name "
            "matching the thesis — not currently on the watchlist. "
            "Review the source filing before drawing conclusions. "
            "If the grid position and financials hold up, this could be worth adding to coverage."
        )

    # Generic fallback
    return (
        f"{entity} filed a disclosure{f' referencing {mw:,} MW' if mw else ''} "
        f"matching keywords: {', '.join(keywords[:4])}. "
        "Review the source document to assess materiality."
    )


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

_CATEGORY_MAP = {
    "Core Scientific": "AI / HPC",
    "IREN Limited": "AI / HPC",
    "Keel Infrastructure": "AI / HPC",
    "Cipher Mining": "AI / HPC",
    "Applied Digital": "AI / HPC",
    "Bit Digital": "AI / HPC",
    "TeraWulf": "AI / HPC",
    "CleanSpark": "AI / HPC",
    "MARA Holdings": "AI / HPC",
    "Riot Platforms": "AI / HPC",
    "PPL Corporation": "UTILITIES",
    "Dominion Energy": "UTILITIES",
    "American Electric Power": "UTILITIES",
    "FirstEnergy": "UTILITIES",
    "FirstEnergy Pennsylvania": "UTILITIES",
    "Exelon": "UTILITIES",
    "PSEG": "UTILITIES",
    "DTE Energy": "UTILITIES",
    "Constellation Energy": "NUCLEAR / GENERATION",
    "Vistra Corp": "NUCLEAR / GENERATION",
    "Talen Energy": "NUCLEAR / GENERATION",
    "NRG Energy": "NUCLEAR / GENERATION",
    "Entergy": "NUCLEAR / GENERATION",
    "Cameco": "NUCLEAR / GENERATION",
    "GE Vernova": "NUCLEAR / GENERATION",
    "Appalachian Power": "UTILITIES",
}

_CATEGORY_ORDER = ["AI / HPC", "UTILITIES", "NUCLEAR / GENERATION", "REGULATORY", "DISCOVERY"]


def _get_category(entity: str, data_type: str) -> str:
    if data_type == "DISCOVERY":
        return "DISCOVERY"
    cat = _CATEGORY_MAP.get(entity)
    if cat:
        return cat
    if data_type in ("REGULATORY_PROTEST", "LARGE_LOAD_FORECAST", "CAPACITY_SCARCITY"):
        return "REGULATORY"
    return "REGULATORY"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_date = sys.argv[1] if len(sys.argv) > 1 else str(date.today())

    conn = sqlite3.connect(DB_PATH)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(grid_events)").fetchall()]

    # Pull events scraped today (or the specified date)
    rows = conn.execute(
        "SELECT * FROM grid_events WHERE date(scraped_at) = ? ORDER BY rowid DESC",
        (run_date,),
    ).fetchall()

    if not rows:
        # Fall back to last 24 hours if nothing for exact date
        rows = conn.execute(
            "SELECT * FROM grid_events WHERE scraped_at >= datetime('now', '-1 day') ORDER BY rowid DESC"
        ).fetchall()

    events = [dict(zip(cols, r)) for r in rows]

    # Group by category
    grouped: dict[str, list[dict]] = {c: [] for c in _CATEGORY_ORDER}
    for e in events:
        cat = _get_category(e["entity_target"], e["data_type"])
        grouped.setdefault(cat, []).append(e)

    total = len(events)
    discovery_count = len(grouped.get("DISCOVERY", []))

    # Print digest
    print()
    print(f"{'=' * 60}")
    print(f"  GRP DAILY DIGEST — {run_date}")
    print(f"  {total} signals  |  {discovery_count} discovery hits")
    print(f"{'=' * 60}")

    found_any = False
    for cat in _CATEGORY_ORDER:
        cat_events = grouped.get(cat, [])
        if not cat_events:
            continue
        found_any = True
        print(f"\n-- {cat} {'─' * (55 - len(cat))}")

        for e in cat_events:
            entity = e["entity_target"]
            data_type = e["data_type"]
            keywords = e["keywords_matched"].split(",") if e["keywords_matched"] else []
            blob = e["raw_text_blob"] or ""
            mw = e["metric_delta"] or 0
            url = e["source_url"] or ""

            print(f"\n  [{entity}]  {data_type}")
            print(f"  {_interpret(entity, data_type, keywords, blob, mw)}")
            if url:
                print(f"  Source: {url}")

    if not found_any:
        print("\n  No new signals today.")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
