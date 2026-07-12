"""Generate GRP queue washout cross-jurisdiction analysis PDF."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = Path(__file__).parent / "GRP_Queue_Washout_Analysis.pdf"

# ── colours ──────────────────────────────────────────────────────────────────
DARK      = colors.HexColor("#1a1a2e")
ACCENT    = colors.HexColor("#e94560")
LIGHT_BG  = colors.HexColor("#f5f5f5")
MID_GREY  = colors.HexColor("#666666")
BORDER    = colors.HexColor("#cccccc")
GREEN     = colors.HexColor("#2d7a4f")
RED       = colors.HexColor("#c0392b")
AMBER     = colors.HexColor("#d68910")

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
    s["label_good"] = ParagraphStyle("label_good", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=9, textColor=GREEN)
    s["label_bad"] = ParagraphStyle("label_bad", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=9, textColor=RED)
    s["label_amber"] = ParagraphStyle("label_amber", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=9, textColor=AMBER)
    s["verdict_box"] = ParagraphStyle("verdict_box", parent=base["Normal"],
        fontName="Helvetica", fontSize=10, textColor=DARK,
        leftIndent=10, rightIndent=10, spaceAfter=4, leading=14)
    s["footnote"] = ParagraphStyle("footnote", parent=base["Normal"],
        fontName="Helvetica", fontSize=8, textColor=MID_GREY,
        spaceAfter=2, leading=11)
    return s

def bq(text, s):
    """Return a shaded blockquote paragraph."""
    return Paragraph(f"“{text}”", s["blockquote"])

def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=0.85*inch, rightMargin=0.85*inch,
        topMargin=0.9*inch, bottomMargin=0.9*inch,
        title="GRP Queue Washout Cross-Jurisdiction Analysis",
        author="Grid Realization Pipeline",
    )
    s = build_styles()
    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    story += [
        Paragraph("GRP Research Memorandum", s["meta"]),
        Paragraph("VA + PA Queue Washout Cross-Jurisdiction Analysis", s["doc_title"]),
        Paragraph("Does the AEP Ohio pattern repeat in Dominion and PPL/Constellation territory?", s["doc_subtitle"]),
        Paragraph("Grid Realization Pipeline · Produced 2026-07-12 · Informational only — not trading advice", s["meta"]),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=14),
    ]

    # ── Baseline ─────────────────────────────────────────────────────────────
    story += [
        Paragraph("Baseline: What the AEP Ohio Filing Said", s["h1"]),
        Paragraph(
            "In a PJM system impact study update, American Electric Power (AEP) disclosed that its "
            "Columbus data center interconnection cluster experienced a significant queue washout "
            "following the implementation of a take-or-pay tariff:", s["body"]),
        Spacer(1, 4),
    ]

    baseline_data = [
        ["Metric", "Value"],
        ["MW withdrawn from uncommitted queue", "24,300 MW"],
        ["Contracted load before washout", "30,000 MW"],
        ["Bankable contracted load after washout", "5,700 MW"],
        ["Avg. COD extension across affected positions", "+14 months"],
        ["Source", "AEP PJM System Impact Study Update (2025–2026)"],
    ]
    t = Table(baseline_data, colWidths=[3.2*inch, 3.2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), DARK),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
        ("BACKGROUND", (0,1), (-1,-1), LIGHT_BG),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT_BG]),
        ("GRID",       (0,0), (-1,-1), 0.4, BORDER),
        ("LEFTPADDING",(0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
    ]))
    story += [t, Spacer(1, 14)]

    # ── Virginia ─────────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Virginia — Dominion Energy (ticker: D)", s["h1"]),
        Paragraph("Finding: Different regulatory layer — no comparable washout signal.", s["h2"]),
        Paragraph(
            "The VA SCC case PUR-2022-00073, titled <i>In the Matter Considering Utility Distributed "
            "Energy Resource Interconnection</i>, is about <b>distributed energy resource (DER)</b> "
            "interconnection reform — rooftop solar, small battery storage, and co-op interconnections. "
            "It is not the same regulatory instrument that would capture utility-scale data center queue activity.", s["body"]),
        Paragraph(
            "Dominion's most recent cluster pilot report (October 2025, filed with VA SCC) disclosed:", s["body"]),
        bq(
            "As the Pilot is now closed with no projects enrolled, the Company, in accordance with the "
            "Order, submits its fifth and final report.",
            s),
        Paragraph(
            "Dominion's <b>large-scale transmission interconnection queue</b> (where hyperscale data centers "
            "would sit) is managed through PJM's RTEP process, not through VA SCC. The VA SCC regulates "
            "Dominion's distribution system, not PJM-level transmission. No take-or-pay tariff equivalent "
            "to AEP's is visible in VA SCC filings.", s["body"]),
        Spacer(1, 4),
    ]

    verdict_va = Table(
        [["VERDICT", "No comparable queue washout found. Different regulatory layer from AEP Ohio.\n"
          "To assess Dominion's true data center queue exposure, PJM zone-level queue data\n"
          "(DOM zone, RTEP filings) would be required — not available via VA SCC."]],
        colWidths=[0.9*inch, 5.5*inch]
    )
    verdict_va.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#2d7a4f")),
        ("BACKGROUND", (1,0), (1,0), colors.HexColor("#eaf4ee")),
        ("TEXTCOLOR",  (0,0), (0,0), colors.white),
        ("FONTNAME",   (0,0), (0,0), "Helvetica-Bold"),
        ("FONTNAME",   (1,0), (1,0), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("GRID",       (0,0), (-1,-1), 0.4, BORDER),
    ]))
    story += [verdict_va, Spacer(1, 14)]

    # ── Pennsylvania ─────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Pennsylvania — PPL Electric (ticker: PPL) &amp; FirstEnergy PA", s["h1"]),
        Paragraph("Finding: Counter-signal — PPL is actively welcoming 9 GW of data center pipeline.", s["h2"]),
        Paragraph(
            "The PA PUC held a formal en banc hearing on <i>Interconnection and Tariffs for Large Load "
            "Customers</i> on April 24, 2025 (Docket No. M-2025-3054271). Unlike Virginia, Pennsylvania "
            "regulators convened this hearing specifically because the data center interconnection wave is "
            "large enough to require a new tariff framework.", s["body"]),
        Paragraph("<b>PPL Electric VP Joseph Lookup testified:</b>", s["body"]),
        bq(
            "PPL Electric is directly seeing the growth of data center development in Pennsylvania, with "
            "requests in advanced stages in excess of 9 GW of new load as reported during PPL Corporation’s "
            "year-end earnings call. To put this into perspective, PPL Electric’s current summer peak is 7.5 GW, "
            "and the new data center requests are poised to more than double PPL Electric’s system peak "
            "within the next 5–6 years.",
            s),
        bq(
            "PPL Electric has invested in the reliability and resiliency of its transmission system to better "
            "serve its customers. An additional benefit of this investment is that PPL Electric now stands ready "
            "to serve this influx of load with large load customers only having to cover the incremental cost "
            "of interconnecting their facilities.",
            s),
        bq(
            "The Company estimates that the first gigawatt of interconnected load will reduce other "
            "customers’ transmission costs by 10%.",
            s),
        Paragraph(
            "PPL is explicitly framing data center load as beneficial to all ratepayers. They have capacity "
            "headroom from prior transmission investment. <b>No take-or-pay tariff has been implemented</b> — "
            "the PA Office of Consumer Advocate (OCA) is advocating for one as a future protection, which "
            "means the washout risk is prospective rather than realized:", s["body"]),
        bq(
            "The objectives of transparency, non-discriminatory access, fair cost allocation, and protection "
            "from stranded assets are achievable through a dedicated large load tariff.",
            s),
        Paragraph(
            "FirstEnergy PA (covering 2.1 million customers across 56 of 67 PA counties) also testified that "
            "it is adapting its load study process for data center characteristics but described the situation "
            "as an evolving challenge, not a washout event.", s["body"]),
        Spacer(1, 4),
    ]

    verdict_pa = Table(
        [["VERDICT", "No queue washout. PPL has 9 GW of active pipeline, capacity headroom, and a\n"
          "favorable regulatory posture. The washout risk the OCA is flagging is a future\n"
          "policy risk (take-or-pay implementation), not a current withdrawal event."]],
        colWidths=[0.9*inch, 5.5*inch]
    )
    verdict_pa.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#2d7a4f")),
        ("BACKGROUND", (1,0), (1,0), colors.HexColor("#eaf4ee")),
        ("TEXTCOLOR",  (0,0), (0,0), colors.white),
        ("FONTNAME",   (0,0), (0,0), "Helvetica-Bold"),
        ("FONTNAME",   (1,0), (1,0), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("GRID",       (0,0), (-1,-1), 0.4, BORDER),
    ]))
    story += [verdict_pa, Spacer(1, 14)]

    # ── Comparison table ─────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Cross-Jurisdiction Comparison", s["h1"]),
    ]

    comp_data = [
        ["Jurisdiction", "Utility", "Queue Status", "Take-or-Pay", "Washout Risk"],
        ["Ohio",         "AEP (AEP)",          "Washout confirmed\n(24.3 GW withdrawn)", "Yes — triggered\nwashout",          "Already realized"],
        ["Virginia",     "Dominion (D)",        "DER queue only;\nPJM manages utility-scale", "No equivalent\nvisible",     "Low\n(different layer)"],
        ["Pennsylvania", "PPL (PPL)",           "9 GW active pipeline;\ncapacity headroom",  "No — OCA pushing\nfor it",    "Future risk;\nnot current"],
        ["Pennsylvania", "FirstEnergy PA",      "Active; adapting\nprocesses",               "No — considering\nit",        "Low-medium"],
    ]

    row_colors = [DARK, RED, LIGHT_BG, colors.HexColor("#eaf4ee"), colors.HexColor("#fafafa")]
    text_colors = [colors.white, colors.white, DARK, DARK, DARK]

    t2 = Table(comp_data, colWidths=[1.1*inch, 1.2*inch, 1.7*inch, 1.4*inch, 1.1*inch])
    style_cmds = [
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        # row 1 = AEP (red)
        ("BACKGROUND",    (0,1), (-1,1),  colors.HexColor("#fdecea")),
        ("TEXTCOLOR",     (4,1), (4,1),   RED),
        ("FONTNAME",      (4,1), (4,1),   "Helvetica-Bold"),
        # row 2 = VA (neutral)
        ("BACKGROUND",    (0,2), (-1,2),  colors.white),
        # row 3 = PPL (green)
        ("BACKGROUND",    (0,3), (-1,3),  colors.HexColor("#eaf4ee")),
        ("TEXTCOLOR",     (4,3), (4,3),   GREEN),
        # row 4 = FE PA
        ("BACKGROUND",    (0,4), (-1,4),  LIGHT_BG),
    ]
    style_cmds.append(("BACKGROUND", (0,0), (-1,0), DARK))
    t2.setStyle(TableStyle(style_cmds))
    story += [t2, Spacer(1, 14)]

    # ── Synthesis ─────────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Synthesis: Does This Break the Sector Thesis?", s["h1"]),
        Paragraph("<b>No — and the cross-check clarifies something important.</b>", s["body"]),
        Paragraph(
            "The AEP Ohio washout appears to be <b>AEP-specific</b>, driven by two compounding factors:", s["body"]),
        Paragraph(
            "1. AEP's specific take-or-pay tariff design for the Columbus data center cluster<br/>"
            "2. That specific cluster having unusually speculative queue composition "
            "(30 GW filed vs. only 5.7 GW bankable demand)", s["body"]),
        Paragraph("What this means for ticker-level differentiation:", s["h2"]),
    ]

    ticker_data = [
        ["Ticker", "Signal", "Rationale"],
        ["AEP",  "NEGATIVE",  "24.3 GW washout confirmed. EPS guidance at risk from\n"
                               "reduced load growth assumptions in Columbus cluster zone."],
        ["PPL",  "POSITIVE",  "9 GW pipeline, capacity headroom from prior capex.\n"
                               "Expects to benefit from rate dilution for existing customers."],
        ["D",    "NEUTRAL /\nMONITOR",
                               "No VA SCC signal. True exposure requires PJM DOM-zone\n"
                               "queue data (RTEP filings) — not captured here."],
        ["CEG",  "NEUTRAL",   "Constellation operates nuclear plants, not distribution.\n"
                               "PA regulatory exposure is indirect via FirstEnergy territory."],
    ]

    t3 = Table(ticker_data, colWidths=[0.7*inch, 1.0*inch, 4.8*inch])
    signal_colors = {
        "NEGATIVE":  (RED,   colors.HexColor("#fdecea")),
        "POSITIVE":  (GREEN, colors.HexColor("#eaf4ee")),
        "NEUTRAL /\nMONITOR": (AMBER, colors.HexColor("#fef9e7")),
        "NEUTRAL":   (MID_GREY, LIGHT_BG),
    }
    t3_style = [
        ("BACKGROUND",    (0,0), (-1,0),  DARK),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("FONTNAME",      (0,1), (1,-1),  "Helvetica-Bold"),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]
    signal_rows = {"NEGATIVE": 1, "POSITIVE": 2, "NEUTRAL /\nMONITOR": 3, "NEUTRAL": 4}
    for signal, row in signal_rows.items():
        fg, bg = signal_colors[signal]
        t3_style += [
            ("BACKGROUND", (0,row), (-1,row), bg),
            ("TEXTCOLOR",  (1,row), (1,row),  fg),
        ]
    t3.setStyle(TableStyle(t3_style))
    story += [t3, Spacer(1, 12)]

    # ── Forward-looking risk ──────────────────────────────────────────────────
    story += [
        Paragraph("Forward-Looking Risk to Monitor", s["h2"]),
        Paragraph(
            "If the PA PUC implements a PPL take-or-pay tariff modeled on AEP’s design "
            "(which the OCA is actively advocating), PPL’s 9 GW pipeline could see a "
            "similar washout event. That would be a <b>negative inflection for PPL</b> — "
            "but it requires a specific PUC ruling to trigger and is likely 12–18 months away "
            "from becoming a realized event, not an immediate earnings risk.", s["body"]),
        Paragraph(
            "The Harvard Electricity Law Initiative paper cited by PA PUC Vice Chair Barrow "
            "(<i>“Extracting Profits from the Public: How Utility Ratepayers are Paying for Big Tech’s Power”</i>) "
            "suggests the political pressure for stronger cost-allocation protections is building. "
            "This is a regulatory trend to track across all PJM-footprint utilities.", s["body"]),
        Spacer(1, 14),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6),
    ]

    # ── Sources ───────────────────────────────────────────────────────────────
    story += [
        Paragraph("Primary Sources", s["h2"]),
        Paragraph("• AEP: PJM System Impact Study Update (Columbus data center cluster, 2025–2026)", s["footnote"]),
        Paragraph("• VA: VA SCC Docket PUR-2022-00073 — In the Matter Considering Utility DER Interconnection. "
                  "Dominion Energy quarterly cluster pilot reports (Jan 2024 – Oct 2025). "
                  "Retrieved via VA SCC DocketSearch REST API.", s["footnote"]),
        Paragraph("• PA: PA PUC Docket M-2025-3054271 — En Banc Hearing on Interconnection and Tariffs for "
                  "Large Load Customers, April 24, 2025. Testimonies of PPL Electric (Joseph Lookup, VP), "
                  "FirstEnergy PA (Kelly Gower, VP), Office of Consumer Advocate (Darryl Lawrence, Acting CA), "
                  "PECO Energy, Amazon Data Services, Data Center Coalition.", s["footnote"]),
        Paragraph("• All documents retrieved programmatically via Grid Realization Pipeline (GRP) on 2026-07-12.", s["footnote"]),
        Spacer(1, 8),
        Paragraph(
            "This memorandum is produced by the Grid Realization Pipeline for informational research purposes only. "
            "It does not constitute investment advice, financial advice, or a recommendation to buy or sell any security.",
            s["footnote"]),
    ]

    doc.build(story)
    print(f"PDF written to: {OUTPUT}")

if __name__ == "__main__":
    build_pdf()
