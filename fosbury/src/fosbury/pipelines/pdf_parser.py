"""PDF intelligence layer — shared across all regulatory scrapers.

Every scraper that downloads regulatory PDFs calls :func:`scan_pdf` with the
raw bytes.  This function:

1. Extracts full text via ``pdfplumber``.
2. Scans for a configurable keyword list.
3. Extracts a delay metric using regex (days / weeks / months / years).
4. Returns a structured result dict that the scraper wraps into a raw event.

Keeping this logic centralised means all four scrapers (VA SCC, Ohio PUCO,
PA PUC, FERC) benefit from improvements in one place.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pdfplumber
import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Default keyword lists by data type
# ---------------------------------------------------------------------------

DELAY_KEYWORDS: list[str] = [
    "transformer procurement",
    "right-of-way acquisition delay",
    "substation hold",
    "restudy",
    "multi-year delay",
    "equipment backlog",
    "queue withdrawal",
    "cost allocation",
    "commercial operation date",
    "energization delay",
    "milestone amendment",
    "days extended",
]

PROTEST_KEYWORDS: list[str] = [
    "protest",
    "intervention",
    "cost-shifting",
    "ratepayer",
    "independent market monitor",
    "show cause",
    "co-location",
    "net injection",
    "behind-the-meter",
    "objection",
    "formal complaint",
]

EQUIPMENT_KEYWORDS: list[str] = [
    "transformer backlog",
    "switchgear lead time",
    "supply chain",
    "delivery delay",
    "procurement waiver",
    "inventory revision",
    "cooling module",
    "battery cell",
    "generator step-up",
]

ALL_KEYWORDS = DELAY_KEYWORDS + PROTEST_KEYWORDS + EQUIPMENT_KEYWORDS

# ---------------------------------------------------------------------------
# Delay extraction patterns (normalised to calendar days)
# ---------------------------------------------------------------------------

_DELAY_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"(\d+)\s*-?\s*years?", re.I), 365),
    (re.compile(r"(\d+)\s*-?\s*months?", re.I), 30),
    (re.compile(r"(\d+)\s*-?\s*weeks?", re.I), 7),
    (re.compile(r"(\d+)\s*-?\s*days?", re.I), 1),
]


def extract_delay_days(text: str) -> int:
    """Return the largest delay figure found in *text*, converted to days.

    Checks years → months → weeks → days and returns the first (and likely
    most significant) match.  Returns 0 if nothing is found.
    """
    for pattern, multiplier in _DELAY_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1)) * multiplier
            except ValueError:
                continue
    return 0


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------


@dataclass
class PdfScanResult:
    """Outcome of scanning one PDF document."""

    full_text: str
    keywords_matched: list[str] = field(default_factory=list)
    metric_delta: int = 0
    page_count: int = 0
    success: bool = True
    error: str = ""

    @property
    def has_signal(self) -> bool:
        """True if at least one keyword matched."""
        return len(self.keywords_matched) > 0

    def excerpt(self, max_chars: int = 1000) -> str:
        """Return a trimmed excerpt of the full text."""
        return self.full_text[:max_chars]


def scan_pdf(
    pdf_bytes: bytes,
    keywords: list[str] | None = None,
) -> PdfScanResult:
    """Extract text from *pdf_bytes* and scan for regulatory signal keywords.

    Args:
        pdf_bytes: Raw bytes of a PDF file (e.g. from ``response.content``).
        keywords: Override the default keyword list.  ``None`` uses
            :data:`ALL_KEYWORDS`.

    Returns:
        :class:`PdfScanResult` with matched keywords and extracted delay metric.
    """
    if keywords is None:
        keywords = ALL_KEYWORDS

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            full_text = "\n".join(pages)
            page_count = len(pdf.pages)
    except Exception as exc:
        log.warning("pdf_parser.open_failed", error=str(exc))
        return PdfScanResult(full_text="", success=False, error=str(exc))

    lower_text = full_text.lower()
    matched = [kw for kw in keywords if kw.lower() in lower_text]
    delta = extract_delay_days(full_text)

    log.debug(
        "pdf_parser.scanned",
        pages=page_count,
        keywords_matched=len(matched),
        metric_delta=delta,
    )

    return PdfScanResult(
        full_text=full_text,
        keywords_matched=matched,
        metric_delta=delta,
        page_count=page_count,
    )


def scan_text(
    text: str,
    keywords: list[str] | None = None,
) -> PdfScanResult:
    """Same as :func:`scan_pdf` but operates on already-extracted text.

    Useful when a scraper retrieves HTML (not PDF) filings.
    """
    if keywords is None:
        keywords = ALL_KEYWORDS

    lower_text = text.lower()
    matched = [kw for kw in keywords if kw.lower() in lower_text]
    delta = extract_delay_days(text)

    return PdfScanResult(
        full_text=text,
        keywords_matched=matched,
        metric_delta=delta,
        page_count=0,
    )
