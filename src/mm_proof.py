"""Moat Momentum · Proof page (brief §6E) from the validation outputs of src/mm_validate.py.

Adds two comparisons on top of validation.json, computed from data/cache/mm/validation_rows.pkl (default settings):
  level later   peer rank / ROIC h years later minus the same-year same-industry median (the brief's test)
  same start    the same, but against companies in the same starting peer-rank decile and year (isolates the
                "strengthening" signal from simply being good already)
Run:  .venv/bin/python src/mm_proof.py
Out:  output/data/proof_data.js (Proof tab), output/proof.html, output/sheet/validation.csv
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"


def pct(v, d=1):
    return "–" if v is None or pd.isna(v) else f"{v * 100:.{d}f}%"


def pts(v):
    return "–" if v is None or pd.isna(v) else f"{v:+.1f}"


def comparisons(r: pd.DataFrame) -> dict:
    r = r.copy()
    r["strong"] = r["moat_strengthening"] & ~r["gate_removed"]
    g = r.groupby(["year", "industry_group"])
    r["dec"] = r.groupby("year")["rank0"].transform(lambda s: pd.qcut(s, 10, labels=False, duplicates="drop"))
    gm = r.groupby(["year", "dec"])
    for h in (1, 3, 5):
        for m in ("rank", "roic"):
            r[f"L_{m}{h}"] = r[f"{m}{h}"] - g[f"{m}{h}"].transform("median")
            r[f"M_{m}{h}"] = r[f"{m}{h}"] - gm[f"{m}{h}"].transform("median")
    out = {}
    for name, mask in (("Shortlist", r["shortlist"]), ("Moat Strengthening", r["strong"]), ("Rest of universe", ~r["strong"])):
        s = r[mask]
        out[name] = {c: float(s[c].median()) for c in s.columns if c[:2] in ("L_", "M_")}
        out[name]["start_rank"] = float(s["rank0"].median())
    return out


SIC2 = {28: "Chemicals & pharma", 49: "Utilities", 56: "Apparel retail", 36: "Electronic equipment", 35: "Machinery & computers",
        26: "Paper", 38: "Instruments", 53: "General merchandise", 87: "Engineering & management services", 73: "Business services & software"}


def market_html() -> str:
    path = ROOT / "output" / "data" / "market.json"
    if not path.exists():
        return ""
    m = json.loads(path.read_text())
    P = m["portfolios"]
    names = {"moat": "Moat Momentum shortlist (25)", "quality": "Quality only: same engine, level only (25)",
             "universe": "Universe, equal weight"}
    rows = ""
    for k, label in names.items():
        n, w, sv = P[k]["neutral"], P[k]["worst"], P[k]["survivors"]
        rows += (f"<tr><td><b>{label}</b></td><td class='r'><b>{pct(n['cagr'])}</b></td><td class='r'>{pct(w['cagr'])} – {pct(sv['cagr'])}</td>"
                 f"<td class='r'>{pct(n['vol'])}</td><td class='r'>{pct(n['max_dd'])}</td></tr>")
    for b in ("^SP500TR", "QUAL", "RSP"):
        n = P[b]["neutral"]
        rows += (f"<tr><td>{html.escape(P[b]['label'])}</td><td class='r'>{pct(n['cagr'])}</td><td class='r'>–</td>"
                 f"<td class='r'>{pct(n['vol'])}</td><td class='r'>{pct(n['max_dd'])}</td></tr>")
    yrs = sorted(P["moat"]["neutral"]["by_year"])
    yrows = "".join(f"<tr><td>{y}–{int(y) + 1 if y != '2025' else '26 (to Oct)'}</td>" + "".join(
        f"<td class='r'>{pct(P[k]['neutral']['by_year'][y])}</td>" for k in ("moat", "quality", "universe", "^SP500TR", "QUAL")) + "</tr>" for y in yrs)
    beat = sum(P["moat"]["neutral"]["by_year"][y] > P["^SP500TR"]["neutral"]["by_year"][y] for y in yrs)
    srows = "".join(f"<tr><td>SIC {k} · {SIC2.get(int(k), '')}</td><td class='r'>{v['n']}</td><td class='r'>{pct(v['median_excess'])}</td></tr>"
                    for k, v in m["sectors"].items())
    miss = sum(c["missing_some_months"] for c in m["coverage"])
    dead = sum(c["stopped_not_acquired"] for c in m["coverage"])
    return f"""<h2>Market validation: no excess return</h2>
<div class="card" style="border-left:4px solid var(--risk)"><p style="margin:0">From July 2013 to October 2026 the shortlist, bought every 30 June in equal weights and held for a year, returned <b>{pct(P['moat']['neutral']['cagr'])} a year</b>. The S&amp;P 500 returned {pct(P['^SP500TR']['neutral']['cagr'])}, and the equal-weight universe {pct(P['universe']['neutral']['cagr'])} using the same method. The shortlist had higher volatility ({pct(P['moat']['neutral']['vol'])} vs {pct(P['^SP500TR']['neutral']['vol'])}) and a deeper drawdown ({pct(P['moat']['neutral']['max_dd'])} vs {pct(P['^SP500TR']['neutral']['max_dd'])}). It beat the S&amp;P 500 in {beat} of {len(yrs)} years, and {pct(m['hit_rate_vs_spx'], 0)} of individual picks beat it over their year ({m['hit_n']} picks with full prices). Turnover is high: {pct(m['turnover'], 0)} of names change each year. Against the "quality only" version of the same engine it was {pct(P['moat']['neutral']['cagr'] - P['quality']['neutral']['cagr'])} a year higher, with more risk.</p></div>
<div class="tbl"><table class="num"><thead><tr><th>Portfolio</th><th class="r">CAGR (neutral)</th><th class="r">Range: worst case – survivors only</th><th class="r">Volatility</th><th class="r">Max drawdown</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small">Prices: Yahoo Finance monthly adjusted close (dividends reinvested), retrieved {m['retrieved']}. Companies without a Yahoo price for part of a year ({miss} of {25 * len(yrs)} shortlist holdings): <b>neutral</b> = those months earn the S&amp;P 500; <b>worst case</b> = companies that stopped filing with no sign of being acquired in SEC filings (8-K item 5.01, SC 14D9, SC TO-T, DEFM14A) lose 100% ({dead} holdings); <b>survivors only</b> = left out. {m['masked_bankruptcy_months']} monthly returns above +300% for companies with a bankruptcy 8-K were treated as Yahoo data errors. The equal-weight universe is likely flattered by survivorship (RSP, which includes delisted members, returned {pct(P['RSP']['neutral']['cagr'])}). Past results do not guarantee future results.</p>
<h3>Every year (July to June, neutral case)</h3><div class="tbl"><table class="num"><thead><tr><th>Year</th><th class="r">Shortlist</th><th class="r">Quality only</th><th class="r">Universe EW</th><th class="r">S&amp;P 500</th><th class="r">QUAL</th></tr></thead><tbody>{yrows}</tbody></table></div>
<h3>By sector (most-picked SIC groups)</h3><div class="tbl"><table class="num"><thead><tr><th>Sector</th><th class="r">Picks</th><th class="r">Median 12-month return vs S&amp;P 500</th></tr></thead><tbody>{srows}</tbody></table></div>"""


def bar(label: str, value: float, scale: float, kind: str) -> str:
    w = max(1.0, value / scale * 100)
    color = {"good": "var(--good)", "risk": "var(--risk)", "co": "var(--navy)", "med": "var(--neutral)"}[kind]
    return (f'<div class="funnel-row"><span>{html.escape(label)}</span><div><div class="funnel-bar" style="width:{w:.1f}%;'
            f'background:{color}"></div></div><b class="r">{value * 100:.1f}%</b></div>')


def main() -> None:
    V = json.loads((ROOT / "output" / "data" / "validation.json").read_text())["variants"]
    D = V["Default (locked v1.0)"]
    rows = pd.read_pickle(CACHE / "validation_rows.pkl")
    cmp_ = comparisons(rows)
    sl, st = D["shortlist"], D["strengthening"]
    years = sorted(D["by_year"])
    n_sl = sl["flagged"]["n"]

    groups = [("Shortlist", sl["flagged"]), ("Moat Strengthening (all)", st["flagged"]), ("Rest of universe", sl["rest"])]
    hit_bars = "".join(bar(n, g["hit_rate_3y"], 0.6, "co" if i < 2 else "med") for i, (n, g) in enumerate(groups))
    fa_bars = "".join(bar(n, g["false_alarm_3y"], 0.6, "risk" if i < 2 else "med") for i, (n, g) in enumerate(groups))
    top_bars = "".join(bar(n, g["reach_top20_roic_3y"], 0.6, "good" if i < 2 else "med") for i, (n, g) in enumerate(groups))

    year_rows = "".join(f"<tr><td>{y}</td><td class='r'>{D['by_year'][y]['n']}</td><td class='r'>{pct(D['by_year'][y]['hit_rate_3y'])}</td>"
                        f"<td class='r'>{pct(D['by_year'][y]['false_alarm_3y'])}</td><td class='r'>{pct(D['by_year'][y]['reach_top20_roic_3y'])}</td>"
                        f"<td class='r'>{pct(D['by_year'][y]['no_outcome_3y'])}</td></tr>" for y in years)
    rob = "".join(f"<tr><td>{html.escape(k)}</td><td class='r'>{pct(v['shortlist']['flagged']['hit_rate_3y'])}</td>"
                  f"<td class='r'>{pct(v['shortlist']['flagged']['false_alarm_3y'])}</td><td class='r'>{pct(v['shortlist']['flagged']['reach_top20_roic_3y'])}</td>"
                  f"<td class='r'>{v['strengthening']['flagged']['n']:,}</td><td class='r'>{pct(v['strengthening']['flagged']['hit_rate_3y'])}</td>"
                  f"<td class='r'>{pct(v['strengthening']['flagged']['false_alarm_3y'])}</td></tr>" for k, v in V.items())
    sub = "".join(f"<tr><td>{k}</td><td class='r'>{v['flagged']['n']}</td><td class='r'>{pct(v['flagged']['hit_rate_3y'])}</td>"
                  f"<td class='r'>{pct(v['flagged']['false_alarm_3y'])}</td><td class='r'>{pct(v['rest']['hit_rate_3y'])}</td>"
                  f"<td class='r'>{pct(v['rest']['false_alarm_3y'])}</td></tr>"
                  for k, v in list(D["sub_periods"].items()) + list(D["sector_exclusions"].items()))
    size = "".join(f"<tr><td>{k} (Moat Strengthening)</td><td class='r'>{v['flagged']['n']}</td><td class='r'>{pct(v['flagged']['hit_rate_3y'])}</td>"
                   f"<td class='r'>{pct(v['flagged']['false_alarm_3y'])}</td><td class='r'>{pct(v['rest']['hit_rate_3y'])}</td>"
                   f"<td class='r'>{pct(v['rest']['false_alarm_3y'])}</td></tr>" for k, v in D["size"].items())
    cmp_rows = "".join(f"<tr><td>{k}</td><td class='r'>{v['start_rank']:.0f}</td><td class='r'>{pts(v['L_rank1'])}</td><td class='r'>{pts(v['L_rank3'])}</td>"
                       f"<td class='r'>{pts(v['L_rank5'])}</td><td class='r'>{pct(v['L_roic3'])}</td><td class='r'>{pts(v['M_rank3'])}</td>"
                       f"<td class='r'>{pct(v['M_roic3'])}</td></tr>" for k, v in cmp_.items())
    names = pd.DataFrame(D["shortlist_names"])
    oc = names["outcome"].value_counts().to_dict()
    badge = {"hit": "b-good", "false alarm": "b-risk", "flat": "b-neutral", "no outcome": "b-conf"}
    name_rows = "".join(f"<tr><td>{int(r.year)}</td><td><b>{html.escape(str(r.ticker))}</b> <span class='small'>{html.escape(str(r.name).title())}</span></td>"
                        f"<td class='r'>{r.moat_score:.1f}</td><td class='r'>{'' if pd.isna(r.rank0) else f'{r.rank0:.0f}'}</td>"
                        f"<td class='r'>{'' if pd.isna(r.rank3) else f'{r.rank3:.0f}'}</td><td class='r'>{pct(r.roic0)}</td><td class='r'>{pct(r.roic3)}</td>"
                        f"<td><span class='badge {badge[r.outcome]}'>{r.outcome}</span></td></tr>"
                        for r in names.sort_values(["year", "moat_score"], ascending=[True, False]).itertuples())

    body = f"""<h1>Proof</h1>
<p class="muted">Fundamental validation, 2013–2023, Methodology v1.0 locked before the run (settings fingerprint in prompts.md round 10). Each year the screen was re-run as of 30 June using only filings made by then, including companies that later delisted. Outcomes are read from later 10-Ks. No price data is used.</p>
<div class="card" style="border-left:4px solid var(--risk)"><h3 style="margin-top:0">Main finding: the signal picks strong companies, but it does not yet predict further strengthening</h3>
<ul><li>Three years after being flagged, shortlist companies still rank <b>{pts(cmp_['Shortlist']['L_rank3'])} points</b> above their industry median on returns, margins and turnover, and their clean ROIC is <b>{pct(cmp_['Shortlist']['L_roic3'])}</b> higher. On the brief's test, they did have higher ROIC and peer rank later.</li>
<li>But they were already strong when flagged (median starting rank {cmp_['Shortlist']['start_rank']:.0f} of 100). Against companies that started at the <b>same rank</b>, their peer rank ended <b>{pts(cmp_['Shortlist']['M_rank3'])} points</b> lower after 3 years; ROIC was {pct(cmp_['Shortlist']['M_roic3'])} higher.</li>
<li>Only <b>{pct(sl['flagged']['hit_rate_3y'])}</b> of shortlist picks kept improving their position over 3 years, against {pct(sl['rest']['hit_rate_3y'])} for everyone else; <b>{pct(sl['flagged']['false_alarm_3y'])}</b> deteriorated by more than 10 points, against {pct(sl['rest']['false_alarm_3y'])}. Picking companies at the top of an improvement tends to catch the point where it slows down.</li>
<li>The result holds in every variant tried (weights ±10 points, level-heavy blend, stricter or no risk gate, 2 or 4 themes), in each sub-period and with energy or tech excluded. It is a property of the signal, not of one setting.</li></ul>
<p><b>Market test (prices, 2013–2026):</b> the shortlist returned about the same as the S&amp;P 500 and the equal-weight universe, with more volatility. There is no evidence of excess return. Details below.</p>
<p><b>What this means for the product:</b> the claim "a strengthening moat shows up in the numbers 1–3 years before it is recognised" is <b>not supported</b> by Methodology v1.0. The shortlist is a list of high-quality, improving businesses, and should not be described as predicting further improvement until a revised method passes a test on years it was not built on.</p></div>
<h2>Did the shortlist keep improving? (3 years later)</h2>
<div class="grid g3"><div class="card"><p class="ctitle">Kept improving (hit rate)</p><p class="csub">Peer rank higher after 3 years</p>{hit_bars}</div>
<div class="card"><p class="ctitle">Deteriorated (false-alarm rate)</p><p class="csub">Peer rank more than 10 points lower</p>{fa_bars}</div>
<div class="card"><p class="ctitle">Reached industry top 20% on ROIC</p><p class="csub">Within 3 years, among those not already there</p>{top_bars}</div></div>
<p class="small">Shortlist: {n_sl} picks ({sl['flagged']['companies']} companies) over 11 years. Moat Strengthening: {st['flagged']['n']:,} company-years. Rest: {sl['rest']['n']:,}. No 10-K three years later (merged, delisted, failed): shortlist {pct(sl['flagged']['no_outcome_3y'])}, rest {pct(sl['rest']['no_outcome_3y'])}; these count as neither hit nor false alarm. Source: SEC EDGAR 10-K filings 2009–2026.</p>
<h2>Later level versus industry, and versus companies starting at the same rank</h2>
<div class="tbl"><table class="num"><thead><tr><th>Group</th><th class="r">Start rank</th><th class="r">Rank vs industry +1y</th><th class="r">+3y</th><th class="r">+5y</th><th class="r">ROIC vs industry +3y</th><th class="r">Rank vs same start +3y</th><th class="r">ROIC vs same start +3y</th></tr></thead><tbody>{cmp_rows}</tbody></table></div>
<p class="small">Medians. Rank = average industry percentile of clean ROIC, gross margin, operating margin and asset turnover (0–100). "Same start": compared with companies in the same starting-rank decile in the same year.</p>
<h2>Every year</h2><div class="tbl"><table class="num"><thead><tr><th>As of 30 June</th><th class="r">Shortlist</th><th class="r">Hit rate</th><th class="r">False alarm</th><th class="r">Reached top 20%</th><th class="r">No outcome</th></tr></thead><tbody>{year_rows}</tbody></table></div>
<p class="small">2022 and 2023 have fewer than 5 years of outcomes; 3-year outcomes for 2023 use FY2025–26 filings.</p>
<h2>Robustness: everything tried</h2><div class="tbl"><table class="num"><thead><tr><th>Variant</th><th class="r">Shortlist hit</th><th class="r">Shortlist false alarm</th><th class="r">Shortlist top 20%</th><th class="r">Strengthening n</th><th class="r">Strengthening hit</th><th class="r">Strengthening false alarm</th></tr></thead><tbody>{rob}</tbody></table></div>
<p class="small">Base rate (rest of universe): hit {pct(sl['rest']['hit_rate_3y'])}, false alarm {pct(sl['rest']['false_alarm_3y'])}. Weight variants change only the order of names, so the Moat Strengthening group is identical across them.</p>
<h2>Sub-periods and sector exclusions (shortlist)</h2><div class="tbl"><table class="num"><thead><tr><th>Slice</th><th class="r">n</th><th class="r">Hit</th><th class="r">False alarm</th><th class="r">Rest: hit</th><th class="r">Rest: false alarm</th></tr></thead><tbody>{sub}{size}</tbody></table></div>
<h2>Every shortlist pick and what happened</h2><p class="small">Hits {oc.get('hit', 0)}, flat {oc.get('flat', 0)}, false alarms {oc.get('false alarm', 0)}, no outcome {oc.get('no outcome', 0)}.</p>
<details><summary>Show all {n_sl} picks</summary><div class="tbl"><table class="num"><thead><tr><th>Year</th><th>Company</th><th class="r">Moat Score</th><th class="r">Rank then</th><th class="r">Rank +3y</th><th class="r">ROIC then</th><th class="r">ROIC +3y</th><th>Outcome</th></tr></thead><tbody>{name_rows}</tbody></table></div></details>
{market_html()}
<h2>Limits of these tests</h2><ul>
<li>The fundamental test uses accounting outcomes; the market test uses Yahoo prices, which miss many companies that no longer trade (bounded with three scenarios).</li>
<li>Peer rank is relative within the industry, so the average company scores zero change by construction.</li>
<li>Levels use fiscal-year data; quarterly TTM is not used in the past runs either.</li>
<li>Companies with no later 10-K are not counted as misses; some of them failed, some were bought at a premium.</li></ul>"""
    # Demo (brief §7): rule stated before choosing: the two highest Moat Scores on the 2016 shortlist, plus the
    # highest-ranked 2016 pick whose outcome was a false alarm.
    y16 = names[names["year"] == 2016].sort_values("moat_score", ascending=False)
    demo = pd.concat([y16.head(2), y16[y16["outcome"] == "false alarm"].head(1)])
    lesson = {"hit": "The screen saw a strengthening position and it kept strengthening: the case the method is built for.",
              "flat": "Position held but did not improve further: a good company, not a strengthening one. This is the most common pattern (see Proof).",
              "false alarm": "The improvement reversed. Picks like this are why the shortlist's false-alarm rate (38%) is higher than the universe's (22%).",
              "no outcome": "No later 10-K: the company was acquired, merged or delisted."}
    cards = "".join(
        f"<div class='card'><span class='badge {badge[r.outcome]}'>{r.outcome}</span><h3>{html.escape(str(r.name).title())}</h3>"
        f"<p class='small'>Picked 30 June 2016 on FY{int(r.fy)} 10-K · Moat Score {r.moat_score:.1f}</p>"
        f"<div class='tbl'><table class='num'><tbody><tr><td>Industry peer rank</td><td class='r'>{r.rank0:.0f} → {'' if pd.isna(r.rank3) else f'{r.rank3:.0f}'}</td></tr>"
        f"<tr><td>Clean ROIC</td><td class='r'>{pct(r.roic0)} → {pct(r.roic3)}</td></tr></tbody></table></div>"
        f"<p class='small'>Then → 3 fiscal years later. Source: SEC EDGAR 10-K filings.</p><p>{lesson[r.outcome]}</p></div>"
        for r in demo.itertuples())
    demo_html = f"""<h1>Demo</h1><p class="muted">A guided walk through the tool in five steps, then three real cases from the 2013–2023 back-test.</p>
<ol><li><b>Screener:</b> start from the shortlist. Each row shows the Moat Score, how many of the 5 themes are improving, and the top reason. <a href="#screener">Open</a></li>
<li><b>Change a setting:</b> move “Level” up to 70 (or pick the “Proven Leaders” scenario) and watch which names join and drop.</li>
<li><b>Deep-Dive:</b> click a company. Read Key observations first, then the charts; every number links to its 10-K. <a href="#deepdive">Open</a></li>
<li><b>Learn:</b> each indicator explained with a worked example. <a href="#learn">Open</a></li>
<li><b>Proof:</b> what happened to past picks, including the misses. <a href="#proof">Open</a></li></ol>
<h2>Three cases from 2016</h2><p class="small">Chosen by a rule fixed before looking: the two highest Moat Scores on the 2016 shortlist, plus the highest-ranked 2016 pick that became a false alarm.</p>
<div class="grid g3">{cards}</div>"""
    (ROOT / "output" / "data" / "demo_data.js").write_text("window.MM_DEMO = " + json.dumps({"html": demo_html}) + ";\n", encoding="utf-8")
    (ROOT / "output" / "data" / "proof_data.js").write_text("window.MM_PROOF = " + json.dumps({"html": body}) + ";\n", encoding="utf-8")
    css = (ROOT / "output" / "moat_momentum.html").read_text(encoding="utf-8").split('<style id="mm-style">')[1].split("</style>")[0]
    (ROOT / "output" / "proof.html").write_text(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Moat Momentum Proof</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet"><style>{css}</style></head>
<body><div class="wrap"><header class="bar"><span class="wordmark"><span>Moat Momentum</span></span><span class="tagline">Proof · Methodology v1.0</span></header>{body}
<div class="disclaimer">Research tool, not investment advice. Past results do not guarantee future results. Source: SEC EDGAR.</div></div></body></html>""", encoding="utf-8")
    with open(ROOT / "output" / "sheet" / "validation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Variant", "Shortlist picks", "Shortlist hit rate 3y", "Shortlist false alarm 3y", "Shortlist reached top 20% ROIC",
                    "Strengthening n", "Strengthening hit rate 3y", "Strengthening false alarm 3y", "Rest hit rate 3y", "Rest false alarm 3y"])
        for k, v in V.items():
            a, b = v["shortlist"], v["strengthening"]
            w.writerow([k, a["flagged"]["n"], a["flagged"]["hit_rate_3y"], a["flagged"]["false_alarm_3y"], a["flagged"]["reach_top20_roic_3y"],
                        b["flagged"]["n"], b["flagged"]["hit_rate_3y"], b["flagged"]["false_alarm_3y"], a["rest"]["hit_rate_3y"], a["rest"]["false_alarm_3y"]])
    print(json.dumps({k: {kk: round(vv, 3) for kk, vv in v.items() if kk in ("start_rank", "L_rank3", "M_rank3", "L_roic3", "M_roic3")} for k, v in cmp_.items()}))
    print("outcomes", oc)


if __name__ == "__main__":
    main()
