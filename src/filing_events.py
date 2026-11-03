"""Phase 1.5: 8-K item events from the SEC submissions index (weak signals, judged by the event study).

  officer_change   8-K item 5.02 (departure/appointment of officers or directors)
  material_deal    8-K item 1.01 (entry into a material definitive agreement)
The submissions JSON keeps the most recent ~1,000 filings in "recent"; older ones are in extra pages listed under
filings.files, fetched once and cached. known_date = 8-K filing date. Onsets only: one event per type per company
per COOLDOWN_DAYS.

Run:  python src/filing_events.py     Out: data/cache/filing_events.pkl
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from sec_client import DATA_CACHE, DATA_PRIVATE, SecClient, cik10, read_cache

OUT = DATA_CACHE / "filing_events.pkl"
ITEMS = {"5.02": "officer_change", "1.01": "material_deal"}
SINCE = "2012-01-01"
COOLDOWN_DAYS = 180


def all_8k(sec: SecClient, cik: str) -> pd.DataFrame:
    sub = read_cache(DATA_CACHE / "submissions" / f"CIK{cik10(cik)}.json.gz")
    if not sub:
        return pd.DataFrame()
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        if f.get("filingTo", "9999") >= SINCE:
            page = sec.get_json_cached(f"https://data.sec.gov/submissions/{f['name']}",
                                       DATA_CACHE / "submissions" / f"{f['name']}.gz")
            if page:
                blocks.append(page)
    rows = []
    for b in blocks:
        for form, d, items, acc in zip(b["form"], b["filingDate"], b["items"], b["accessionNumber"]):
            if form == "8-K" and d >= SINCE:
                rows.append({"cik": cik, "known_date": d, "items": items, "accn": acc})
    return pd.DataFrame(rows)


def events_for(df: pd.DataFrame) -> list[dict]:
    out = []
    for item, name in ITEMS.items():
        hits = df[df["items"].fillna("").str.split(",").map(lambda x: item in x)].sort_values("known_date")
        last = None
        for r in hits.itertuples():
            d = pd.Timestamp(r.known_date)
            if last is None or (d - last).days > COOLDOWN_DAYS:
                out.append({"cik": r.cik, "event": name, "kind": "filing", "known_date": r.known_date,
                            "url": f"https://www.sec.gov/Archives/edgar/data/{int(r.cik)}/{r.accn.replace('-', '')}/"})
                last = d
    return out


def main() -> None:
    uni = pd.read_csv(DATA_PRIVATE / "universe_with_cik_2026-11-02.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    sec = SecClient()
    with ThreadPoolExecutor(max_workers=6) as pool:
        frames = list(pool.map(lambda c: all_8k(sec, c), uni["cik"]))
    rows = []
    for df in frames:
        if not df.empty:
            rows += events_for(df)
    ev = pd.DataFrame(rows).merge(uni[["cik", "ticker"]], on="cik", how="left")
    ev.to_pickle(OUT)
    print(f"8-K events: {len(ev):,} · SEC requests {sec.requests_made}")
    print(ev["event"].value_counts().to_string())


if __name__ == "__main__":
    main()
