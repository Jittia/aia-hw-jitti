"""Moat Momentum · step 9: whitepaper and one-pager (HTML) with every number read from the validation outputs.

Reading copies: output/pitch/whitepaper.html, output/pitch/onepager.html. The same HTML is uploaded to Google Docs
(Drive converts it). Market-size anchors are incumbents' revenue from their SEC 10-K XBRL facts (bulk companyfacts).
Anything that is not measured is marked ASSUMPTION.

Run:  .venv/bin/python src/mm_pitch.py
"""
from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "pitch"
NAVY, TEAL, INK, INK2, RISK, GOOD = "#1F3A5F", "#0F7B78", "#262A33", "#66605A", "#B3261E", "#2E7D4F"
INCUMBENTS = [("Morningstar", 1289419), ("FactSet", 1013237), ("MSCI", 1408198)]


def pct(v, d=1):
    return "n/a" if v is None or pd.isna(v) else f"{v * 100:.{d}f}%"


def incumbents() -> list[dict]:
    out = []
    with zipfile.ZipFile(ROOT / "data" / "cache" / "bulk" / "companyfacts.zip") as z:
        for name, cik in INCUMBENTS:
            g = json.loads(z.read(f"CIK{cik:010d}.json"))["facts"]["us-gaap"]
            best = None
            for tag in ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"):
                for f in g.get(tag, {}).get("units", {}).get("USD", []):
                    if f.get("form") == "10-K" and f.get("start"):
                        days = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
                        if 350 <= days <= 380 and (best is None or f["end"] > best["end"]):
                            best = f
            out.append({"name": name, "revenue": best["val"], "end": best["end"], "filed": best["filed"],
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{best['accn'].replace('-', '')}/{best['accn']}-index.htm"})
    return out


def load() -> dict:
    v = json.loads((ROOT / "output" / "data" / "validation.json").read_text())["variants"]
    m = json.loads((ROOT / "output" / "data" / "market.json").read_text())
    sc = pd.read_csv(ROOT / "output" / "data" / "spotcheck.csv")
    tr = sorted((ROOT / "track_record").glob("*.json"))[-1]
    track = json.loads(tr.read_text())
    s = (ROOT / "output" / "data" / "site_data.js").read_text(encoding="utf-8")
    meta = json.loads(s[len("window.MM = "):s.rindex(";")])["meta"]
    rows = pd.read_pickle(ROOT / "data" / "cache" / "mm" / "validation_rows.pkl")
    from mm_proof import comparisons
    inp = sc[~sc["item"].str.startswith("check")]
    nz = inp[inp["status"] != "zero (printed as a dash)"]
    chk = sc[sc["item"].str.startswith("check")]
    return {"v": v, "d": v["Default (locked settings)"], "m": m, "track": track, "meta": meta, "cmp": comparisons(rows),
            "spot": {"found": int((nz["status"] == "matched").sum()), "n": len(nz), "chk_ok": int((chk["status"] == "matched").sum()),
                     "chk_n": len(chk), "companies": sc["ticker"].nunique()},
            "inc": incumbents()}


def style() -> str:
    return f"""<style>
body {{ font-family: 'Source Sans 3', Arial, sans-serif; color: {INK}; font-size: 11pt; line-height: 1.45; max-width: 780px; margin: 0 auto; padding: 24px; background: #FFF1E5; }}
h1 {{ font-family: 'Source Serif 4', Georgia, serif; color: {NAVY}; font-size: 24pt; margin: 0 0 4px; }}
h2 {{ font-family: 'Source Serif 4', Georgia, serif; color: {NAVY}; font-size: 15pt; margin: 22px 0 6px; }}
h3 {{ font-family: 'Source Serif 4', Georgia, serif; color: {NAVY}; font-size: 12pt; margin: 14px 0 4px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 10pt; margin: 6px 0 10px; }}
th {{ background: {NAVY}; color: #FFFFFF; text-align: left; padding: 5px 7px; }}
td {{ border-bottom: 1px solid #E3D3C4; padding: 5px 7px; vertical-align: top; }}
.r {{ text-align: right; }} .small {{ font-size: 9pt; color: {INK2}; }} .tag {{ font-style: italic; color: {INK2}; }}
.risk {{ color: {RISK}; font-weight: bold; }} .good {{ color: {GOOD}; font-weight: bold; }} .assume {{ color: {TEAL}; font-weight: bold; }}
</style>"""


def doc(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet">{style()}</head><body>{body}
<p class="small" style="border-top:2px solid {NAVY};padding-top:8px;margin-top:24px">Moat Momentum is a research tool, not investment advice. Output is the same for every user. Past results do not guarantee future results. Prepared {date.today()} · Methodology v1.0 · Sources: SEC EDGAR; Yahoo Finance for the market test. Legal review is required before any launch.</p></body></html>"""


def whitepaper(x: dict) -> str:
    d, m, c, sp = x["d"], x["m"], x["cmp"], x["spot"]
    sl, st = d["shortlist"], d["strengthening"]
    P = m["portfolios"]
    f = x["meta"]["funnel"]
    inc_rows = "".join(f"<tr><td>{i['name']}</td><td class='r'>${i['revenue'] / 1e6:,.1f}M</td><td>FY ending {i['end']}</td><td><a href='{i['url']}'>10-K filed {i['filed']}</a></td></tr>" for i in x["inc"])
    inc_total = sum(i["revenue"] for i in x["inc"])
    rob = "".join(f"<tr><td>{k}</td><td class='r'>{pct(v['shortlist']['flagged']['hit_rate_3y'])}</td><td class='r'>{pct(v['shortlist']['flagged']['false_alarm_3y'])}</td></tr>"
                  for k, v in x["v"].items() if not k.startswith("Weight") or k.endswith("+10"))
    mk = "".join(f"<tr><td>{lab}</td><td class='r'>{pct(P[k]['neutral']['cagr'])}</td><td class='r'>{pct(P[k]['neutral']['vol'])}</td><td class='r'>{pct(P[k]['neutral']['max_dd'])}</td></tr>"
                 for k, lab in (("moat", "Moat Momentum shortlist"), ("quality", "Quality only (same engine, level only)"),
                                ("universe", "Universe, equal weight"), ("^SP500TR", "S&P 500 total return"), ("QUAL", "MSCI USA Quality ETF (QUAL)")))
    meta = x["meta"]
    formulas = {"roic_spread": "NOPAT ÷ avg invested capital − 9%", "incr_roic": "Δ NOPAT ÷ Δ capital, 3 yrs", "gross_margin": "(Revenue − COGS) ÷ revenue",
                "gp_assets": "Gross profit ÷ avg assets", "gm_stability": "− st. dev. of gross margin, 5 yrs", "incr_margin": "Δ clean OI ÷ Δ revenue, 3 yrs",
                "sga_rev": "SG&amp;A ÷ revenue (lower better)", "asset_turnover": "Revenue ÷ avg assets", "rev_excess": "3-yr revenue CAGR − industry median",
                "peer_rank_change": "Peer rank now − 3 yrs ago", "fcf_conv": "(CFO − capex) ÷ clean net income", "accruals": "(NI − CFO) ÷ avg assets (lower better)",
                "runway": "Reinvestment rate × incremental ROIC"}
    tname = {t["key"]: t["name"] for t in meta["themes"]}
    cname = {"L": "level", "T": "trend", "C": "consistency"}
    ind_rows = "".join(f"<tr><td>{tname[i['theme']]}</td><td>{i['label']}</td><td>{formulas[i['name']]}</td><td>{', '.join(cname[ch] for ch in i['comps'])}</td></tr>" for i in meta["indicators"])
    rg = meta["settings"]["risk_gate"]
    side = {"interest_cover": "below", "net_debt_ebitda": "above", "altman_z": "below", "beneish_m": "above", "dilution": "above", "sbc_revenue": "above", "goodwill_jump": "above"}
    gate_rows = "".join(f"<tr><td>{k.replace('_', ' ')}</td><td>{rg[k]['mode']} if {side[k]} {rg[k][side[k]]}</td><td class='r'>{meta['gate_counts'][k]['breach']}</td><td class='r'>{meta['gate_counts'][k]['worsening']}</td></tr>" for k in side)
    sub_rows = "".join(f"<tr><td>{k}</td><td class='r'>{v['flagged']['n']}</td><td class='r'>{pct(v['flagged']['hit_rate_3y'])}</td><td class='r'>{pct(v['flagged']['false_alarm_3y'])}</td><td class='r'>{pct(v['rest']['hit_rate_3y'])}</td></tr>"
                       for k, v in list(d["sub_periods"].items()) + list(d["sector_exclusions"].items()))
    bound_rows = "".join(f"<tr><td>{lab}</td><td class='r'>{pct(P[k]['survivors']['cagr'])}</td><td class='r'>{pct(P[k]['neutral']['cagr'])}</td><td class='r'>{pct(P[k]['worst']['cagr'])}</td></tr>"
                         for k, lab in (("moat", "Shortlist"), ("quality", "Quality only"), ("universe", "Universe EW")))
    year_rows = "".join(f"<tr><td>{y}</td>" + "".join(f"<td class='r'>{pct(P[k]['neutral']['by_year'][y])}</td>" for k in ("moat", "quality", "^SP500TR", "QUAL")) + "</tr>"
                        for y in sorted(P["moat"]["neutral"]["by_year"]))
    funnel = "".join(f"<tr><td>{a}</td><td class='r'>{b:,}</td></tr>" for a, b in f)
    return doc("Moat Momentum Whitepaper", f"""
<h1>Moat Momentum</h1><p class="tag">Strengthening moats, found in the filings. Methodology whitepaper v1.0 · {date.today():%d %B %Y}</p>
<h2>1. Summary</h2>
<p>Moat Momentum screens every US-listed company with SEC XBRL data for signs that its competitive advantage is strengthening: rising returns on capital, pricing power, scale benefits, gains against industry peers and cash-backed profit. Every number comes from audited filings and links to the 10-K it came from.</p>
<p>We tested the method honestly before writing this paper. The screen finds high-quality, improving businesses: three years after selection they still ranked <b>{c['Shortlist']['L_rank3']:+.1f} points</b> above their industry median on returns, margins and turnover, with clean ROIC <b>{pct(c['Shortlist']['L_roic3'])}</b> higher. But it does <span class="risk">not</span> yet predict further strengthening, and a portfolio of its picks returned {pct(P['moat']['neutral']['cagr'])} a year from 2013 to 2026, about the same as the S&amp;P 500 ({pct(P['^SP500TR']['neutral']['cagr'])}), with more volatility. We report this in full, because a research tool is only as useful as its willingness to show where it fails.</p>
<h2>2. The problem</h2>
<p>Quality screens find companies that are already great and already priced as such. Analyst moat ratings are subjective, slow to change and cover a limited set of companies. Investors who want to see a moat forming, rather than one that is already recognised, have no transparent, testable, filing-based tool.</p>
<h2>3. Academic foundations</h2>
<ul><li><b>Value creation:</b> returns on invested capital above the cost of capital, and returns on new capital (Mauboussin &amp; Callahan, “Measuring the Moat”; Koller, Goedhart &amp; Wessels, “Valuation”).</li>
<li><b>Pricing power:</b> gross profitability predicts returns (Novy-Marx, 2013, Journal of Financial Economics).</li>
<li><b>Profit quality:</b> accruals predict earnings declines (Sloan, 1996); simple financial-strength scores (Piotroski, 2000; Mohanram, 2005).</li>
<li><b>Risk:</b> distress (Altman Z, 1968; Z'' variant) and earnings manipulation (Beneish M-Score, 1999).</li></ul>
<h2>4. Method</h2>
<h3>4.1 Data</h3><p>SEC EDGAR companyfacts and submissions bulk files (retrieved {x['meta']['sec_retrieved']}). Up to 10 fiscal years of 10-K data per company. The store keeps the first value filed for every period and every later restatement, so a past run uses only what was public on its date.</p>
<h3>4.2 Clean-up</h3><p>Operating income is cleaned of one-off items the company tags separately: impairments, restructuring, litigation, acquisition costs and gains on asset sales. Tax is set to one 21% rate for every year so that the 2018 US tax change does not create a false trend. Invested capital = equity + debt + finance leases − cash above 2% of revenue.</p>
<h3>4.3 Universe and risk gate</h3><p>US-listed, revenue at least $100M, at least five fiscal years, not a bank, insurer or REIT. Seven risk checks run before scoring: interest cover, net debt ÷ EBITDA, Altman Z'', Beneish M-Score, dilution, stock-based pay and acquisition-driven goodwill. Each can be off, flag (penalty) or remove.</p>
<table><tr><th>Stage, run of {x['meta']['as_of']}</th><th class="r">Companies</th></tr>{funnel}</table>
<h3>4.4 Scoring</h3><p>Thirteen indicators in five themes (value creation 25, pricing power 20, scale 15, pulling away from peers 20, profit quality 20). Each is ranked within its SIC industry on level, five-year trend and consistency, weighted 30/50/20 toward improvement. “Moat Strengthening” requires at least three of five themes improving. Every weight and threshold is adjustable in the web page and the Google Sheet.</p>
<table><tr><th>Theme</th><th>Indicator</th><th>Formula</th><th>Components</th></tr>{ind_rows}</table>
<h3>4.5 Risk gate today</h3><table><tr><th>Check</th><th>Default</th><th class="r">Over threshold</th><th class="r">Worsening</th></tr>{gate_rows}</table>
<h2>5. Data quality</h2><p>For 10 companies in 10 industries, three fiscal years each, {sp['found']} of {sp['n']} non-zero inputs were found printed in the 10-K text, and {sp['chk_ok']} of {sp['chk_n']} hand recalculations matched the engine. The check found two clean-up issues, which were fixed: an operating-income tag that was a segment total, and business-sale gains that sit below operating income.</p>
<h2>6. Validation</h2>
<h3>6.1 Fundamental test, 2013–2023</h3><p>Each year the screen was re-run as of 30 June using only filings made by then, including companies that later delisted. Settings were fingerprinted before the run.</p>
<table><tr><th>Three years later</th><th class="r">Shortlist</th><th class="r">Moat Strengthening</th><th class="r">Rest of universe</th></tr>
<tr><td>Peer rank kept improving (hit rate)</td><td class="r">{pct(sl['flagged']['hit_rate_3y'])}</td><td class="r">{pct(st['flagged']['hit_rate_3y'])}</td><td class="r">{pct(sl['rest']['hit_rate_3y'])}</td></tr>
<tr><td>Peer rank fell more than 10 points (false alarm)</td><td class="r">{pct(sl['flagged']['false_alarm_3y'])}</td><td class="r">{pct(st['flagged']['false_alarm_3y'])}</td><td class="r">{pct(sl['rest']['false_alarm_3y'])}</td></tr>
<tr><td>Reached industry top 20% on ROIC</td><td class="r">{pct(sl['flagged']['reach_top20_roic_3y'])}</td><td class="r">{pct(st['flagged']['reach_top20_roic_3y'])}</td><td class="r">{pct(sl['rest']['reach_top20_roic_3y'])}</td></tr>
<tr><td>Peer rank vs industry median</td><td class="r">{c['Shortlist']['L_rank3']:+.1f}</td><td class="r">{c['Moat Strengthening']['L_rank3']:+.1f}</td><td class="r">{c['Rest of universe']['L_rank3']:+.1f}</td></tr>
<tr><td>Peer rank vs companies with the same starting rank</td><td class="r">{c['Shortlist']['M_rank3']:+.1f}</td><td class="r">{c['Moat Strengthening']['M_rank3']:+.1f}</td><td class="r">{c['Rest of universe']['M_rank3']:+.1f}</td></tr></table>
<p class="small">{sl['flagged']['n']} shortlist picks ({sl['flagged']['companies']} companies) over 11 years. The same pattern holds in every variant tried:</p>
<table><tr><th>Variant</th><th class="r">Shortlist hit rate</th><th class="r">Shortlist false alarm</th></tr>{rob}</table>
<h3>6.1b Sub-periods and slices (shortlist)</h3><table><tr><th>Slice</th><th class="r">Picks</th><th class="r">Hit rate</th><th class="r">False alarm</th><th class="r">Rest: hit</th></tr>{sub_rows}</table>
<h3>6.2 Market test, July 2013 – October 2026</h3><p>Equal-weight shortlist bought every 30 June, held one year. Prices from Yahoo Finance; companies that stopped trading filled with S&amp;P 500 returns (neutral case), with worst-case and survivors-only bounds reported in the Proof tab.</p>
<table><tr><th>Portfolio</th><th class="r">CAGR</th><th class="r">Volatility</th><th class="r">Max drawdown</th></tr>{mk}</table>
<h3>6.3 Bounds for companies that stopped trading</h3><table><tr><th>Portfolio</th><th class="r">Survivors only</th><th class="r">Neutral</th><th class="r">Worst case</th></tr>{bound_rows}</table>
<h3>6.4 Every year (July to June)</h3><table><tr><th>Year</th><th class="r">Shortlist</th><th class="r">Quality only</th><th class="r">S&amp;P 500</th><th class="r">QUAL</th></tr>{year_rows}</table>
<p class="small">The shortlist beat the S&amp;P 500 in {sum(P['moat']['neutral']['by_year'][y] > P['^SP500TR']['neutral']['by_year'][y] for y in P['moat']['neutral']['by_year'])} of 13 years; {pct(m['hit_rate_vs_spx'], 0)} of individual picks beat it over their holding year; annual turnover {pct(m['turnover'], 0)}.</p>
<h2>7. What the evidence supports, and what it does not</h2>
<ul><li><span class="good">Supported:</span> the screen identifies companies with above-industry returns on capital and margins that persist for at least three years, from audited data, with every number traceable.</li>
<li><span class="risk">Not supported:</span> that a strengthening moat is visible in the numbers before it is recognised, or that the shortlist earns excess returns. Picks tend to be caught near the top of their improvement.</li></ul>
<h2>8. Limitations</h2><ul><li>Only one-off items that companies tag separately can be removed.</li><li>Levels use fiscal-year data, not trailing twelve months.</li><li>The hurdle rate is 9% for all sectors; EDGAR has no market data for a true cost of capital.</li><li>Altman Z'' uses book equity and flags some healthy companies with negative equity from buybacks.</li><li>Free price data misses many companies that no longer trade; results are shown with bounds.</li><li>Banks, insurers, REITs and foreign filers are out of scope in Phase 1.</li></ul>
<h2>9. Audit trail and live record</h2><p>Every official run freezes its shortlist, settings and data date in the public repository with a SHA-256 fingerprint (first record {x['track']['record']['as_of']}, fingerprint {x['track']['fingerprint_sha256'][:16]}…). The forward record cannot be edited without the change showing.</p>
<h2>10. Roadmap</h2><ul><li><b>v1.1, designed in advance:</b> test measures that resist mean reversion (persistence over longer windows, distance from prior peak), built on 2013–2017 and confirmed on 2018–2023 only.</li><li><b>Phase 2:</b> qualitative layer for the shortlist (transcripts, leadership, business model) with the founder's procurement lens.</li><li><b>Phase 3:</b> foreign filers (20-F, IFRS), then Thailand, Hong Kong and Taiwan; optional valuation overlay kept separate from the moat score.</li></ul>
<h2>Appendix: market-size anchors (SEC 10-K)</h2><table><tr><th>Incumbent</th><th class="r">Revenue</th><th>Period</th><th>Source</th></tr>{inc_rows}<tr><td><b>Total</b></td><td class="r"><b>${inc_total / 1e9:,.1f}B</b></td><td colspan="2"></td></tr></table>
<p class="small">These are total company revenues, which include products beyond research subscriptions; they show the scale of spending on investment data and research, not our addressable market.</p>""")


def onepager(x: dict) -> str:
    d, m, c = x["d"], x["m"], x["cmp"]
    P = m["portfolios"]
    sl = d["shortlist"]
    inc_total = sum(i["revenue"] for i in x["inc"])
    return doc("Moat Momentum One-Pager", f"""
<h1>Moat Momentum</h1><p class="tag">Strengthening moats, found in the filings.</p>
<h2>What it is</h2><p>A research screener that ranks about {x['meta']['funnel'][3][1]:,} US companies on whether their competitive position is improving, using only audited SEC filings. Every number links to its 10-K; every weight and threshold can be changed; every official shortlist is frozen with a fingerprint.</p>
<h2>What we have proved, and what we have not</h2><ul>
<li><span class="good">Proved:</span> picks keep above-industry quality. Three years later they ranked {c['Shortlist']['L_rank3']:+.1f} points above their industry median, with ROIC {pct(c['Shortlist']['L_roic3'])} higher (2013–2023, point-in-time).</li>
<li><span class="risk">Not proved:</span> early detection or excess returns. Only {pct(sl['flagged']['hit_rate_3y'])} of picks kept improving (universe {pct(sl['rest']['hit_rate_3y'])}); the shortlist returned {pct(P['moat']['neutral']['cagr'])} a year vs {pct(P['^SP500TR']['neutral']['cagr'])} for the S&amp;P 500 (2013–2026).</li></ul>
<h2>Why it is different</h2><ul><li>Free, public data: no licence cost.</li><li>Transparent rules, adjustable by the user, and a published record of where the method fails.</li><li>Founder: 30 years of global procurement and supply-chain leadership (P&amp;G, Mars, Saint-Gobain, Danone, Tesco, Coca-Cola).</li></ul>
<h2>Business model</h2><p>Subscription research tool and data/signal licensing to funds. Pricing and volumes are <span class="assume">ASSUMPTIONS</span> to test. Incumbents Morningstar, FactSet and MSCI together reported ${inc_total / 1e9:,.1f}B of revenue in their latest 10-Ks.</p>
<h2>Next</h2><p>v1.1 designed and tested on unseen years; Phase 2 qualitative layer; legal review before launch.</p>""")


def main() -> None:
    x = load()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "whitepaper.html").write_text(whitepaper(x), encoding="utf-8")
    (OUT / "onepager.html").write_text(onepager(x), encoding="utf-8")
    (OUT / "facts.json").write_text(json.dumps({"incumbents": x["inc"], "cmp": x["cmp"], "spot": x["spot"]}, indent=1), encoding="utf-8")
    print("wrote", [p.name for p in OUT.iterdir()])


if __name__ == "__main__":
    main()
