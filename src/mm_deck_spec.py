"""Moat Momentum · step 9: Google Slides deck spec (inch-based) with numbers read from the validation outputs.

The spec is turned into Slides API requests by the google-workspace skill's slides_helper.py build, then sent
with the Slides connector. Prices, volumes and the ask are left for the founder to set: they are shown as
[to set] and labelled ASSUMPTION, never invented.

Run:  .venv/bin/python src/mm_deck_spec.py <out.json> <first_slide> <last_slide>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER, CARD, INK, INK2, NAVY, TEAL, GOOD, RISK = "#FFF1E5", "#FBE6D4", "#262A33", "#66605A", "#1F3A5F", "#0F7B78", "#2E7D4F", "#B3261E"
SERIF, SANS = "Source Serif 4", "Source Sans 3"


def pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def title(sid, text, y=0.3, h=1.12):
    return {"id": f"{sid}_t", "type": "text", "x": 0.5, "y": y, "w": 9, "h": h, "text": text, "size": 26, "bold": True,
            "color": NAVY, "font": SERIF}


def foot(sid, text):
    return {"id": f"{sid}_f", "type": "text", "x": 0.5, "y": 5.15, "w": 9, "h": 0.35, "text": text, "size": 9, "color": INK2, "font": SANS}


def body(sid, key, x, y, w, h, text, size=16, bullets=False, color=INK, bold=False, align="START"):
    e = {"id": f"{sid}_{key}", "type": "text", "x": x, "y": y, "w": w, "h": h, "text": text, "size": size, "color": color,
         "font": SANS, "bold": bold, "align": align}
    if bullets:
        e["bullets"] = True
        e["space_below"] = 6
    return e


def card(sid, key, x, y, w, h, text, size=15, fill=CARD, color=INK):
    return {"id": f"{sid}_{key}", "type": "round_rect", "x": x, "y": y, "w": w, "h": h, "fill": fill, "text": text,
            "size": size, "color": color, "font": SANS}


def table(sid, x, y, w, rows, widths, align):
    return {"id": f"{sid}_tb", "type": "table", "x": x, "y": y, "w": w, "rows": rows, "header": True, "size": 14,
            "col_widths": widths, "col_align": align, "font": SANS}


def slides() -> list[dict]:
    v = json.loads((ROOT / "output" / "data" / "validation.json").read_text())["variants"]["Default (locked v1.0)"]
    m = json.loads((ROOT / "output" / "data" / "market.json").read_text())
    pf = json.loads((ROOT / "output" / "pitch" / "facts.json").read_text())
    s = (ROOT / "output" / "data" / "site_data.js").read_text(encoding="utf-8")
    meta = json.loads(s[len("window.MM = "):s.rindex(";")])["meta"]
    tr = json.loads(sorted((ROOT / "track_record").glob("*.json"))[-1].read_text())
    sl, P, c, inc = v["shortlist"], m["portfolios"], pf["cmp"], pf["incumbents"]
    beat = sum(P["moat"]["neutral"]["by_year"][y] > P["^SP500TR"]["neutral"]["by_year"][y] for y in P["moat"]["neutral"]["by_year"])
    inc_total = sum(i["revenue"] for i in inc)
    f = {a: b for a, b in meta["funnel"]}
    src_val = "Source: SEC EDGAR 10-K filings 2009–2026; Moat Momentum validation, Methodology v1.0 locked before the run."
    S = []

    S.append({"id": "s01", "bg": NAVY, "elements": [
        {"id": "s01_t", "type": "text", "x": 0.7, "y": 1.5, "w": 8.6, "h": 1.0, "text": "Moat Momentum", "size": 44, "bold": True, "color": PAPER, "font": SERIF},
        {"id": "s01_s", "type": "text", "x": 0.7, "y": 2.5, "w": 8.6, "h": 0.6, "text": "Strengthening moats, found in the filings.", "size": 20, "color": PAPER, "font": SERIF},
        {"id": "s01_d", "type": "text", "x": 0.7, "y": 3.4, "w": 8.6, "h": 0.5, "text": "Investor presentation · draft · 3 November 2026 · Jitti", "size": 14, "color": PAPER, "font": SANS},
        {"id": "s01_f", "type": "text", "x": 0.7, "y": 5.0, "w": 8.6, "h": 0.4, "text": "Research tool, not investment advice. Past results do not guarantee future results.", "size": 9, "color": PAPER, "font": SANS}]})

    S.append({"id": "s02", "elements": [title("s02", "Executive summary"),
        body("s02", "b", 0.5, 1.4, 9, 3.6,
             f"A research tool that scores {f['Revenue ≥ $100M and ≥ 5 fiscal years (universe)']:,} US companies on whether their competitive position is improving, from SEC filings only\n"
             f"Tested before pitching: picks stay above their industry ({c['Shortlist']['L_rank3']:+.1f} rank points after 3 years), but do not keep improving ({pct(sl['flagged']['hit_rate_3y'])} vs {pct(sl['rest']['hit_rate_3y'])})\n"
             f"Market test 2013–2026: {pct(P['moat']['neutral']['cagr'])} a year, the same as the S&P 500, with more volatility\n"
             "The product is transparency: every number traced to a 10-K, every rule adjustable, every miss published\n"
             "We ask for support to build v1.1 on unseen years and to test demand", 16, bullets=True),
        foot("s02", src_val)]})

    S.append({"id": "s03", "elements": [title("s03", "Quality screens find moats after the market has already priced them"),
        card("s03", "a", 0.5, 1.6, 2.85, 2.6, "Quality screens\n\nRank today's level of returns, so they find companies that are already great"),
        card("s03", "b", 3.575, 1.6, 2.85, 2.6, "Analyst moat ratings\n\nJudgement-based, slow to change and limited in coverage"),
        card("s03", "c", 6.65, 1.6, 2.85, 2.6, "Investors\n\nHave no transparent, testable, filing-based way to see a moat forming"),
        foot("s03", "Problem statement from the founder's brief; Morningstar describes its moat ratings as analyst-assigned (public methodology).")]})

    funnel = [("All SEC filers with data", f["Companies with SEC XBRL data (non-financial SIC, revenue ≥ $50M at least once)"]),
              ("Universe", f["Revenue ≥ $100M and ≥ 5 fiscal years (universe)"]),
              ("Pass risk gate", f["Pass the risk gate (no Remove rule hit)"]),
              ("Moat strengthening", f["Moat Strengthening (≥ 3 of 5 themes improving)"]), ("Shortlist", f["Shortlist"])]
    els = [title("s04", f"{f['Revenue ≥ $100M and ≥ 5 fiscal years (universe)']:,} companies, 5 tests, a 25-name shortlist traced to 10-Ks")]
    for i, (lab, n) in enumerate(funnel):
        els.append(card("s04", f"f{i}", 0.5 + i * 1.84, 1.7, 1.66, 1.6, f"{n:,}\n{lab}", 16, fill=NAVY if i == 4 else CARD, color=PAPER if i == 4 else INK))
    els += [body("s04", "n", 0.5, 3.6, 9, 1.3, "Clean-up of one-off items · risk gate (debt, distress, manipulation, dilution, acquisitions) · five themes ranked within each industry on level, 5-year trend and consistency", 15),
            foot("s04", f"Source: SEC EDGAR companyfacts and submissions, retrieved {meta['sec_retrieved']}; official run {meta['as_of']}.")]
    S.append({"id": "s04", "elements": els})

    S.append({"id": "s05", "elements": [title("s05", "One screen, adjustable rules, and a Deep-Dive for every company"),
        card("s05", "a", 0.5, 1.6, 2.1, 2.7, "Screener\n\nMove weights and risk rules; the list re-ranks at once"),
        card("s05", "b", 2.8, 1.6, 2.1, 2.7, "Deep-Dive\n\n20 charts, observations, peers, each number linked to its 10-K"),
        card("s05", "c", 5.1, 1.6, 2.1, 2.7, "Proof\n\nEvery past pick and what happened, misses included"),
        card("s05", "d", 7.4, 1.6, 2.1, 2.7, "Sheet + Learn\n\nGoogle Sheet source of truth; every indicator explained"),
        body("s05", "l", 0.5, 4.45, 9, 0.5, "Live demo: output/moat_momentum.html in github.com/Jittia/aia-hw-jitti", 14, color=TEAL),
        foot("s05", "Product as built on 2026-11-03 (Methodology v1.0).")]})

    S.append({"id": "s06", "elements": [title("s06", "Picks stay above their industry, but do not keep improving"),
        table("s06", 0.5, 1.5, 9, [["Three years after selection", "Shortlist", "Rest"],
              ["Peer rank kept improving", pct(sl["flagged"]["hit_rate_3y"]), pct(sl["rest"]["hit_rate_3y"])],
              ["Peer rank fell > 10 points", pct(sl["flagged"]["false_alarm_3y"]), pct(sl["rest"]["false_alarm_3y"])],
              ["Rank vs industry median", f"{c['Shortlist']['L_rank3']:+.1f}", f"{c['Rest of universe']['L_rank3']:+.1f}"],
              ["Rank vs same starting rank", f"{c['Shortlist']['M_rank3']:+.1f}", f"{c['Rest of universe']['M_rank3']:+.1f}"]],
              [5.4, 1.8, 1.8], ["START", "END", "END"]),
        body("s06", "n", 0.5, 4.2, 9, 0.8, f"{sl['flagged']['n']} picks, 2013–2023, point-in-time. Same result in all 17 variants tested.", 14, color=INK2),
        foot("s06", src_val)]})

    S.append({"id": "s07", "elements": [title("s07", f"The shortlist matched the S&P 500 at {pct(P['moat']['neutral']['cagr'])} a year, with more volatility"),
        table("s07", 0.5, 1.5, 9, [["Jul 2013 – Oct 2026", "CAGR", "Volatility", "Max drawdown"],
              ["Moat Momentum shortlist", pct(P["moat"]["neutral"]["cagr"]), pct(P["moat"]["neutral"]["vol"]), pct(P["moat"]["neutral"]["max_dd"])],
              ["Quality only (same engine)", pct(P["quality"]["neutral"]["cagr"]), pct(P["quality"]["neutral"]["vol"]), pct(P["quality"]["neutral"]["max_dd"])],
              ["S&P 500 total return", pct(P["^SP500TR"]["neutral"]["cagr"]), pct(P["^SP500TR"]["neutral"]["vol"]), pct(P["^SP500TR"]["neutral"]["max_dd"])],
              ["MSCI USA Quality ETF", pct(P["QUAL"]["neutral"]["cagr"]), pct(P["QUAL"]["neutral"]["vol"]), pct(P["QUAL"]["neutral"]["max_dd"])]],
              [4.2, 1.6, 1.6, 1.6], ["START", "END", "END", "END"]),
        body("s07", "n", 0.5, 4.2, 9, 0.8, f"Beat the index in {beat} of 13 years. Worst case for delisted names: {pct(P['moat']['worst']['cagr'])} a year.", 14, color=INK2),
        foot("s07", f"Source: Yahoo Finance monthly adjusted prices, retrieved {m['retrieved']}; missing names bounded with SEC filings. Not investment advice.")]})

    S.append({"id": "s08", "elements": [title("s08", "Every official shortlist is frozen with a fingerprint from day one"),
        body("s08", "big", 0.5, 1.6, 9, 0.9, tr["record"]["as_of"], 40, color=NAVY, bold=True),
        body("s08", "fp", 0.5, 2.5, 9, 0.8, f"SHA-256 {tr['fingerprint_sha256']}", 14, color=INK2),
        body("s08", "b", 0.5, 3.3, 9, 1.6, "Shortlist, settings and data date committed to a public Git repository\nChanging a frozen list later breaks its fingerprint\nPerformance is measured from the first month-end after each freeze", 16, bullets=True),
        foot("s08", "Source: track_record/ in github.com/Jittia/aia-hw-jitti. The live record starts on 2026-11-03, so there are no live results yet.")]})

    S.append({"id": "s09", "elements": [title("s09", "Thirty years inside how companies win with suppliers and customers"),
        body("s09", "b", 0.5, 1.5, 9, 3.3, "Global procurement and supply-chain leadership at P&G, Mars, Saint-Gobain, Danone, Tesco and Coca-Cola\nSees bargaining power and switching costs from the inside: the forces behind a moat\nBuilt and tested Moat Momentum end to end, and published where it fails", 17, bullets=True),
        foot("s09", "Founder background as stated in the brief.")]})

    S.append({"id": "s10", "elements": [title("s10", f"Three incumbents earn ${inc_total / 1e9:.1f}B a year from investment data and research"),
        table("s10", 0.5, 1.5, 5.6, [["Incumbent", "Revenue", "Fiscal year"]] + [[i["name"], f"${i['revenue'] / 1e9:.2f}B", i["end"][:4]] for i in inc],
              [2.4, 1.6, 1.6], ["START", "END", "END"]),
        body("s10", "c", 6.4, 1.5, 3.1, 3.3, "Target customers\nIndividual investors\nProfessional analysts\nFunds and research teams (data licensing)", 15, bullets=True),
        foot("s10", "Source: Morningstar, FactSet, MSCI 10-K revenue (SEC XBRL). Total company revenue, not our addressable market.")]})

    S.append({"id": "s11", "elements": [title("s11", "Two revenue lines: subscriptions and data licensing"),
        table("s11", 0.5, 1.5, 9, [["Offer", "Includes", "Price"],
              ["Individual", "Screener, Deep-Dives, alerts", "[to set] ASSUMPTION"],
              ["Professional", "+ exports, scenarios, history", "[to set] ASSUMPTION"],
              ["Team", "+ seats, shared scenarios", "[to set] ASSUMPTION"],
              ["Data licence", "Scores, history, file/API feed", "[to set] ASSUMPTION"]],
              [2.2, 4.6, 2.2], ["START", "START", "END"]),
        body("s11", "n", 0.5, 4.1, 9, 0.9, "Unit economics ASSUMPTIONS: data cost near zero (SEC data is public); costs are hosting, support and acquisition, to be measured in a pilot.", 14, color=TEAL),
        foot("s11", "All prices and volumes are assumptions to validate. No revenue yet.")]})

    S.append({"id": "s12", "elements": [title("s12", "Our edge is transparency and self-testing, not a return claim"),
        table("s12", 0.5, 1.5, 9, [["", "Data", "Rules visible", "Published misses"],
              ["Moat Momentum", "SEC filings", "Yes, adjustable", "Yes"],
              ["Analyst moat ratings", "Analysts", "Framework only", "To verify"],
              ["Fundamental screeners", "Vendor data", "Partly", "To verify"],
              ["Quality-factor ETFs", "Index rules", "Yes", "Index history"]],
              [2.8, 2.0, 2.2, 2.0], ["START", "START", "START", "START"]),
        foot("s12", "Competitor entries to verify against each provider's public documentation before external use.")]})

    S.append({"id": "s13", "elements": [title("s13", "Next 24 months: prove the signal, then test demand"),
        card("s13", "a", 0.5, 1.5, 2.85, 2.4, "0–6 months\n\nv1.1 designed in advance, tested on 2018–2023 only; Phase 2 qualitative layer"),
        card("s13", "b", 3.575, 1.5, 2.85, 2.4, "6–12 months\n\nPilot with 20–50 users; live track record; legal review"),
        card("s13", "c", 6.65, 1.5, 2.85, 2.4, "12–24 months\n\nForeign filers, then Thailand, Hong Kong, Taiwan; data licence pilot"),
        body("s13", "ask", 0.5, 4.1, 9, 0.9, "The ask: [amount and use of funds to be set by the founder] · legal review required before launch", 16, color=NAVY, bold=True),
        foot("s13", "Roadmap from the brief. Timings are plans, not commitments.")]})
    return S


def main(out: str, a: int, b: int) -> None:
    sel = slides()[a - 1:b]
    spec = {"slides": [{"id": "mm_" + x["id"], "layout": "BLANK", "elements": x["elements"]} for x in sel]}
    Path(out).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(out).with_suffix(".bg.json").write_text(json.dumps({"mm_" + x["id"]: x.get("bg", PAPER) for x in sel}), encoding="utf-8")
    print(f"{len(sel)} slides → {out}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
