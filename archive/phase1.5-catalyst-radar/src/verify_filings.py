"""Day 7: check signal inputs against the filing text itself (spec.md success criterion 3).

For each ticker, takes the latest quarter used by Layer 1 and looks for each XBRL value, formatted the way
filings print it (in thousands or millions, with commas), inside the 10-Q/10-K document it came from.
Cash-flow lines are year-to-date in a 10-Q, so the YTD fact is checked (the quarter is derived from it).

Run:  python src/verify_filings.py DERM TRT AAPL
"""
from __future__ import annotations

import re
import sys

import pandas as pd

from edgar import METRICS, facts_as_of
from layer2_prep import html_to_text
from sec_client import DATA_PRIVATE, SecClient, cik10, read_cache, DATA_CACHE

CHECK = ["revenue", "gross_profit", "cost_of_revenue", "operating_income", "cfo", "capex"]
SHARES = ("WeightedAverageNumberOfDilutedSharesOutstanding", "us-gaap", "shares")


def printed_forms(v: float) -> list[str]:
    """How a filing may print this value: full, thousands, millions (rounded), with commas; negatives in ()."""
    a = abs(v)
    return [f"{a:,.0f}", f"{a / 1e3:,.0f}", f"{a / 1e6:,.0f}", f"{a / 1e6:,.1f}"]


def doc_url_for(cik: str, accn: str) -> str | None:
    recent = read_cache(DATA_CACHE / "submissions" / f"CIK{cik10(cik)}.json.gz")["filings"]["recent"]
    for a, d in zip(recent["accessionNumber"], recent["primaryDocument"]):
        if a == accn:
            return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{d}"
    return None


def main(tickers: list[str]) -> None:
    sc = pd.read_csv(DATA_PRIVATE / "layer1_scores_2026-11-02.csv", dtype={"cik": str})
    sec = SecClient()
    rows = []
    for t in tickers:
        r = sc[sc["ticker"] == t].iloc[0]
        cik, q0 = r["cik"], r["q0_end"]
        texts: dict[str, str] = {}
        items = [(m, None) for m in CHECK] + [(SHARES[0], SHARES)]
        for metric, raw in items:
            f = facts_as_of(cik, metric, "2026-11-02", **({"taxonomy": raw[1], "unit": raw[2]} if raw else {}))
            f = f[f["end"] == q0] if not f.empty else f
            if f.empty:
                rows.append({"ticker": t, "item": metric, "status": "not reported for this quarter"})
                continue
            fact = f.sort_values("period_days").iloc[0]   # shortest period ending Q0 = the quarter (or YTD in 10-Q cash flow)
            url = doc_url_for(cik, fact["accn"])
            if url not in texts:
                texts[url] = html_to_text(sec.session.get(url, timeout=60).text) if url else ""
            text = texts[url].replace("\xa0", " ")
            hit = next((p for p in printed_forms(fact["val"]) if re.search(rf"(?<![\d,.]){re.escape(p)}(?![\d,]|\.\d)", text)), None)
            rows.append({"ticker": t, "item": metric, "period": f"{fact['start']}→{fact['end']}", "xbrl_value": fact["val"],
                         "found_as": hit or "", "status": "matched" if hit else "NOT FOUND", "filing": url})
    df = pd.DataFrame(rows)
    with pd.option_context("display.width", 250, "display.max_colwidth", 60):
        print(df.drop(columns=["filing"]).to_string(index=False))
    print(f"\nmatched {int((df['status'] == 'matched').sum())} / checked {int(df['status'].isin(['matched', 'NOT FOUND']).sum())}")
    df.to_csv(DATA_CACHE / "verify_filings.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1:] or ["DERM", "TRT", "AAPL"])
