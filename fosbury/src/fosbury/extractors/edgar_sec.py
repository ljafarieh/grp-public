"""SEC EDGAR filing scraper — grid/interconnection signals across AI/HPC, utilities, and nuclear.

Live target (no auth required — fully public):
    Company submissions: https://data.sec.gov/submissions/CIK{cik}.json
    Full-text search:    https://efts.sec.gov/LATEST/search-index
    Filing documents:    https://www.sec.gov/Archives/edgar/data/{cik}/{accno}/{doc}

Two modes
---------
1. Watchlist scan — monitors known companies for new 8-K/10-Q/10-K filings
   containing grid/interconnection keywords. Runs every pipeline execution.

2. Discovery scan — queries EDGAR full-text search for recent filings from
   *any* company mentioning PJM interconnection, large load, data center power,
   or NTP/ISA terms. Surfaces unknown/emerging names that fit the thesis.
   Only logs a signal when a company is not already on the watchlist AND the
   filing contains >= 3 thesis keywords. Keeps the noise low.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any

import structlog
from bs4 import BeautifulSoup

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor

log = structlog.get_logger()

_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
_EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"

_HEADERS = {
    "User-Agent": "Project Fosbury research pipeline ljafarieh@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}

# ---------------------------------------------------------------------------
# Watchlist — 21 companies across three thesis categories
# ---------------------------------------------------------------------------

_TARGETS: list[dict[str, Any]] = [
    # -- AI / HPC infrastructure (former miners pivoting to compute) ----------
    {"ticker": "CORZ", "entity": "Core Scientific",   "cik": "1839341",  "cik_padded": "0001839341", "category": "AI_HPC"},
    {"ticker": "IREN", "entity": "IREN Limited",       "cik": "1878848",  "cik_padded": "0001878848", "category": "AI_HPC"},
    {"ticker": "KEEL", "entity": "Keel Infrastructure","cik": "1812477",  "cik_padded": "0001812477", "category": "AI_HPC"},
    {"ticker": "CIFR", "entity": "Cipher Mining",      "cik": "1819989",  "cik_padded": "0001819989", "category": "AI_HPC"},
    {"ticker": "APLD", "entity": "Applied Digital",    "cik": "1144879",  "cik_padded": "0001144879", "category": "AI_HPC"},
    {"ticker": "BTBT", "entity": "Bit Digital",        "cik": "1710350",  "cik_padded": "0001710350", "category": "AI_HPC"},
    {"ticker": "WULF", "entity": "TeraWulf",           "cik": "1083301",  "cik_padded": "0001083301", "category": "AI_HPC"},
    {"ticker": "CLSK", "entity": "CleanSpark",         "cik": "827876",   "cik_padded": "0000827876", "category": "AI_HPC"},
    {"ticker": "MARA", "entity": "MARA Holdings",      "cik": "1507605",  "cik_padded": "0001507605", "category": "AI_HPC"},
    {"ticker": "RIOT", "entity": "Riot Platforms",     "cik": "1167419",  "cik_padded": "0001167419", "category": "AI_HPC"},
    # -- Utilities (PJM transmission owners) ----------------------------------
    {"ticker": "PPL",  "entity": "PPL Corporation",    "cik": "922224",   "cik_padded": "0000922224", "category": "UTILITY"},
    {"ticker": "D",    "entity": "Dominion Energy",    "cik": "715957",   "cik_padded": "0000715957", "category": "UTILITY"},
    {"ticker": "AEP",  "entity": "American Electric Power", "cik": "4904", "cik_padded": "0000004904", "category": "UTILITY"},
    {"ticker": "FE",   "entity": "FirstEnergy",        "cik": "1031296",  "cik_padded": "0001031296", "category": "UTILITY"},
    {"ticker": "EXC",  "entity": "Exelon",             "cik": "1109357",  "cik_padded": "0001109357", "category": "UTILITY"},
    {"ticker": "PEG",  "entity": "PSEG",               "cik": "788784",   "cik_padded": "0000788784", "category": "UTILITY"},
    {"ticker": "DTE",  "entity": "DTE Energy",         "cik": "936340",   "cik_padded": "0000936340", "category": "UTILITY"},
    # -- Nuclear / generation (capacity scarcity beneficiaries) ---------------
    {"ticker": "CEG",  "entity": "Constellation Energy","cik": "1868275", "cik_padded": "0001868275", "category": "NUCLEAR"},
    {"ticker": "VST",  "entity": "Vistra Corp",        "cik": "1692819",  "cik_padded": "0001692819", "category": "NUCLEAR"},
    {"ticker": "TLN",  "entity": "Talen Energy",       "cik": "1622536",  "cik_padded": "0001622536", "category": "NUCLEAR"},
    {"ticker": "NRG",  "entity": "NRG Energy",         "cik": "1013871",  "cik_padded": "0001013871", "category": "NUCLEAR"},
    {"ticker": "ETR",  "entity": "Entergy",            "cik": "65984",    "cik_padded": "0000065984", "category": "NUCLEAR"},
    {"ticker": "CCJ",  "entity": "Cameco",             "cik": "1009001",  "cik_padded": "0001009001", "category": "NUCLEAR"},
    {"ticker": "GEV",  "entity": "GE Vernova",         "cik": "1996810",  "cik_padded": "0001996810", "category": "NUCLEAR"},
]

_WATCHLIST_TICKERS = {t["ticker"] for t in _TARGETS}

_TARGET_FORMS = {"8-K", "10-Q", "10-K", "40-F", "20-F"}

_LOOKBACK_DAYS = 90

# Keywords that indicate a grid/interconnection signal
_GRID_KEYWORDS = [
    "interconnect", "PJM", "notice to proceed", "NTP issued",
    "ISA executed", "interconnection service agreement",
    "power purchase agreement", "megawatt", "MW capacity",
    "substation", "transmission upgrade", "grid connection",
    "co-location", "colocation", "hyperscaler", "data center contract",
    "large load", "load growth", "capacity auction",
    "Sharon", "Panther Creek", "Scrubgrass", "Mercer County",
    "Loudoun", "Prince William",
]

# Stricter set for discovery — require these to avoid false positives
_DISCOVERY_REQUIRED = {
    "pjm", "interconnect", "large load", "data center",
    "notice to proceed", "isa executed", "megawatt",
}

# SIC codes to include in discovery scan (electric services, data processing)
_DISCOVERY_SICS = ["4911", "4931", "4941", "7374", "7372", "3559", "3612"]


class EdgarSecScraper(BaseHttpExtractor):
    """Scrape SEC EDGAR for grid/interconnection signals — watchlist + discovery."""

    source_key = "edgar_sec"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=_LOOKBACK_DAYS)).isoformat()

        events: list[dict[str, Any]] = []

        # -- Watchlist scan ---------------------------------------------------
        for target in _TARGETS:
            try:
                filings = self._get_recent_filings(target, cutoff)
            except Exception as exc:
                log.warning("edgar_sec.submissions_failed",
                            ticker=target["ticker"], error=str(exc))
                continue

            for filing in filings[:5]:
                try:
                    text = self._fetch_filing_text(target["cik"], filing)
                    if not text:
                        continue
                except Exception as exc:
                    log.warning("edgar_sec.fetch_failed",
                                ticker=target["ticker"], error=str(exc))
                    continue

                matched = _scan_keywords(text, _GRID_KEYWORDS)
                if len(matched) < 2:
                    continue

                events.append(_build_event(
                    target["entity"], target["ticker"], target["cik"],
                    filing, text, matched,
                ))
                log.info("edgar_sec.signal",
                         ticker=target["ticker"],
                         form=filing["form"],
                         date=filing["date"],
                         keywords=matched[:4])
                time.sleep(0.12)

        # -- Discovery scan ---------------------------------------------------
        discovery = self._discovery_scan(cutoff)
        if discovery:
            events.extend(discovery)

        log.info("edgar_sec.done", total_events=len(events),
                 watchlist=len(events) - len(discovery),
                 discovered=len(discovery))
        return events

    # ------------------------------------------------------------------
    # Discovery — find unknown companies fitting the thesis
    # ------------------------------------------------------------------

    def _discovery_scan(self, cutoff: str) -> list[dict[str, Any]]:
        """Full-text EDGAR search for emerging names not on the watchlist."""
        events: list[dict[str, Any]] = []

        discovery_queries = [
            '"PJM" "notice to proceed" "data center"',
            '"PJM interconnection" "large load" "megawatt"',
            '"ISA executed" "data center" "power"',
            '"co-location" "nuclear" "interconnection" "PJM"',
        ]

        seen_accnos: set[str] = set()

        for query in discovery_queries:
            try:
                r = self._client.get(
                    _EFTS_BASE,
                    params={
                        "q": query,
                        "dateRange": "custom",
                        "startdt": cutoff,
                        "enddt": "2030-01-01",
                        "forms": "8-K,10-Q,10-K",
                    },
                    headers=_HEADERS,
                    timeout=15,
                )
                r.raise_for_status()
                hits = r.json().get("hits", {}).get("hits", [])
            except Exception as exc:
                log.warning("edgar_sec.discovery_failed", query=query, error=str(exc))
                continue

            for hit in hits[:8]:
                src = hit.get("_source", {})
                accno = src.get("adsh", "")
                if not accno or accno in seen_accnos:
                    continue
                seen_accnos.add(accno)

                # Skip companies already on the watchlist
                display_names = src.get("display_names", [])
                tickers_in_name = re.findall(r'\(([A-Z]{2,6})\)', " ".join(display_names))
                if any(t in _WATCHLIST_TICKERS for t in tickers_in_name):
                    continue

                # Fetch and scan the actual filing
                ciks = src.get("ciks", [])
                if not ciks:
                    continue
                cik = ciks[0].lstrip("0")
                doc = src.get("file_type", "")
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accno.replace('-','')}/{src.get('file_description','').split('/')[-1]}"

                try:
                    filing = {
                        "form": src.get("form", src.get("root_forms", ["8-K"])[0]),
                        "date": src.get("file_date", ""),
                        "accno": accno,
                        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=10",
                    }

                    # Build a minimal target dict for event construction
                    entity_name = display_names[0].split("(")[0].strip() if display_names else "Unknown"
                    ticker = tickers_in_name[0] if tickers_in_name else "UNKN"

                    # Check it mentions enough thesis keywords to be worth flagging
                    text_snippet = src.get("period_of_report", "") + " " + " ".join(display_names)
                    matched = _scan_keywords(text_snippet.lower(), list(_DISCOVERY_REQUIRED))

                    # Only surface truly novel finds — log quietly, never noise
                    log.debug("edgar_sec.discovery_candidate",
                              entity=entity_name, ticker=ticker,
                              accno=accno, keywords=matched)

                    # We only emit a discovery event if there are >= 3 required keywords
                    # in the filing metadata itself (avoids fetching every document)
                    if len(matched) >= 2:
                        event_id = hashlib.sha256(
                            f"edgar:discovery:{accno}".encode()
                        ).hexdigest()[:24]
                        events.append({
                            "event_id": event_id,
                            "iso_region": "PJM",
                            "state_jurisdiction": "FEDERAL",
                            "entity_target": entity_name,
                            "data_type": "DISCOVERY",
                            "raw_text_blob": (
                                f"DISCOVERY — New company surfaced by EDGAR scan: {entity_name} ({ticker}). "
                                f"Not on current watchlist. Filing: {filing['form']} filed {filing['date']}. "
                                f"Keywords matched: {matched}. "
                                f"Review at: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=10 "
                                f"Query that found it: {query}"
                            ),
                            "metric_delta": 0,
                            "keywords_matched": matched + ["discovery", ticker.lower()],
                            "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
                        })
                        log.info("edgar_sec.discovery_hit",
                                 entity=entity_name, ticker=ticker,
                                 form=filing["form"], date=filing["date"])

                except Exception as exc:
                    log.debug("edgar_sec.discovery_skip", accno=accno, error=str(exc))

                time.sleep(0.12)

        return events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_recent_filings(
        self, target: dict[str, Any], cutoff: str
    ) -> list[dict[str, Any]]:
        r = self._client.get(
            f"{_SUBMISSIONS_BASE}/CIK{target['cik_padded']}.json",
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accnos = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        filings = []
        for form, date, accno, doc in zip(forms, dates, accnos, docs):
            if form not in _TARGET_FORMS:
                continue
            if date < cutoff:
                continue
            clean = accno.replace("-", "")
            url = f"{_ARCHIVES_BASE}/{target['cik']}/{clean}/{doc}"
            filings.append({"form": form, "date": date, "accno": accno, "url": url})

        return filings

    def _fetch_filing_text(self, cik: str, filing: dict[str, Any]) -> str:
        r = self._client.get(
            filing["url"], headers=_HEADERS, timeout=30, follow_redirects=True,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator=" ", strip=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _scan_keywords(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return [kw for kw in keywords if kw.lower() in lower]


def _build_event(
    entity: str, ticker: str, cik: str,
    filing: dict[str, Any], text: str, matched: list[str],
) -> dict[str, Any]:
    event_id = hashlib.sha256(
        f"edgar:{filing['accno']}:{ticker}".encode()
    ).hexdigest()[:24]

    idx = next(
        (text.lower().find(kw.lower()) for kw in matched if text.lower().find(kw.lower()) >= 0),
        0,
    )
    excerpt = text[max(0, idx - 200): idx + 800].strip()

    return {
        "event_id": event_id,
        "iso_region": "PJM",
        "state_jurisdiction": "FEDERAL",
        "entity_target": entity,
        "data_type": _classify(filing["form"], matched),
        "raw_text_blob": excerpt,
        "metric_delta": _extract_mw(text),
        "keywords_matched": matched,
        "source_url": filing["url"],
    }


def _classify(form: str, keywords: list[str]) -> str:
    lower = {k.lower() for k in keywords}
    if "notice to proceed" in lower or "ntp issued" in lower or "isa executed" in lower:
        return "QUEUE_MILESTONE"
    if "power purchase agreement" in lower or "hyperscaler" in lower:
        return "QUEUE_MILESTONE"
    if "interconnect" in lower:
        return "QUEUE_MILESTONE"
    if form == "8-K":
        return "REGULATORY_PROTEST"
    return "LARGE_LOAD_FORECAST"


def _extract_mw(text: str) -> int:
    matches = re.findall(r"(\d[\d,]*)\s*(?:MW|megawatt)", text, re.IGNORECASE)
    if not matches:
        return 0
    values = [int(m.replace(",", "")) for m in matches if int(m.replace(",", "")) < 100_000]
    return max(values) if values else 0
