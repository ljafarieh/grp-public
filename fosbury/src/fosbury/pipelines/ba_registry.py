"""Balancing Authority (BA) → publicly traded parent company registry.

Maps the EIA respondent codes returned by the v2 API to the utility company
that owns or operates that balancing authority and its stock ticker.

Sources: EIA-861, FERC Form 714, SEC filings.
Last verified: 2026-06.

Usage::

    from fosbury.pipelines.ba_registry import lookup_ba

    info = lookup_ba("DOM")
    info.ticker        # "D"
    info.company_name  # "Dominion Energy"
    info.notes         # "Dominion Energy Virginia transmission zone"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BAInfo:
    ticker: str        # NYSE/NASDAQ ticker; "" if not publicly traded
    company_name: str  # Full legal name of the public parent
    notes: str = ""    # Brief context (subsidiary, merger history, etc.)


# ---------------------------------------------------------------------------
# Registry — keyed by EIA respondent code (upper-case)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, BAInfo] = {
    # ── PJM region ──────────────────────────────────────────────────────────
    "PJM":   BAInfo("",    "PJM Interconnection (non-traded ISO)", "Grid operator for 13-state Mid-Atlantic/Midwest footprint"),
    "DOM":   BAInfo("D",   "Dominion Energy",            "Dominion Energy Virginia transmission zone"),
    "DOMV":  BAInfo("D",   "Dominion Energy",            "Dominion Energy Virginia (alt code)"),
    "AEP":   BAInfo("AEP", "American Electric Power",    "AEP Texas/Ohio/WV service territories"),
    "AECI":  BAInfo("AEP", "American Electric Power",    "AEP Central Interconnection"),
    "FE":    BAInfo("FE",  "FirstEnergy",                "FirstEnergy transmission zone (OH/PA/NJ/WV/MD)"),
    "ATSI":  BAInfo("FE",  "FirstEnergy",                "American Transmission Systems Inc. — FE subsidiary"),
    "DAY":   BAInfo("AES", "AES Corporation",            "Dayton Power & Light — AES subsidiary (DP&L)"),
    "DUK":   BAInfo("DUK", "Duke Energy",                "Duke Energy Carolinas / Progress Energy"),
    "CPLE":  BAInfo("DUK", "Duke Energy",                "Duke Energy Progress East (formerly Progress Energy Carolinas)"),
    "CPLW":  BAInfo("DUK", "Duke Energy",                "Duke Energy Progress West"),
    "EXC":   BAInfo("EXC", "Exelon",                     "Exelon Utilities: ComEd, PECO, BGE, PHI"),
    "PECO":  BAInfo("EXC", "Exelon",                     "PECO Energy — Exelon subsidiary (PA)"),
    "BGE":   BAInfo("EXC", "Exelon",                     "Baltimore Gas & Electric — Exelon (MD)"),
    "PEPCO": BAInfo("EXC", "Exelon",                     "Pepco Holdings — Exelon (DC/MD)"),
    "PPL":   BAInfo("PPL", "PPL Corporation",            "PPL Electric Utilities (PA/KY)"),
    "PSEG":  BAInfo("PEG", "Public Service Enterprise Group", "PSEG (NJ)"),
    "JC":    BAInfo("PEG", "Public Service Enterprise Group", "Jersey Central Power & Light — PSEG subsidiary"),
    "METED": BAInfo("FE",  "FirstEnergy",                "Metropolitan Edison — FirstEnergy (PA)"),
    "PN":    BAInfo("FE",  "FirstEnergy",                "Penn Power — FirstEnergy (PA)"),
    "PE":    BAInfo("FE",  "FirstEnergy",                "Potomac Edison — FirstEnergy (MD/WV)"),
    "TEN":   BAInfo("TLN", "Talen Energy",               "Talen Energy Supply (PA nuclear, Susquehanna)"),

    # ── MISO region ─────────────────────────────────────────────────────────
    "MISO":  BAInfo("",    "MISO (non-traded ISO)",      "Midcontinent ISO — members include AEE, ETR, CMS, WEC"),
    "AEE":   BAInfo("AEE", "Ameren",                     "Ameren Missouri / Ameren Illinois"),
    "ETR":   BAInfo("ETR", "Entergy",                    "Entergy Arkansas/Louisiana/Mississippi/Texas"),
    "CMS":   BAInfo("CMS", "CMS Energy",                 "Consumers Energy — CMS subsidiary (MI)"),
    "WEC":   BAInfo("WEC", "WEC Energy Group",           "Wisconsin Energy / Peoples Energy (WI/IL)"),
    "DTE":   BAInfo("DTE", "DTE Energy",                 "Detroit Edison / Michigan Consolidated Gas"),
    "IP":    BAInfo("EXC", "Exelon",                     "Illinois Power — Ameren / now ComEd territory"),
    "NSP":   BAInfo("XEL", "Xcel Energy",                "Northern States Power (MN/WI/ND/SD)"),
    "SPS":   BAInfo("XEL", "Xcel Energy",                "Southwestern Public Service — Xcel (TX/NM)"),
    "PSCO":  BAInfo("XEL", "Xcel Energy",                "Public Service Co. of Colorado — Xcel"),
    "NSPW":  BAInfo("XEL", "Xcel Energy",                "Northern States Power-Wisconsin — Xcel"),

    # ── ISO-NE region ────────────────────────────────────────────────────────
    "ISNE":  BAInfo("",    "ISO New England (non-traded)", "Members: ES, AGR, UI, NSTAR"),
    "NSTAR": BAInfo("ES",  "Eversource Energy",          "NSTAR Electric — Eversource (MA)"),
    "PSNH":  BAInfo("ES",  "Eversource Energy",          "Public Service of NH — Eversource"),
    "WMECO": BAInfo("ES",  "Eversource Energy",          "Western Mass Electric — Eversource"),
    "CL&P":  BAInfo("ES",  "Eversource Energy",          "Connecticut Light & Power — Eversource"),
    "UI":    BAInfo("AGR", "Avangrid",                   "United Illuminating — Avangrid/Iberdrola (CT)"),
    "CMP":   BAInfo("AGR", "Avangrid",                   "Central Maine Power — Avangrid"),
    "RGE":   BAInfo("AGR", "Avangrid",                   "Rochester Gas & Electric — Avangrid"),
    "NYSEG": BAInfo("AGR", "Avangrid",                   "NY State Electric & Gas — Avangrid"),

    # ── NYISO region ─────────────────────────────────────────────────────────
    "NYIS":  BAInfo("",    "NYISO (non-traded ISO)",     "Members: AGR, CEG, EXC, CNL"),
    "CNL":   BAInfo("",    "Consolidated Edison",        "Con Ed (NYC) — private subsidiary of ConEd Inc (ED)"),
    "ED":    BAInfo("ED",  "Consolidated Edison",        "Consolidated Edison (NYC/Westchester)"),
    "ORAN":  BAInfo("AGR", "Avangrid",                   "Orange & Rockland — Avangrid (NY)"),

    # ── SPP region ────────────────────────────────────────────────────────────
    "SWPP":  BAInfo("",    "SPP (non-traded ISO)",       "Southwest Power Pool — members include OGE, GRMA, CLCO"),
    "OGE":   BAInfo("OGE", "OGE Energy",                 "Oklahoma Gas & Electric — OGE Energy (OK/AR)"),
    "GRMA":  BAInfo("",    "Grand River Dam Authority",  "Oklahoma public authority — non-traded"),
    "WFEC":  BAInfo("",    "Western Farmers Electric",   "Oklahoma co-op — non-traded"),

    # ── ERCOT (Texas) ────────────────────────────────────────────────────────
    "ERCO":  BAInfo("",    "ERCOT (non-traded ISO)",     "Texas grid — members include VST, NRG, CenterPoint"),
    "VST":   BAInfo("VST", "Vistra Energy",              "Vistra Energy (TX nuclear/coal/gas) — AI data center plays"),
    "NRG":   BAInfo("NRG", "NRG Energy",                 "NRG Energy (TX/NE retail + generation)"),
    "CNP":   BAInfo("CNP", "CenterPoint Energy",         "CenterPoint transmission & distribution (TX)"),

    # ── WECC / CAISO region ──────────────────────────────────────────────────
    "CISO":  BAInfo("",    "CAISO (non-traded ISO)",     "California ISO — members include PCG, SCE, SDG&E"),
    "PCG":   BAInfo("PCG", "PG&E Corporation",           "Pacific Gas & Electric (CA)"),
    "SCE":   BAInfo("EIX", "Edison International",       "Southern California Edison — Edison Intl subsidiary"),
    "SDGE":  BAInfo("SRE", "Sempra Energy",              "San Diego Gas & Electric — Sempra subsidiary"),
    "AVA":   BAInfo("AVA", "Avista Corporation",         "Avista Utilities (WA/ID/MT)"),
    "PGN":   BAInfo("POR", "Portland General Electric",  "Portland General Electric (OR)"),
    "PAC":   BAInfo("BRK.B","Berkshire Hathaway Energy", "PacifiCorp — BHE subsidiary (UT/OR/WA/WY/ID/CA)"),
    "NEVP":  BAInfo("BRK.B","Berkshire Hathaway Energy", "Nevada Power — BHE subsidiary"),
    "SPPC":  BAInfo("BRK.B","Berkshire Hathaway Energy", "Sierra Pacific Power — BHE subsidiary"),
    "PACE":  BAInfo("BRK.B","Berkshire Hathaway Energy", "PacifiCorp East — BHE"),
    "WAUW":  BAInfo("BRK.B","Berkshire Hathaway Energy", "MidAmerican Energy — BHE subsidiary (IA)"),
    "WALC":  BAInfo("",    "Western Area Power Administration", "Federal power marketing — non-traded"),
    "WACM":  BAInfo("",    "Western Area Power Administration", "WAPA Colorado/Missouri — non-traded"),
    "BPAT":  BAInfo("",    "Bonneville Power Administration",   "Federal BPA — non-traded"),
    "IPCO":  BAInfo("IDA", "IDACORP",                    "Idaho Power — IDACORP subsidiary"),
    "NWMT":  BAInfo("NWE", "NorthWestern Energy",        "NorthWestern Energy (MT/SD)"),

    # ── Southeast / Southern Co. ─────────────────────────────────────────────
    "SOCO":  BAInfo("SO",  "Southern Company",           "Alabama Power / Georgia Power / Mississippi Power"),
    "GVL":   BAInfo("SO",  "Southern Company",           "Georgia Power — Southern Co. subsidiary"),
    "TVA":   BAInfo("",    "Tennessee Valley Authority", "Federal agency — non-traded"),
    "LGEE":  BAInfo("PPL", "PPL Corporation",            "Louisville Gas & Electric / Kentucky Utilities — PPL"),

    # ── Independents with AI/data center relevance ───────────────────────────
    "CEG":   BAInfo("CEG", "Constellation Energy",       "Constellation nuclear fleet (IL/PA/MD/NY) — AI co-location plays"),
    "PWR":   BAInfo("PWR", "Quanta Services",            "Electric transmission construction — indirect exposure"),
    "GEV":   BAInfo("GEV", "GE Vernova",                 "Grid equipment (transformers, switchgear) — supply chain exposure"),
    "ETN":   BAInfo("ETN", "Eaton Corporation",          "Power management / data center UPS — indirect exposure"),
}

_UNKNOWN = BAInfo("", "Unknown", "BA code not in registry")


def lookup_ba(respondent_code: str) -> BAInfo:
    """Return :class:`BAInfo` for *respondent_code*, or an unknown sentinel.

    Args:
        respondent_code: EIA balancing-authority code (case-insensitive).

    Returns:
        :class:`BAInfo` with ticker, company_name, notes fields.
    """
    return _REGISTRY.get(respondent_code.upper(), _UNKNOWN)
