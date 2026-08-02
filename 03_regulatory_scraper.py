"""
Snippet 03 — Scraping a public state regulatory docket API
-----------------------------------------------------------
State public utility commissions publish every filing made in every
docket they oversee. Most have web portals. A few have REST APIs.

The Virginia State Corporation Commission runs a JavaScript SPA for
its docket search — but the SPA calls a public JSON API under the hood.
By reverse-engineering the network requests, you can query it directly
with no credentials, no scraping, no browser automation needed.

This snippet shows how to:
  1. Search for all active cases involving a specific participant (e.g. Dominion)
  2. Fetch the document list for a specific case
  3. Get the PDF download URL for each document

The same pattern — find the API the SPA calls, hit it directly — works
for many state regulatory portals.

Requirements:
    pip install httpx
"""

import httpx

API_BASE  = "https://www.scc.virginia.gov/DocketSearchAPI"
CASES_URL = f"{API_BASE}/breeze/CASES_ESTABDATE/GetCasesEstDateByParticipant"
DOCS_URL  = f"{API_BASE}/breeze/CaseDetails/GetDocuments"
PDF_BASE  = "https://www.scc.virginia.gov/docketsearch/docs"

HEADERS = {
    "Accept":           "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent":       "Mozilla/5.0 (research tool)",
}

# Only look at open/active cases
ACTIVE_STATUSES = {"O", "A"}


def get_active_cases(participant: str) -> list[dict]:
    """Return open cases involving a named participant."""
    resp = httpx.get(
        CASES_URL,
        params={"Participant": participant},
        headers=HEADERS,
        timeout=15,
        follow_redirects=True,
    )
    resp.raise_for_status()
    cases = resp.json() if isinstance(resp.json(), list) else []
    return [c for c in cases if c.get("STATUS", "") in ACTIVE_STATUSES]


def get_documents(matter_no: int) -> list[dict]:
    """
    Return all documents filed in a specific case (by matter number).

    Note: the Breeze OData API requires both $filter and $select to avoid
    a serialization bug where all results collapse to the same $ref object.
    Without $select, you only get one document back regardless of how many
    are in the case.
    """
    resp = httpx.get(
        DOCS_URL,
        params={
            "$filter": f"MATTER_NO eq {matter_no}",
            "$select": "Document_Name,Date_Filed,DocID,FileName",
        },
        headers=HEADERS,
        timeout=15,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    # Filter out Breeze $ref placeholder objects (deduplication artifacts)
    return sorted(
        [d for d in data if "$ref" not in d and d.get("FileName")],
        key=lambda d: d.get("Date_Filed", ""),
        reverse=True,
    )


def pdf_url(filename: str) -> str:
    """Construct the direct PDF download URL from a FileName field."""
    return f"{PDF_BASE}/{filename}"


if __name__ == "__main__":
    print("Searching VA SCC for active Dominion cases...\n")
    cases = get_active_cases("Dominion")
    print(f"Found {len(cases)} active cases.\n")

    for case in cases[:3]:  # look at 3 most recent
        matter_no  = case.get("MATTER_NO")
        case_no    = case.get("Case_Number", "")
        case_name  = case.get("Case_Name",   "")[:60]
        print(f"  Case {case_no} | Matter {matter_no} | {case_name}")

        docs = get_documents(matter_no)
        print(f"  → {len(docs)} documents filed")
        for doc in docs[:3]:
            print(
                f"     [{doc.get('Date_Filed','')[:10]}] "
                f"{doc.get('Document_Name','')[:60]}"
            )
            print(f"     PDF: {pdf_url(doc['FileName'])}")
        print()
