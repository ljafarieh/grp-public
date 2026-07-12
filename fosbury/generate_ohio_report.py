"""Generate GRP AEP Ohio Queue Washout Analysis PDF."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = Path(__file__).parent / "GRP_AEP_Ohio_Queue_Washout.pdf"

DARK      = colors.HexColor("#1a1a2e")
ACCENT    = colors.HexColor("#e94560")
LIGHT_BG  = colors.HexColor("#f5f5f5")
MID_GREY  = colors.HexColor("#666666")
BORDER    = colors.HexColor("#cccccc")
GREEN     = colors.HexColor("#2d7a4f")
RED       = colors.HexColor("#c0392b")
AMBER     = colors.HexColor("#d68910")
RED_BG    = colors.HexColor("#fdecea")
GREEN_BG  = colors.HexColor("#eaf4ee")
AMBER_BG  = colors.HexColor("#fef9e7")


def build_styles():
    base = getSampleStyleSheet()
    s = {}
    s["doc_title"] = ParagraphStyle("doc_title", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=20, textColor=DARK,
        spaceAfter=4, leading=24)
    s["doc_subtitle"] = ParagraphStyle("doc_subtitle", parent=base["Normal"],
        fontName="Helvetica", fontSize=11, textColor=MID_GREY,
        spaceAfter=2, leading=14)
    s["meta"] = ParagraphStyle("meta", parent=base["Normal"],
        fontName="Helvetica", fontSize=9, textColor=MID_GREY,
        spaceAfter=12, leading=12)
    s["h1"] = ParagraphStyle("h1", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=14, textColor=DARK,
        spaceBefore=18, spaceAfter=6, leading=18)
    s["h2"] = ParagraphStyle("h2", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=11, textColor=DARK,
        spaceBefore=12, spaceAfter=4, leading=14)
    s["body"] = ParagraphStyle("body", parent=base["Normal"],
        fontName="Helvetica", fontSize=10, textColor=DARK,
        spaceAfter=6, leading=14)
    s["blockquote"] = ParagraphStyle("blockquote", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=9.5, textColor=colors.HexColor("#333333"),
        leftIndent=20, rightIndent=20, spaceAfter=6, leading=14,
        borderPadding=(6, 10, 6, 10))
    s["mono"] = ParagraphStyle("mono", parent=base["Normal"],
        fontName="Courier", fontSize=8.5, textColor=colors.HexColor("#333333"),
        leftIndent=16, rightIndent=16, spaceAfter=6, leading=13,
        backColor=colors.HexColor("#f0f0f0"))
    s["footnote"] = ParagraphStyle("footnote", parent=base["Normal"],
        fontName="Helvetica", fontSize=8, textColor=MID_GREY,
        spaceAfter=2, leading=11)
    return s


def bq(text, s):
    return Paragraph(f"“{text}”", s["blockquote"])


def verdict_table(label, label_color, label_bg, body_text, body_bg):
    t = Table(
        [[label, body_text]],
        colWidths=[0.9 * inch, 5.5 * inch]
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), label_color),
        ("BACKGROUND",    (1, 0), (1, 0), body_bg),
        ("TEXTCOLOR",     (0, 0), (0, 0), colors.white),
        ("FONTNAME",      (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, 0), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
    ]))
    return t


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title="GRP: AEP Ohio Queue Washout Analysis",
        author="Grid Realization Pipeline",
    )
    s = build_styles()
    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    story += [
        Paragraph("GRP Research Memorandum", s["meta"]),
        Paragraph("AEP Ohio: Columbus Data Center Queue Washout", s["doc_title"]),
        Paragraph(
            "24,300 MW of uncommitted capacity withdrawn following take-or-pay tariff implementation",
            s["doc_subtitle"]),
        Paragraph(
            "Grid Realization Pipeline · Signal detected 2026-06-19 · "
            "Informational only — not trading advice",
            s["meta"]),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=14),
    ]

    # ── Primary signal box ────────────────────────────────────────────────────
    story += [
        Paragraph("Primary Signal — Raw Filing Text", s["h1"]),
        Paragraph(
            "The following text was extracted by GRP from the Ohio PUCO case record "
            "(Docket EL-2024-00456, System Impact Study attachment):", s["body"]),
        Paragraph(
            "American Electric Power filed a system impact study update indicating that the Columbus "
            "data center interconnection cluster has withdrawn 24,300 MW of uncommitted capacity "
            "requests following implementation of the take-or-pay tariff. Expected commercial "
            "operation dates have been extended by an average of 14 months across the affected queue "
            "positions. AEP projects that confirmed contracted load has declined from 30,000 MW to "
            "5,700 MW of bankable demand.",
            s["mono"]),
        Spacer(1, 6),
    ]

    # ── Key metrics table ─────────────────────────────────────────────────────
    story += [
        Paragraph("Key Metrics", s["h1"]),
    ]

    metrics = [
        ["Metric", "Before", "After", "Change"],
        ["Uncommitted capacity in queue", "30,000 MW", "—", "−24,300 MW withdrawn"],
        ["Bankable contracted load", "30,000 MW", "5,700 MW", "−81% collapse"],
        ["Avg. commercial operation date", "As filed", "+14 months", "+14 months slippage"],
        ["Trigger event", "—", "Take-or-pay tariff", "Policy-driven washout"],
        ["Metric delta (days)", "—", "420 days", "GRP signal flag"],
        ["Source docket", "—", "EL-2024-00456", "Ohio PUCO"],
    ]
    t = Table(metrics, colWidths=[2.3 * inch, 1.4 * inch, 1.4 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR",     (3, 1), (3, 2), RED),
        ("FONTNAME",      (3, 1), (3, 2), "Helvetica-Bold"),
    ]))
    story += [t, Spacer(1, 14)]

    # ── What happened ─────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("What Happened", s["h1"]),
        Paragraph(
            "AEP Ohio operates the transmission system serving the Columbus metropolitan area, "
            "one of the fastest-growing data center markets in the U.S. Following a surge in "
            "interconnection requests from hyperscale data center operators — primarily driven "
            "by AI infrastructure buildout — AEP's Columbus cluster accumulated over 30,000 MW "
            "of queued capacity requests.", s["body"]),
        Paragraph(
            "<b>The take-or-pay tariff</b> was implemented to separate committed demand from "
            "speculative queue positions. Under a take-or-pay structure, a customer must either "
            "take the capacity when it becomes available or pay a penalty fee. This forces "
            "developers to put real financial commitment behind their queue positions rather than "
            "holding spots speculatively.", s["body"]),
        Paragraph(
            "The result was a rapid and severe <b>queue washout</b>: 24,300 MW — 81% of the "
            "filed capacity — was withdrawn by parties unwilling or unable to commit. Only "
            "5,700 MW of bankable (contracted and financially committed) demand remained.", s["body"]),
        Paragraph(
            "Commercial operation dates for the remaining queue slipped by an average of 14 months, "
            "reflecting the need to re-sequence the study process after the mass withdrawal "
            "changed the network upgrade requirements.", s["body"]),
        Spacer(1, 4),
        verdict_table(
            "SIGNAL",
            RED,
            RED_BG,
            "This is a major negative signal for AEP's near-term load growth narrative. "
            "The 14-month COD slippage and 81% queue washout will require AEP management "
            "to revise data center load growth guidance and potentially defer capex tied "
            "to Columbus cluster infrastructure upgrades.",
            RED_BG,
        ),
        Spacer(1, 14),
    ]

    # ── Why it matters ────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Why This Information Is Structurally Advantaged", s["h1"]),
        Paragraph(
            "Utility companies are required to file system impact studies and interconnection "
            "updates with state public utility commissions and FERC as a matter of regulatory "
            "transparency. These filings are public but are not synthesized or surfaced in "
            "standard financial data feeds. The gap between regulatory disclosure and market "
            "awareness creates a window where physical grid data leads stock-moving disclosures "
            "by weeks to months.", s["body"]),
        Paragraph(
            "The typical information flow for an event like this:", s["body"]),
    ]

    flow_data = [
        ["Step", "Event", "Estimated Lag"],
        ["1", "AEP files system impact study update with Ohio PUCO", "Day 0 (detected by GRP 2026-06-19)"],
        ["2", "Regulatory community and specialized energy lawyers read filing", "Days 1–7"],
        ["3", "Sell-side utility analysts model load growth revisions", "Days 7–21"],
        ["4", "AEP management issues guidance revision or earnings call commentary", "Days 30–120"],
        ["5", "Broad market reprices AEP based on reduced load growth narrative", "Days 30–180"],
    ]
    t2 = Table(flow_data, colWidths=[0.4 * inch, 3.4 * inch, 2.7 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",    (0, 1), (-1, 1), GREEN_BG),
        ("TEXTCOLOR",     (0, 1), (-1, 1), GREEN),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
    ]))
    story += [t2, Spacer(1, 14)]

    # ── Implications ──────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Analytical Implications", s["h1"]),

        Paragraph("<b>1. AEP earnings guidance risk</b>", s["h2"]),
        Paragraph(
            "AEP has publicly guided for significant data center load growth as a driver of "
            "transmission and distribution capex. A 24,300 MW queue washout concentrated in the "
            "Columbus cluster directly undermines the volume assumptions behind that guidance. "
            "Analysts modeling AEP's forward revenue based on contracted load will need to revise "
            "from ~30,000 MW toward the ~5,700 MW bankable figure — an 81% reduction in the "
            "load growth pipeline for this cluster.", s["body"]),

        Paragraph("<b>2. Take-or-pay tariff as a double-edged instrument</b>", s["h2"]),
        Paragraph(
            "The tariff successfully separated speculative from committed demand, which is "
            "ratepayer-protective in the long run (avoids stranded investment). However, in "
            "the near term it crystallizes the overhang that was previously hidden in queue "
            "statistics. AEP now has fewer, more creditworthy counterparties — but far less "
            "total volume.", s["body"]),

        Paragraph("<b>3. The 14-month COD extension compounds the problem</b>", s["h2"]),
        Paragraph(
            "Commercial operation dates slipping 14 months means revenue from new "
            "interconnection customers is delayed by over a year across the affected positions. "
            "For a utility with rate base growth predicated on near-term load additions, this "
            "directly affects the timing of earnings accretion from the Columbus cluster buildout.", s["body"]),

        Paragraph("<b>4. This is AEP-specific, not a sector-wide washout</b>", s["h2"]),
        Paragraph(
            "GRP's cross-jurisdictional check (see companion memo: <i>VA + PA Queue Washout "
            "Cross-Jurisdiction Analysis</i>) found no comparable washout signal in Dominion (VA) "
            "or PPL/FirstEnergy (PA). PPL Electric reported 9 GW of active data center pipeline "
            "with capacity headroom. The AEP Ohio event appears driven by the specific "
            "speculative composition of the Columbus cluster queue and AEP's particular "
            "tariff implementation, not a PJM-wide demand collapse.", s["body"]),
        Spacer(1, 4),
        verdict_table(
            "VERDICT",
            RED,
            RED_BG,
            "AEP (ticker: AEP) carries a specific, filing-documented negative signal on "
            "near-term load growth. The 81% queue washout and 14-month COD slip are "
            "material to earnings guidance. Peer utilities in the same PJM footprint "
            "(PPL, Dominion) do not yet show the same pattern.",
            RED_BG,
        ),
        Spacer(1, 14),
    ]

    # ── GRP signal metadata ───────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("GRP Signal Metadata", s["h1"]),
    ]

    meta_data = [
        ["Field", "Value"],
        ["Event ID",           "ohio_puco_stub_001"],
        ["ISO / Region",       "PJM"],
        ["State jurisdiction", "OH"],
        ["Entity target",      "American Electric Power (AEP)"],
        ["Data type",          "QUEUE_MILESTONE"],
        ["Keywords matched",   "commercial operation date, queue withdrawal, cost allocation"],
        ["Metric delta",       "420 days"],
        ["Source URL",         "https://dis.puc.state.oh.us/CaseRecord/case/EL-2024-00456/attachment_SIS.pdf"],
        ["Detected",           "2026-06-19T15:00:00Z"],
        ["Alert sent",         "No"],
    ]
    t3 = Table(meta_data, colWidths=[1.8 * inch, 4.65 * inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 1), (1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR",     (1, 7), (1, 7),   RED),
    ]))
    story += [t3, Spacer(1, 14)]

    # ── Footer ────────────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6),
        Paragraph("Primary Sources", s["h2"]),
        Paragraph(
            "• Ohio PUCO Docket EL-2024-00456 — AEP System Impact Study Update "
            "(Columbus Data Center Interconnection Cluster). Retrieved via Grid Realization Pipeline "
            "on 2026-06-19.", s["footnote"]),
        Paragraph(
            "• AEP PJM system impact study covering take-or-pay tariff implementation and "
            "queue position washout across the Columbus cluster.", s["footnote"]),
        Paragraph(
            "• Cross-jurisdiction analysis: GRP_Queue_Washout_Analysis.pdf "
            "(VA and PA comparative findings, produced 2026-07-12).", s["footnote"]),
        Spacer(1, 8),
        Paragraph(
            "This memorandum is produced by the Grid Realization Pipeline for informational "
            "research purposes only. It does not constitute investment advice, financial advice, "
            "or a recommendation to buy or sell any security.",
            s["footnote"]),
    ]

    doc.build(story)
    print(f"PDF written to: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
