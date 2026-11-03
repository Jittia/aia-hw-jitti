"""Phase 1.5: month-end price panel 2012→today for the event study, from Yahoo Finance (via yfinance).

  adj  month-end adjusted close (splits + dividends)  -> total return between two month-ends
  raw  month-end price actually traded                -> market cap = raw × SEC share count on that date
yfinance `Close` is split-adjusted only, so raw = Close × product of splits after that day (PROJECT_MEMORY rule).

Run:  python src/prices_monthly.py      Out: data/cache/prices_monthly.pkl  {"adj": DataFrame, "raw": DataFrame}
Source: Yahoo Finance https://finance.yahoo.com, retrieved on the run date.
"""
from __future__ import annotations

import warnings

import pandas as pd
import yfinance as yf

from prices import yahoo_ticker
from sec_client import DATA_CACHE, DATA_PRIVATE

warnings.filterwarnings("ignore")

START, END = "2012-01-01", "2026-11-03"
OUT = DATA_CACHE / "prices_monthly.pkl"
CHUNK = 100


def month_end_panel(data: pd.DataFrame, tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    adj, raw = {}, {}
    for t in tickers:
        try:
            close, a, splits = data["Close"][t].dropna(), data["Adj Close"][t].dropna(), data["Stock Splits"][t]
        except KeyError:
            continue
        if close.empty:
            continue
        splits = splits[splits > 0]
        # Cumulative product of splits strictly after each day (reverse cumulative product, shifted one day).
        factor = pd.Series(1.0, index=close.index)
        if not splits.empty:
            factor = splits.reindex(close.index).fillna(1.0)[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
        last_day = close.groupby(close.index.to_period("M")).tail(1)
        adj[t] = a.reindex(last_day.index).set_axis(last_day.index.to_period("M"))
        raw[t] = (last_day * factor.reindex(last_day.index)).set_axis(last_day.index.to_period("M"))
    return pd.DataFrame(adj), pd.DataFrame(raw)


def main() -> None:
    uni = pd.read_csv(DATA_PRIVATE / "universe_with_cik_2026-11-02.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    tickers = sorted({yahoo_ticker(t) for t in uni["ticker"]})
    adj_parts, raw_parts = [], []
    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i + CHUNK]
        data = yf.download(chunk, start=START, end=END, auto_adjust=False, actions=True,
                           progress=False, threads=True, group_by="column")
        a, r = month_end_panel(data, chunk)
        adj_parts.append(a)
        raw_parts.append(r)
        print(f"  {min(i + CHUNK, len(tickers))}/{len(tickers)}", flush=True)
    adj, raw = pd.concat(adj_parts, axis=1).sort_index(), pd.concat(raw_parts, axis=1).sort_index()
    pd.to_pickle({"adj": adj, "raw": raw}, OUT)
    print(f"months {len(adj)} ({adj.index.min()} → {adj.index.max()}) · tickers {adj.shape[1]} · "
          f"with 2012-12 price {int(adj.loc[pd.Period('2012-12')].notna().sum())}")


if __name__ == "__main__":
    main()
