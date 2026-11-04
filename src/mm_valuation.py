"""Moat Momentum · market value and clean P/E for the Screener (added 2026-11-04 at Jitti's request).

  market value = Yahoo Finance month-end close (latest month in the price cache) × shares outstanding from the cover
                 page of the latest 10-K/10-Q (dei:EntityCommonStockSharesOutstanding); when a company does not tag
                 it (e.g. multi-class Alphabet), the diluted weighted-average share count of the latest period
  clean P/E    = market value ÷ clean net income over the last 12 months
                 (net income + tagged one-off items × (1 − 21%), same clean-up as the Moat Score); none when ≤ 0
Display only: neither number is used in the Moat Score or the Compounder Signal.
Sanity check: a market value below 0.2% or above 200× of 12-month revenue almost always means a mis-scaled share count
(diluted shares are sometimes tagged in thousands or millions); both numbers are then hidden and marked `check`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LO, HI = 0.002, 200.0  # plausible market value ÷ 12-month revenue


def valuation(latest: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """latest: cik, ticker, clean_ni and revenue (12 months), shares (diluted), optional cover_shares.
    px: monthly closes, PeriodIndex, Yahoo tickers as columns."""
    month = px.index[-1]
    last = px.iloc[-1]
    yt = latest["ticker"].map(lambda t: t.replace(".", "-") if isinstance(t, str) else None)
    price = yt.map(lambda t: last.get(t, np.nan) if t else np.nan).astype(float)
    cover = latest["cover_shares"] if "cover_shares" in latest else pd.Series(np.nan, index=latest.index)
    cover = cover.where(cover > 0)
    shares = cover.fillna(latest["shares"].where(latest["shares"] > 0))
    source = np.where(cover.notna(), "cover page", np.where(shares.notna(), "diluted", "none"))
    mcap = price * shares
    ratio = mcap / latest["revenue"].where(latest["revenue"] > 0)
    check = ratio.notna() & ((ratio < LO) | (ratio > HI))
    mcap = mcap.where(~check)
    pe = mcap / latest["clean_ni"].where(latest["clean_ni"] > 0)
    return pd.DataFrame({"cik": latest["cik"].to_numpy(), "price": price.to_numpy(), "price_month": str(month),
                         "mcap": mcap.to_numpy(), "pe": pe.to_numpy(), "check": check.to_numpy(),
                         "shares_source": source})


# ---- v3.0 (spec docs/specs/2026-11-04-moat-map-v3-design.md §4) ----

def price_before(px: pd.DataFrame, date: str) -> pd.Series:
    """Close of the latest month in `px` earlier than the month of `date` (never a price from after the date)."""
    month = pd.Period(date[:7], "M")
    earlier = px.index[px.index < month]
    return px.loc[earlier[-1]] if len(earlier) else pd.Series(dtype=float)


def cover_at(cover: pd.DataFrame, date: str) -> pd.Series:
    """cik → shares outstanding from the latest filing cover page filed on or before `date`."""
    c = cover[cover["filed"] <= pd.Timestamp(date)].sort_values(["filed", "end"])
    return c.drop_duplicates("cik", keep="last").set_index("cik")["val"]


def multiples(df: pd.DataFrame) -> pd.DataFrame:
    """EV and multiples from mcap, debt, cash, revenue, clean_oi, clean_ni, fcf (12-month figures)."""
    out = df.copy()
    pos = lambda s: s.where(s > 0)  # noqa: E731
    out["ev"] = out["mcap"] + out["debt"].fillna(0) - out["cash"].fillna(0)
    out["ev_sales"] = out["ev"] / pos(out["revenue"])
    out["ev_ebit"] = out["ev"] / pos(out["clean_oi"])
    out["pe"] = out["mcap"] / pos(out["clean_ni"])
    out["fcf_yield"] = out["fcf"] / pos(out["mcap"])
    return out


def split_factor_after(splits: pd.Series, month: pd.Period) -> float:
    """Product of split ratios dated after the end of `month`. Yahoo adjusted closes are divided by later splits, so
    multiplying by this factor gives the price actually quoted then (to pair with share counts filed then)."""
    if splits is None or not len(splits):
        return 1.0
    end = month.to_timestamp(how="end")
    later = splits[pd.to_datetime(splits.index) > end]
    return float(later.prod()) if len(later) else 1.0
