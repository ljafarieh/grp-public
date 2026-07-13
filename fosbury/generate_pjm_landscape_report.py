"""Generate GRP PJM-wide take-or-pay landscape analysis PDF."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
)

OUTPUT = Path(__file__).parent / "GRP_PJM_TakeOrPay_Landscape.pdf"

DARK     = colors.HexColor("#1a1a2e")
ACCENT   = colors.HexColor("#e94560")
LIGHT_BG = colors.HexColor("#f5f5f5")
MID_GREY = colors.HexColor("#666666")
BORDER   = colors.HexColor("#cccccc")
GREEN    = colors.HexColor("#2d7a4f")
RED      = colors.HexColor("#c0392b")
AMBER    = colors.HexColor("#d68910")
RED_BG   = colors.HexColor("#fdecea")
GREEN_BG = colors.HexColor("#eaf4ee")
AMBER_BG = colors.HexColor("#fef9e7")
BLUE     = colors.HexColor("#1a5276")
BLUE_BG  = colors.HexColor("#eaf0fb")


def styles():
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle("doc_title", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=20, textColor=DARK,
            spaceAfter=4, leading=24),
        "doc_subtitle": ParagraphStyle("doc_subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=11, textColor=MID_GREY,
            spaceAfter=2, leading=14),
        "meta": ParagraphStyle("meta", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, textColor=MID_GREY,
            spaceAfter=12, leading=12),
        "h1": ParagraphStyle("h1", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=14, textColor=DARK,
            spaceBefore=18, spaceAfter=6, leading=18),
        "h2": ParagraphStyle("h2", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=11, textColor=DARK,
            spaceBefore=10, spaceAfter=4, leading=14),
        "body": ParagraphStyle("body", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, textColor=DARK,
            spaceAfter=6, leading=14),
        "bq": ParagraphStyle("bq", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=9.5,
            textColor=colors.HexColor("#333333"),
            leftIndent=20, rightIndent=20, spaceAfter=6, leading=14),
        "footnote": ParagraphStyle("footnote", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=MID_GREY,
            spaceAfter=2, leading=11),
    }


def bq(text, s):
    return Paragraph(f"“{text}”", s["bq"])


def verdict(label, lc, body, bc):
    t = Table([[label, body]], colWidths=[0.9*inch, 5.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,0), lc),
        ("BACKGROUND",    (1,0),(1,0), bc),
        ("TEXTCOLOR",     (0,0),(0,0), colors.white),
        ("FONTNAME",      (0,0),(0,0), "Helvetica-Bold"),
        ("FONTNAME",      (1,0),(1,0), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("GRID",          (0,0),(-1,-1), 0.4, BORDER),
    ]))
    return t


def build():
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter,
        leftMargin=0.85*inch, rightMargin=0.85*inch,
        topMargin=0.9*inch, bottomMargin=0.9*inch,
        title="GRP: PJM Take-or-Pay Landscape — All States",
        author="Grid Realization Pipeline",
    )
    s = styles()
    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    story += [
        Paragraph("GRP Research Memorandum", s["meta"]),
        Paragraph("PJM Take-or-Pay Landscape: All 13 States", s["doc_title"]),
        Paragraph(
            "Which PJM states have implemented large-load tariffs — and which are next to trigger a queue washout?",
            s["doc_subtitle"]),
        Paragraph(
            "Grid Realization Pipeline · Produced 2026-07-12 · "
            "Informational only — not trading advice",
            s["meta"]),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=14),
    ]

    # ── Context ──────────────────────────────────────────────────────────────
    story += [
        Paragraph("Context: The PJM-Wide Tariff Policy Shift", s["h1"]),
        Paragraph(
            "Through 2024, most PJM-footprint utilities served data center load under standard "
            "industrial tariffs — customers paid retail rates with no special commitment to "
            "consume the capacity they requested during interconnection. The resulting "
            "speculative queue buildup culminated in the AEP Ohio washout (June 2026), "
            "where 81% of the Columbus cluster's 30,000 MW queue evaporated after a "
            "take-or-pay tariff was introduced.", s["body"]),
        Paragraph(
            "Two parallel policy pressures are now reshaping interconnection economics "
            "across all 13 PJM states:", s["body"]),
        Paragraph(
            "<b>1. State legislatures</b> are mandating that data centers bear their own "
            "grid upgrade costs through stand-alone large-load tariffs with minimum demand "
            "commitments (take-or-pay floors).", s["body"]),
        Paragraph(
            "<b>2. FERC at the federal level</b> directed PJM to implement new firm and "
            "non-firm transmission services for co-located loads (February 2026 compliance "
            "filing) and accepted PJM's FERC Order 2023 interconnection queue reforms, "
            "which increase financial commitment deposits and withdrawal penalties.", s["body"]),
        Paragraph(
            "Crucially, in January 2026 all 13 PJM state governors issued a joint "
            "<b>Statement of Principles</b> demanding that data centers bear the "
            "infrastructure costs of their own load growth rather than shifting those "
            "burdens to residential ratepayers. This signals bipartisan political alignment "
            "that will accelerate state-level tariff implementation.", s["body"]),
        Spacer(1, 6),
    ]

    # ── Master landscape table ────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("PJM State-by-State Take-or-Pay Status", s["h1"]),
    ]

    landscape = [
        ["State", "Key Utility/Ticker", "Tariff Status", "Take-or-Pay Terms", "Washout Risk"],
        ["Ohio",        "AEP (AEP)",              "IMPLEMENTED\nWashout confirmed",     "Full take-or-pay;\ntriggered washout",           "REALIZED"],
        ["Maryland",    "Exelon: BGE, Pepco,\nDelmarva (EXC)",
                                                   "ENACTED (2025 law +\n2026 RELIEF Act)",
                                                   "≥25 MW threshold;\n60% utilization floor;\nPJM capacity costs\npassed to data centers",
                                                   "HIGH — tariff now\nbeing implemented"],
        ["New Jersey",  "PSEG (PEG),\nFirstEnergy: JCP&L (FE)",
                                                   "PASSED legislature\n6/30/2026; pending\nGovernor signature",
                                                   "≥50 MW threshold;\n85% take-or-pay\nfloor; 10-year term",
                                                   "HIGH — BPU has\n12 months to set\nstandards"],
        ["Virginia",    "Dominion (D)",            "PARTIAL — Dominion\nDER tariff reform;\nno utility-scale\nequivalent visible",
                                                   "DER cluster rules\nonly; PJM manages\nlarge-scale queue",
                                                   "MEDIUM — requires\nPJM DOM-zone\nqueue data to assess"],
        ["Pennsylvania","PPL (PPL),\nFirstEnergy PA (FE)",
                                                   "NOT YET — OCA\nadvocating; PA PUC\nen banc hearing\nheld Apr 2025",
                                                   "None enacted;\nOCA pushing for\ntake-or-pay floor",
                                                   "LOW-MEDIUM — 9 GW\nPPL pipeline active;\nno tariff yet"],
        ["West Virginia","FirstEnergy: Mon Power,\nPotomac Edison (FE)",
                                                   "No specific\nlegislation found",
                                                   "None identified",
                                                   "LOW — limited\ndata center\nconcentration"],
        ["Delaware",    "Delmarva Power (EXC)",    "Part of MD framework\n(Exelon subsidiary)",
                                                   "Follows MD RELIEF\nAct provisions",
                                                   "MEDIUM — tracks\nMaryland"],
        ["Indiana",     "AEP: Indiana Michigan\nPower (AEP)",
                                                   "No specific\nlegislation found",
                                                   "None identified",
                                                   "LOW"],
        ["Illinois",    "Exelon: ComEd (EXC)",     "No large-load tariff\nlegislation found",
                                                   "None identified;\nComEd demand\nresponse programs",
                                                   "LOW — no major\ndata center\ncluster signal"],
        ["Michigan",    "Consumers Energy (CMS),\nDTE Energy (DTE)",
                                                   "No specific\nlegislation found",
                                                   "None identified",
                                                   "LOW"],
        ["Kentucky",    "AEP: Kentucky Power\n(AEP), Duke (DUK)",
                                                   "No specific\nlegislation found",
                                                   "None identified",
                                                   "LOW"],
        ["NC / TN\n(small PJM\nportion)",
                        "Duke (DUK)",              "No specific\nlegislation found",
                                                   "None identified",
                                                   "LOW"],
    ]

    risk_colors = {
        "REALIZED":      (RED,   RED_BG),
        "HIGH — tariff now\nbeing implemented": (RED, RED_BG),
        "HIGH — BPU has\n12 months to set\nstandards": (RED, RED_BG),
        "MEDIUM — requires\nPJM DOM-zone\nqueue data to assess": (AMBER, AMBER_BG),
        "LOW-MEDIUM — 9 GW\nPPL pipeline active;\nno tariff yet": (AMBER, AMBER_BG),
        "MEDIUM — tracks\nMaryland": (AMBER, AMBER_BG),
    }

    col_w = [0.75*inch, 1.5*inch, 1.35*inch, 1.55*inch, 1.35*inch]
    t = Table(landscape, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (0,0),(-1,0),  DARK),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 7.5),
        ("GRID",          (0,0),(-1,-1), 0.4, BORDER),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        # AEP Ohio row
        ("BACKGROUND",    (0,1),(-1,1),  RED_BG),
        ("TEXTCOLOR",     (4,1),(4,1),   RED),
        ("FONTNAME",      (2,1),(2,1),   "Helvetica-Bold"),
        ("TEXTCOLOR",     (2,1),(2,1),   RED),
        # MD row
        ("BACKGROUND",    (0,2),(-1,2),  RED_BG),
        ("TEXTCOLOR",     (4,2),(4,2),   RED),
        # NJ row
        ("BACKGROUND",    (0,3),(-1,3),  RED_BG),
        ("TEXTCOLOR",     (4,3),(4,3),   RED),
        # VA row
        ("BACKGROUND",    (0,4),(-1,4),  AMBER_BG),
        ("TEXTCOLOR",     (4,4),(4,4),   AMBER),
        # PA row
        ("BACKGROUND",    (0,5),(-1,5),  AMBER_BG),
        ("TEXTCOLOR",     (4,5),(4,5),   AMBER),
        # DE row
        ("BACKGROUND",    (0,8),(-1,8),  AMBER_BG),
        ("TEXTCOLOR",     (4,8),(4,8),   AMBER),
        # Remaining rows: light
        ("ROWBACKGROUNDS",(0,6),(-1,-1), [LIGHT_BG, colors.white]),
    ]
    t.setStyle(TableStyle(style_cmds))
    story += [t, Spacer(1, 14)]

    # ── Maryland deep-dive ────────────────────────────────────────────────────
    story += [
        PageBreak(),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Maryland — Exelon (ticker: EXC)", s["h1"]),
        Paragraph("Finding: Most advanced take-or-pay implementation outside Ohio — two-layer legislative framework enacted.", s["h2"]),
        Paragraph(
            "Maryland has the most aggressive regulatory response to data center load in the "
            "PJM footprint after Ohio. Two laws now apply:", s["body"]),

        Paragraph("<b>Layer 1: Next Generation Energy Act (2025)</b>", s["h2"]),
        Paragraph(
            "Mandated that Maryland utilities create stand-alone tariffs for data centers "
            "and other large load customers. Initial threshold: ≥100 MW, 80% utilization floor. "
            "Utilities affected: BGE (Baltimore Gas and Electric), Pepco (Potomac Electric), "
            "Delmarva Power — all Exelon subsidiaries.", s["body"]),

        Paragraph("<b>Layer 2: Utility RELIEF Act (2026)</b>", s["h2"]),
        Paragraph(
            "Passed in 2026, this law significantly expanded the tariff's reach:", s["body"]),
        Paragraph(
            "• Lowered the threshold from 100 MW → <b>25 MW</b> (capturing more data centers)<br/>"
            "• Lowered utilization floor from 80% → <b>60%</b><br/>"
            "• Required utilities to pass along <b>PJM capacity auction costs</b> assigned "
            "to data centers directly to those data centers (preventing cost-shifting to "
            "residential ratepayers)<br/>"
            "• Prohibited speculative rate-setting based on projected (rather than committed) load",
            s["body"]),
        Paragraph(
            "The Maryland PSC notched a milestone in implementation as of June 30, 2026. "
            "The tariff is now being actively implemented by BGE, Pepco, and Delmarva.", s["body"]),

        Paragraph("<b>The Maryland FERC Complaint — A Critical Signal</b>", s["h2"]),
        Paragraph(
            "On May 7, 2026, Maryland's Office of People's Counsel filed a complaint with FERC "
            "over PJM's cost allocation methodology. Backed by 80 Maryland state lawmakers "
            "(June 17, 2026), the complaint revealed the scale of the problem:", s["body"]),
        bq(
            "Maryland ratepayers face a projected $1.6 billion burden over the next decade from "
            "transmission projects approved in PJM's last three regional transmission expansion "
            "plans — with 'billions more' projected as data center demand exceeds 80,000 MW "
            "over 20 years.",
            s),
        Paragraph(
            "The complaint argues that state-level large-load tariffs alone are insufficient "
            "because PJM's cost allocation spreads data center transmission upgrade costs "
            "across all ratepayers in the zone, not just the data centers that caused them.", s["body"]),

        Paragraph("<b>Exelon Exposure Assessment</b>", s["h2"]),
        Paragraph(
            "Exelon (EXC) operates BGE, Pepco, Delmarva Power, Atlantic City Electric (NJ), "
            "and ComEd (IL) within the PJM footprint. Maryland and New Jersey together "
            "represent Exelon's highest take-or-pay tariff exposure. Unlike AEP Ohio, "
            "the Maryland framework is designed to <i>attract</i> committed data center "
            "load rather than immediately trigger washouts — the 2025/2026 laws are "
            "still being implemented and no queue washout event has been detected.", s["body"]),
        Spacer(1, 4),
        verdict("WATCH", AMBER,
            "Maryland tariff is live but no washout yet detected. "
            "GRP monitoring: BGE and Pepco case filings at Maryland PSC for "
            "large-load queue withdrawal data once tariff standards finalize. "
            "Exelon Q3 2026 earnings call is the next likely disclosure point.",
            AMBER_BG),
        Spacer(1, 14),
    ]

    # ── New Jersey deep-dive ──────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("New Jersey — PSEG (PEG) &amp; FirstEnergy: JCP&L (FE)", s["h1"]),
        Paragraph("Finding: Take-or-pay bill passed June 30, 2026 — pending Governor signature. BPU has 12 months to set standards.", s["h2"]),
        Paragraph(
            "New Jersey's legislature passed a data center tariff bill on June 30, 2026, "
            "sending it to Governor Mikie Sherrill for signature. The bill is widely expected "
            "to be signed — the Governor's office was involved in drafting the final version.", s["body"]),

        Paragraph("<b>Key Take-or-Pay Provisions</b>", s["h2"]),
        Paragraph(
            "• Applies to data centers with ≥<b>50 MW</b> of requested capacity "
            "(earlier draft was 100 MW; lowered via amendment)<br/>"
            "• <b>85% take-or-pay floor</b>: data centers must pay for at least 85% of "
            "contracted capacity whether consumed or not<br/>"
            "• <b>10-year minimum term</b><br/>"
            "• Annual performance reporting obligations<br/>"
            "• Priority curtailment of data centers before residential customers in emergencies<br/>"
            "• New Jersey BPU has <b>12 months from enactment</b> to establish specific "
            "tariff standards",
            s["body"]),

        Paragraph("<b>Utilities Affected</b>", s["h2"]),
        Paragraph(
            "Four utilities serve New Jersey within PJM: PSE&amp;G (PSEG subsidiary, ticker PEG), "
            "Jersey Central Power &amp; Light (JCP&amp;L, FirstEnergy subsidiary, ticker FE), "
            "Atlantic City Electric (Exelon/EXC subsidiary), and Rockland Electric (Orange &amp; "
            "Rockland, Consolidated Edison subsidiary). PSE&amp;G and JCP&amp;L have the largest "
            "exposure to data center load given the concentration of hyperscale facilities in "
            "northern and central New Jersey.", s["body"]),

        Paragraph("<b>Queue Context</b>", s["h2"]),
        Paragraph(
            "As of March 2025, PJM's New Jersey interconnection queue contained "
            "<b>143 GW of pending projects across 79 applications</b> in the state. "
            "Over 95% are renewable and storage projects, but the data center load "
            "interconnections are the high-urgency segment for tariff purposes. "
            "No NJ-specific queue washout has been detected — the tariff standards "
            "have not yet been set.", s["body"]),
        Spacer(1, 4),
        verdict("WATCH", AMBER,
            "NJ bill pending signature — once enacted, BPU has 12 months to finalize tariff. "
            "The 85% floor is stronger than most state frameworks. "
            "GRP flag: a washout event in NJ (PSE&G or JCP&L territory) could materialize "
            "12-24 months after tariff standards are set, mirroring the AEP Ohio pattern.",
            AMBER_BG),
        Spacer(1, 14),
    ]

    # ── Federal layer ─────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Federal Layer: FERC Order 2023 + PJM Tariff Revisions", s["h1"]),
        Paragraph(
            "Cutting across all 13 PJM states is a federal-level financial commitment "
            "framework that functions as a PJM-wide quasi-take-or-pay mechanism:", s["body"]),
        Paragraph(
            "<b>FERC Order No. 2023</b> (July 2023, implemented 2024–2025): "
            "Interconnection queue reforms requiring study deposits of $75,000–$400,000 "
            "per application (10% non-refundable upfront), demonstration of site control, "
            "commercial readiness deposits, and financial withdrawal penalties. "
            "This raised the cost of holding speculative queue positions across all PJM states.", s["body"]),
        Paragraph(
            "<b>PJM February 2026 Compliance Filing</b>: Per FERC's December 2025 direction, "
            "PJM filed new transmission services for co-located data center loads: "
            "Firm Contract Demand Transmission Service and Non-Firm Contract Demand "
            "Transmission Service. These give data centers defined capacity commitments "
            "at the transmission level, creating an implicit take-or-pay structure for "
            "firm service.", s["body"]),
        Paragraph(
            "<b>January 2026 Statement of Principles</b>: All 13 PJM state governors "
            "jointly demanded data centers bear their own infrastructure costs. "
            "This provides political cover for state PSCs to implement aggressive "
            "large-load tariffs without concern about deterring data center investment.", s["body"]),
        Spacer(1, 14),
    ]

    # ── Ticker exposure matrix ────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("Ticker-Level Exposure Matrix", s["h1"]),
    ]

    tickers = [
        ["Ticker", "Company", "PJM States\nExposed", "Take-or-Pay\nExposure", "Signal", "Monitoring Priority"],
        ["AEP",  "American Electric Power",
                 "OH, WV, IN, KY,\nMI (partial)",
                 "Ohio: REALIZED\nwashout (81%)",
                 "NEGATIVE",      "Confirmed — Q3 guidance\nrevision expected"],
        ["EXC",  "Exelon",
                 "MD (BGE, Pepco,\nDelmarva), NJ (ACE),\nIL (ComEd)",
                 "MD: ENACTED\n(25 MW / 60%)\nNJ: PENDING",
                 "WATCH —\nNEGATIVE RISK",  "High — MD tariff live;\nNJ bill pending signature"],
        ["PEG",  "PSEG (Public Service\nEnterprise Group)",
                 "NJ (PSE&G)",
                 "NJ: PENDING\n(85% / 10yr term)",
                 "WATCH —\nNEGATIVE RISK",  "High — 85% floor strongest\nin PJM after NJ enacts"],
        ["FE",   "FirstEnergy",
                 "PA (FE PA), NJ\n(JCP&L), WV\n(Mon Power,\nPotomac Ed)",
                 "PA: OCA advocating\nNJ: PENDING\nWV: None",
                 "NEUTRAL /\nMONITOR",       "Medium — PA + NJ\nexposure; no tariff yet"],
        ["PPL",  "PPL Corporation",
                 "PA (PPL Electric)",
                 "PA: None enacted",
                 "POSITIVE",      "9 GW pipeline active;\nwelcoming load growth"],
        ["D",    "Dominion Energy",
                 "VA",
                 "VA: DER only;\nno utility-scale\nequivalent",
                 "NEUTRAL",       "Needs PJM DOM-zone\nqueue data; not VA SCC"],
        ["DUK",  "Duke Energy",
                 "OH (small),\nKY, NC/TN\n(PJM portion)",
                 "No specific\nframework",
                 "NEUTRAL",       "Low — limited data\ncenter concentration\nin PJM zones"],
        ["CMS",  "Consumers Energy",
                 "MI",
                 "None identified",
                 "NEUTRAL",       "Low"],
        ["DTE",  "DTE Energy",
                 "MI",
                 "None identified",
                 "NEUTRAL",       "Low"],
    ]

    sig_col = {
        "NEGATIVE":           (RED,   RED_BG),
        "WATCH —\nNEGATIVE RISK": (AMBER, AMBER_BG),
        "POSITIVE":           (GREEN, GREEN_BG),
        "NEUTRAL /\nMONITOR": (BLUE,  BLUE_BG),
        "NEUTRAL":            (MID_GREY, LIGHT_BG),
    }

    col_w2 = [0.55*inch, 1.25*inch, 1.15*inch, 1.3*inch, 0.85*inch, 1.4*inch]
    t2 = Table(tickers, colWidths=col_w2, repeatRows=1)
    cmds2 = [
        ("BACKGROUND",    (0,0),(-1,0),  DARK),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTNAME",      (0,1),(0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("GRID",          (0,0),(-1,-1), 0.4, BORDER),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]
    row_signals = {
        1: "NEGATIVE",
        2: "WATCH —\nNEGATIVE RISK",
        3: "WATCH —\nNEGATIVE RISK",
        4: "NEUTRAL /\nMONITOR",
        5: "POSITIVE",
        6: "NEUTRAL",
        7: "NEUTRAL",
        8: "NEUTRAL",
        9: "NEUTRAL",
    }
    for row, sig in row_signals.items():
        fg, bg = sig_col[sig]
        cmds2 += [
            ("BACKGROUND", (0,row),(-1,row), bg),
            ("TEXTCOLOR",  (4,row),(4,row),  fg),
            ("FONTNAME",   (4,row),(4,row),  "Helvetica-Bold"),
        ]
    t2.setStyle(TableStyle(cmds2))
    story += [t2, Spacer(1, 14)]

    # ── What to watch ─────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8),
        Paragraph("GRP Forward Monitoring — Trigger Events to Watch", s["h1"]),
    ]

    triggers = [
        ["Trigger", "State/Utility", "Estimated Window", "Signal Type"],
        ["NJ Governor signs data center tariff bill",
         "NJ / PSEG, JCP&L",
         "July–Aug 2026",
         "POLICY IMPLEMENTATION"],
        ["NJ BPU issues tariff standards (85% / 10yr)",
         "NJ / PSEG, JCP&L",
         "6–12 months post-signing",
         "TARIFF EFFECTIVE DATE"],
        ["NJ queue withdrawal filings (post-tariff)",
         "NJ / PSE&G, JCP&L",
         "12–24 months post-tariff",
         "QUEUE WASHOUT RISK"],
        ["MD PSC finalizes BGE/Pepco large-load tariff",
         "MD / BGE, Pepco (EXC)",
         "Q3–Q4 2026",
         "TARIFF EFFECTIVE DATE"],
        ["MD BGE/Pepco queue withdrawal filings",
         "MD / BGE, Pepco (EXC)",
         "6–18 months post-tariff",
         "QUEUE WASHOUT RISK"],
        ["AEP Q3 2026 earnings — Columbus load guidance revision",
         "OH / AEP",
         "October 2026",
         "EARNINGS CATALYST"],
        ["PA PUC rulemaking on large-load tariff",
         "PA / PPL, FE PA",
         "2026–2027",
         "POLICY RISK (PPL)"],
        ["PJM DOM-zone queue data (Dominion VA exposure)",
         "VA / Dominion (D)",
         "Ongoing",
         "DATA GAP TO FILL"],
    ]

    t3 = Table(triggers, colWidths=[2.2*inch, 1.6*inch, 1.35*inch, 1.35*inch], repeatRows=1)
    t3_cmds = [
        ("BACKGROUND",    (0,0),(-1,0),  DARK),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, LIGHT_BG]),
        ("GRID",          (0,0),(-1,-1), 0.4, BORDER),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TEXTCOLOR",     (3,2),(3,2),   RED),
        ("TEXTCOLOR",     (3,3),(3,3),   RED),
        ("TEXTCOLOR",     (3,5),(3,5),   RED),
        ("TEXTCOLOR",     (3,6),(3,6),   RED),
        ("FONTNAME",      (3,2),(3,3),   "Helvetica-Bold"),
        ("FONTNAME",      (3,5),(3,6),   "Helvetica-Bold"),
    ]
    t3.setStyle(TableStyle(t3_cmds))
    story += [t3, Spacer(1, 14)]

    # ── Footer ────────────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6),
        Paragraph("Primary Sources", s["h2"]),
        Paragraph(
            "• Ohio PUCO Docket EL-2024-00456: AEP system impact study (Columbus queue washout). "
            "Detected by GRP 2026-06-19.", s["footnote"]),
        Paragraph(
            "• Maryland Next Generation Energy Act (2025); Utility RELIEF Act (2026, HB1532). "
            "Maryland PSC Docket (large load tariff rule). "
            "Maryland OPC FERC complaint (May 7, 2026) — $1.6B ratepayer burden figure.", s["footnote"]),
        Paragraph(
            "• New Jersey data center tariff bill, passed June 30, 2026 "
            "(85% take-or-pay / 10yr / ≥50 MW). Pending Governor Sherrill signature.", s["footnote"]),
        Paragraph(
            "• PA PUC Docket M-2025-3054271: En Banc Hearing on Interconnection and "
            "Tariffs for Large Load Customers, April 24, 2025. PPL Electric (9 GW pipeline), "
            "OCA advocacy for take-or-pay.", s["footnote"]),
        Paragraph(
            "• FERC Order No. 2023 (July 2023); PJM compliance filing February 2026. "
            "PJM Statement of Principles — all 13 governors, January 2026.", s["footnote"]),
        Paragraph(
            "• Environment+Energy Leader: '23 states have already decided' on data center "
            "build-out cost allocation (May 2026).", s["footnote"]),
        Paragraph(
            "• VA SCC Docket PUR-2022-00073 (DER interconnection), "
            "Dominion cluster pilot final report October 2025. Retrieved via GRP.", s["footnote"]),
        Spacer(1, 8),
        Paragraph(
            "This memorandum is produced by the Grid Realization Pipeline for informational "
            "research purposes only. It does not constitute investment advice, financial "
            "advice, or a recommendation to buy or sell any security.",
            s["footnote"]),
    ]

    doc.build(story)
    print(f"PDF written to: {OUTPUT}")


if __name__ == "__main__":
    build()
