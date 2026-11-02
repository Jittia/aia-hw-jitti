"""Day 4: price points for the backtest from Yahoo Finance (via yfinance), cached locally.

For each ticker and each date in DATES (last trading day on/before the date):
  adj_close      split- and dividend-adjusted close  -> total return between two dates
  raw_close      price actually traded that day      -> market cap = raw_close × SEC shares
yfinance `Close` is split-adjusted only, so raw_close = Close × product of splits after that day.

Run:  python src/prices.py      Out: data/cache/prices_summary.csv (gitignored)
Source: Yahoo Finance https://finance.yahoo.com (retrieved via yfinance on the run date).
"""
from __future__ import annotations

import warnings

import pandas as pd
import yfinance as yf

from sec_client import DATA_CACHE, DATA_PRIVATE

warnings.filterwarnings("ignore", category=Warning, module="yfinance")

DATES = ["2018-12-31", "2019-12-31", "2023-12-31", "2024-12-31"]
START, END = "2018-12-01", "2026-11-03"
OUT = DATA_CACHE / "prices_summary.csv"


def yahoo_ticker(t: str) -> str:
    return str(t).replace(".", "-")


def summarize(data: pd.DataFrame, tickers: list[str]) -> list[dict]:
    rows = []
    for t in tickers:
        try:
            adj, close, splits = data["Adj Close"][t], data["Close"][t], data["Stock Splits"][t]
        except KeyError:
            continue
        splits = splits[splits > 0]
        row = {"yahoo_ticker": t}
        for d in DATES:
            s = close.loc[:d].dropna()
            # Must have traded within 7 days of the date, otherwise the stock was not listed yet.
            if s.empty or (pd.Timestamp(d) - s.index[-1]).days > 7:
                continue
            day = s.index[-1]
            factor = float(splits[splits.index > day].prod()) if not splits.empty else 1.0
            row[f"adj_{d}"] = float(adj.loc[day])
            row[f"raw_{d}"] = float(s.iloc[-1]) * factor
        rows.append(row)
    return rows


def main() -> None:
    uni = pd.read_csv(DATA_PRIVATE / "universe_with_cik_2026-11-02.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    tickers = sorted({yahoo_ticker(t) for t in uni["ticker"]})
    rows: list[dict] = []
    for i in range(0, len(tickers), 200):
        chunk = tickers[i:i + 200]
        data = yf.download(chunk, start=START, end=END, auto_adjust=False, actions=True,
                           progress=False, threads=True, group_by="column")
        rows += summarize(data, chunk)
        print(f"  {min(i + 200, len(tickers))}/{len(tickers)} tickers", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"tickers with any price: {len(df)} · with 2019-12-31 price: {df['adj_2019-12-31'].notna().sum()}")
    print(f"output: {OUT}")


if __name__ == "__main__":
    main()
