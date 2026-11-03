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
