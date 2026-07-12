"""Virginia State Corporation Commission (SCC) — docket scraper.

Live target (direct JSON API, reverse-engineered from the DocketSearch SPA):
    Cases:     /DocketSearchAPI/breeze/CASES_ESTABDATE/GetCasesEstDateByParticipant
    Documents: /DocketSearchAPI/breeze/CaseDetails/GetDocuments?MATTER_NO=<n>
    PDF:       /DocketSearchAPI/Home/Document/12/<DocID>

No credentials required — the API is fully public.

Arbitrage focus (per GRP document):
    Dominion Energy transmission delay dockets signal slower capital
    deployment rates → near-term earnings guidance risk for ticker D.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import scan_pdf

log = structlog.get_logger()

_API_BASE = "https://www.scc.virginia.gov/DocketSearchAPI"
_CASES_URL = f"{_API_BASE}/breeze/CASES_ESTABDATE/GetCasesEstDateByParticipant"
_DOCS_URL  = f"{_API_BASE}/breeze/CaseDetails/GetDocuments"
_PDF_BASE  = "https://www.scc.virginia.gov/docketsearch/docs"

_HEADERS = {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

_TARGET_PARTICIPANTS = [
    ("Dominion", "Dominion Energy"),
    ("Appalachian Power", "Appalachian Power"),
    ("North Anna", "Dominion Energy"),
]

# Only scan open/active cases
_ACTIVE_STATUSES = {"O", "A"}


class VirginiaSCCScraper(BaseHttpExtractor):
    """Scrape VA SCC filings via the public DocketSearch REST API."""

    source_key = "va_scc"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        seen_doc_ids: set[int] = set()

        for participant, entity_name in _TARGET_PARTICIPANTS:
            log.info("va_scc.search", participant=participant)
            try:
                cases = self._fetch_cases(participant)
            except Exception as exc:
                log.warning("va_scc.cases_failed", participant=participant, error=str(exc))
                continue

            # Focus on open/active cases, newest first, cap at 3
            active = [c for c in cases if c.get("STATUS", "") in _ACTIVE_STATUSES][:3]
            log.debug("va_scc.active_cases", participant=participant, count=len(active))

            for case in active:
                matter_no = case.get("MATTER_NO")
                case_number = case.get("Case_Number", "")
                if not matter_no:
                    continue

                try:
                    docs = self._fetch_documents(matter_no)
                except Exception as exc:
                    log.warning("va_scc.docs_failed", case=case_number, error=str(exc))
                    continue

                # 3 most recent docs per case
                for doc in docs[:3]:
                    doc_id = doc.get("DocID")
                    filename = doc.get("FileName", "").strip()
                    if not doc_id or doc_id in seen_doc_ids or not filename:
                        continue
                    seen_doc_ids.add(doc_id)

                    pdf_url = f"{_PDF_BASE}/{filename}"
                    try:
                        resp = self._client.get(
                            pdf_url, timeout=20,
                            headers={"Accept": "application/pdf,*/*", "User-Agent": "Mozilla/5.0"},
                        )
                        resp.raise_for_status()
                        ct = resp.headers.get("content-type", "")
                        if "pdf" not in ct.lower() and not resp.content.startswith(b"%PDF"):
                            continue
                        result = scan_pdf(resp.content)
                    except Exception as exc:
                        log.warning("va_scc.pdf_failed", doc_id=doc_id, filename=filename, error=str(exc))
                        continue

                    if not result.has_signal:
                        continue

                    event_id = hashlib.sha256(
                        f"va_scc:{doc_id}:{result.full_text[:200]}".encode()
                    ).hexdigest()[:24]

                    events.append({
                        "event_id": event_id,
                        "iso_region": "PJM",
                        "state_jurisdiction": "VA",
                        "entity_target": entity_name,
                        "data_type": _classify(result.keywords_matched),
                        "raw_text_blob": result.excerpt(1500),
                        "metric_delta": result.metric_delta,
                        "keywords_matched": result.keywords_matched,
                        "source_url": pdf_url,
                    })
                    log.info("va_scc.signal_found", doc_id=doc_id, case=case_number,
                             entity=entity_name, keywords=result.keywords_matched[:3])

        log.info("va_scc.done", events=len(events))
        return events

    def _fetch_cases(self, participant: str) -> list[dict[str, Any]]:
        resp = self._client.get(
            _CASES_URL,
            params={"Participant": participant},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def _fetch_documents(self, matter_no: int) -> list[dict[str, Any]]:
        resp = self._client.get(
            _DOCS_URL,
            params={"MATTER_NO": matter_no},
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


def _classify(keywords: list[str]) -> str:
    protest_kws = {"protest", "intervention", "show cause", "ratepayer", "objection"}
    equipment_kws = {"transformer", "switchgear", "supply chain", "procurement", "cooling"}
    lower_kws = {k.lower() for k in keywords}
    if lower_kws & protest_kws:
        return "REGULATORY_PROTEST"
    if lower_kws & equipment_kws:
        return "EQUIPMENT_DELAY"
    return "QUEUE_MILESTONE"
