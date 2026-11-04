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
import os
import warnings
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import yfinance as yf

from mm_fundamentals import scoring_table
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
    # the two other built-in scenarios of the web page (same definitions as mm_validate.variants)
    pl = copy.deepcopy(settings)
    pl["scoring"]["blend"] = {"level": 70, "trend": 20, "consistency": 10}
    sr = copy.deepcopy(settings)
    for k in sr["risk_gate"]:
        if isinstance(sr["risk_gate"][k], dict):
            sr["risk_gate"][k]["mode"] = "remove"
    rows = []
    tax, cash, ttm = settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"], bool(settings["data"].get("ttm"))
    for y in YEARS:
        as_of = f"{y}-06-30"
        d = scoring_table(facts, as_of, tax, cash, ttm=ttm)
        a = score_as_of(d, companies, as_of, settings, live=False)["results"]
        b = score_as_of(d, companies, as_of, q, live=False)["results"]
        # same settings on fiscal years only (the v1.1 method), to show what the 12-month figures change
        c = score_as_of(scoring_table(facts, as_of, tax, cash, ttm=False), companies, as_of, settings, live=False)["results"] if ttm else a
        e = score_as_of(d, companies, as_of, pl, live=False)["results"]
        g = score_as_of(d, companies, as_of, sr, live=False)["results"]
        a = a[a["in_universe"]]
        qual = set(b.loc[b["shortlist"], "cik"])
        fy_only = set(c.loc[c["shortlist"], "cik"])
        proven, strict = set(e.loc[e["shortlist"], "cik"]), set(g.loc[g["shortlist"], "cik"])
        for _, r in a.iterrows():
            rows.append({"year": y, "cik": int(r["cik"]), "sic": int(r["sic"]), "moat": bool(r["shortlist"]),
                         "quality": int(r["cik"]) in qual, "moat_fy": int(r["cik"]) in fy_only,
                         "proven": int(r["cik"]) in proven, "strict": int(r["cik"]) in strict})
        print(f"  portfolios {y}: universe {len(a)}", flush=True)
    p = pd.DataFrame(rows)
    p.to_pickle(path)
    return p


def prices(tickers: list[str]) -> pd.DataFrame:
    path = CACHE / "prices_monthly.pkl"
    old = pd.read_pickle(path) if path.exists() else None
    if old is not None:
        missing = [t for t in tickers if t not in old.columns]
        if not missing:
            return old
        tickers = missing  # a new method can pick companies outside the cached list: fetch only those
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
    if old is not None:
        px = pd.concat([old, px.reindex(old.index)], axis=1)
        px.attrs["retrieved"] = old.attrs.get("retrieved")
        px.attrs["topped_up"] = str(date.today())
    else:
        px.attrs["retrieved"] = str(date.today())
    px.to_pickle(path)
    return px


def last_closes(frame: pd.DataFrame, run_date: str) -> tuple[dict, dict]:
    """Each column's last close strictly before `run_date` (a bar dated today may be intraday)."""
    f = frame[pd.to_datetime(frame.index).normalize() < pd.Timestamp(run_date)]
    closes, dates = {}, {}
    for t in f.columns:
        col = f[t].dropna()
        if len(col):
            closes[t], dates[t] = float(col.iloc[-1]), str(pd.Timestamp(col.index[-1]).date())
    return closes, dates


def splits_history(tickers: list[str], path: Path | None = None) -> dict:
    """Yahoo split history per ticker (date → ratio), 2013 onward, cached in splits.pkl (v3.0 back-test valuation)."""
    path = path or CACHE / "splits.pkl"
    if path.exists():
        old = pd.read_pickle(path)
        if set(tickers) <= set(old):
            return old
    out = {}
    for i in range(0, len(tickers), 200):
        chunk = tickers[i:i + 200]
        d = yf.download(chunk, start="2013-01-01", end=str(date.today()), interval="1d", actions=True, auto_adjust=True,
                        progress=False, threads=True, group_by="column")["Stock Splits"]
        if isinstance(d, pd.Series):
            d = d.to_frame(chunk[0])
        for t in d.columns:
            s = d[t][d[t] > 0]
            out[t] = s
        print(f"  splits {min(i + 200, len(tickers))}/{len(tickers)}", flush=True)
    pd.to_pickle(out, path)
    return out


def prices_daily(tickers: list[str], path: Path | None = None) -> pd.Series:
    """v3.0 live valuation: each ticker's latest daily close (not adjusted), from Yahoo Finance.
    attrs: 'date' = close date of most tickers, 'retrieved' = run date. Cached for the day in prices_daily.pkl."""
    path = path or CACHE / "prices_daily.pkl"
    if path.exists() and os.environ.get("MM_REUSE_DAILY") == "1":  # re-run on the cached closes (same as-of data)
        return pd.read_pickle(path)
    if path.exists():
        old = pd.read_pickle(path)
        if old.attrs.get("retrieved") == str(date.today()) and set(tickers) <= set(old.index):
            return old
    closes, dates = {}, {}
    for i in range(0, len(tickers), 200):
        chunk = tickers[i:i + 200]
        data = yf.download(chunk, period="7d", interval="1d", auto_adjust=False, progress=False, threads=True,
                           group_by="column")["Close"]
        if isinstance(data, pd.Series):
            data = data.to_frame(chunk[0])
        c, dd = last_closes(data, str(date.today()))
        closes.update(c)
        dates.update(dd)
    out = pd.Series(closes, dtype=float)
    out.attrs["date"] = pd.Series(dates).mode().iloc[0] if dates else None
    out.attrs["retrieved"] = str(date.today())
    out.to_pickle(path)
    return out


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


def hold_paths(members: pd.DataFrame, months: list, start: pd.Period, stop_cutoff: str, rets: pd.DataFrame,
               px: pd.DataFrame, status: pd.DataFrame, spx: pd.Series) -> dict:
    """Monthly returns of an equal-weight, buy-and-hold basket over `months`, in three cases for missing prices:
    survivors (only names priced throughout), neutral (missing months earn the S&P 500), worst (a company that
    stopped filing 10-Ks before `stop_cutoff` and was not acquired loses everything in its first missing month)."""
    paths = {s: [] for s in ("survivors", "neutral", "worst")}
    n_missing = n_dead = 0
    for _, m in members.iterrows():
        t = m["ticker"]
        r = rets[t].reindex(months) if t in rets else pd.Series(np.nan, index=months)
        first_px = px[t].reindex([start]).notna().iloc[0] if t in px else False
        st = status.loc[m["cik"]] if m["cik"] in status.index else None
        stopped = st is not None and (st["last10k"] is None or st["last10k"] < stop_cutoff)
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
    out = {}
    for s, lst in paths.items():
        if lst:
            g = pd.concat(lst, axis=1).fillna(0).add(1).cumprod()
            v = g.mean(axis=1)  # equal weight at the start, buy and hold
            out[s] = v / v.shift(1, fill_value=1.0) - 1
    out["_missing"], out["_dead"] = n_missing, n_dead
    return out


def compounder_picks(settings: dict) -> pd.DataFrame:
    """v2.0: top shortlist_size by Compounder Signal at each screen, after the risk gate's Remove rules; plus the
    whole universe at each screen (key 'universe'). Empty if discovery has not been run."""
    path = ROOT / "output" / "data" / "discovery.json"
    from mm_discover import rows_path
    parts = [rows_path(settings, k) for k in ("train", "test")]
    if not path.exists() or not all(x.exists() for x in parts):
        return pd.DataFrame()
    from mm_discover import combine  # noqa: F811
    kept = json.loads(path.read_text())["kept"]
    rows = pd.concat([pd.read_pickle(x) for x in parts], ignore_index=True)
    rows["cs"] = combine(rows, kept)
    rows["ticker"] = rows["ticker"].map(lambda t: t.replace(".", "-") if isinstance(t, str) else None)
    n = settings["compounder"]["shortlist_size"]
    elig = rows[~rows["gate_removed"].astype(bool) & rows["cs"].notna()]
    top = elig.sort_values("cs", ascending=False).groupby("screen").head(n).assign(key="compounder")
    return pd.concat([top, rows.assign(key="universe")], ignore_index=True)[["screen", "cik", "ticker", "sic", "key"]]


def compounder_section(cp: pd.DataFrame, rets, px, status, spx, port_series) -> dict:
    """Quarterly rebalance: bought at the month-end of the screen month, held to the month-end of the next screen's
    month. Two windows: the test period (screens 2020–2023) and all screens (2013–2023)."""
    scr = sorted(cp["screen"].unique())
    series = {k: {s: [] for s in ("survivors", "neutral", "worst")} for k in ("compounder", "universe")}
    for i, sc in enumerate(scr):
        start = pd.Period(sc[:7], "M")
        end = pd.Period(scr[i + 1][:7], "M") if i + 1 < len(scr) else start + 3
        months = [m for m in pd.period_range(start + 1, end, freq="M") if m in rets.index]
        cutoff = f"{int(sc[:4]) + 2}{sc[4:]}"
        for k in series:
            hp = hold_paths(cp[(cp["screen"] == sc) & (cp["key"] == k)], months, start, cutoff, rets, px, status, spx)
            hp.pop("_missing"), hp.pop("_dead")
            for s, v in hp.items():
                series[k][s].append(v)
    v11 = pd.concat(port_series["moat"]["neutral"])
    out = {"rebalance": "quarterly, at each screen", "windows": {}}
    for wname, (a, b) in {"test 2020-2023": ("2020-03-15", "2023-11-15"), "all 2013-2023": (scr[0], scr[-1])}.items():
        lo, hi = pd.Period(a[:7], "M") + 1, pd.Period(b[:7], "M") + 3
        w = {}
        for k, d in series.items():
            for s, lst in d.items():
                ser = pd.concat(lst)
                ser = ser[(ser.index >= lo) & (ser.index <= hi)]
                w[f"{k}_{s}"] = stats(ser)
        for b_, lab in (("^SP500TR", "sp500"), ("QUAL", "qual")):
            w[lab] = stats(rets[b_].loc[lo:hi].dropna())
        w["v11_shortlist"] = stats(v11[(v11.index >= lo) & (v11.index <= hi)])
        out["windows"][wname] = w
    return out


def main() -> None:
    settings = yaml.safe_load((ROOT / "settings.yaml").read_text())
    p = portfolios(settings)
    comp = pd.read_pickle(CACHE / "companies.pkl").set_index("cik")
    p["ticker"] = p["cik"].map(comp["tickers"].map(lambda t: t[0].replace(".", "-") if t else None))
    cp = compounder_picks(settings)
    tickers = sorted(set(p["ticker"].dropna()) | set(cp["ticker"].dropna())) + list(BENCH)
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
    port_series = {k: {s: [] for s in ("survivors", "neutral", "worst")} for k in ("moat", "moat_fy", "proven", "strict", "quality", "universe")}
    yearly = []
    for y in YEARS:
        months = holding(y)
        if y == 2025:
            months = pd.period_range("2025-07", "2026-10", freq="M")
        months = [m for m in months if m in rets.index]
        py = p[p["year"] == y]
        for key, members in (("moat", py[py["moat"]]), ("moat_fy", py[py["moat_fy"]]), ("proven", py[py["proven"]]),
                             ("strict", py[py["strict"]]), ("quality", py[py["quality"]]), ("universe", py)):
            hp = hold_paths(members, months, pd.Period(f"{y}-06", "M"), f"{y + 2}-06-30", rets, px, status, spx)
            n_missing, n_dead = hp.pop("_missing"), hp.pop("_dead")
            for s, v in hp.items():
                port_series[key][s].append(v)
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
    if len(cp):
        out["compounder"] = compounder_section(cp, rets, px, status, spx, port_series)
    (ROOT / "output" / "data" / "market.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out["portfolios"].items():
        for s, st in v.items():
            if isinstance(st, dict) and "cagr" in st:
                print(f"{k:10} {s:9} CAGR {st['cagr']:.1%} vol {st['vol']:.1%} maxDD {st['max_dd']:.1%} {st['start']}→{st['end']}")
    print("hit rate vs S&P", out["hit_rate_vs_spx"], out["hit_n"], "turnover", out["turnover"])
    print(yearly)


if __name__ == "__main__":
    main()
