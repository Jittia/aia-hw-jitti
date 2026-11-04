"""Moat Momentum v3.0 · Moat Map positions and movement rules (spec docs/specs/2026-11-04-moat-map-v3-design.md §2–3).

positions(panel)   on every 12-month point of a ttm_panel: x = 3-year revenue growth a year, y = clean ROIC − 9%,
                   d = distance to the top-right corner, the same values 4 quarters earlier (x_4, y_4, d_4) and the
                   trail 1–5 years earlier (x_t1…x_t5, y_t1…y_t5)
classify(rows)     for one date: industry median growth, top-right, quadrant label, R1 (entered), R2 (moving toward)
map_at(...)        universe rows at a date (filings available by then) with positions and classification
top25(rows, rule)  the rule's shortlist: passes the v1.1 risk gate, ranked by distance moved, then y
value_at(...)      market value, EV, multiples, implied growth, Expectation Gap and R3 at a date (§4)
leading_at(...)    backlog and deferred-revenue growth vs revenue growth, R&D and capex intensity (§5, display only)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mm_quarterly import lag_q

HURDLE, GROWTH_LINE, R2_FALL, R2_NEAR = 0.09, 0.10, 0.05, 0.10
EPS = 1e-9


def _dist(x: pd.Series, y: pd.Series) -> pd.Series:
    return (GROWTH_LINE - x).clip(lower=0) + (-y).clip(lower=0)


def positions(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.sort_values(["cik", "end"]).reset_index(drop=True).copy()
    base = lag_q(p, "revenue", 12)
    ratio = p["revenue"] / base.where(base > 0)
    p["x"] = (ratio.where(ratio > 0) ** (1 / 3) - 1).where(lambda s: np.isfinite(s))
    p["y"] = p["roic_ttm"] - HURDLE
    p["d"] = _dist(p["x"], p["y"])
    p["rev_4"] = lag_q(p, "revenue", 4)
    peak = pd.concat([lag_q(p, "revenue", k) for k in range(1, 9)], axis=1).max(axis=1)
    p["rebound"] = p["revenue"] < 0.8 * peak  # recovering toward an earlier level (v2.0 rebound check, spec §6)
    for k in (1, 2, 3, 4, 5):
        p[f"x_t{k}"], p[f"y_t{k}"] = lag_q(p, "x", 4 * k), lag_q(p, "y", 4 * k)
    p["x_4"], p["y_4"] = p["x_t1"], p["y_t1"]
    p["d_4"] = _dist(p["x_4"], p["y_4"])
    return p


def _quadrant(x: pd.Series, y: pd.Series) -> pd.Series:
    q = np.select([(y >= 0) & (x >= GROWTH_LINE), y >= 0, x >= GROWTH_LINE], ["Compounder", "Profitable, slow", "Growing, below hurdle"], "Neither")
    return pd.Series(q, index=x.index).where(x.notna() & y.notna())


def classify(rows: pd.DataFrame) -> pd.DataFrame:
    r = rows.copy()
    g = r["industry_group"]
    r["ind_med_x"] = r.groupby(g)["x"].transform("median")
    med4 = r.groupby(g)["x_4"].transform("median")  # median a year earlier, among today's universe (see ledger ruling)
    have = r["x"].notna() & r["y"].notna()
    have4 = r["x_4"].notna() & r["y_4"].notna()
    r["top_right"] = have & (r["x"] >= GROWTH_LINE) & (r["y"] >= 0) & (r["x"] > r["ind_med_x"])
    r["top_right_4"] = have4 & (r["x_4"] >= GROWTH_LINE) & (r["y_4"] >= 0) & (r["x_4"] > med4)
    r["quadrant"] = _quadrant(r["x"], r["y"])
    r["moved"] = (r["d_4"] - r["d"]).where(have & have4)
    r["r1"] = r["top_right"] & have4 & ~r["top_right_4"]
    r["r2"] = (have & have4 & ~r["top_right"] & (r["x"] > r["x_4"]) & (r["y"] > r["y_4"])
               & (r["moved"] >= R2_FALL - EPS) & (r["d"] <= R2_NEAR + EPS))
    return r


def top25(rows: pd.DataFrame, rule_col: str, n: int = 25) -> pd.DataFrame:
    sel = rows[rows[rule_col].fillna(False).astype(bool) & ~rows["gate_removed"].fillna(False).astype(bool)]
    return sel.sort_values(["moved", "y"], ascending=False).head(n)


def map_at(facts: pd.DataFrame, companies: pd.DataFrame, date: str, settings: dict, live: bool,
           panel: pd.DataFrame | None = None) -> pd.DataFrame:
    """Universe B at `date` (v1.1 engine: universe, industry group, risk gate) with Moat Map positions from the
    company's latest 12-month point filed by then and ending within ~18 months."""
    from mm_fundamentals import scoring_table
    from mm_quarterly import ttm_panel
    from mm_score import score_as_of
    tax, cash = settings["data"]["tax_rate"], settings["data"]["excess_cash_pct_revenue"]
    res = score_as_of(scoring_table(facts, date, tax, cash, ttm=False), companies, date, settings, live)["results"]
    u = res[res["in_universe"]][["cik", "ticker", "name", "sic", "sic_desc", "industry_group", "moat_score", "gate_removed"]]
    p = positions(ttm_panel(facts, date, tax, cash) if panel is None else panel)
    a = pd.Timestamp(date)
    p = p[(p["filed"] <= a) & (p["end"] >= a - pd.Timedelta(days=548))]
    latest = p.sort_values("end").drop_duplicates("cik", keep="last")
    out = u.merge(latest, on="cik", how="left", suffixes=("", "_p"))
    out = classify(out.assign(industry_group=out["industry_group"].fillna("all")))
    out["date"] = date
    return out


LEAD_TAGS = {"backlog": ["RevenueRemainingPerformanceObligation"],
             "defrev": ["ContractWithCustomerLiability", "ContractWithCustomerLiabilityCurrent", "DeferredRevenue",
                        "DeferredRevenueCurrent"]}


def _lead_value(lead: pd.DataFrame, cik, end, tags: list[str]) -> float:
    """First tag (priority order) with an instant at `end` (±20 days) for this company."""
    g = lead[lead["cik"] == cik]
    for t in tags:
        h = g[(g["tag"] == t) & ((g["end"] - end).abs() <= pd.Timedelta(days=20))]
        if len(h):
            return float(h.sort_values("filed")["val"].iloc[-1])
    return float("nan")


def leading_at(rows: pd.DataFrame, lead: pd.DataFrame, date: str) -> pd.DataFrame:
    """Growth over 4 quarters minus revenue growth for backlog and deferred revenue; R&D and capex ÷ revenue.
    NaN = not reported (never zero). `lead` = leading.pkl rows (cik, tag, end, val, filed)."""
    r = rows.copy()
    lead = lead[pd.to_datetime(lead["filed"]) <= pd.Timestamp(date)].copy() if len(lead) else lead
    if len(lead):
        lead["end"] = pd.to_datetime(lead["end"])
        lead = lead[lead["cik"].isin(set(r["cik"]))]
    rev_g = r["revenue"] / r["rev_4"].where(r["rev_4"] > 0) - 1
    for key, tags in LEAD_TAGS.items():
        vals = []
        for cik, end in zip(r["cik"], pd.to_datetime(r["end"])):
            if not len(lead) or pd.isna(end):
                vals.append(float("nan"))
                continue
            now, then = _lead_value(lead, cik, end, tags), _lead_value(lead, cik, end - pd.DateOffset(years=1), tags)
            vals.append(now / then - 1 if then and then > 0 and np.isfinite(now) else float("nan"))
        r[f"{key}_g"] = pd.Series(vals, index=r.index) - rev_g
    rev = r["revenue"].where(r["revenue"] > 0)
    r["rnd_int"] = r["rnd"] / rev if "rnd" in r else np.nan
    r["capex_int"] = r["capex"] / rev if "capex" in r else np.nan
    return r


def value_at(rows: pd.DataFrame, date: str, px: pd.DataFrame, cover: pd.DataFrame, live: bool,
             daily: pd.Series | None = None, splits: dict | None = None) -> pd.DataFrame:
    """Market value (price before the date, or yesterday's close when live) × cover-page shares known by the date,
    then EV, multiples, implied growth, Expectation Gap and R3."""
    from mm_revdcf import expectation_gap, implied_growth
    from mm_valuation import cover_at, multiples, split_factor_after, valuation
    r = rows.copy()
    if live and daily is not None:
        prices = pd.DataFrame([daily.to_dict()], index=pd.PeriodIndex([str(daily.attrs.get("date", date))[:7]], freq="M"))
    else:
        month = pd.Period(date[:7], "M")
        prices = px.loc[px.index < month]
        if len(prices) and splits:
            # undo splits after the price month (Yahoo adjusts history for them; share counts are as filed then)
            last = prices.index[-1]
            fac = pd.Series({t: split_factor_after(sp, last) for t, sp in splits.items() if t in prices.columns})
            prices = prices.copy()
            prices.loc[last, fac.index] = prices.loc[last, fac.index] * fac
    r["cover_shares"] = r["cik"].map(cover_at(cover, date)) if len(cover) else np.nan
    for c in ("clean_ni", "revenue", "shares"):
        if c not in r:
            r[c] = np.nan
    if len(prices):
        v = valuation(r[["cik", "ticker", "clean_ni", "revenue", "shares", "cover_shares"]].reset_index(drop=True), prices)
        r["mcap"] = v["mcap"].to_numpy()
    else:
        r["mcap"] = np.nan
    r = multiples(r)
    margin = r["clean_oi"] / r["revenue"].where(r["revenue"] > 0)
    r["g_implied"] = [implied_growth(e, s, m, k) for e, s, m, k in zip(r["ev"], r["revenue"], margin, r["roic_ttm"])]
    r["gap"] = [expectation_gap(x, g) for x, g in zip(r["x"], r["g_implied"])]
    r["r3"] = (r["r1"].fillna(False).astype(bool) | r["r2"].fillna(False).astype(bool)) & (r["gap"] > 0)
    return r
