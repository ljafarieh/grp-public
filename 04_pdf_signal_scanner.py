"""
Snippet 04 — Extracting text from regulatory PDFs and scanning for signals
---------------------------------------------------------------------------
Once you have a PDF URL from a docket, you need to extract the text and
check whether it contains meaningful signal keywords.

This snippet shows how GRP turns a raw PDF into a structured signal:
  - Download the PDF bytes
  - Extract full text with pdfplumber
  - Run keyword matching for interconnection queue events
  - Extract numeric MW figures (the actual quantity that matters)

The keyword list here is a simplified version of what GRP uses. The real
system has tiered signal weights, context-window checks (to avoid false
positives), and per-source tuning. But this core pattern is enough to
replicate the Ohio finding.

Requirements:
    pip install httpx pdfplumber
"""

import re
import httpx
import pdfplumber
from dataclasses import dataclass, field
from io import BytesIO

# Keywords that indicate a meaningful interconnection queue event
SIGNAL_KEYWORDS = [
    # Queue withdrawal signals
    "queue withdrawal",
    "withdrawn",
    "take-or-pay",
    "take or pay",
    "bankable demand",
    "uncommitted capacity",
    "commercial operation date",

    # Cost allocation / ratepayer signals
    "cost allocation",
    "ratepayer",
    "stranded",

    # Physical infrastructure signals
    "supply chain",
    "transformer",
    "interconnection cluster",
    "impact study",
]

# Pattern to extract MW/GW figures from text
MW_PATTERN = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(MW|GW|megawatt|gigawatt)",
    re.IGNORECASE,
)


@dataclass
class ScanResult:
    keywords_matched: list[str] = field(default_factory=list)
    mw_figures:       list[float] = field(default_factory=list)
    full_text:        str = ""
    pages:            int = 0

    @property
    def has_signal(self) -> bool:
        return len(self.keywords_matched) >= 2

    def excerpt(self, chars: int = 800) -> str:
        """Return the first N characters of meaningful text."""
        return self.full_text[:chars]


def scan_pdf_bytes(pdf_bytes: bytes) -> ScanResult:
    """Extract text from PDF bytes and scan for signal keywords."""
    result = ScanResult()
    text_parts = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        result.pages = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    result.full_text = "\n".join(text_parts)
    lower_text = result.full_text.lower()

    # Keyword matching
    for kw in SIGNAL_KEYWORDS:
        if kw.lower() in lower_text:
            result.keywords_matched.append(kw)

    # Extract MW figures
    for match in MW_PATTERN.finditer(result.full_text):
        raw_val = float(match.group(1).replace(",", ""))
        unit    = match.group(2).upper()
        mwh = raw_val * 1000 if unit in ("GW", "GIGAWATT") else raw_val
        result.mw_figures.append(mwh)

    return result


def scan_pdf_url(url: str) -> ScanResult:
    """Download a PDF from a URL and scan it."""
    resp = httpx.get(
        url,
        headers={"Accept": "application/pdf,*/*", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=20,
    )
    resp.raise_for_status()

    if not resp.content.startswith(b"%PDF"):
        raise ValueError(f"Response is not a PDF (got {resp.headers.get('content-type')})")

    return scan_pdf_bytes(resp.content)


if __name__ == "__main__":
    # Demo: create a synthetic "filing" that mimics the AEP Ohio language
    # and show what the scanner extracts from it.
    #
    # In practice, you'd pass a real URL from snippet 03:
    #   result = scan_pdf_url("https://www.scc.virginia.gov/docketsearch/docs/8dd701!.PDF")

    DEMO_TEXT = b"""%PDF-1.4
    1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
    2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
    3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
    /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font
    /Subtype /Type1 /BaseFont /Helvetica >> >> >> >> endobj
    4 0 obj << /Length 600 >>
    stream
    BT /F1 12 Tf 50 750 Td
    (American Electric Power System Impact Study Update) Tj
    0 -20 Td
    (The Columbus data center interconnection cluster has withdrawn 24,300 MW) Tj
    0 -20 Td
    (of uncommitted capacity requests following implementation of the take-or-pay) Tj
    0 -20 Td
    (tariff. Expected commercial operation date extensions average 14 months.) Tj
    0 -20 Td
    (Confirmed contracted load has declined from 30,000 MW to 5,700 MW of) Tj
    0 -20 Td
    (bankable demand. Cost allocation impacts are being assessed for ratepayers.) Tj
    ET
    endstream
    endobj
    xref
    0 5
    0000000000 65535 f
    trailer << /Size 5 /Root 1 0 R >>
    startxref 0
    %%EOF"""

    result = scan_pdf_bytes(DEMO_TEXT)

    print("=== PDF Signal Scanner Demo ===\n")
    print(f"Pages scanned:     {result.pages}")
    print(f"Keywords matched:  {result.keywords_matched}")
    print(f"MW figures found:  {sorted(set(result.mw_figures), reverse=True)}")
    print(f"Has signal:        {result.has_signal}")
    print(f"\nText excerpt:\n{result.excerpt(400)}")

    print("\n---")
    print("To scan a real regulatory PDF, use:")
    print("  result = scan_pdf_url('https://...')")
    print("  if result.has_signal:")
    print("      print(result.keywords_matched)")
    print("      print(result.mw_figures)")
