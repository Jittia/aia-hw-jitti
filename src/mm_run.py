"""Moat Momentum · official live run → data for the web page, the Sheet and the track record.

Run:  .venv/bin/python src/mm_run.py [--as-of 2026-11-03]
Out:  output/data/results.csv        one row per universe company (scores, gate, confidence, reasons)
      output/data/site_data.js       everything the web page needs (embedded, works offline)
      data/cache/mm/run_latest.pkl   full results for the Sheet writer and the track record
"""
from __future__ import annotations

import argparse
import json
import math
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mm_fundamentals import scoring_table
from mm_score import INDICATORS, THEME_NAMES, THEMES, score_as_of
from mm_valuation import valuation

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"
OUTD = ROOT / "output" / "data"

SERIES = ["revenue", "gross_profit", "op_income", "one_offs", "clean_oi", "clean_ni", "fcf",
          "roic", "roic_ex_gw", "incr_roic", "gross_margin", "gp_assets", "gm_stability", "op_margin", "incr_margin",
          "sga_rev", "asset_turnover", "rev_growth", "rev_excess", "peer_level_rank", "fcf_conv", "accruals",
          "reinvest_rate", "nd_ebitda", "interest_cover", "altman_z", "shares", "sbc_rev", "gw_assets",
          "impairment", "restructuring", "litigation", "acq_costs", "gains", "gains_business"]
MEDIAN_SERIES = ["roic", "gross_margin", "gp_assets", "op_margin", "sga_rev", "asset_turnover", "rev_growth",
                 "fcf_conv", "accruals", "nd_ebitda", "interest_cover", "altman_z", "sbc_rev"]
SIG_LABEL = {  # v2.0 Compounder Signal (experimental second list; spec docs/specs/2026-11-03-compounder-signal-design.md)
    "s01_roic_chg": "ROIC change vs a year earlier", "s02_incr_roic": "Return on capital added in the last year",
    "s03_gm_chg": "Gross margin vs same quarter last year", "s04_gm_accel": "Gross-margin acceleration",
    "s05_om_chg": "Operating margin vs same quarter last year", "s08_rev_excess": "Revenue growth vs industry (latest quarter)",
    "s09_rev_accel": "Revenue-growth acceleration", "s10_peer_rank_chg": "Peer-rank change over 4 quarters",
    "s11_fcf_margin_chg": "Free-cash-flow margin change", "s14_roic_rank": "ROIC rank in industry",
}
IND_LABEL = {
    "roic_spread": "Clean ROIC minus hurdle", "incr_roic": "Incremental ROIC (3 yrs)", "gross_margin": "Gross margin",
    "gp_assets": "Gross profit ÷ assets", "gm_stability": "Gross-margin stability", "incr_margin": "Incremental operating margin (3 yrs)",
    "sga_rev": "SG&A ÷ revenue", "asset_turnover": "Asset turnover", "rev_excess": "Revenue growth vs industry (3-yr CAGR)",
    "peer_rank_change": "Peer rank change (3 yrs)", "fcf_conv": "FCF ÷ clean net income", "accruals": "Accruals ÷ assets",
    "runway": "Reinvestment × incremental ROIC",
}


def filing_url(cik: int, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{str(accn).replace('-', '')}/{accn}-index.htm"


def pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:.{d}f}%"


def num(x, d=1, suffix="x"):
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{d}f}{suffix}"


def usd(x):
    if x is None or not np.isfinite(x):
        return "n/a"
    a = abs(x)
    return f"${x / 1e9:.1f}B" if a >= 1e9 else f"${x / 1e6:.0f}M"


def _hist(panel: pd.DataFrame, cik: int, fy: int, n: int = 10) -> pd.DataFrame:
    h = panel[(panel["cik"] == cik) & (panel["fy"] <= fy)].sort_values("fy").tail(n)
    return h.set_index("fy")


def _v(h: pd.DataFrame, fy: int, col: str):
    try:
        v = h.loc[fy, col]
        return float(v) if pd.notna(v) else None
    except KeyError:
        return None


def _label(h: pd.DataFrame, fy: int) -> str:
    """Display name of a point in the series: 'FY2025' or 'TTM Sep 2026' (12 months to that 10-Q)."""
    try:
        return str(h.loc[fy, "period"])
    except KeyError:
        return f"FY{fy}"


def observations(row: pd.Series, h: pd.DataFrame, med: pd.DataFrame, settings: dict) -> list[dict]:
    """Deterministic GOOD / NEUTRAL / RISK observations; risks first; at most 10."""
    fy, cik = int(row["fy"]), int(row["cik"])
    link = filing_url(cik, row["accn"])
    src = f"10-Q, {row['period']}" if row.get("is_ttm") else f"10-K {row['period']}"
    rg = settings["risk_gate"]
    m = lambda col: _v(med, fy, col)  # noqa: E731
    P = lambda y: _label(h, y)  # noqa: E731
    obs = []

    def add(kind, text):
        obs.append({"kind": kind, "text": text, "link": link, "src": src})

    risk_txt = {
        "interest_cover": lambda: f"Interest cover was {num(row['interest_cover'])} in {P(fy)} (clean operating income ÷ interest), threshold {rg['interest_cover']['below']}x.",
        "net_debt_ebitda": lambda: (f"Net debt ÷ EBITDA was {num(row['nd_ebitda'])} in {P(fy)}, threshold {rg['net_debt_ebitda']['above']}x." if np.isfinite(row['nd_ebitda'])
                                    else f"EBITDA was zero or negative in {P(fy)} while the company had net debt of {usd(row['net_debt'])}."),
        "altman_z": lambda: f"Altman Z'' was {num(row['altman_z'], 2, '')} in {P(fy)}; below {rg['altman_z']['below']} is the distress zone.",
        "beneish_m": lambda: f"Beneish M-Score was {num(row['beneish_m'], 2, '')} in {P(fy)}, above the {rg['beneish_m']['above']} threshold that can signal earnings manipulation.",
        "dilution": lambda: f"Diluted share count grew {pct(row['dilution'])} a year over 3 years to {P(fy)}, threshold {pct(rg['dilution']['above'], 0)}.",
        "sbc_revenue": lambda: f"Stock-based compensation was {pct(row['sbc_rev'])} of revenue in {P(fy)}, threshold {pct(rg['sbc_revenue']['above'], 0)}.",
        "goodwill_jump": lambda: f"Goodwill added over 3 years equals {pct(row['goodwill_jump'])} of assets ({P(fy)}), threshold {pct(rg['goodwill_jump']['above'], 0)}: growth may be bought.",
    }
    for rule, fn in risk_txt.items():
        if row.get(f"gate_{rule}_breach"):
            add("RISK", fn())
        elif row.get(f"gate_{rule}_worsening"):
            add("RISK", fn() + " Not yet over the threshold, but it has worsened 3 years in a row.")
    oi = row.get("op_income")
    if pd.notna(oi) and oi != 0 and abs(row["one_offs"]) > 0.25 * abs(oi):
        add("RISK", f"One-off items of {usd(row['one_offs'])} were added back in {P(fy)} ({pct(row['one_offs'] / abs(oi), 0)} of reported operating income); check them in the filing.")
    gap = row.get("oi_check_gap")
    if pd.notna(gap) and gap > 0.10:
        add("RISK", f"Tagged operating income ({usd(oi)}) differs from revenue minus total costs ({usd(row['revenue'] - row['costs_total'])}) by {pct(gap, 0)} of operating income in {P(fy)}; the tag may be a segment total. Data confidence lowered.")
    if row["confidence"] == "Low":
        add("RISK", f"Data confidence is Low: only {pct(row['coverage'], 0)} of core items are tagged over the last 5 years.")

    fy4 = fy - 4
    r0, r4 = _v(h, fy, "roic"), _v(h, fy4, "roic")
    if r0 is not None and r4 is not None:
        kind = "GOOD" if r0 > r4 and r0 > settings["hurdle_rate"] else ("RISK" if r0 < r4 - 0.03 else "NEUTRAL")
        add(kind, f"Clean ROIC moved from {pct(r4)} ({P(fy4)}) to {pct(r0)} ({P(fy)}); hurdle {pct(settings['hurdle_rate'], 0)}, industry median {pct(m('roic'))}.")
    g0, g4 = _v(h, fy, "gross_margin"), _v(h, fy4, "gross_margin")
    if g0 is not None and g4 is not None:
        kind = "GOOD" if g0 - g4 >= 0.02 else ("RISK" if g0 - g4 <= -0.03 else "NEUTRAL")
        add(kind, f"Gross margin moved from {pct(g4)} ({P(fy4)}) to {pct(g0)} ({P(fy)}); industry median {pct(m('gross_margin'))}.")
    s0, s4 = _v(h, fy, "sga_rev"), _v(h, fy4, "sga_rev")
    if s0 is not None and s4 is not None:
        kind = "GOOD" if s4 - s0 >= 0.02 else ("RISK" if s0 - s4 >= 0.03 else "NEUTRAL")
        add(kind, f"SG&A ÷ revenue moved from {pct(s4)} ({P(fy4)}) to {pct(s0)} ({P(fy)}); industry median {pct(m('sga_rev'))}.")
    ex = row.get("rev_excess")
    if pd.notna(ex):
        kind = "GOOD" if ex >= 0.05 else ("RISK" if ex <= -0.05 else "NEUTRAL")
        add(kind, f"Revenue grew {pct(row['rev_cagr3'])} a year over 3 years to {P(fy)}, {pct(ex)} versus the industry median.")
    fc = row.get("fcf_conv")
    if pd.notna(fc):
        kind = "GOOD" if fc >= 0.9 else ("RISK" if fc < 0.5 else "NEUTRAL")
        add(kind, f"Free cash flow was {pct(fc, 0)} of clean net income in {P(fy)} ({usd(row['fcf'])} vs {usd(row['clean_ni'])}).")
    order = {"RISK": 0, "GOOD": 1, "NEUTRAL": 2}
    return sorted(obs, key=lambda o: order[o["kind"]])[:10]


def top_reasons(row: pd.Series, h: pd.DataFrame) -> list[str]:
    fy = int(row["fy"])
    P = lambda y: _label(h, y)  # noqa: E731
    scores = {n: row[f"ind_{n}"] for n, *_ in INDICATORS if pd.notna(row.get(f"ind_{n}"))}
    best = sorted(scores, key=scores.get, reverse=True)[:3]
    txt = {
        "roic_spread": lambda: f"Clean ROIC {pct(_v(h, fy - 4, 'roic'))} → {pct(row['roic'])} ({P(fy - 4)} to {P(fy)})",
        "incr_roic": lambda: f"Incremental ROIC {'over 200%' if row['incr_roic'] >= 2 else pct(row['incr_roic'], 0)} on capital added over 3 yrs",
        "gross_margin": lambda: f"Gross margin {pct(_v(h, fy - 4, 'gross_margin'))} → {pct(row['gross_margin'])}",
        "gp_assets": lambda: f"Gross profit ÷ assets {pct(row['gp_assets'], 0)}",
        "gm_stability": lambda: "Gross margin among the steadiest in its industry",
        "incr_margin": lambda: f"Incremental operating margin {pct(row['incr_margin'], 0)} over 3 yrs",
        "sga_rev": lambda: f"SG&A ÷ revenue {pct(_v(h, fy - 4, 'sga_rev'))} → {pct(row['sga_rev'])}",
        "asset_turnover": lambda: f"Asset turnover {num(_v(h, fy - 4, 'asset_turnover'), 2)} → {num(row['asset_turnover'], 2)}",
        "rev_excess": lambda: f"Revenue {pct(row['rev_cagr3'])} a year over 3 yrs, {pct(row['rev_excess'])} vs industry median",
        "peer_rank_change": lambda: f"Peer rank up {row['peer_rank_change']:.0f} points in 3 yrs",
        "fcf_conv": lambda: f"FCF {pct(row['fcf_conv'], 0)} of clean net income",
        "accruals": lambda: f"Low accruals ({pct(row['accruals'])} of assets)",
        "runway": lambda: f"Reinvests {pct(row['reinvest_rate'], 0)} of NOPAT at {pct(row['incr_roic'], 0)} incremental ROIC",
    }
    def clean(t: str) -> str:
        # a start year with no value: say the latest value instead of "n/a → x"
        return re.sub(r"n/a → ([^ ]+)( \((?:FY\d{4}|TTM \w{3} \d{4}) to (FY\d{4}|TTM \w{3} \d{4})\))?",
                      lambda m: f"{m.group(1)}" + (f" in {m.group(3)}" if m.group(3) else ""), t)
    return [f"{IND_LABEL[n]} — {clean(txt[n]())}" for n in best]


def _clean(x):
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(x) else float(f"{x:.4g}")
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def moat_map_rec(mmap: pd.DataFrame, cik: int) -> dict | None:
    """Per-company Moat Map block for the web page (v3.0)."""
    if cik not in mmap.index:
        return None
    r = mmap.loc[cik]
    trail = [[_clean(r.get(f"x_t{k}")), _clean(r.get(f"y_t{k}"))] for k in (5, 4, 3, 2, 1)]
    keys = ("x", "y", "d", "moved", "ev", "ev_sales", "ev_ebit", "pe", "fcf_yield", "g_implied", "gap", "mcap",
            "backlog_g", "defrev_g", "rnd_int", "capex_int", "ind_med_x")
    out = {k: _clean(r.get(k)) for k in keys}
    out.update({"quad": r.get("quadrant") if isinstance(r.get("quadrant"), str) else None, "trail": trail,
                "r1": bool(r.get("r1")), "r2": bool(r.get("r2")), "r3": bool(r.get("r3")),
                "top": [k for k in ("r1", "r2", "r3") if bool(r.get(f"top_{k}"))]})
    return out


def scenario_eval(disc: dict) -> dict:
    """Back-test results per scenario shown in the Screener's list tabs (validation.json, market.json, discovery.json)."""
    V = json.loads((OUTD / "validation.json").read_text())["variants"]
    mk = json.loads((OUTD / "market.json").read_text())
    def sl(key):
        f, r = V[key]["shortlist"]["flagged"], V[key]["shortlist"]["rest"]
        return {"hit": f["hit_rate_3y"], "fa": f["false_alarm_3y"], "top20": f["reach_top20_roic_3y"], "n": f["n"],
                "rest_hit": r["hit_rate_3y"], "rest_fa": r["false_alarm_3y"]}
    def mkt(key):
        P = mk["portfolios"]
        return {"cagr": P[key]["neutral"]["cagr"], "spx": P["^SP500TR"]["neutral"]["cagr"]} if key in P else {}
    w = mk.get("compounder", {}).get("windows", {})
    lf = disc.get("label_fix", {})
    return {
        "Early Moat — Default": {**sl("Default (locked settings)"), "cagr": mk["portfolios"]["moat"]["neutral"]["cagr"],
                                 "spx": mk["portfolios"]["^SP500TR"]["neutral"]["cagr"]},
        "Proven Leaders": {**sl("Proven Leaders (70% level)"), **mkt("proven")},
        "Strict Risk": {**sl("Strict Risk (all rules remove)"), **mkt("strict")},
        "Compounder": {"test_multiple": lf.get("test", {}).get("multiple"), "train_multiple": lf.get("train", {}).get("multiple"),
                       "test_base": lf.get("test", {}).get("base_rate"),
                       "cagr_test": w.get("test 2020-2023", {}).get("compounder_neutral", {}).get("cagr"),
                       "spx_test": w.get("test 2020-2023", {}).get("sp500", {}).get("cagr"),
                       "cagr_all": w.get("all 2013-2023", {}).get("compounder_neutral", {}).get("cagr"),
                       "spx_all": w.get("all 2013-2023", {}).get("sp500", {}).get("cagr")},
    }


def main(as_of: str) -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    facts = pd.read_pickle(CACHE / "facts.pkl")
    companies = pd.read_pickle(CACHE / "companies.pkl")
    d, cand = scoring_table(facts, as_of, settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"],
                            ttm=bool(settings["data"].get("ttm")), with_quarters=True)
    out = score_as_of(d, companies, as_of, settings, live=True)
    # last 12 quarters of 12-month figures (10-Q TTM points and fiscal-year ends) for the quarterly chart
    cand = cand[cand["filed"] <= pd.Timestamp(as_of)].sort_values(["cik", "end"])
    cand = cand.drop_duplicates(["cik", "end"], keep="first")
    quarters = {c: g.tail(settings["data"]["quarters"]) for c, g in cand.groupby("cik")}
    res, pctl, panel = out["results"], out["pct"], out["panel"]

    # v2.0 Compounder Signal: experimental second list (failed its 2020–2023 test; output/data/discovery.json)
    from mm_discover import combine
    from mm_signals import signals_at
    disc = json.loads((OUTD / "discovery.json").read_text())
    kept = disc["kept"]
    sx = signals_at(facts, companies, as_of, settings, live=True).set_index("cik")
    sx["cs"] = combine(sx, kept)
    elig = sx[~sx["gate_removed"].astype(bool) & sx["cs"].notna()].sort_values("cs", ascending=False)
    sx["cs_rank"] = pd.Series(np.arange(1, len(elig) + 1), index=elig.index)
    sx["cs_short"] = sx["cs_rank"] <= settings["compounder"]["shortlist_size"]

    # market value and clean P/E (display only)
    from mm_market import BENCH, prices
    lat = cand.sort_values("end").drop_duplicates("cik", keep="last")[["cik", "clean_ni", "shares", "revenue"]]
    lat = lat.merge(res.loc[res["in_universe"], ["cik", "ticker"]], on="cik")
    # cover-page shares in the units Yahoo prices: ADS tickers divided by ordinary shares per ADS (SEC 10-K cover;
    # src/mm_adr.py; BeOne ONC 13, Zai Lab ZLAB 10)
    from mm_adr import adjust_cover, load_ratios
    cover_all = adjust_cover(pd.read_pickle(CACHE / "cover_shares.pkl"), load_ratios())
    cov = cover_all
    cov = cov[cov["filed"] <= pd.Timestamp(as_of)].sort_values(["filed", "end"]).drop_duplicates("cik", keep="last")
    lat["cover_shares"] = lat["cik"].map(cov.set_index("cik")["val"])
    px = prices(sorted({t.replace(".", "-") for t in lat["ticker"].dropna()}) + list(BENCH))
    val = valuation(lat, px).set_index("cik")

    # v3.0 Moat Map + Expectation Gap (spec docs/specs/2026-11-04-moat-map-v3-design.md); its rules failed the
    # one-time 2021–2023 test (output/data/v3_test.json) and are shown as a description, labelled failed
    from mm_market import prices_daily
    from mm_moatmap import leading_at, map_at, top25, value_at
    from mm_quarterly import ttm_panel
    tpanel = ttm_panel(facts, as_of, settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"])
    mmap = map_at(facts, companies, as_of, settings, live=True, panel=tpanel)
    daily = prices_daily(sorted({t.replace(".", "-") for t in mmap["ticker"].dropna()}))
    mmap = value_at(mmap.assign(ticker=mmap["ticker"].map(lambda t: t.replace(".", "-") if isinstance(t, str) else t)),
                    as_of, px, cover_all, live=True, daily=daily)

    # Screener (spec docs/specs/2026-11-04-screener-design.md): risk measures and four 2×2 groups, now and 4 quarters
    # back. Untested screening tool; filters, thresholds and lists are computed in the page.
    from mm_market import splits_history
    from mm_screener import screener_block
    scr = screener_block(tpanel, mmap[["cik", "ticker", "ev"]], px, splits_history(sorted(mmap["ticker"].dropna().unique())),
                         cover_all, as_of)
    scr["meta"] |= {"price_date": daily.attrs.get("date"), "prices_retrieved": daily.attrs.get("retrieved"),
                    "sec_retrieved": settings["data"]["sec_retrieved"]}
    mmap = leading_at(mmap, pd.read_pickle(CACHE / "leading.pkl"), as_of)
    for rule in ("r1", "r2", "r3"):
        mmap[f"top_{rule}"] = mmap.index.isin(top25(mmap, rule).index)
    mmap = mmap.set_index("cik")
    u = res[res["in_universe"]].copy()
    u["grp"] = u["industry_group"]

    # industry medians per peer group and fiscal year (for charts and observations)
    panel = panel.merge(u[["cik", "grp"]], on="cik", how="left")
    meds = panel[panel["grp"].notna()].groupby(["grp", "fy"])[MEDIAN_SERIES].median()

    comp = companies.set_index("cik")
    PCT_COLS = [c for c in pctl.columns if c != "industry_group"]
    rows, deep = [], {}
    for i, r in u.iterrows():
        cik, fy = int(r["cik"]), int(r["fy"])
        h = _hist(panel, cik, fy)
        h["gw_assets"] = h["goodwill"] / h["assets"]
        med = meds.loc[r["grp"]] if r["grp"] in meds.index.get_level_values(0) else pd.DataFrame()
        r["reasons"] = top_reasons(r, h)
        obs = observations(r, h, med, settings)
        filings = comp.at[cik, "filings"]
        links = {}
        for form, date, accn, doc in filings:
            if form in ("10-K", "10-Q", "8-K") and form not in links:
                links[form] = {"date": date, "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}"}
        qq = quarters.get(cik, pd.DataFrame())
        deep[cik] = {
            "years": [int(y) for y in h.index], "periods": [str(p) for p in h["period"]],
            "q": {"end": [str(e.date()) for e in qq["end"]], "ttm": [bool(t) for t in qq["is_ttm"]],
                  "revenue": [_clean(v) for v in qq["revenue"]],
                  "gross_margin": [_clean(v) for v in (qq["gross_profit"] / qq["revenue"])],
                  "op_margin": [_clean(v) for v in (qq["clean_oi"] / qq["revenue"])],
                  "fcf_margin": [_clean(v) for v in (qq["fcf"] / qq["revenue"])]} if len(qq) else None,
            "s": {c: [_clean(v) for v in h[c].to_numpy()] for c in SERIES if c in h},
            "obs": obs, "links": links,
            "accn": [str(a) for a in h["accn"]], "filed": [str(f.date()) for f in h["filed"]],
        }
        rec = {
            "cik": cik, "ticker": r["ticker"], "name": r["name"], "sic": int(r["sic"]), "sic_desc": r["sic_desc"],
            "group": r["grp"], "fy": fy, "period": r["period"], "ttm": bool(r["is_ttm"]), "fy_end": str(r["end"].date()), "filed": str(r["filed"].date()),
            "accn": r["accn"], "revenue": r["revenue"], "confidence": r["confidence"], "coverage": r["coverage"],
            "years": int(r["years"]), "reasons": r["reasons"],
            "risk": {k: (999.0 if r[f"gate_{k}"] == np.inf else _clean(r[f"gate_{k}"])) for k in ("interest_cover", "net_debt_ebitda", "altman_z", "beneish_m",
                                                        "dilution", "sbc_revenue", "goodwill_jump")},
            "worse": [k for k in ("interest_cover", "net_debt_ebitda", "altman_z") if r[f"gate_{k}_worsening"]],
            "pct": [_clean(pctl.at[i, c]) for c in PCT_COLS],
            "moat_score": r["moat_score"], "rank": r["rank"], "shortlist": bool(r["shortlist"]),
            "strengthening": bool(r["moat_strengthening"]), "removed": bool(r["gate_removed"]),
            "flags": int(r["gate_flags"]), "gate_reasons": r["gate_reasons"],
            "mcap": _clean(val["mcap"].get(cik)), "pe": _clean(val["pe"].get(cik)), "price": _clean(val["price"].get(cik)),
            "mcap_check": bool(val["check"].get(cik, False)), "shares_src": val["shares_source"].get(cik),
            "cs": _clean(sx["cs"].get(cik)), "cs_rank": _clean(sx["cs_rank"].get(cik)),
            "cs_short": bool(sx["cs_short"].get(cik, False)),
            "mm": moat_map_rec(mmap, cik),
            "sig": [_clean(sx[f"r_{n}"].get(cik)) for n in kept],
            "themes": {t: _clean(r[f"theme_{t}"]) for t in THEMES},
            "improving": {t: _clean(r[f"improving_{t}"]) for t in THEMES},
        }
        rows.append({k: _clean(v) if not isinstance(v, (dict, list)) else v for k, v in rec.items()})

    lt = res
    funnel = [
        ["Companies with SEC XBRL data (non-financial SIC, revenue ≥ $50M at least once)", len(companies)],
        ["Latest 10-K or 10-Q covers a period ending in the last 18 months" if settings["data"].get("ttm")
         else "Annual report filed in the last 18 months", len(lt)],
        ["Listed on a US exchange", int(lt["exchange"].isin(settings["universe"]["exchanges"]).sum())],
        ["Revenue ≥ $100M and ≥ 5 fiscal years (universe)", len(u)],
        ["Pass the risk gate (no Remove rule hit)", int((~u["gate_removed"]).sum())],
        ["Moat Strengthening (≥ 3 of 5 themes improving)", int((~u["gate_removed"] & u["moat_strengthening"]).sum())],
        ["Shortlist", int(u["shortlist"].sum())],
    ]
    med_out = {}
    for g in u["grp"].dropna().unique():
        mg = meds.loc[g]
        mg = mg[mg.index >= 2010]
        med_out[g] = {"years": [int(y) for y in mg.index], **{c: [_clean(v) for v in mg[c].to_numpy()] for c in MEDIAN_SERIES}}
    t = disc.get("test", {})
    meta_v2 = {"kept": [{"name": n, "dir": d, "label": SIG_LABEL[n]} for n, d in kept.items()],
               "test": {k: t.get(k) for k in ("top_rate", "base_rate", "multiple", "passed")},
               "train_multiple": None, "shortlist_size": settings["compounder"]["shortlist_size"]}
    meta_val = {"price_month": str(px.index[-1]), "prices_retrieved": px.attrs.get("retrieved"),
                "source": "Yahoo Finance month-end close × SEC cover-page shares outstanding (else diluted shares); P/E on clean net income (12 months)"}
    v3 = json.loads((OUTD / "v3_test.json").read_text()) if (OUTD / "v3_test.json").exists() else {}
    meta_mm = {"price_date": daily.attrs.get("date"), "prices_retrieved": daily.attrs.get("retrieved"),
               "assumptions": {"horizon_years": 10, "discount": 0.09, "terminal_growth": 0.03, "tax": 0.21,
                               "hurdle": 0.09, "growth_line": 0.10},
               "coverage": {"xy": float((mmap["x"].notna() & mmap["y"].notna()).mean())}
                           | {k: float(mmap[c].notna().mean()) for k, c in (("gap", "gap"), ("backlog", "backlog_g"),
                            ("defrev", "defrev_g"), ("rnd", "rnd_int"), ("capex", "capex_int"))},
               "test": {k: v3.get(k) for k in ("rules", "top25", "no_rebound", "compare", "still_top_right", "coverage")}
               | {"split_fix": {k: v for k, v in v3.get("split_fix", {}).items() if k != "price_r3"}}
               | {"price": {r: {k: x for k, x in v.items() if k != "per_date"} for r, v in v3.get("price", {}).items()}}}
    meta = {"as_of": as_of, "compounder": meta_v2, "moatmap": meta_mm, "valuation": meta_val, "scenario_eval": scenario_eval(disc), "medians": med_out, "pct_cols": PCT_COLS, "methodology": settings["methodology_version"], "sec_retrieved": settings["data"]["sec_retrieved"],
            "settings": settings, "funnel": funnel,
            "indicators": [{"name": n, "theme": t, "comps": c, "label": IND_LABEL[n]} for n, t, _col, _d, c in INDICATORS],
            "themes": [{"key": t, "name": THEME_NAMES[t]} for t in THEMES],
            "gate_counts": {k: {"breach": int(u[f"gate_{k}_breach"].sum()), "worsening": int(u[f"gate_{k}_worsening"].sum())}
                            for k in ("interest_cover", "net_debt_ebitda", "altman_z", "beneish_m", "dilution", "sbc_revenue", "goodwill_jump")},
            "confidence": u["confidence"].value_counts().to_dict()}
    OUTD.mkdir(parents=True, exist_ok=True)
    (OUTD / "site_data.js").write_text(
        "window.MM = " + json.dumps({"meta": meta, "companies": rows, "scr": scr}, separators=(",", ":"), default=str) + ";\n",
        encoding="utf-8")
    (OUTD / "deep_data.js").write_text(
        "window.MM_DEEP = " + json.dumps({str(k): v for k, v in deep.items()}, separators=(",", ":"), default=str) + ";\n",
        encoding="utf-8")
    flat = pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, (dict, list))} | r["risk"] | {
        **{f"theme_{t}": r["themes"][t] for t in THEMES}, "reasons": " | ".join(r["reasons"])} for r in rows])
    flat.sort_values("rank").to_csv(OUTD / "results.csv", index=False)
    res.to_pickle(CACHE / "run_latest.pkl")
    print(f"as of {as_of}: universe {len(u)}, shortlist {int(u['shortlist'].sum())}; wrote {OUTD}")
    for name, n in funnel:
        print(f"  {n:>6,}  {name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-11-03")
    main(ap.parse_args().as_of)
