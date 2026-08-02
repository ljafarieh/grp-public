"""Generate a daily run report PDF summarising Project Fosbury findings.

Usage:
    python generate_daily_report.py [YYYY-MM-DD]

If no date is given, today's ISO date is used.  The report reads events from
fosbury.db, splits them into today's events vs. database totals, and writes
GRP_Daily_Report_<DATE>.pdf in the current directory.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Colours matching the established Fosbury design language
# ---------------------------------------------------------------------------
DARK_BG = colors.HexColor("#0D1117")
ACCENT  = colors.HexColor("#00FF88")
WARNING = colors.HexColor("#FFD700")
DANGER  = colors.HexColor("#FF4444")
MUTED   = colors.HexColor("#8B949E")
PANEL   = colors.HexColor("#161B22")
BORDER  = colors.HexColor("#21262D")
WHITE   = colors.white

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
BASE  = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "Title",
    fontName="Helvetica-Bold",
    fontSize=22,
    textColor=WHITE,
    leading=28,
    spaceAfter=4,
)
SUBTITLE_STYLE = ParagraphStyle(
    "Subtitle",
    fontName="Helvetica",
    fontSize=11,
    textColor=ACCENT,
    leading=16,
    spaceAfter=16,
)
SECTION_STYLE = ParagraphStyle(
    "Section",
    fontName="Helvetica-Bold",
    fontSize=13,
    textColor=ACCENT,
    leading=20,
    spaceBefore=14,
    spaceAfter=6,
)
BODY_STYLE = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=10,
    textColor=WHITE,
    leading=15,
    spaceAfter=6,
)
SMALL_STYLE = ParagraphStyle(
    "Small",
    fontName="Helvetica",
    fontSize=9,
    textColor=MUTED,
    leading=13,
    spaceAfter=4,
)
LABEL_STYLE = ParagraphStyle(
    "Label",
    fontName="Helvetica-Bold",
    fontSize=9,
    textColor=MUTED,
    leading=13,
)
CODE_STYLE = ParagraphStyle(
    "Code",
    fontName="Courier",
    fontSize=9,
    textColor=ACCENT,
    leading=13,
    spaceAfter=4,
)
WARN_STYLE = ParagraphStyle(
    "Warn",
    fontName="Helvetica-Bold",
    fontSize=9,
    textColor=WARNING,
    leading=13,
)
DANGER_STYLE = ParagraphStyle(
    "Danger",
    fontName="Helvetica-Bold",
    fontSize=9,
    textColor=DANGER,
    leading=13,
)
OK_STYLE = ParagraphStyle(
    "OK",
    fontName="Helvetica-Bold",
    fontSize=9,
    textColor=ACCENT,
    leading=13,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table(data: list[list], col_widths: list[float], row_heights: list | None = None) -> Table:
    tbl = Table(data, colWidths=col_widths, rowHeights=row_heights)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  PANEL),
        ("BACKGROUND",  (0, 1), (-1, -1), DARK_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  ACCENT),
        ("TEXTCOLOR",   (0, 1), (-1, -1), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("GRID",        (0, 0), (-1, -1), 0.5, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [DARK_BG, PANEL]),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _hr() -> HRFlowable:
    return HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=10, spaceBefore=4)


def _badge(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(f"[ {text} ]", style)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_events(db_path: str, run_date: str) -> tuple[list[dict], list[dict]]:
    """Return (today_events, all_events) from the db."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    all_rows = conn.execute(
        "SELECT * FROM grid_events ORDER BY loaded_at DESC"
    ).fetchall()
    all_events = [dict(r) for r in all_rows]

    today_rows = conn.execute(
        "SELECT * FROM grid_events WHERE DATE(loaded_at) = ? ORDER BY loaded_at DESC",
        (run_date,),
    ).fetchall()
    today_events = [dict(r) for r in today_rows]

    conn.close()
    return today_events, all_events


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------

def build_report(run_date_str: str, output_path: str) -> None:
    today_events, all_events = load_events("data/sqlite/fosbury.db", run_date_str)

    # Classify today's events
    signals   = [e for e in today_events if len((e.get("keywords_matched") or "").split(",")) >= 2]
    dismissed = [e for e in today_events if len((e.get("keywords_matched") or "").split(",")) < 2]

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    W = letter[0] - 1.5 * inch  # usable width

    def canvas_bg(canv, doc_):  # noqa: ANN001
        canv.setFillColor(DARK_BG)
        canv.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)

    story: list = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("PROJECT FOSBURY", TITLE_STYLE))
    story.append(Paragraph("Grid Realization Pipeline  ·  Daily Run Report", SUBTITLE_STYLE))
    story.append(Paragraph(
        f"Run date: {run_date_str}  ·  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        SMALL_STYLE,
    ))
    story.append(_hr())

    # ── Run summary table ────────────────────────────────────────────────────
    story.append(Paragraph("Pipeline Run Summary", SECTION_STYLE))

    sources = [
        ("VA SCC (Virginia State Corporation Commission)",
         str(len([e for e in today_events if e.get("state_jurisdiction") == "VA"])),
         str(len([e for e in today_events if e.get("state_jurisdiction") == "VA" and
                  len((e.get("keywords_matched") or "").split(",")) >= 2]))),
        ("Ohio PUCO",
         str(len([e for e in today_events if e.get("state_jurisdiction") == "OH"])),
         str(len([e for e in today_events if e.get("state_jurisdiction") == "OH" and
                  len((e.get("keywords_matched") or "").split(",")) >= 2]))),
        ("PA PUC (portal unreachable)",
         "—",
         "—"),
        ("FERC eLIbrary",
         str(len([e for e in today_events if e.get("state_jurisdiction") == "FEDERAL"])),
         str(len([e for e in today_events if e.get("state_jurisdiction") == "FEDERAL" and
                  len((e.get("keywords_matched") or "").split(",")) >= 2]))),
    ]

    summary_data = [
        ["Source", "Events Written", "Signals (≥2 keywords)"],
    ] + sources

    tbl = _table(summary_data, [W * 0.55, W * 0.22, W * 0.23])
    story.append(tbl)
    story.append(Spacer(1, 10))

    # ── Signal / dismissed counts ────────────────────────────────────────────
    net_txt = (
        f"<b>Events written today:</b> {len(today_events)}    "
        f"<b>Genuine signals:</b> {len(signals)}    "
        f"<b>Dismissed (false positive):</b> {len(dismissed)}"
    )
    story.append(Paragraph(net_txt, BODY_STYLE))
    story.append(Spacer(1, 6))

    # ── Genuine signals ──────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph(f"Genuine Signals — {len(signals)} found", SECTION_STYLE))

    if signals:
        for ev in signals:
            kws = ev.get("keywords_matched", "")
            kw_list = [k.strip() for k in kws.split(",") if k.strip()]
            story.append(Paragraph(
                f"<b>{ev.get('entity_target','?')}</b>  ·  "
                f"{ev.get('state_jurisdiction','?')}  ·  "
                f"Type: {ev.get('data_type','?')}",
                BODY_STYLE,
            ))
            story.append(Paragraph(f"Event ID: {ev.get('event_id','')}", CODE_STYLE))
            story.append(Paragraph(f"Keywords ({len(kw_list)}): {', '.join(kw_list)}", BODY_STYLE))
            if ev.get("metric_delta", 0):
                story.append(Paragraph(
                    f"Delay metric extracted: {ev['metric_delta']} days",
                    WARN_STYLE,
                ))
            story.append(Paragraph(f"Source: {ev.get('source_url', 'N/A')}", SMALL_STYLE))
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("No genuine signals found in this run.", BODY_STYLE))

    # ── Dismissed events ─────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph(f"Events Written but Dismissed — {len(dismissed)} false positives", SECTION_STYLE))
    story.append(Paragraph(
        "These events were written to the database but failed the ≥2 keyword threshold "
        "added on 2026-07-16 to prevent single-keyword false positives.",
        SMALL_STYLE,
    ))
    story.append(Spacer(1, 6))

    if dismissed:
        for ev in dismissed:
            kws = ev.get("keywords_matched", "")
            kw_list = [k.strip() for k in kws.split(",") if k.strip()]
            story.append(Paragraph(
                f"<b>{ev.get('entity_target','?')}</b>  ·  "
                f"{ev.get('state_jurisdiction','?')}  ·  "
                f"{ev.get('data_type','?')}",
                BODY_STYLE,
            ))
            story.append(Paragraph(f"Event ID: {ev.get('event_id','')}", CODE_STYLE))
            story.append(Paragraph(
                f"Keywords matched ({len(kw_list)}): {', '.join(kw_list) if kw_list else 'none'}  "
                f"← below threshold, dismissed",
                DANGER_STYLE,
            ))
            story.append(Paragraph(f"Source: {ev.get('source_url', 'N/A')}", SMALL_STYLE))
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("No dismissed events.", BODY_STYLE))

    # ── False-positive fix note ───────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Engineering Note: False-Positive Filter (applied 2026-07-16)", SECTION_STYLE))
    story.append(Paragraph(
        "During the July 16 run, two VA SCC events with only one keyword match each were written "
        "to the database and later confirmed as unrelated to the grid/data-center thesis:",
        BODY_STYLE,
    ))
    story.append(Paragraph(
        "  • <b>5d67df890a4c245bf2bb14e2</b> — Dominion Energy, PUR-2018-00151 "
        "(Harris Teeter 2018 retail aggregation petition). Matched only 'cost-shifting'.",
        BODY_STYLE,
    ))
    story.append(Paragraph(
        "  • <b>4a7a3ff21dcb268ceed6f8c0</b> — Appalachian Power, PUR-2026-00017 "
        "(Mark Mellon residential solar waiver). Matched only 'behind-the-meter'.",
        BODY_STYLE,
    ))
    story.append(Paragraph(
        "Fix applied: <b>PdfScanResult.has_signal</b> now requires ≥2 keyword matches "
        "(previously >0). All active scrapers use this property as the signal gate.",
        WARN_STYLE,
    ))
    story.append(Spacer(1, 6))

    # ── Database snapshot ────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Database Snapshot (all-time)", SECTION_STYLE))

    # Pivot by jurisdiction
    jurisdictions = {}
    for ev in all_events:
        j = ev.get("state_jurisdiction", "?")
        jurisdictions.setdefault(j, {"total": 0, "signal": 0})
        jurisdictions[j]["total"] += 1
        kws = ev.get("keywords_matched", "") or ""
        if len([k for k in kws.split(",") if k.strip()]) >= 2:
            jurisdictions[j]["signal"] += 1

    snap_data = [["Jurisdiction", "Total Events", "Signal Events"]]
    for j, counts in sorted(jurisdictions.items()):
        snap_data.append([j, str(counts["total"]), str(counts["signal"])])
    snap_data.append(["TOTAL", str(len(all_events)),
                      str(sum(c["signal"] for c in jurisdictions.values()))])

    snap_tbl = _table(snap_data, [W * 0.40, W * 0.30, W * 0.30])
    # Highlight total row
    snap_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, len(snap_data) - 1), (-1, len(snap_data) - 1), PANEL),
        ("TEXTCOLOR",   (0, len(snap_data) - 1), (-1, len(snap_data) - 1), ACCENT),
        ("FONTNAME",    (0, len(snap_data) - 1), (-1, len(snap_data) - 1), "Helvetica-Bold"),
    ]))
    story.append(snap_tbl)
    story.append(Spacer(1, 10))

    # ── Watchlists ───────────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Active Watchlists", SECTION_STYLE))

    watchlist_data = [
        ["Entity", "Jurisdiction", "Signal Type", "Status"],
        ["Dominion Energy", "VA", "GS-5 tariff + co-location protests",
         "MONITORING — signal today"],
        ["PPL Corporation", "PA", "PPL_TARIFF_THREAT (take-or-pay)",
         "MONITORING — PA PUC portal down"],
        ["American Electric Power", "OH", "Queue collapse / take-or-pay",
         "AEP filing confirmed 2026-02-13"],
        ["Constellation / Talen", "PA / FEDERAL", "Nuclear co-location protests",
         "MONITORING"],
    ]
    wl_tbl = _table(watchlist_data, [W * 0.20, W * 0.15, W * 0.34, W * 0.31])
    story.append(wl_tbl)
    story.append(Spacer(1, 10))

    # ── Key confirmed events ─────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph("Key Confirmed Events (historical)", SECTION_STYLE))

    key_data = [
        ["Event", "Date", "Source", "MW Impact"],
        ["AEP Ohio take-or-pay filing (Case 24-0508-EL-ATA)",
         "2026-02-13", "Ohio PUCO", "30,000 → 5,700 MW bankable"],
        ["Dominion GS-5 tariff approval",
         "2026 (eff. 2027-01-01)", "VA SCC", "N. Virginia queue re-sort"],
        ["PA PUC Model Large Load Tariff finalized",
         "2026-05", "PA PUC", "PPL 9 GW pipeline at risk"],
    ]
    key_tbl = _table(key_data, [W * 0.38, W * 0.18, W * 0.18, W * 0.26])
    story.append(key_tbl)
    story.append(Spacer(1, 10))

    # ── Disclaimer ───────────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph(
        "This report is generated automatically by Project Fosbury, an informational analytics "
        "pipeline. It is not financial advice. All data sourced from public regulatory filings. "
        "Signal classifications are heuristic and subject to manual review.",
        SMALL_STYLE,
    ))

    # ── Build ────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=canvas_bg, onLaterPages=canvas_bg)
    print(f"Report written → {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    output   = f"GRP_Daily_Report_{run_date.replace('-', '_')}.pdf"
    build_report(run_date, output)
