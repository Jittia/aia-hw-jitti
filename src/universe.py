"""Day 2 · Task A: map the Stock Analysis universe to SEC CIKs and decide who is in scope.

Input : data/private/stockanalysis_us_universe_<date>.csv  (licensed, local only)
Output: data/private/universe_with_cik_<date>.csv          (local only, contains licensed columns)

Exclusion rules (spec.md §4, plan "quarterly 10-Q data needed"):
  no_cik        ticker not found in SEC company_tickers files
  annual_20F/40F latest annual report is a foreign-filer form (no quarterly 10-Q)
  no_10q_2y     no 10-Q filed in the 2 years before the universe date
Royalty trusts are kept but flagged; dual share classes are kept, one marked primary per CIK.

Sources:
  https://www.sec.gov/files/company_tickers.json
  https://www.sec.gov/files/company_tickers_exchange.json
  https://data.sec.gov/submissions/CIK##########.json
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

from sec_client import DATA_CACHE, DATA_PRIVATE, SecClient, cik10

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

ROYALTY_TRUSTS = {"PBT", "SBR", "MSB", "SJT"}
ANNUAL_FORMS = {"10-K", "10-KT", "20-F", "40-F"}  # amendments (/A) ignored on purpose
FOREIGN_ANNUAL = {"20-F", "40-F"}


def norm_ticker(t: str) -> str:
    """SEC writes class shares as BRK-B; Stock Analysis writes BRK.B."""
    return str(t).strip().upper().replace(".", "-").replace("/", "-")


def load_sec_ticker_map(sec: SecClient, refresh: bool) -> dict[str, int]:
    plain = sec.get_json_cached(TICKERS_URL, DATA_CACHE / "company_tickers.json.gz", refresh)
    exch = sec.get_json_cached(TICKERS_EXCHANGE_URL, DATA_CACHE / "company_tickers_exchange.json.gz", refresh)
    mapping: dict[str, int] = {}
    for row in plain.values():
        mapping[norm_ticker(row["ticker"])] = int(row["cik_str"])
    fields = exch["fields"]
    for row in exch["data"]:
        rec = dict(zip(fields, row))
        mapping.setdefault(norm_ticker(rec["ticker"]), int(rec["cik"]))
    return mapping


def filing_profile(sub: dict | None, since: date) -> tuple[str | None, bool]:
    """Latest annual form type and whether any 10-Q was filed on/after `since`."""
    if not sub:
        return None, False
    recent = sub.get("filings", {}).get("recent", {})
    forms, filed = recent.get("form", []), recent.get("filingDate", [])
    annual = None
    latest_annual_date = ""
    has_10q = False
    for form, d in zip(forms, filed):
        if form in ANNUAL_FORMS and d > latest_annual_date:
            annual, latest_annual_date = form, d
        if form == "10-Q" and d >= since.isoformat():
            has_10q = True
    return annual, has_10q


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-02", help="universe file date (YYYY-MM-DD)")
    ap.add_argument("--refresh", action="store_true", help="re-download SEC files instead of using cache")
    args = ap.parse_args()

    universe_date = date.fromisoformat(args.date)
    src = DATA_PRIVATE / f"stockanalysis_us_universe_{args.date}.csv"
    df = pd.read_csv(src)
    sec = SecClient()

    ticker_map = load_sec_ticker_map(sec, args.refresh)
    df["cik"] = df["ticker"].map(lambda t: ticker_map.get(norm_ticker(t)))
    matched = df["cik"].notna()

    since = universe_date - timedelta(days=730)

    def profile(cik: int) -> tuple[str | None, bool]:
        sub = sec.get_json_cached(
            SUBMISSIONS_URL.format(cik=cik10(cik)), DATA_CACHE / "submissions" / f"CIK{cik10(cik)}.json.gz", args.refresh
        )
        return filing_profile(sub, since)

    ciks = sorted(df.loc[matched, "cik"].astype(int).unique())
    with ThreadPoolExecutor(max_workers=6) as pool:  # shares the 10 req/s throttle in SecClient
        results = list(pool.map(profile, ciks))
    forms = {c: r[0] for c, r in zip(ciks, results)}
    has_q = {c: r[1] for c, r in zip(ciks, results)}

    df["cik"] = df["cik"].map(lambda c: cik10(c) if pd.notna(c) else "")
    df["sec_form_annual"] = df["cik"].map(lambda c: forms.get(int(c)) if c else None)
    df["has_10q_recent"] = df["cik"].map(lambda c: has_q.get(int(c), False) if c else False)

    def reason(row) -> str:
        if not row["cik"]:
            return "no_cik"
        if row["sec_form_annual"] in FOREIGN_ANNUAL:
            return f"annual_{row['sec_form_annual'].replace('-', '')}"
        if not row["has_10q_recent"]:
            return "no_10q_2y"
        return ""

    df["exclude_reason"] = df.apply(reason, axis=1)
    df["include_flag"] = df["exclude_reason"] == ""
    df["flag_note"] = df["ticker"].map(lambda t: "royalty_trust" if t in ROYALTY_TRUSTS else "")

    # Primary share class = the most liquid ticker for each CIK.
    df["is_primary_class"] = False
    has_cik = df["cik"] != ""
    primary_idx = (
        df[has_cik].sort_values("avg_dollar_volume_usd_computed", ascending=False).groupby("cik").head(1).index
    )
    df.loc[primary_idx, "is_primary_class"] = True
    multi = df[has_cik].groupby("cik")["ticker"].transform("count") > 1
    df.loc[multi[multi].index, "flag_note"] = df.loc[multi[multi].index, "flag_note"].str.cat(
        ["multi_class"] * int(multi.sum()), sep=";"
    ).str.strip(";")

    out = DATA_PRIVATE / f"universe_with_cik_{args.date}.csv"
    df.to_csv(out, index=False)

    # Counts only — the universe file is licensed data, so no rows are printed.
    print(f"rows in universe        : {len(df)}")
    print(f"matched to CIK          : {int(matched.sum())}")
    print(f"unmatched               : {int((~matched).sum())} -> {sorted(df.loc[~matched, 'ticker'].tolist())}")
    print("excluded by reason      :")
    for r, n in df.loc[~df["include_flag"], "exclude_reason"].value_counts().items():
        print(f"    {r:<14} {n}")
    inc = df["include_flag"]
    print(f"included tickers        : {int(inc.sum())}")
    print(f"included unique CIKs    : {df.loc[inc, 'cik'].nunique()}")
    print(f"multi-class CIKs        : {df.loc[inc & df['flag_note'].str.contains('multi_class'), 'cik'].nunique()}")
    print(f"royalty trusts included : {int((inc & df['flag_note'].str.contains('royalty_trust')).sum())}")
    print(f"SEC requests this run   : {sec.requests_made}")
    print(f"output                  : {out.relative_to(DATA_PRIVATE.parent.parent)}")


if __name__ == "__main__":
    main()
