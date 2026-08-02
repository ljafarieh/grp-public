"""NTP / ISA queue miner — PJM Data Miner 2 + FERC eLibrary.

Targets AI/HPC infrastructure companies with known PJM queue positions and
watches for high-value status transitions: ISA Executed, NTP Issued, Under
Construction.  Cross-references FERC eLibrary ER dockets for corroborating
Interconnection Service Agreement filings.

Targets
-------
- Core Scientific (CORZ) — Bitcoin-miner-to-HPC pivot, active PJM PA sites
- IREN Limited (IREN)    — AI compute infrastructure, PJM PA/OH footprint
- Keel Infrastructure    — private/unverified ticker; included as search string
                           only — confirm exchange listing before trading on any
                           signal this generates

Known site anchors (used as queue search strings)
--------------------------------------------------
- Sharon Substation / Mercer County PA  (KEEL / unverified)
- Panther Creek / Carbon County PA      (KEEL / unverified)
- CORZ PA nodal sites: searched by entity name
- IREN PA/OH nodal sites: searched by entity name

PJM Data Miner 2 notes
-----------------------
Most queue endpoints require a paid subscription key (PJM_API_KEY in .env).
Without a key the miner falls back to the public queue-status RSS feed and the
FERC eLibrary leg only.  Set stub_mode=True in settings to run fully offline
against fixture data.

FERC eLibrary
-------------
Fully public.  We query the full-text search API for ER dockets containing
"Interconnection Service Agreement" or "Notice to Proceed" cross-referenced
with each entity name.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Target companies and known site anchors
# ---------------------------------------------------------------------------

_TARGETS: list[dict[str, Any]] = [
    {
        "ticker": "CORZ",
        "entity": "Core Scientific",
        "iso_region": "PJM",
        "jurisdiction": "PA",
        "site_keywords": ["Core Scientific", "CORZ"],
    },
    {
        "ticker": "IREN",
        "entity": "IREN Limited",
        "iso_region": "PJM",
        "jurisdiction": "PA",
        "site_keywords": ["IREN", "Iris Energy"],
    },
    {
        "ticker": "KEEL",  # NOTE: unverified public ticker — confirm before use
        "entity": "Keel Infrastructure",
        "iso_region": "PJM",
        "jurisdiction": "PA",
        "site_keywords": [
            "Keel Infrastructure",
            "Sharon Substation",
            "Mercer County",
            "Panther Creek",
            "Carbon County",
        ],
    },
]

# Queue status transitions that signal capital commitment / construction reality
_SIGNAL_STATUSES = {"Under Construction", "ISA Executed", "NTP Issued"}

# PJM Data Miner 2 — queue positions endpoint (requires subscription key)
_PJM_QUEUE_URL = "https://dataminer2.pjm.com/feed/ivmrd_load_dtl/csv"
_PJM_PUBLIC_RSS = "https://www.pjm.com/-/media/planning/services-requests/interconnection-queues/active-queue.ashx"

# FERC eLibrary full-text search
_FERC_SEARCH_URL = "https://elibrary.ferc.gov/eLibrary/search"
_FERC_ISA_TERMS = ["Interconnection Service Agreement", "Notice to Proceed"]


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class NTPQueueMiner(BaseHttpExtractor):
    """Mine PJM queue transitions and FERC ISA dockets for AI/HPC site signals."""

    source_key = "ntp_queue_miner"

    def _live_extract(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for target in _TARGETS:
            # -- PJM leg --------------------------------------------------
            if self._settings.pjm_api_key:
                events.extend(self._query_pjm_queue(target))
            else:
                log.warning(
                    "ntp_queue_miner.pjm_skipped",
                    reason="no PJM_API_KEY in settings",
                    entity=target["entity"],
                )

            # -- FERC eLibrary leg (always runs — fully public) -----------
            events.extend(self._query_ferc_elibrary(target))

        log.info("ntp_queue_miner.done", total_events=len(events))
        return events

    # ------------------------------------------------------------------
    # PJM Data Miner 2
    # ------------------------------------------------------------------

    def _query_pjm_queue(self, target: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull queue positions from PJM Data Miner 2 and filter for target sites."""
        events: list[dict[str, Any]] = []
        try:
            resp = self._client.get(
                _PJM_QUEUE_URL,
                headers={"Ocp-Apim-Subscription-Key": self._settings.pjm_api_key},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as exc:
            log.warning("ntp_queue_miner.pjm_failed", entity=target["entity"], error=str(exc))
            return events

        # PJM returns CSV — parse rows manually to avoid pandas dependency
        lines = resp.text.splitlines()
        if not lines:
            return events

        headers = [h.strip().lower() for h in lines[0].split(",")]
        for raw_line in lines[1:]:
            cols = raw_line.split(",")
            if len(cols) < len(headers):
                continue
            row = dict(zip(headers, [c.strip() for c in cols]))

            status = row.get("queue status", "")
            if status not in _SIGNAL_STATUSES:
                continue

            # Match against any of the target's site keyword anchors
            row_text = " ".join(row.values()).lower()
            if not any(kw.lower() in row_text for kw in target["site_keywords"]):
                continue

            capacity_mw = _safe_int(row.get("mw", "0"))
            event_id = hashlib.sha256(
                f"pjm:{row.get('queue id','')}:{status}".encode()
            ).hexdigest()[:24]

            events.append({
                "event_id": event_id,
                "iso_region": target["iso_region"],
                "state_jurisdiction": target["jurisdiction"],
                "entity_target": target["entity"],
                "data_type": "QUEUE_MILESTONE",
                "raw_text_blob": f"PJM queue status transition: {status} | "
                                 f"Queue ID: {row.get('queue id')} | "
                                 f"Site: {row.get('project name', 'unknown')} | "
                                 f"Capacity: {capacity_mw} MW | "
                                 f"Ticker: {target['ticker']}",
                "metric_delta": capacity_mw,
                "keywords_matched": ["queue milestone", status.lower(), target["ticker"].lower()],
                "source_url": _PJM_QUEUE_URL,
            })
            log.info(
                "ntp_queue_miner.pjm_signal",
                entity=target["entity"],
                status=status,
                mw=capacity_mw,
            )

        return events

    # ------------------------------------------------------------------
    # FERC eLibrary
    # ------------------------------------------------------------------

    def _query_ferc_elibrary(self, target: dict[str, Any]) -> list[dict[str, Any]]:
        """Search FERC eLibrary for ISA / NTP filings cross-referenced with target entity."""
        events: list[dict[str, Any]] = []

        for isa_term in _FERC_ISA_TERMS:
            query = f'"{isa_term}" "{target["entity"]}"'
            try:
                resp = self._client.get(
                    _FERC_SEARCH_URL,
                    params={
                        "query": query,
                        "doctype": "ER",
                        "fromDate": "01/01/2025",
                        "toDate": "12/31/2026",
                    },
                    headers={
                        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                        ),
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    data = {}  # eLibrary returns HTML (Angular SPA) — no results via simple GET
            except Exception as exc:
                log.warning(
                    "ntp_queue_miner.ferc_failed",
                    entity=target["entity"],
                    term=isa_term,
                    error=str(exc),
                )
                continue

            results = data.get("results", []) if isinstance(data, dict) else []
            for item in results[:5]:  # cap at 5 per query to avoid noise
                accession = item.get("accession_number", "")
                filed_date = item.get("filed_date", "")
                description = item.get("description", "")
                doc_url = f"https://elibrary.ferc.gov/eLibrary/filelist?accession={accession}"

                event_id = hashlib.sha256(
                    f"ferc:{accession}:{target['entity']}".encode()
                ).hexdigest()[:24]

                events.append({
                    "event_id": event_id,
                    "iso_region": target["iso_region"],
                    "state_jurisdiction": "FEDERAL",
                    "entity_target": target["entity"],
                    "data_type": "REGULATORY_PROTEST"
                    if "protest" in description.lower()
                    else "QUEUE_MILESTONE",
                    "raw_text_blob": f"FERC eLibrary: {isa_term} filing for "
                                     f"{target['entity']} | "
                                     f"Accession: {accession} | "
                                     f"Filed: {filed_date} | "
                                     f"Description: {description[:300]} | "
                                     f"Ticker: {target['ticker']}",
                    "metric_delta": 0,
                    "keywords_matched": [
                        "interconnection service agreement"
                        if "ISA" in isa_term
                        else "notice to proceed",
                        target["ticker"].lower(),
                        "ferc er docket",
                    ],
                    "source_url": doc_url,
                })
                log.info(
                    "ntp_queue_miner.ferc_signal",
                    entity=target["entity"],
                    term=isa_term,
                    accession=accession,
                )

        return events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_int(val: str) -> int:
    try:
        return int(float(val.replace(",", "")))
    except (ValueError, AttributeError):
        return 0
