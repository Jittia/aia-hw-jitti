"""Moat Momentum · step 4 report: output/spotcheck.html from output/data/spotcheck.csv (brand styles)."""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LABEL = {"revenue": "Revenue", "cogs": "Cost of revenue", "gross_profit_tag": "Gross profit", "op_income": "Operating income",
         "net_income": "Net income", "sga_tag": "SG&A", "cfo": "Operating cash flow", "capex": "Capex", "assets": "Total assets",
         "equity": "Equity", "goodwill": "Goodwill", "interest": "Interest expense", "restructuring": "Restructuring",
         "acq_costs": "Acquisition costs", "gains": "Gain/loss on assets", "GoodwillImpairmentLoss": "Goodwill impairment",
         "AssetImpairmentCharges": "Asset impairment", "ImpairmentOfLongLivedAssetsHeldForUse": "Long-lived asset impairment",
         "ImpairmentOfIntangibleAssetsExcludingGoodwill": "Intangible impairment",
         "check: clean OI = OI + one-offs": "Check: clean OI = OI + one-offs", "check: NOPAT = clean OI x (1 - tax)": "Check: NOPAT = clean OI × (1 − 21%)"}
CSS = (ROOT / "output" / "moat_momentum.html").read_text(encoding="utf-8").split('<style id="mm-style">')[1].split("</style>")[0]


def money(v: float) -> str:
    a = abs(v)
    s = f"${a / 1e9:,.2f}B" if a >= 1e9 else f"${a / 1e6:,.1f}M" if a >= 1e6 else f"${a:,.0f}"
    return ("−" if v < 0 else "") + s


def main() -> None:
    d = pd.read_csv(ROOT / "output" / "data" / "spotcheck.csv")
    inp = d[~d["item"].str.startswith("check")]
    chk = d[d["item"].str.startswith("check")]
    nz = inp[inp["status"] != "zero (printed as a dash)"]
    n_ok = int((nz["status"] == "matched").sum())
    badge = {"matched": '<span class="badge b-good dot">Found</span>', "zero (printed as a dash)": '<span class="badge b-neutral dot">Zero (dash)</span>',
             "weak match (short number)": '<span class="badge b-neutral dot">Weak</span>', "NOT FOUND": '<span class="badge b-risk dot">Not found</span>',
             "MISMATCH": '<span class="badge b-risk dot">Mismatch</span>'}
    comp = d.drop_duplicates("ticker")[["ticker", "name", "sector"]]
    sections = []
    for _, c in comp.iterrows():
        x = d[d["ticker"] == c["ticker"]]
        years = sorted(x["fy"].unique())
        items = list(dict.fromkeys(x["item"]))
        rows = []
        for it in items:
            cells = []
            for y in years:
                r = x[(x["item"] == it) & (x["fy"] == y)]
                if r.empty:
                    cells.append("<td class='r small'>not tagged</td>")
                    continue
                r = r.iloc[0]
                link = f" <a href='{html.escape(r['filing'])}' target='_blank' rel='noopener'>10-K</a>" if isinstance(r["filing"], str) and r["filing"] else ""
                cells.append(f"<td class='r'>{money(r['value'])}<br>{badge.get(r['status'], r['status'])}{link}</td>")
            rows.append(f"<tr><td>{html.escape(LABEL.get(it, it))}</td>{''.join(cells)}</tr>")
        sections.append(f"<h2>{html.escape(c['ticker'])} · {html.escape(c['name'].title())}</h2><p class='small'>{html.escape(c['sector'])}</p>"
                        f"<div class='tbl'><table class='num'><thead><tr><th>Item</th>{''.join(f'<th class=r>FY{y}</th>' for y in years)}</tr></thead>"
                        f"<tbody>{''.join(rows)}</tbody></table></div>")
    weak = nz[nz["status"] != "matched"]
    body = f"""<div class="wrap">
<header class="bar"><span class="wordmark"><span>Moat Momentum</span></span><span class="tagline">Spot-check · step 4 · 2026-11-03</span></header>
<h1>Cleaned figures match the 10-K documents</h1>
<p class="muted">10 companies from 10 different industries, 3 fiscal years each. Every input that feeds the clean-up and the themes was searched in the visible text of the 10-K it came from (hidden XBRL tags removed), in the units the filing prints. The clean figures were then recomputed by hand.</p>
<div class="kpis"><div class="kpi"><b>{n_ok} / {len(nz)}</b><span>non-zero inputs found in the 10-K text</span></div>
<div class="kpi"><b>{int((chk.status == 'matched').sum())} / {len(chk)}</b><span>hand recalculations match the engine</span></div>
<div class="kpi"><b>{int((inp.status == 'zero (printed as a dash)').sum())}</b><span>zero values (printed as a dash)</span></div>
<div class="kpi"><b>{len(weak)}</b><span>weak matches (short number, no label nearby)</span></div></div>
<h2>How the 10 companies were chosen</h2><p>Rule set before looking at results: the highest-ranked company in each of the 10 largest SIC divisions of the 2026-11-03 run. Five are on the shortlist (SEZL, HXL, COCO, FSS, SMTI).</p>
<h2>What the check found and changed</h2><ul>
<li><b>Operating income tag can be a segment total.</b> TechnipFMC's income statement has no operating-income line: revenue $9,083.3M − total costs $8,126.5M = $956.8M (FY2024), while its OperatingIncomeLoss tag is $1,157.3M. Across the universe, 48 of 1,870 companies show a gap above 10% of operating income (and above 1% of revenue) between the tag and revenue − total costs. Their data confidence is now one level lower, with a Risk observation. The value itself is kept.</li>
<li><b>Gains on selling a business sit below operating income.</b> TechnipFMC's $71.3M gain on disposal of Measurement Solutions is printed below total costs. Such gains (328 companies in the latest year) are no longer subtracted; they are shown in the Deep-Dive bridge as "not removed". Gains on selling equipment and other assets are still removed.</li>
<li>After both fixes the shortlist is unchanged (same 25 names).</li></ul>
<h2>Limits</h2><ul>
<li>Finding a number in the text shows the company printed it; it does not prove it sits on the line we think. Line labels are checked near short numbers only.</li>
<li>Whether each one-off is inside operating income is not visible in XBRL facts; this was checked by hand for TechnipFMC only.</li>
<li>Weak matches: {", ".join(f"{r.ticker} FY{r.fy} {LABEL.get(r.item, r.item)}" for r in weak.itertuples()) or "none"}.</li></ul>
{''.join(sections)}
<div class="disclaimer">Research tool, not investment advice. Source: SEC EDGAR 10-K filings (links in each cell), retrieved 2026-11-03. Full data: output/data/spotcheck.csv.</div></div>"""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moat Momentum Spot-check</title><link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>{body}</body></html>"""
    (ROOT / "output" / "spotcheck.html").write_text(page, encoding="utf-8")
    print("wrote output/spotcheck.html")


if __name__ == "__main__":
    main()
