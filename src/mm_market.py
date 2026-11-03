"""Moat Momentum · step 6 (brief §6B): market validation with Yahoo prices + SEC bounds for companies that stopped trading.

Portfolios, rebuilt every 30 June 2013–2025 with Methodology v1.0 (point-in-time, no exchange filter), equal weight,
held 12 months (buy and hold), then rebalanced:
  Moat Momentum  the shortlist (25)
  Quality only   the same engine with blend 100% level / 0% trend / 0% consistency (25): a "known quality" baseline
  Universe EW    every universe company that year
Benchmarks from Yahoo: S&P 500 total return (^SP500TR), iShares MSCI USA Quality Factor ETF (QUAL, from Jul 2013),
Invesco S&P 500 Equal Weight ETF (RSP).

Companies with no Yahoo price for part of a holding year are filled three ways (each reported):
  survivors only  drop them (what a naive test shows)
  neutral         missing months earn the S&P 500 total return
  worst case      as neutral, but a company that stopped filing and shows no sign of being acquired in its SEC
                  filings (8-K item 5.01, SC 14D9, SC TO-T, DEFM14A) loses 100% in its first missing month
SEC status: 8-K item 1.03 = bankruptcy; acquisition signs as above.

Run:  .venv/bin/python src/mm_market.py
Out:  output/data/market.json, data/cache/mm/prices_monthly.pkl (Yahoo, retrieved on run date)
"""
from __future__ import annotations

import copy
import json
import warnings
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import yfinance as yf

from mm_fundamentals import annual_table
from mm_score import score_as_of

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "mm"
YEARS = list(range(2013, 2026))
BENCH = {"^SP500TR": "S&P 500 (total return)", "QUAL": "MSCI USA Quality ETF (QUAL)", "RSP": "S&P 500 Equal Weight ETF (RSP)"}


def portfolios(settings: dict) -> pd.DataFrame:
    path = CACHE / "market_portfolios.pkl"
    if path.exists():
        return pd.read_pickle(path)
    facts, companies = pd.read_pickle(CACHE / "facts.pkl"), pd.read_pickle(CACHE / "companies.pkl")
    q = copy.deepcopy(settings)
    q["scoring"]["blend"] = {"level": 100, "trend": 0, "consistency": 0}
    q["scoring"]["confirm_themes"] = 0  # quality only: no improvement requirement
    rows = []
    for y in YEARS:
        as_of = f"{y}-06-30"
        d = annual_table(facts, as_of, settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"])
        a = score_as_of(d, companies, as_of, settings, live=False)["results"]
        b = score_as_of(d, companies, as_of, q, live=False)["results"]
        a = a[a["in_universe"]]
        qual = set(b.loc[b["shortlist"], "cik"])
        for _, r in a.iterrows():
            rows.append({"year": y, "cik": int(r["cik"]), "sic": int(r["sic"]), "moat": bool(r["shortlist"]),
                         "quality": int(r["cik"]) in qual})
        print(f"  portfolios {y}: universe {len(a)}", flush=True)
    p = pd.DataFrame(rows)
    p.to_pickle(path)
    return p


def prices(tickers: list[str]) -> pd.DataFrame:
    path = CACHE / "prices_monthly.pkl"
    if path.exists():
        return pd.read_pickle(path)
    frames = []
    for i in range(0, len(tickers), 200):
        chunk = tickers[i:i + 200]
        data = yf.download(chunk, start="2013-05-01", end="2026-11-01", interval="1mo", auto_adjust=True,
                           progress=False, threads=True, group_by="column")
        frames.append(data["Close"] if len(chunk) > 1 else data[["Close"]].rename(columns={"Close": chunk[0]}))
        print(f"  prices {min(i + 200, len(tickers))}/{len(tickers)}", flush=True)
    px = pd.concat(frames, axis=1)
    px.index = pd.to_datetime(px.index).to_period("M")
    px = px.loc[:, ~px.columns.duplicated()]
    px.attrs["retrieved"] = str(date.today())
    px.to_pickle(path)
    return px


def sec_status(ciks: set[int]) -> pd.DataFrame:
    rows = []
    with zipfile.ZipFile(ROOT / "data" / "cache" / "bulk" / "submissions.zip") as z:
        for cik in ciks:
            try:
                s = json.loads(z.read(f"CIK{cik:010d}.json"))
            except KeyError:
                continue
            r = s["filings"]["recent"]
            forms, items, dates = r["form"], r.get("items", [""] * len(r["form"])), r["filingDate"]
            last10k = max([d for f, d in zip(forms, dates) if f in ("10-K", "10-KT")], default=None)
            acq = any(f in ("SC 14D9", "SC TO-T", "DEFM14A") for f in forms) or any(
                f == "8-K" and "5.01" in (it or "") for f, it in zip(forms, items))
            bk = any(f == "8-K" and "1.03" in (it or "") for f, it in zip(forms, items))
            rows.append({"cik": cik, "last10k": last10k, "acquired": acq, "bankrupt": bk})
    return pd.DataFrame(rows).set_index("cik")


def stats(series: pd.Series) -> dict:
    r = series.dropna()
    if r.empty:
        return {}
    v = (1 + r).cumprod()
    years = len(r) / 12
    dd = (v / v.cummax() - 1).min()
    return {"cagr": float(v.iloc[-1] ** (1 / years) - 1), "vol": float(r.std() * np.sqrt(12)), "max_dd": float(dd),
            "growth": float(v.iloc[-1]), "months": int(len(r)), "start": str(r.index[0]), "end": str(r.index[-1])}


def main() -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    p = portfolios(settings)
    comp = pd.read_pickle(CACHE / "companies.pkl").set_index("cik")
    p["ticker"] = p["cik"].map(comp["tickers"].map(lambda t: t[0].replace(".", "-") if t else None))
    tickers = sorted(set(p["ticker"].dropna())) + list(BENCH)
    px = prices(tickers)
    rets = px.pct_change(fill_method=None)
    status = sec_status(set(p["cik"]))
    spx = rets["^SP500TR"]
    # Yahoo joins old and new shares of some companies that went through Chapter 11 (e.g. CHRD +30,991% in a month).
    # For companies with a bankruptcy 8-K (item 1.03), a month above +300% is treated as missing data.
    bk_tickers = set(p.loc[p["cik"].map(status["bankrupt"]).fillna(False).astype(bool), "ticker"].dropna())
    masked = 0
    for t in bk_tickers & set(rets.columns):
        bad = rets[t] > 3
        masked += int(bad.sum())
        rets.loc[bad, t] = np.nan

    def holding(y: int) -> pd.PeriodIndex:
        return pd.period_range(f"{y}-07", f"{min(y + 1, 2026)}-{'06' if y < 2026 - 0 else '10'}", freq="M")

    out = {"retrieved": px.attrs.get("retrieved"), "portfolios": {}, "coverage": {}, "years": {}}
    port_series = {k: {s: [] for s in ("survivors", "neutral", "worst")} for k in ("moat", "quality", "universe")}
    yearly = []
    for y in YEARS:
        months = holding(y)
        if y == 2025:
            months = pd.period_range("2025-07", "2026-10", freq="M")
        months = [m for m in months if m in rets.index]
        py = p[p["year"] == y]
        for key, members in (("moat", py[py["moat"]]), ("quality", py[py["quality"]]), ("universe", py)):
            paths = {s: [] for s in ("survivors", "neutral", "worst")}
            n_missing = n_dead = 0
            for _, m in members.iterrows():
                t = m["ticker"]
                r = rets[t].reindex(months) if t in rets else pd.Series(np.nan, index=months)
                first_px = px[t].reindex([pd.Period(f"{y}-06", "M")]).notna().iloc[0] if t in px else False
                st = status.loc[m["cik"]] if m["cik"] in status.index else None
                stopped = st is not None and (st["last10k"] is None or st["last10k"] < f"{y + 2}-06-30")
                dead = stopped and not st["acquired"]
                missing = r.isna()
                if missing.any():
                    n_missing += 1
                    n_dead += int(dead)
                if first_px and not missing.any():
                    paths["survivors"].append(r)
                neutral = r.where(~missing, spx.reindex(months))
                paths["neutral"].append(neutral)
                worst = neutral.copy()
                if dead and missing.any():
                    first = missing.idxmax()
                    worst.loc[first] = -1.0
                    worst.loc[worst.index > first] = 0.0
                paths["worst"].append(worst)
            for s, lst in paths.items():
                if not lst:
                    continue
                g = pd.concat(lst, axis=1).fillna(0).add(1).cumprod()
                v = g.mean(axis=1)  # equal weight at the start, buy and hold
                port_series[key][s].append(v / v.shift(1, fill_value=1.0) - 1)
            if key == "moat":
                yearly.append({"year": y, "picks": int(len(members)), "missing_some_months": n_missing,
                               "stopped_not_acquired": n_dead})
    for key, d in port_series.items():
        out["portfolios"][key] = {s: stats(pd.concat(v)) for s, v in d.items() if v}
        for s, v in d.items():
            if v:
                ser = pd.concat(v)
                out["portfolios"][key][s]["by_year"] = {str(y): float((1 + ser[(ser.index >= pd.Period(f"{y}-07", "M")) &
                                                        (ser.index <= pd.Period(f"{y + 1}-06", "M"))]).prod() - 1) for y in YEARS}
                if key == "moat" and s == "neutral":
                    moat_neutral = ser
    start, end = moat_neutral.index[0], moat_neutral.index[-1]
    for b, name in BENCH.items():
        out["portfolios"][b] = {"neutral": stats(rets[b].loc[start:end])}
        out["portfolios"][b]["neutral"]["by_year"] = {str(y): float((1 + rets[b].loc[pd.Period(f"{y}-07", "M"):pd.Period(f"{y + 1}-06", "M")]).prod() - 1) for y in YEARS}
        out["portfolios"][b]["label"] = name
    # hit rate per pick (12-month return beats the S&P 500), turnover, sector view
    picks = p[p["moat"]].copy()
    hits, sect = [], []
    for _, m in picks.iterrows():
        months = [mm for mm in pd.period_range(f"{m['year']}-07", f"{m['year'] + 1}-06", freq="M") if mm in rets.index]
        if not months or m["ticker"] not in rets or rets[m["ticker"]].reindex(months).isna().any():
            continue
        r12 = float((1 + rets[m["ticker"]].reindex(months)).prod() - 1)
        b12 = float((1 + spx.reindex(months)).prod() - 1)
        hits.append(r12 > b12)
        sect.append({"div": m["sic"] // 100, "excess": r12 - b12})
    turn = [1 - len(set(picks[picks.year == y].cik) & set(picks[picks.year == y - 1].cik)) / max(1, len(picks[picks.year == y]))
            for y in YEARS[1:]]
    sec = pd.DataFrame(sect).groupby("div")["excess"].agg(["count", "median"]).sort_values("count", ascending=False).head(10)
    out["hit_rate_vs_spx"] = float(np.mean(hits)) if hits else None
    out["hit_n"] = len(hits)
    out["turnover"] = float(np.mean(turn))
    out["sectors"] = {int(k): {"n": int(v["count"]), "median_excess": float(v["median"])} for k, v in sec.iterrows()}
    out["coverage"] = yearly
    out["masked_bankruptcy_months"] = masked
    (ROOT / "output" / "data" / "market.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out["portfolios"].items():
        for s, st in v.items():
            if isinstance(st, dict) and "cagr" in st:
                print(f"{k:10} {s:9} CAGR {st['cagr']:.1%} vol {st['vol']:.1%} maxDD {st['max_dd']:.1%} {st['start']}→{st['end']}")
    print("hit rate vs S&P", out["hit_rate_vs_spx"], out["hit_n"], "turnover", out["turnover"])
    print(yearly)


if __name__ == "__main__":
    main()
