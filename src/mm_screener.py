"""Moat Momentum · Screener data (spec docs/specs/2026-11-04-screener-design.md).

risk_measures(rows)          the three pre-screen measures (12 months): interest cover, net debt ÷ EBITDA,
                             operating cash flow ÷ debt, plus net-cash and interest-tagged flags. The pass rules and
                             thresholds live in the web page (user-adjustable): riskPass() mirrors spec §4.
group_series(panel)          the four 2×2 groups' X/Y on every 12-month point
earnings_yield_history(...)  Group 4 Y at past quarter-ends: clean operating income ÷ EV, with EV from that month's
                             price (later splits undone) × shares filed by then
screener_block(...)          per company: risk measures and each group's [X, Y] now and 1–4 quarters back
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HURDLE = 0.09


def _pos(s: pd.Series) -> pd.Series:
    return s.where(s > 0)


def risk_measures(rows: pd.DataFrame) -> pd.DataFrame:
    r = rows.copy()
    debt, cash = r["debt"].fillna(0), r["cash"].fillna(0)
    ebitda = r["clean_oi"] + r["da"].fillna(0)
    net = debt - cash
    r["int_tagged"] = r["interest"].notna() & (r["interest"] > 0)
    r["int_cover"] = (r["clean_oi"] / _pos(r["interest"])).where(r["int_tagged"])
    r["net_cash"] = net <= 0
    r["nd_ebitda"] = (net / _pos(ebitda)).where(~((ebitda <= 0) & (net > 0)), np.inf)
    r["cfo_debt"] = r["cfo"] / _pos(debt)
    r["has_debt"] = debt > 0
    return r


def lags5(panel: pd.DataFrame, col: str) -> pd.DataFrame:
    """Columns 0..4 = `col` now and 1..4 quarters earlier (same company, period ends matched within ±20 days)."""
    from mm_quarterly import lag_q
    return pd.concat([panel[col].astype(float)] + [lag_q(panel, col, k) for k in (1, 2, 3, 4)], axis=1,
                     keys=range(5))


def group_series(panel: pd.DataFrame) -> pd.DataFrame:
    """The four groups' X/Y on every 12-month point (spec §5). Panel must be sorted by cik, end."""
    from mm_quarterly import lag_q
    p = panel.sort_values(["cik", "end"]).reset_index(drop=True).copy()
    base = lag_q(p, "revenue", 12)
    ratio = p["revenue"] / base.where(base > 0)
    growth = (ratio.where(ratio > 0) ** (1 / 3) - 1).where(lambda s: np.isfinite(s))
    p["g1x"] = p["g3x"] = growth
    p["g1y"] = p["roic_ttm"]  # plain clean ROIC; the hurdle is the line
    ic4, ic12, n12 = lag_q(p, "ic", 4), lag_q(p, "ic", 12), lag_q(p, "nopat", 12)
    p["g2x"] = (p["ic"] - ic4) / _pos(p["nopat"])
    dic = p["ic"] - ic12
    grew = dic >= 0.10 * ic12.abs()
    p["g2y"] = ((p["nopat"] - n12) / dic.where(grew & (dic > 0))).where(lambda s: np.isfinite(s))
    p["g3y"] = p["gross_margin"] - lag_q(p, "gross_margin", 4)
    p["g4x"] = p["roic_ttm"]
    return p


def earnings_yield_history(panel: pd.DataFrame, tickers: pd.Series, px: pd.DataFrame, splits: dict,
                           cover: pd.DataFrame) -> pd.Series:
    """Group 4 Y at each row's quarter-end: clean operating income ÷ EV. Price = month-end adjusted close of the
    quarter's last month × later splits undone; shares = cover page filed by the row's filing date."""
    from mm_valuation import HI, LO
    out = pd.Series(np.nan, index=panel.index)
    cover = cover.sort_values(["filed", "end"])
    for i, r in panel.iterrows():
        t = tickers.get(r["cik"])
        m = pd.Period(pd.Timestamp(r["end"]), "M")
        if t is None or t not in px.columns or m not in px.index:
            continue
        price = px.at[m, t]
        c = cover[(cover["cik"] == r["cik"]) & (cover["filed"] <= pd.Timestamp(r["filed"]))]
        shares = c["val"].iloc[-1] if len(c) else np.nan
        counted = c["end"].iloc[-1] if len(c) else None
        if not shares > 0:  # same fallback as mm_valuation.valuation: cover page, else diluted shares
            shares, counted = _nz(r.get("shares")), pd.Timestamp(r["filed"])
        if not np.isfinite(price) or not shares > 0:
            continue
        # Yahoo's adjusted close is in today's share terms; the count is in the terms of the day it was taken.
        # Undo only the splits after that day (a split between quarter-end and count is already in both).
        mcap = price * _splits_after(splits.get(t), counted) * shares
        rev = _nz(r.get("revenue"))
        if rev > 0 and not LO <= mcap / rev <= HI:  # same sanity range as the live market value
            continue
        ev = mcap + _nz(r.get("debt")) - _nz(r.get("cash"))
        if ev > 0 and np.isfinite(r["clean_oi"]):
            out.at[i] = r["clean_oi"] / ev
    return out


def _splits_after(splits: pd.Series | None, date) -> float:
    if splits is None or not len(splits):
        return 1.0
    later = splits[pd.to_datetime(splits.index) > pd.Timestamp(date)]
    return float(later.prod()) if len(later) else 1.0


def _nz(v) -> float:
    return 0.0 if v is None or not np.isfinite(v) else float(v)


LINES = {"g1": [0.10, HURDLE], "g2": [0.50, HURDLE], "g3": [0.10, 0.0]}
RISK_DEFAULTS = {"ic": 3.0, "nd": 3.0, "cd": 0.20}
GROUPS = ("g1", "g2", "g3", "g4")


def _r(v, nd: int = 4):
    if v is None:
        return None
    v = float(v)
    if v == np.inf:
        return 999.0
    return round(v, nd) if np.isfinite(v) else None


def screener_block(panel: pd.DataFrame, live: pd.DataFrame, px: pd.DataFrame, splits: dict, cover: pd.DataFrame,
                   as_of: str) -> dict:
    """Per universe company: risk measures (latest 12 months) and each group's [X, Y] now and 1–4 quarters back.
    `live` = the live Moat Map rows (cik, ticker, ev at yesterday's close); `panel` = ttm_panel known by `as_of`."""
    a = pd.Timestamp(as_of)
    ciks = set(live["cik"].astype(int))
    p = panel[panel["cik"].isin(ciks) & (panel["filed"] <= a)]
    g = group_series(p)
    tick = live.set_index("cik")["ticker"]
    recent = g["end"] >= a - pd.Timedelta(days=548 + 400)
    g["g4y"] = np.nan
    g.loc[recent, "g4y"] = earnings_yield_history(g[recent], tick, px, splits, cover)
    five = {f"{gr}{ax}": lags5(g, f"{gr}{ax}") for gr in GROUPS for ax in "xy"}
    g = risk_measures(g)
    latest = g[g["end"] >= a - pd.Timedelta(days=548)].sort_values("end").drop_duplicates("cik", keep="last")
    ev_now = live.set_index("cik")["ev"]
    co = {}
    for i, r in latest.iterrows():
        cik = int(r["cik"])
        ev = ev_now.get(cik, np.nan)
        y4now = r["clean_oi"] / ev if np.isfinite(ev) and ev > 0 and np.isfinite(r["clean_oi"]) else np.nan
        rec = {"end": str(r["end"].date()), "ic": _r(r["int_cover"], 2), "nd": _r(r["nd_ebitda"], 2),
               "cd": _r(r["cfo_debt"], 3), "nc": bool(r["net_cash"]), "it": bool(r["int_tagged"]),
               "hd": bool(r["has_debt"])}
        for gr in GROUPS:
            xs, ys = five[f"{gr}x"].loc[i].to_list(), five[f"{gr}y"].loc[i].to_list()
            if gr == "g4":
                ys[0] = y4now
            rec[gr] = [[_r(x), _r(y)] for x, y in zip(xs, ys)]
        co[cik] = rec
    both = [(v["g4"][0][0], v["g4"][0][1]) for v in co.values() if None not in v["g4"][0]]
    med = {"g4x": float(np.median([b[0] for b in both])), "g4y": float(np.median([b[1] for b in both]))} if both else {}
    lines = dict(LINES, g4=[_r(med.get("g4x")), _r(med.get("g4y"))])
    return {"meta": {"medians": med, "lines": lines, "defaults": RISK_DEFAULTS, "as_of": as_of,
                     "price_month_past": "Yahoo month-end close of each quarter's last month, later splits undone"},
            "co": co}
