"""Moat Momentum · Google Sheet data, one CSV per tab in output/sheet/.

Each data tab in the Sheet is =IMPORTDATA(<raw GitHub URL of its CSV>), so the Sheet refreshes itself after every
push and nothing has to be copied cell by cell. Settings, Scenarios and Read me are typed in the Sheet; the
Moat Score and risk-gate results are Sheet formulas that read weights and thresholds from Settings.

Run:  .venv/bin/python src/mm_sheet_payload.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "sheet"
RULES = [("interest_cover", "below"), ("net_debt_ebitda", "above"), ("altman_z", "below"), ("beneish_m", "above"),
         ("dilution", "above"), ("sbc_revenue", "above"), ("goodwill_jump", "above")]


def load(name: str, var: str) -> dict:
    s = (ROOT / "output" / "data" / name).read_text(encoding="utf-8")
    return json.loads(s[len(f"window.{var} = "):s.rindex(";")])


def sec_url(cik: int, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{accn}-index.htm"


def r(v, d=1):
    return "" if v is None else round(v, d)


def main() -> None:
    M, D = load("site_data.js", "MM"), load("deep_data.js", "MM_DEEP")
    meta = M["meta"]
    themes = [t["key"] for t in meta["themes"]]
    imp_rank = meta["settings"]["scoring"]["improving_rank"]
    comp = sorted(M["companies"], key=lambda c: c["rank"])
    sl = [c for c in comp if c["shortlist"]]
    status = lambda c: "Shortlist" if c["shortlist"] else "Removed" if c["removed"] else "Strengthening" if c["strengthening"] else ""  # noqa: E731
    tabs = {}

    tabs["universe"] = [["Rank", "Ticker", "Company", "Industry (SIC)", "Peer group", "Period scored", "Revenue ($M)",
                         "Moat Score", "Themes improving", "Status", "Risk flags", "Data confidence", "Top reason", "Filing used (10-K or 10-Q)",
                         "Market value ($M)", "Clean P/E (12 months)", "Compounder Signal (experimental)", "Candidate rank"]]
    for c in comp:
        tabs["universe"].append([int(c["rank"]), c["ticker"], c["name"], c["sic_desc"], c["group"], c.get("period", c["fy"]),
                                 round(c["revenue"] / 1e6), r(c["moat_score"]),
                                 sum(1 for t in themes if (c["improving"][t] or 0) >= imp_rank), status(c), c["flags"],
                                 c["confidence"], c["reasons"][0] if c["reasons"] else "", sec_url(c["cik"], c["accn"]),
                                 round(c["mcap"] / 1e6) if c.get("mcap") else "", r(c.get("pe")) if c.get("pe") else "",
                                 r(c.get("cs")) if c.get("cs") is not None else "", int(c["cs_rank"]) if c.get("cs_rank") else ""])

    tabs["moatmap"] = [["Ticker", "Company", "Industry (SIC)", "Quadrant", "3-yr revenue growth", "ROIC minus 9%",
                        "Distance moved (1 yr)", "R1 entered", "R2 moving toward", "R3 not priced in", "EV/Sales",
                        "EV/clean EBIT", "Clean P/E", "FCF yield", "Implied growth", "Expectation Gap", "Market value ($M)",
                        "Backlog vs revenue growth", "Deferred revenue vs revenue growth", "R&D / revenue", "Capex / revenue"]]
    for c in comp:
        m = c.get("mm")
        if not m or m.get("x") is None:
            continue
        f = lambda k, d=3: round(m[k], d) if m.get(k) is not None else ""  # noqa: E731
        tabs["moatmap"].append([c["ticker"], c["name"], c["sic_desc"], m["quad"] or "", f("x"), f("y"), f("moved"),
                                "yes" if m["r1"] else "", "yes" if m["r2"] else "", "yes" if m["r3"] else "",
                                f("ev_sales", 2), f("ev_ebit", 1), f("pe", 1), f("fcf_yield"), f("g_implied"), f("gap"),
                                round(m["mcap"] / 1e6) if m.get("mcap") else "", f("backlog_g"), f("defrev_g"),
                                f("rnd_int"), f("capex_int")])
    kept = meta["compounder"]["kept"]
    tabs["compounder"] = [["Candidate rank", "Ticker", "Company", "Industry (SIC)", "Compounder Signal", "Market value ($M)",
                           "Clean P/E (12 months)", "Moat Score", "On Moat shortlist"] + [k["label"] + " (rank)" for k in kept]]
    for c in sorted([c for c in comp if c.get("cs_short")], key=lambda c: c["cs_rank"]):
        tabs["compounder"].append([int(c["cs_rank"]), c["ticker"], c["name"], c["sic_desc"], r(c["cs"]),
                                   round(c["mcap"] / 1e6) if c.get("mcap") else "", r(c.get("pe")) if c.get("pe") else "",
                                   r(c["moat_score"]), "yes" if c["shortlist"] else "", *[r(v) if v is not None else "" for v in c["sig"]]])

    tabs["shortlist"] = [tabs["universe"][0]] + [row for row, c in zip(tabs["universe"][1:], comp) if c["shortlist"]]

    tabs["theme_scores"] = [["Ticker", "Value creation", "Pricing power", "Scale advantage", "Pulling away from peers",
                             "Profit quality & runway", "Risk flags", "Themes improving"]]
    for c in sl:
        tabs["theme_scores"].append([c["ticker"], *[r(c["themes"][t]) for t in themes], c["flags"],
                                     sum(1 for t in themes if (c["improving"][t] or 0) >= imp_rank)])

    tabs["risk_gate"] = [["Ticker"] + [k for k, _ in RULES]]
    for c in sl:
        tabs["risk_gate"].append([c["ticker"]] + [r(c["risk"][k], 4) for k, _ in RULES])

    tabs["clean_data"] = [["Ticker", "Period (12 months)", "Revenue ($M)", "Reported operating income ($M)", "One-offs added back ($M)",
                           "Clean operating income ($M)", "Clean ROIC", "Gross margin", "SG&A / revenue", "FCF ($M)",
                           "Clean net income ($M)", "10-K filing"]]
    for c in sl:
        dd = D[str(c["cik"])]
        s = dd["s"]
        for j in range(max(0, len(dd["years"]) - 10), len(dd["years"])):
            m = lambda k: "" if s[k][j] is None else round(s[k][j] / 1e6, 1)  # noqa: E731
            q = lambda k: "" if s[k][j] is None else round(s[k][j], 4)  # noqa: E731
            tabs["clean_data"].append([c["ticker"], (dd.get("periods") or dd["years"])[j], m("revenue"), m("op_income"), m("one_offs"), m("clean_oi"),
                                       q("roic"), q("gross_margin"), q("sga_rev"), m("fcf"), m("clean_ni"),
                                       sec_url(c["cik"], dd["accn"][j])])

    tabs["observations"] = [["Ticker", "Label", "Observation", "Source"]]
    for c in sl:
        for o in D[str(c["cik"])]["obs"]:
            tabs["observations"].append([c["ticker"], o["kind"], o["text"], o["link"]])

    tabs["phase2"] = [["Ticker", "Company", "Latest 10-K", "Latest 10-Q", "Latest 8-K", "Question 1", "Question 2"]]
    for c in sl:
        dd = D[str(c["cik"])]
        L = dd["links"]
        obs = [o for o in dd["obs"] if o["kind"] != "NEUTRAL"][:1]
        q1 = f"What explains this, and is it structural? {obs[0]['text']}" if obs else "What explains the improvement, and is it structural?"
        tabs["phase2"].append([c["ticker"], c["name"], L.get("10-K", {}).get("url", ""), L.get("10-Q", {}).get("url", ""),
                               L.get("8-K", {}).get("url", ""), q1,
                               "Which customers or suppliers give the company bargaining power, and is it rising?"])

    tabs["funnel"] = [["Stage", "Companies"]] + [[a, b] for a, b in meta["funnel"]]

    tabs["glossary"] = [["Term", "Theme", "Definition", "Formula", "Evidence"],
        ["Clean ROIC", "Value creation", "After-tax operating profit, one-offs removed, per dollar of invested capital", "NOPAT / average invested capital", "Mauboussin, Measuring the Moat; McKinsey, Valuation"],
        ["Hurdle rate", "Value creation", "Minimum return a business should earn on capital", "9% (Settings)", "McKinsey, Valuation"],
        ["Incremental ROIC", "Value creation", "Return on capital added over 3 years", "Change in NOPAT / change in invested capital (3 yrs)", "Mauboussin"],
        ["Gross margin", "Pricing power", "Revenue minus cost of revenue, as a share of revenue", "(Revenue - COGS) / revenue", "Novy-Marx (2013)"],
        ["Gross profit / assets", "Pricing power", "Gross profit per dollar of assets", "Gross profit / average assets", "Novy-Marx (2013)"],
        ["Incremental operating margin", "Scale advantage", "Share of extra revenue that became operating profit", "Change in clean OI / change in revenue (3 yrs)", "Mauboussin; Morningstar"],
        ["SG&A / revenue", "Scale advantage", "Overhead per dollar of sales (lower is better)", "SG&A / revenue", "Morningstar"],
        ["Asset turnover", "Scale advantage", "Revenue per dollar of assets", "Revenue / average assets", "McKinsey, Valuation"],
        ["Growth vs industry", "Peers", "Revenue growth above the industry median", "3-yr CAGR - industry median", "Morningstar; Mauboussin"],
        ["Peer rank change", "Peers", "Move in industry rank on ROIC, margins, turnover", "Rank now - rank 3 yrs ago", "Brief v4"],
        ["FCF / clean net income", "Quality", "Share of profit that became free cash", "(CFO - capex) / clean NI", "Sloan (1996); Piotroski (2000)"],
        ["Accruals", "Quality", "Profit not backed by cash (lower is better)", "(NI - CFO) / average assets", "Sloan (1996)"],
        ["Reinvestment runway", "Quality", "How much is reinvested and at what return", "(Change in capital / NOPAT) x incremental ROIC", "Mauboussin; Mohanram (2005)"],
        ["Interest cover", "Risk gate", "Operating profit per dollar of interest", "Clean OI / interest expense", "Rating-agency practice"],
        ["Net debt / EBITDA", "Risk gate", "Years of cash profit to repay net debt (999 = EBITDA zero or negative)", "(Debt - cash) / EBITDA", "Rating-agency practice"],
        ["Altman Z''", "Risk gate", "Distress score from four ratios, book values", "6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4", "Altman (1968, 1995)"],
        ["Beneish M-Score", "Risk gate", "Eight-ratio earnings-manipulation score", "-4.84 + 0.92 DSRI + ... - 0.327 LVGI", "Beneish (1999)"],
        ["Data confidence", "Data", "Share of core items tagged over 5 years", "High >= 90%, Medium >= 70%", "Brief v4"]]

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in tabs.items():
        with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
    print({k: len(v) - 1 for k, v in tabs.items()})


if __name__ == "__main__":
    main()
