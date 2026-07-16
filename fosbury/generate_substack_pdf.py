"""Generate the optimized Substack post as a polished PDF with embedded charts."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Preformatted, Table, TableStyle, Flowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

OUTPUT = Path(__file__).parent / "GRP_Substack_Post_1.pdf"

DARK      = colors.HexColor("#111111")
MID       = colors.HexColor("#555555")
LIGHT_BG  = colors.HexColor("#f5f5f3")
BORDER    = colors.HexColor("#dddddd")
ACCENT    = colors.HexColor("#d85a30")
BLUE      = colors.HexColor("#3d7eaa")
GREEN     = colors.HexColor("#2d7a4f")
QUOTE_BG  = colors.HexColor("#f7f7f5")
STAT_BG   = colors.HexColor("#fdf3ef")
STAT_BDR  = colors.HexColor("#f09575")

W = letter[0] - 2 * inch


def styles():
    b = getSampleStyleSheet()
    return {
        "h1":     ParagraphStyle("h1",     fontName="Helvetica-Bold",   fontSize=22, leading=28, textColor=DARK,  spaceAfter=4),
        "h1b":    ParagraphStyle("h1b",    fontName="Helvetica-Bold",   fontSize=18, leading=24, textColor=DARK,  spaceAfter=10),
        "byline": ParagraphStyle("byline", fontName="Helvetica-Oblique",fontSize=10, leading=14, textColor=MID,   spaceAfter=4),
        "deck":   ParagraphStyle("deck",   fontName="Helvetica-Bold",   fontSize=11, leading=16, textColor=DARK,
                                 backColor=STAT_BG, borderPadding=(8,12,8,12), spaceAfter=12),
        "h2":     ParagraphStyle("h2",     fontName="Helvetica-Bold",   fontSize=14, leading=18, textColor=DARK,  spaceBefore=18, spaceAfter=5),
        "h3":     ParagraphStyle("h3",     fontName="Helvetica-Bold",   fontSize=11, leading=15, textColor=DARK,  spaceBefore=12, spaceAfter=4),
        "body":   ParagraphStyle("body",   fontName="Helvetica",        fontSize=10.5, leading=16, textColor=DARK, spaceAfter=7),
        "bq":     ParagraphStyle("bq",     fontName="Helvetica-Oblique",fontSize=10, leading=15, textColor=colors.HexColor("#333333"),
                                 leftIndent=20, rightIndent=20, spaceAfter=4, backColor=QUOTE_BG, borderPadding=(8,12,8,12)),
        "bq_src": ParagraphStyle("bq_src", fontName="Helvetica",        fontSize=8.5, leading=12, textColor=MID, leftIndent=20, spaceAfter=8),
        "code_lbl": ParagraphStyle("code_lbl", fontName="Helvetica-Bold", fontSize=8.5, textColor=MID, spaceBefore=10, spaceAfter=2),
        "code":   ParagraphStyle("code",   fontName="Courier",          fontSize=8,  leading=12, textColor=colors.HexColor("#1a1a1a"),
                                 backColor=LIGHT_BG, leftIndent=12, rightIndent=12, spaceAfter=10, borderPadding=(8,10,8,10)),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica",        fontSize=10.5, leading=15, textColor=DARK, leftIndent=14, spaceAfter=5),
        "cap":    ParagraphStyle("cap",    fontName="Helvetica",        fontSize=8,  leading=11, textColor=MID,   spaceAfter=4),
        "fn":     ParagraphStyle("fn",     fontName="Helvetica-Oblique",fontSize=8,  leading=11, textColor=MID,   spaceAfter=2),
        "link":   ParagraphStyle("link",   fontName="Helvetica-Bold",   fontSize=10.5, leading=14, textColor=colors.HexColor("#1a5276"), spaceAfter=8),
        "stat_n": ParagraphStyle("stat_n", fontName="Helvetica-Bold",   fontSize=26, leading=30, textColor=ACCENT, alignment=TA_CENTER),
        "stat_l": ParagraphStyle("stat_l", fontName="Helvetica",        fontSize=9,  leading=12, textColor=MID,   alignment=TA_CENTER),
    }


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=6, spaceAfter=10)

def accenthr():
    return HRFlowable(width="100%", thickness=2, color=ACCENT, spaceBefore=2, spaceAfter=14)


class QueueBarChart(Flowable):
    def __init__(self, width, height):
        Flowable.__init__(self)
        self.width  = width
        self.height = height

    def draw(self):
        c = self.canv
        lm, bm = 68, 28
        ch = self.height - bm - 24
        cw = self.width  - lm - 16
        total = 30000
        bar_w = cw * 0.20
        gap   = cw * 0.14
        scale = ch / total

        for mw, label in [(0,"0"), (10000,"10K"), (20000,"20K"), (30000,"30K MW")]:
            y = bm + mw * scale
            c.setStrokeColor(colors.HexColor("#e8e8e8"))
            c.setLineWidth(0.5)
            c.line(lm, y, self.width - 8, y)
            c.setFont("Helvetica", 7)
            c.setFillColor(MID)
            c.drawRightString(lm - 4, y - 3, label)

        x1 = lm + gap
        c.setFillColor(ACCENT)
        c.rect(x1, bm + 5700 * scale, bar_w, 24300 * scale, fill=1, stroke=0)
        c.setFillColor(BLUE)
        c.rect(x1, bm, bar_w, 5700 * scale, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x1 + bar_w/2, bm + 5700*scale + 24300*scale*0.44, "24,300 MW")
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(x1 + bar_w/2, bm + 5700*scale*0.38, "5,700 MW")
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x1 + bar_w/2, bm + total*scale + 7, "-81%")

        x2 = x1 + bar_w + gap * 1.5
        c.setFillColor(BLUE)
        c.rect(x2, bm, bar_w, 5700 * scale, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x2 + bar_w/2, bm + 5700*scale*0.38, "5,700 MW")
        c.setFillColor(BLUE)
        c.setFont("Helvetica", 8)
        c.drawCentredString(x2 + bar_w/2, bm + 5700*scale + 5, "bankable")

        c.setFillColor(DARK)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x1 + bar_w/2, bm - 14, "Before tariff")
        c.drawCentredString(x2 + bar_w/2, bm - 14, "After tariff")

        lx = self.width - 155
        ly = self.height - 14
        c.setFillColor(ACCENT)
        c.rect(lx, ly, 8, 8, fill=1, stroke=0)
        c.setFillColor(MID); c.setFont("Helvetica", 7.5)
        c.drawString(lx+12, ly+1, "Withdrew after tariff")
        c.setFillColor(BLUE)
        c.rect(lx, ly-13, 8, 8, fill=1, stroke=0)
        c.setFillColor(MID)
        c.drawString(lx+12, ly-12, "Bankable demand (stayed)")


class PJMStateGrid(Flowable):
    STATES = [
        ("Ohio",              "$AEP",       "COLLAPSED",           ACCENT,                    colors.HexColor("#fcebeb")),
        ("Maryland",          "$EXC",       "ENACTED",             colors.HexColor("#b7770d"), colors.HexColor("#fdf3dc")),
        ("New Jersey",        "$PEG / $FE", "PASSED LEGISLATURE",  colors.HexColor("#b7770d"), colors.HexColor("#fdf3dc")),
        ("Pennsylvania",      "$PPL",       "NOT YET",             MID,                       LIGHT_BG),
        ("Virginia",          "$D",         "NOT YET",             MID,                       LIGHT_BG),
        ("IL/IN/MI/WV + more","PJM others", "NOT YET",             MID,                       LIGHT_BG),
    ]

    def __init__(self, width, height):
        Flowable.__init__(self)
        self.width  = width
        self.height = height

    def draw(self):
        c = self.canv
        cols  = 3
        col_w = (self.width - 12) / cols
        row_h = (self.height - 16) / 2

        for idx, (state, ticker, status, sc, bg) in enumerate(self.STATES):
            col = idx % cols
            row = idx // cols
            x = col * col_w + 6
            y = self.height - 16 - (row + 1) * row_h + 5
            bh = row_h - 8

            c.setFillColor(bg)
            c.setStrokeColor(sc)
            c.setLineWidth(0.6)
            c.roundRect(x, y, col_w - 8, bh, 4, fill=1, stroke=1)

            c.setFillColor(sc)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(x+8, y+bh-16, status)

            c.setFillColor(DARK)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(x+8, y+bh-28, state)

            c.setFillColor(sc)
            c.setFont("Helvetica", 8)
            c.drawString(x+8, y+8, ticker)

        c.setFillColor(MID)
        c.setFont("Helvetica-Oblique", 7)
        c.drawString(6, 2, "All 13 PJM governors signed a joint Statement of Principles, Jan 2026: data centers pay for their own grid upgrades.")


def build():
    s = styles()
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter,
        leftMargin=inch, rightMargin=inch,
        topMargin=inch, bottomMargin=inch,
        title="81% of AEP's Data Center Backlog Just Evaporated",
        author="Luke Jafarieh",
    )
    story = []

    story += [
        Paragraph("81% of AEP's Data Center Backlog", s["h1"]),
        Paragraph("Just Evaporated. My Bot Found It First.", s["h1b"]),
        Spacer(1, 4),
        Paragraph("By Luke Jafarieh — Grid Realization Pipeline", s["byline"]),
        Spacer(1, 2),
        accenthr(),
        Paragraph(
            "<b>In short:</b> A public regulatory filing revealed that 24,300 MW of data center demand "
            "behind AEP's Ohio grid quietly withdrew after a new tariff forced developers to put money down. "
            "The queue went from 30,000 MW to 5,700 MW overnight. Wall Street still hasn't connected the dots.",
            s["deck"]),
        Spacer(1, 6),
        Paragraph("Three weeks ago, a filing hit the Ohio public utility commission docket. Nobody was reading it.", s["body"]),
        Paragraph("My pipeline was.", s["body"]),
        Paragraph("It flagged the document at 2:47 AM. By morning I had read it twice.", s["body"]),
        hr(),
    ]

    story += [
        Paragraph("The Finding", s["h2"]),
        Paragraph("Here is the exact language from the filing, verbatim:", s["body"]),
        Paragraph(
            "<i>\"The Columbus data center interconnection cluster has withdrawn 24,300 MW of uncommitted "
            "capacity requests following implementation of the take-or-pay tariff. Expected commercial "
            "operation dates have been extended by an average of 14 months across the affected queue "
            "positions. AEP projects that confirmed contracted load has declined from 30,000 MW to "
            "5,700 MW of bankable demand.\"</i>",
            s["bq"]),
        Paragraph("-- American Electric Power, Ohio PUC System Impact Study Update", s["bq_src"]),
        Paragraph(
            "AEP had 30,000 megawatts of data centers in line to connect to its Ohio grid. When regulators "
            "forced those developers to financially commit -- pay a deposit or give up their spot -- "
            "<b>81% of them walked.</b> The 30,000 MW of demand AEP has been telling investors about? "
            "The real number is 5,700 MW.",
            s["body"]),
    ]

    stat_data = [
        [Paragraph("30,000 MW", s["stat_n"]), Paragraph("5,700 MW", s["stat_n"]), Paragraph("-81%", s["stat_n"])],
        [Paragraph("Queue before tariff", s["stat_l"]), Paragraph("Bankable demand after", s["stat_l"]), Paragraph("Withdrew overnight", s["stat_l"])],
    ]
    st = Table(stat_data, colWidths=[W/3]*3, rowHeights=[38, 16])
    st.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), STAT_BG),
        ("BOX",           (0,0), (-1,-1), 0.5, STAT_BDR),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, STAT_BDR),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story += [Spacer(1,8), st, Spacer(1,10)]

    chart = QueueBarChart(W, 155)
    story += [chart, Paragraph("AEP Ohio -- Columbus data center interconnection queue before and after take-or-pay tariff.", s["cap"]), hr()]

    story += [
        Paragraph("Why This Gets More Dangerous From Here", s["h2"]),
        Paragraph(
            "This is not an AEP-specific problem. The tariff that triggered Ohio's collapse is spreading "
            "across the entire PJM grid -- 13 states, 65 million people, the electricity backbone of the "
            "Mid-Atlantic and Midwest.",
            s["body"]),
        Paragraph("<b>The policy timeline:</b>", s["body"]),
        Paragraph("<b>Ohio (done):</b> AEP implements take-or-pay. 81% of the Columbus queue withdraws.", s["bullet"]),
        Paragraph(
            "<b>Maryland (enacted 2025-2026):</b> Two laws passed forcing BGE, Pepco, and Delmarva (all "
            "Exelon, $EXC) to create take-or-pay tariffs for loads over 25 MW. Maryland's ratepayer advocate "
            "is in federal court over $1.6 billion in grid upgrades built for data centers that may not show up.",
            s["bullet"]),
        Paragraph(
            "<b>New Jersey (passed June 30, 2026):</b> 85% commitment required, 10-year term, projects over "
            "50 MW. Pending Governor Sherrill. PSE&amp;G ($PEG) and JCP&amp;L ($FE) exposed.",
            s["bullet"]),
        Paragraph(
            "<b>All 13 PJM governors:</b> Joint Statement of Principles, January 2026. Data centers pay for "
            "their own grid upgrades. Full stop.",
            s["bullet"]),
        Spacer(1, 8),
    ]

    grid = PJMStateGrid(W, 175)
    story += [grid, Paragraph("PJM interconnection -- take-or-pay tariff status across 13 member states.", s["cap"]), hr()]

    story += [Paragraph("The Specific Stocks to Watch", s["h2"])]
    ticker_rows = [
        ["Utility", "Ticker", "Signal"],
        ["American Electric Power (Ohio)", "$AEP", "Negative. Queue collapsed 81%. Watch Q3 guidance."],
        ["Exelon BGE/Pepco/Delmarva (Maryland)", "$EXC", "Caution. Tariff enacted. Queue data not yet public."],
        ["PSEG / PSE&G (New Jersey)", "$PEG", "Watch. Tariff standards set within 12 months of signature."],
        ["FirstEnergy / JCP&L (New Jersey)", "$FE", "Watch. Same NJ exposure as PEG."],
        ["PPL Electric (Pennsylvania)", "$PPL", "Positive for now. 9 GW pipeline, no tariff yet."],
    ]
    def tcell(t, bold=False):
        return Paragraph(t, ParagraphStyle("tc", fontName="Helvetica-Bold" if bold else "Helvetica",
                                           fontSize=8.5, leading=12, textColor=DARK))
    tt = Table(
        [[tcell(c, i==0) for c in row] for i, row in enumerate(ticker_rows)],
        colWidths=[W*0.38, W*0.12, W*0.50],
    )
    tt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  LIGHT_BG),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story += [tt, hr()]

    story += [
        Paragraph("The Information Gap Is the Point", s["h2"]),
        Paragraph(
            "The filing was publicly available the morning it was submitted. It sat in a government portal, "
            "in a docket, behind search filters most people don't know how to navigate.",
            s["body"]),
    ]
    lag_rows = [
        ["Step", "What happens",              "Who knows"],
        ["1",    "Filing hits Ohio PUC docket","GRP flags it at 2:47 AM"],
        ["2",    "Regulatory analysts read it","Days to weeks later"],
        ["3",    "Sell-side picks it up",      "Weeks later, if at all"],
        ["4",    "Management addresses it",    "Next earnings call"],
        ["5",    "Consensus estimates revise", "Months after the filing"],
    ]
    lt = Table(
        [[tcell(c, i==0) for c in row] for i, row in enumerate(lag_rows)],
        colWidths=[W*0.08, W*0.44, W*0.48],
    )
    lt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  LIGHT_BG),
        ("BACKGROUND",    (0,1), (-1,1),  colors.HexColor("#eaf3de")),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story += [lt, Spacer(1,6),
              Paragraph("Grid data is informationally rich and operationally inaccessible. That gap is the edge.", s["body"]),
              hr()]

    story += [
        Paragraph("What I Built (and How It Found This)", s["h2"]),
        Paragraph(
            "GRP is a Python ETL pipeline I built from scratch. It hits regulatory APIs on a schedule, "
            "extracts PDFs, scans for keywords, and runs Z-score anomaly detection on live EIA demand data. "
            "The Ohio filing matched five signal keywords: <i>take-or-pay, queue withdrawal, bankable demand, "
            "commercial operation date, cost allocation.</i>",
            s["body"]),
        Paragraph(
            "I'm a student. I taught myself Python building this, using Claude as a coding partner. "
            "No formal CS background -- just a thesis and enough stubbornness to see it through.",
            s["body"]),
        Paragraph("Four standalone scripts: github.com/ljafarieh/grp-public", s["link"]),
        Paragraph("The core loop:", s["code_lbl"]),
        Preformatted(
            "demand  = pull_hourly_demand(ba_code=\"AEP\", days_back=30)\n"
            "spikes  = detect_anomalies(demand)          # 2.0σ over 168-hr window\n"
            "docs    = get_new_documents(participant=\"American Electric Power\")\n"
            "for doc in docs:\n"
            "    result = scan_pdf_url(doc[\"pdf_url\"])\n"
            "    if result.has_signal:                   # 5+ keywords → flag\n"
            "        alert(doc, result)",
            s["code"]),
        hr(),
        Paragraph("What I'm Watching Next", s["h2"]),
        Paragraph("<b>Maryland BGE/Pepco dockets</b> -- tariff is enacted. When does the queue move?", s["bullet"]),
        Paragraph(
            "<b>New Jersey BPU</b> -- once Sherrill signs, tariff standards set within 12 months. "
            "First filings from PSE&amp;G and JCP&amp;L will be the tell.", s["bullet"]),
        Paragraph(
            "<b>AEP Q3 2026 earnings</b> -- does management revise data center load guidance? "
            "That's when this filing becomes a market event for retail investors.", s["bullet"]),
        Paragraph(
            "<b>Pennsylvania</b> -- PPL has 9 GW of pipeline. No take-or-pay yet. "
            "Ohio's 30,000 MW looked real too.", s["bullet"]),
        Spacer(1, 14),
        hr(),
        Paragraph(
            "The grid is the biggest infrastructure story of the decade. "
            "It plays out in documents nobody reads. I'm trying to change that.",
            s["body"]),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=4, spaceAfter=8),
        Paragraph(
            "Not financial advice. All sources fully public: Ohio PUCO, Maryland PSC, NJ BPU, VA SCC, FERC eLibrary, EIA Open Data.",
            s["fn"]),
    ]

    doc.build(story)
    print(f"PDF written -> {OUTPUT}")


if __name__ == "__main__":
    build()
