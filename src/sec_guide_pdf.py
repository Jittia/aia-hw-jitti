"""SEC Filings Quick Reference → output/sec_filings_guide.pdf (round 30, 2026-11-05).

A 4-page guide to the main SEC filings (10-K, 10-Q, 8-K, proxy, Form 4, 13D/G, 13F, S-1, 20-F) and how to use them
for moat research. Deadlines and 8-K item names were checked against the SEC form instructions listed in Sources.
Run: .venv/bin/python src/sec_guide_pdf.py   (needs reportlab)
"""
import sys
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = sys.argv[1] if len(sys.argv) > 1 else "output/sec_filings_guide.pdf"
INK = colors.HexColor("#1d2733")
MUTED = colors.HexColor("#5b6675")
ACCENT = colors.HexColor("#1f4e79")
RULE = colors.HexColor("#c9d1db")
HEAD_BG = colors.HexColor("#e8eef5")
NOTE_BG = colors.HexColor("#f4f6f9")

base = dict(fontName="Helvetica", alignment=TA_LEFT)
ParagraphStyle.defaults["textColor"] = INK
S = {
    "title": ParagraphStyle("title", **{**base, "fontName": "Helvetica-Bold"}, fontSize=22, leading=27, textColor=ACCENT),
    "sub": ParagraphStyle("sub", **base, fontSize=11, leading=15, textColor=MUTED),
    "h1": ParagraphStyle("h1", **{**base, "fontName": "Helvetica-Bold"}, fontSize=14, leading=18, textColor=ACCENT,
                         spaceBefore=14, spaceAfter=6, keepWithNext=1),
    "h2": ParagraphStyle("h2", **{**base, "fontName": "Helvetica-Bold"}, fontSize=11, leading=14, spaceBefore=10,
                         spaceAfter=4),
    "body": ParagraphStyle("body", **base, fontSize=9.5, leading=13.5, spaceAfter=5),
    "cell": ParagraphStyle("cell", **base, fontSize=8.5, leading=11),
    "cellb": ParagraphStyle("cellb", **{**base, "fontName": "Helvetica-Bold"}, fontSize=8.5, leading=11),
    "th": ParagraphStyle("th", **{**base, "fontName": "Helvetica-Bold"}, fontSize=8.5, leading=11, textColor=ACCENT),
    "note": ParagraphStyle("note", **base, fontSize=8.5, leading=12, textColor=MUTED),
    "bullet": ParagraphStyle("bullet", **base, fontSize=9.5, leading=13.5, leftIndent=14, bulletIndent=4,
                             spaceAfter=2),
    "src": ParagraphStyle("src", **base, fontSize=8, leading=11, textColor=MUTED, spaceAfter=3),
}
W = letter[0] - 1.5 * inch


def P(t, s="body"):
    return Paragraph(t, S[s])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def table(head, rows, widths, bold_first=True):
    data = [[P(h, "th") for h in head]]
    for r in rows:
        data.append([P(c, "cellb" if (i == 0 and bold_first) else "cell") for i, c in enumerate(r)])
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def note(text):
    t = Table([[P(text, "note")]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NOTE_BG), ("LINEBEFORE", (0, 0), (0, -1), 2, ACCENT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def page_frame(c, doc):
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawString(0.75 * inch, 0.5 * inch, "SEC Filings Quick Reference  |  Moat Momentum (Jitti, AI Investor Alpha)  |  "
                 "Prepared 2026-11-05  |  Education only, not investment advice")
    c.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    c.restoreState()


story = []
story += [P("SEC Filings Quick Reference", "title"), Spacer(1, 4),
          P("What each main US company filing is for, what it contains, and how to use it to judge a company's "
            "moat, its history and its outlook.", "sub"), Spacer(1, 10)]
story.append(note("All filings are free on SEC EDGAR (sec.gov/edgar/search). Deadlines below are the general rules from "
                  "the SEC's own form instructions and Investor.gov, checked 2026-11-05; see Sources on the last page. "
                  "This guide explains documents; it does not recommend any security."))

story.append(P("1. The filings at a glance", "h1"))
story.append(table(
    ["Filing", "What it is", "When it is filed", "Audited?", "Most useful for"],
    [["10-K", "Annual report: the full picture of the business, its risks, management's discussion and complete "
      "financial statements", "60 days after year end (large accelerated filers), 75 days (accelerated), 90 days "
      "(others)", "Yes", "Moat, long-term history, risks"],
     ["10-Q", "Quarterly report: financial statements, management's discussion, changes in risk factors",
      "For each of the first 3 quarters: 40 days (large accelerated and accelerated), 45 days (others)",
      "No (reviewed)", "Recent trend, early warnings"],
     ["8-K", "Current report: one major event, filed as it happens", "Generally within 4 business days of the "
      "event", "No", "News, results, guidance, management changes"],
     ["DEF 14A", "Proxy statement: notice of the shareholder meeting, executive pay, board, items to vote on",
      "Before the annual meeting", "No", "Management incentives, governance"],
     ["Form 4", "Insider (officer, director, over-10% holder) buys and sells", "Within 2 business days of the "
      "trade", "No", "Insider behaviour"],
     ["13D / 13G", "A person or group now owns more than 5%. 13D = may seek change (activist); 13G = shorter form "
      "for passive holders", "13D: within 5 days of the purchase", "No", "Who is accumulating shares"],
     ["13F", "Quarterly list of US stock holdings of managers with at least $100 million", "Within 45 days of "
      "quarter end", "No", "What large funds own"],
     ["S-1 / 424B", "Registration statement and prospectus for an IPO or new offering", "Before the offering",
      "Yes (accounts)", "The deepest one-time business description"],
     ["20-F / 6-K", "Foreign private issuers' annual report and current report (similar to 10-K and 8-K)",
      "20-F: within 4 months of year end", "20-F: yes", "Non-US companies (often IFRS)"],
     ["10-K/A, 10-Q/A", "Amendment correcting or adding to an earlier report", "As needed", "Depends",
      "Restatements, missing Part III"]],
    [0.11, 0.32, 0.24, 0.12, 0.21]))

story.append(PageBreak())
story.append(P("2. Inside the 10-K (annual report)", "h1"))
story.append(P("The single most important document. Read the same sections across several years: what changes "
               "tells you as much as what is written."))
story.append(table(
    ["Section", "What it covers", "What to look for"],
    [["Item 1 Business", "Products, customers, markets, competitors, patents, regulation, employees",
      "How the company says it wins; customer concentration; named competitors"],
     ["Item 1A Risk Factors", "Material risks as management sees them",
      "New risks year over year (new competitor, pricing pressure, key customer loss)"],
     ["Item 1C Cybersecurity", "How cyber risk is managed and governed", "Weak oversight in data-heavy businesses"],
     ["Item 3 Legal Proceedings", "Material lawsuits and investigations", "Cases that threaten a core product or patent"],
     ["Item 5 Market for Equity", "Share data, dividends, buybacks", "How capital is returned to owners"],
     ["Item 7 MD&amp;A", "Management explains results, trends, liquidity, outlook factors",
      "Drivers of growth and margin; whether explanations keep changing"],
     ["Item 7A Market Risk", "Interest-rate, currency and commodity exposure", "Sensitivity of profits to factors "
      "outside management's control"],
     ["Item 8 Financial Statements", "Audited income statement, balance sheet, cash flows, notes, auditor's report",
      "Return on capital, margins, cash conversion; notes on revenue, debt, leases, segments"],
     ["Item 9A Controls", "Effectiveness of internal control over financial reporting",
      "Any material weakness is a red flag"],
     ["Part III (Items 10-14)", "Directors, executive pay, ownership, related parties, auditor fees",
      "Often 'incorporated by reference' from the proxy (DEF 14A)"]],
    [0.22, 0.38, 0.40]))

story.append(P("Inside the 10-Q (quarterly report)", "h2"))
story.append(table(
    ["Section", "What it covers"],
    [["Part I, Item 1", "Unaudited financial statements for the quarter and year to date"],
     ["Part I, Item 2 MD&amp;A", "Quarter's results and trends; liquidity"],
     ["Part I, Items 3-4", "Market risk; controls and procedures"],
     ["Part II, Item 1A", "Only changes to the risk factors since the 10-K: worth reading every time"],
     ["Part II, Item 2", "Share buybacks during the quarter"]],
    [0.25, 0.75]))

story.append(P("3. 8-K items worth knowing", "h1"))
story.append(P("Every 8-K lists its item numbers on the cover and in EDGAR, so you can scan them without opening "
               "the document. Item names below are from the SEC's Form 8-K."))
story.append(table(
    ["Item", "Event", "Why it matters"],
    [["1.01 / 1.02", "Material agreement entered into / terminated", "Big contracts, partnerships, credit lines"],
     ["1.03", "Bankruptcy or receivership", "Severe distress"],
     ["1.05", "Material cybersecurity incident", "Operational and reputational damage"],
     ["2.01", "Acquisition or disposal of assets completed", "Changes what the business is"],
     ["2.02", "Results of operations (earnings release, usually Exhibit 99.1)", "First look at results; "
      "often includes guidance"],
     ["2.03", "New direct financial obligation", "New debt"],
     ["2.05 / 2.06", "Exit or disposal costs / material impairment", "Restructuring; write-downs of past investments"],
     ["3.01", "Delisting notice or failure of a listing rule", "Exchange compliance problem"],
     ["4.01", "Change of auditor", "Ask why"],
     ["4.02", "Earlier financial statements can no longer be relied on", "Restatement: a serious red flag"],
     ["5.01", "Change in control", "Takeover or new controlling holder"],
     ["5.02", "Directors or officers leave or are appointed; pay arrangements", "CEO or CFO turnover"],
     ["5.07", "Shareholder vote results", "Support for pay and board"],
     ["7.01 / 8.01", "Regulation FD disclosure / other events", "Investor presentations, other news"],
     ["9.01", "Financial statements and exhibits", "The attached documents"]],
    [0.14, 0.46, 0.40]))

story.append(P("4. Using filings for investment research", "h1"))
story.append(P("Three questions, and where the evidence is."))
story.append(table(
    ["Question", "Best sources", "Evidence for", "Warning signs"],
    [["Is there a moat?", "10-K Items 1, 1A, 7, 8; S-1 for newer companies",
      "Return on invested capital well above the cost of capital for many years; stable or rising gross margin "
      "(pricing power); recurring revenue and retention; leading share; patents, network effects, switching "
      "costs, scale, licences described concretely",
      "Margins falling while revenue grows; new competition named in Risk Factors; dependence on a few customers"],
     ["What happened before?", "Several years of 10-Ks and 10-Qs; 8-K items 2.01, 2.06, 4.01, 4.02, 5.02",
      "Steady growth funded by cash flow; acquisitions that earned their cost; consistent explanations in MD&amp;A",
      "Restatements; write-downs after acquisitions; frequent CEO or CFO changes; auditor changes; material weakness"],
     ["What lies ahead?", "8-K item 2.02 (guidance); 10-K MD&amp;A; notes on remaining performance obligations "
      "(contracted future revenue); DEF 14A; Form 4",
      "Growing contracted backlog; planned investment with a clear return; executive pay tied to return on "
      "capital or per-share value; insider buying",
      "Guidance cut; pay tied only to size (revenue, adjusted EBITDA); heavy insider selling; rising debt for buybacks"]],
    [0.14, 0.24, 0.33, 0.29]))
story.append(Spacer(1, 6))
story.append(note("Filings mostly describe the past. Guidance and plans are management's own statements: unaudited, "
                  "carrying legal cautions, and sometimes wrong. Earnings-call transcripts are usually not filed with "
                  "the SEC. Treat forward-looking statements as hypotheses to test against later filings."))

story.append(P("5. A reading order for a new company", "h1"))
story += bullets([
    "<b>Latest 10-K, Item 1:</b> what the company sells, to whom, and how it says it wins.",
    "<b>Item 8 over 5-10 years:</b> revenue growth, gross and operating margin, return on capital, free cash flow, debt.",
    "<b>Item 1A, compared with 2-3 years ago:</b> which risks are new or reworded.",
    "<b>Item 7 MD&amp;A:</b> do management's explanations match the numbers?",
    "<b>Latest 10-Qs:</b> is the trend holding? Read Part II Item 1A for changed risks.",
    "<b>8-Ks since the last 10-K:</b> scan item numbers; open 2.02 (results), 4.02, 5.02, 2.06 first.",
    "<b>DEF 14A:</b> how executives are paid, and on which measures.",
    "<b>Form 4 and 13D/13G:</b> what insiders and large holders are doing.",
])

story.append(KeepTogether([P("6. How the Moat Momentum dashboard uses filings today", "h1"), table(
    ["Filing", "Used today", "Not used yet"],
    [["10-K / 10-Q", "All numbers (XBRL values as filed, point in time) and page numbers in the Excel calculation "
      "sheet; Item 1 description in the Deep-Dive", "Risk Factors, MD&amp;A text"],
     ["8-K", "Filing list only; item numbers 1.03 and 5.01 in the back-test of earlier versions; latest 8-K link "
      "saved in the data", "Content of events and press releases; the saved link is not shown on the page"],
     ["DEF 14A, Form 4, 13D/G, 13F", "Not used", "Executive pay, insider and holder activity"]],
    [0.20, 0.48, 0.32])]))

story.append(P("Sources (accessed 2026-11-05)", "h1"))
for s in [
    "SEC, Form 10-K and General Instructions (filing deadlines 60/75/90 days): https://www.sec.gov/files/form10-k.pdf",
    "SEC, Form 10-Q and General Instructions (40/45 days): https://www.sec.gov/files/form10-q.pdf",
    "SEC, Form 8-K and General Instructions (item list; four business days): https://www.sec.gov/files/form8-k.pdf",
    "SEC, Form 13F instructions (USD 100 million; 45 days): https://www.sec.gov/files/form13f.pdf",
    "SEC, Form 20-F General Instructions (four months): https://www.sec.gov/files/form20-f.pdf",
    "SEC, Forms 3, 4 and 5 investor bulletin (Form 4 within two business days): https://www.sec.gov/files/forms-3-4-5.pdf",
    "Investor.gov, Form 10-K: https://www.investor.gov/introduction-investing/investing-basics/glossary/form-10-k",
    "Investor.gov, Form 10-Q: https://www.investor.gov/introduction-investing/investing-basics/glossary/form-10-q",
    "Investor.gov, Form 8-K: https://www.investor.gov/introduction-investing/investing-basics/glossary/form-8-k",
    "Investor.gov, Proxy Statements: https://www.investor.gov/introduction-investing/investing-basics/glossary/proxy-statements",
    "Investor.gov, Schedules 13D and 13G (13D within five days): "
    "https://www.investor.gov/introduction-investing/investing-basics/glossary/schedules-13d-and-13g",
    "Investor.gov, Registration Statement (Form S-1): "
    "https://www.investor.gov/introduction-investing/investing-basics/glossary/registration-statement",
    "SEC EDGAR full-text and company search: https://www.sec.gov/edgar/search/",
]:
    story.append(P(s, "src"))

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                        topMargin=0.7 * inch, bottomMargin=0.8 * inch, title="SEC Filings Quick Reference",
                        author="Jitti (Moat Momentum)", subject="Guide to SEC filings for moat research")
doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
print("wrote", OUT)
