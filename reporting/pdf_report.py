"""
PDF report generator for the daily research pipeline.

Produces reports/YYYY-MM-DD.pdf — a clean, readable document designed
for a quick daily review. Sections are ordered by "need to see first":
  1. Header + disclaimer
  2. Notable moves (the day's action)
  3. Thesis scorecard (how the baskets are doing)
  4. Sector rotation (what's shifting)
  5. Correlation shifts (structural changes)
  6. Noise & uncertainty summary
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from analysis.attribution import AttributedMove
from analysis.correlations import CorrelationShift, LeadLagResult
from analysis.rotation import RotationSignal
from analysis.scorecard import ScorecardResult

PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
NAVY    = colors.HexColor("#1a2340")
SLATE   = colors.HexColor("#3d5068")
TEAL    = colors.HexColor("#0d7a78")
RED     = colors.HexColor("#c0392b")
GREEN   = colors.HexColor("#1a7a4a")
AMBER   = colors.HexColor("#d4760a")
LGRAY   = colors.HexColor("#f4f6f8")
MGRAY   = colors.HexColor("#c8d0da")
DGRAY   = colors.HexColor("#6b7a8d")
WHITE   = colors.white
BLACK   = colors.HexColor("#1a1a1a")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _make_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title",
            fontName="Helvetica-Bold", fontSize=20, textColor=NAVY,
            spaceAfter=4, leading=24),
        "subtitle": ParagraphStyle("subtitle",
            fontName="Helvetica", fontSize=10, textColor=SLATE,
            spaceAfter=2, leading=14),
        "section": ParagraphStyle("section",
            fontName="Helvetica-Bold", fontSize=13, textColor=NAVY,
            spaceBefore=14, spaceAfter=4, leading=16),
        "subsection": ParagraphStyle("subsection",
            fontName="Helvetica-Bold", fontSize=10, textColor=SLATE,
            spaceBefore=8, spaceAfter=2, leading=13),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=9, textColor=BLACK,
            spaceAfter=4, leading=13),
        "small": ParagraphStyle("small",
            fontName="Helvetica", fontSize=8, textColor=DGRAY,
            spaceAfter=3, leading=11),
        "disclaimer": ParagraphStyle("disclaimer",
            fontName="Helvetica-Oblique", fontSize=8, textColor=DGRAY,
            spaceAfter=4, leading=11,
            borderColor=AMBER, borderWidth=0.5, borderPadding=6,
            backColor=colors.HexColor("#fffbf0")),
        "move_up": ParagraphStyle("move_up",
            fontName="Helvetica-Bold", fontSize=11, textColor=GREEN, leading=14),
        "move_down": ParagraphStyle("move_down",
            fontName="Helvetica-Bold", fontSize=11, textColor=RED, leading=14),
        "confidence_high": ParagraphStyle("conf_high",
            fontName="Helvetica-Bold", fontSize=8, textColor=GREEN),
        "confidence_med": ParagraphStyle("conf_med",
            fontName="Helvetica-Bold", fontSize=8, textColor=AMBER),
        "confidence_low": ParagraphStyle("conf_low",
            fontName="Helvetica-Bold", fontSize=8, textColor=DGRAY),
        "note": ParagraphStyle("note",
            fontName="Helvetica-Oblique", fontSize=8, textColor=DGRAY,
            leading=11, spaceAfter=4),
    }


def _divider(color=MGRAY, thickness=0.5) -> HRFlowable:
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=6, spaceBefore=2)


def _spacer(h: float = 0.1) -> Spacer:
    return Spacer(1, h * inch)


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

BASE_TABLE_STYLE = TableStyle([
    ("BACKGROUND",   (0, 0), (-1, 0), NAVY),
    ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
    ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",     (0, 0), (-1, 0), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
    ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",     (0, 1), (-1, -1), 8),
    ("TEXTCOLOR",    (0, 1), (-1, -1), BLACK),
    ("GRID",         (0, 0), (-1, -1), 0.25, MGRAY),
    ("TOPPADDING",   (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
])


def _color_return(val: float) -> colors.Color:
    if val >= 5:   return GREEN
    if val >= 0:   return colors.HexColor("#1a6e3a")
    if val >= -5:  return RED
    return colors.HexColor("#8b0000")


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(as_of: date, generated_at: datetime, s: dict) -> list:
    elems = [
        Paragraph("AI-Compute Buildout", s["subtitle"]),
        Paragraph(f"Daily Research Report — {as_of.strftime('%B %d, %Y')}", s["title"]),
        Paragraph(
            f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}  |  "
            "Thesis: Aschenbrenner (June 2024) — treated as a testable hypothesis",
            s["subtitle"],
        ),
        _spacer(0.1),
        Paragraph(
            "NOT FINANCIAL ADVICE. Every item in this document is an observation or a testable "
            "hypothesis with a stated confidence level — not a buy, sell, or hold recommendation. "
            "Inclusion of any ticker is a research choice, not an endorsement.",
            s["disclaimer"],
        ),
        _divider(NAVY, 1),
    ]
    return elems


def _build_notable_moves(attributed: list[AttributedMove], as_of: date, s: dict) -> list:
    elems = [Paragraph("Notable Moves", s["section"])]

    if not attributed:
        elems += [
            Paragraph(
                f"No moves exceeded the 2-sigma detection threshold on {as_of}. "
                "The universe was quiet — this is a valid and informative result.",
                s["body"],
            ),
            _spacer(0.05),
        ]
        return elems

    for am in attributed:
        sig = am.signal
        up = sig.daily_return_pct >= 0
        arrow = "▲" if up else "▼"
        style = s["move_up"] if up else s["move_down"]
        sign = "+" if up else ""

        elems.append(Paragraph(
            f"{arrow} {sig.ticker}  {sign}{sig.daily_return_pct:.2f}%  "
            f"<font color='#{DGRAY.hexval()[2:]}' size='9'>"
            f"z={sig.zscore:+.1f} | close ${sig.close:.2f} | "
            f"trailing vol {sig.trailing_vol_annualized:.0f}% ann."
            f"</font>",
            style,
        ))

        if am.sector_return_pct is not None:
            elems.append(Paragraph(
                f"Sector peers averaged {am.sector_return_pct:+.1f}% on the same day.",
                s["small"],
            ))

        for ex in am.explanations[:2]:
            conf = ex.confidence.upper()
            conf_style = (s["confidence_high"] if conf == "HIGH"
                          else s["confidence_med"] if conf == "MEDIUM"
                          else s["confidence_low"])
            # Wrap in body paragraph with inline confidence tag
            elems.append(Paragraph(
                f"<b>[{conf}]</b> {ex.hypothesis}",
                s["body"],
            ))
            elems.append(Paragraph(f"Evidence: {ex.evidence[:220]}{'...' if len(ex.evidence) > 220 else ''}", s["small"]))

        elems.append(_spacer(0.05))

    n = len(attributed)
    elems.append(Paragraph(
        f"Multiple-comparisons note: {n} signal(s) from {22} tickers scanned. "
        f"At 2σ, ~{round(n * 0.05, 1)} false positive(s) expected by chance.",
        s["note"],
    ))
    return elems


def _build_scorecard(scorecard: list[ScorecardResult], s: dict) -> list:
    elems = [Paragraph("Thesis Scorecard", s["section"]),
             Paragraph(
                 "Equal-weight basket returns per thesis role vs benchmarks. "
                 "Hypothesis scorecard — not a strategy backtest.",
                 s["small"],
             )]

    for sc in scorecard:
        bench = sc.benchmark_returns
        spy = bench.get("SPY", 0.0)
        bench_str = "  ".join(f"{t} {v:+.1f}%" for t, v in sorted(bench.items()))
        elems.append(Paragraph(f"Window: {sc.window}  |  Benchmarks: {bench_str}", s["subsection"]))

        header = ["Role", "Total Rtn", "Ann. Rtn", "vs SPY", "Best", "Worst"]
        rows = [header]
        for b in sc.basket_returns:
            vs = b.total_return_pct - spy
            rows.append([
                b.role,
                f"{b.total_return_pct:+.1f}%",
                f"{b.annualized_return_pct:+.1f}%",
                f"{vs:+.1f}%",
                f"{b.best_ticker} {b.best_ticker_return_pct:+.1f}%",
                f"{b.worst_ticker} {b.worst_ticker_return_pct:+.1f}%",
            ])

        col_widths = [1.6*inch, 0.75*inch, 0.75*inch, 0.65*inch, 1.3*inch, 1.3*inch]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(BASE_TABLE_STYLE)

        # Colour the return cells
        for row_idx, b in enumerate(sc.basket_returns, start=1):
            vs = b.total_return_pct - spy
            t.setStyle(TableStyle([
                ("TEXTCOLOR", (1, row_idx), (1, row_idx), _color_return(b.total_return_pct)),
                ("TEXTCOLOR", (3, row_idx), (3, row_idx), _color_return(vs)),
                ("FONTNAME",  (1, row_idx), (1, row_idx), "Helvetica-Bold"),
            ]))

        elems += [t, _spacer(0.08)]

    return elems


def _build_rotation(signals: list[RotationSignal], s: dict) -> list:
    elems = [
        Paragraph("Sector Rotation", s["section"]),
        Paragraph(
            "Return rank per thesis role: last 30 days vs prior 30 days. "
            "Descriptive observation only — not a prediction.",
            s["small"],
        ),
    ]

    if not signals:
        elems.append(Paragraph("Insufficient data.", s["body"]))
        return elems

    n = signals[0].n_roles
    header = ["Role", "Prior 30d", "Recent 30d", "Prior Rank", "Recent Rank", "Shift"]
    rows = [header]
    flagged_rows = []
    for i, sig in enumerate(signals, start=1):
        flag = " ◀" if sig.flagged else ""
        rows.append([
            sig.role + flag,
            f"{sig.prior_return_pct:+.1f}%",
            f"{sig.recent_return_pct:+.1f}%",
            f"{sig.prior_rank}/{n}",
            f"{sig.recent_rank}/{n}",
            f"{sig.rank_shift:+d}",
        ])
        if sig.flagged:
            flagged_rows.append(i)

    col_widths = [1.7*inch, 0.8*inch, 0.9*inch, 0.75*inch, 0.85*inch, 0.6*inch]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(BASE_TABLE_STYLE)
    for row_idx in flagged_rows:
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#fff3e0")),
            ("FONTNAME",   (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
        ]))
    # Colour return and shift columns
    for row_idx, sig in enumerate(signals, start=1):
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (1, row_idx), (1, row_idx), _color_return(sig.prior_return_pct)),
            ("TEXTCOLOR", (2, row_idx), (2, row_idx), _color_return(sig.recent_return_pct)),
            ("TEXTCOLOR", (5, row_idx), (5, row_idx),
             GREEN if sig.rank_shift > 0 else (RED if sig.rank_shift < 0 else DGRAY)),
        ]))

    elems += [t, _spacer(0.08)]
    return elems


def _build_correlations(shifts: list[CorrelationShift], lead_lag: list[LeadLagResult], s: dict) -> list:
    elems = [Paragraph("Correlation Shifts", s["section"]),
             Paragraph(
                 "Rolling 30-day vs prior 30-day correlation. "
                 "Correlation ≠ causation. Magnitude threshold = 0.20.",
                 s["small"],
             )]

    if not shifts:
        elems.append(Paragraph("No shifts >= 0.20 detected.", s["body"]))
    else:
        n_pairs = shifts[0].n_pairs_tested
        elems.append(Paragraph(
            f"{n_pairs} pairs tested — ~{round(n_pairs * 0.32)} spurious shifts expected by chance.",
            s["note"],
        ))
        header = ["Pair", "Roles", "Prior", "Recent", "Shift"]
        rows = [header]
        for cs in shifts[:12]:
            direction = "+" if cs.shift > 0 else ""
            rows.append([
                f"{cs.ticker_a}/{cs.ticker_b}",
                f"{cs.role_a} / {cs.role_b}",
                f"{cs.corr_prior:+.3f}",
                f"{cs.corr_recent:+.3f}",
                f"{direction}{cs.shift:.3f}",
            ])
        col_widths = [1.1*inch, 2.4*inch, 0.65*inch, 0.7*inch, 0.65*inch]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(BASE_TABLE_STYLE)
        for row_idx, cs in enumerate(shifts[:12], start=1):
            t.setStyle(TableStyle([
                ("TEXTCOLOR", (4, row_idx), (4, row_idx),
                 GREEN if cs.shift > 0 else RED),
                ("FONTNAME", (4, row_idx), (4, row_idx), "Helvetica-Bold"),
            ]))
        elems += [t, _spacer(0.06)]

    # Lead-lag summary line
    surviving = [r for r in lead_lag if r.survives_correction]
    n_tests = lead_lag[0].n_tests if lead_lag else 0
    if surviving:
        elems.append(Paragraph(
            f"Lead-lag: {len(surviving)} relationship(s) survive Bonferroni correction "
            f"({n_tests} pairs tested). See markdown report for details.",
            s["note"],
        ))
    else:
        elems.append(Paragraph(
            f"Lead-lag: No relationships survive Bonferroni correction ({n_tests} pairs tested). "
            "Absence of day-ahead predictability is the expected and informative result.",
            s["note"],
        ))

    return elems


def _build_noise_summary(
    attributed: list[AttributedMove],
    lead_lag: list[LeadLagResult],
    shifts: list[CorrelationShift],
    rotation: list[RotationSignal],
    s: dict,
) -> list:
    elems = [
        _divider(),
        Paragraph("Noise & Uncertainty Summary", s["section"]),
        Paragraph("What is uncertain or likely noise:", s["subsection"]),
    ]

    items = []
    surviving_ll = [r for r in lead_lag if r.survives_correction]
    no_cause = [am for am in attributed if am.explanations and am.explanations[0].source == "none"]

    if no_cause:
        tickers = ", ".join(am.signal.ticker for am in no_cause)
        items.append(f"{tickers}: flagged move(s) with no identifiable cause — likely noise.")
    if not surviving_ll:
        items.append("No lead-lag relationships survive correction — no day-ahead predictability detected.")
    if shifts:
        n = shifts[0].n_pairs_tested
        items.append(
            f"{len(shifts)} correlation shift(s) from {n} pairs; "
            f"~{round(n * 0.32)} expected spurious. Treat all as candidates."
        )
    flagged_rot = [sig for sig in rotation if sig.flagged]
    if flagged_rot:
        roles = ", ".join(sig.role for sig in flagged_rot)
        items.append(f"Rotation flag(s) for {roles} are descriptive only — not predictive.")
    if not attributed:
        items.append("No moves flagged — universe was quiet.")

    for item in items:
        elems.append(Paragraph(f"• {item}", s["small"]))

    elems += [
        _spacer(0.06),
        Paragraph("What has stronger support:", s["subsection"]),
    ]

    strong = []
    low_conf = [am for am in attributed if am.explanations and am.explanations[0].confidence != "low" and am.explanations[0].source != "none"]
    if low_conf and not no_cause:
        strong.append("All flagged moves have at least MEDIUM-confidence candidate explanations.")
    if surviving_ll:
        strong.append(f"{len(surviving_ll)} lead-lag relationship(s) survive Bonferroni — flag for OOS check.")
    if not strong:
        strong.append("No findings with strong support today.")

    for item in strong:
        elems.append(Paragraph(f"• {item}", s["small"]))

    return elems


def _build_footer(as_of: date, s: dict) -> list:
    return [
        _spacer(0.1),
        _divider(MGRAY, 0.25),
        Paragraph(
            f"AI-Compute Buildout Research Pipeline  |  {as_of}  |  "
            "Data: Yahoo Finance via yfinance (unofficial, adjusted prices)  |  "
            "Thesis: Aschenbrenner 'Situational Awareness' (June 2024), treated as testable hypothesis  |  "
            "NOT FINANCIAL ADVICE",
            s["note"],
        ),
    ]


# ---------------------------------------------------------------------------
# Page template with page numbers
# ---------------------------------------------------------------------------

def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(DGRAY)
    canvas.drawRightString(
        doc.pagesize[0] - 0.5 * inch,
        0.4 * inch,
        f"Page {doc.page}",
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def write_pdf_report(
    as_of: date,
    attributed: list[AttributedMove],
    shifts: list[CorrelationShift],
    lead_lag: list[LeadLagResult],
    scorecard: list[ScorecardResult],
    rotation: list[RotationSignal],
    output_path: Optional[Path] = None,
) -> Path:
    """
    Generate a PDF research report. Returns the path written to.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output_path or REPORTS_DIR / f"{as_of.isoformat()}.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"AI-Compute Research Report {as_of}",
        author="Research Pipeline",
        subject="Not financial advice",
    )

    s = _make_styles()
    generated_at = datetime.now(timezone.utc)

    story = []
    story += _build_header(as_of, generated_at, s)
    story += _build_notable_moves(attributed, as_of, s)
    story += [_divider()]
    story += _build_scorecard(scorecard, s)
    story += [_divider()]
    story += _build_rotation(rotation, s)
    story += [_divider()]
    story += _build_correlations(shifts, lead_lag, s)
    story += _build_noise_summary(attributed, lead_lag, shifts, rotation, s)
    story += _build_footer(as_of, s)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return output_path
