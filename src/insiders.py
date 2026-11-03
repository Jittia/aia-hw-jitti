"""Phase 1.5: insider cluster-buy events from the SEC Insider Transactions Data Sets (Forms 3/4/5).

Source: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets (quarterly zip files).
Kept: open-market purchases (TRANS_CODE "P", acquired) by officers or directors of companies in our universe.
Event "insider_cluster": on a filing date, ≥ insider_min_buyers different insiders have bought within the last
insider_window_days, worth ≥ MIN_VALUE_USD in total; at most one event per company per COOLDOWN_DAYS.
known_date = the Form 4 filing date that completes the cluster.

Run:  python src/insiders.py     Out: data/cache/insiders/purchases.pkl, data/cache/insider_events.pkl
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from score import load_config
from sec_client import DATA_CACHE, DATA_PRIVATE, SecClient

PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
DIR = DATA_CACHE / "insiders"
PURCHASES = DIR / "purchases.pkl"
OUT = DATA_CACHE / "insider_events.pkl"
FIRST_QUARTER = "2011q3"   # covers 90-day windows ending in 2012
MIN_VALUE_USD = 100_000
COOLDOWN_DAYS = 180


def quarter_links(sec: SecClient) -> list[str]:
    html = sec.session.get(PAGE, timeout=60).text
    links = sorted(set(re.findall(r'href="([^"]+?(\d{4}q\d)_form345\.zip)"', html)), key=lambda x: x[1])
    return ["https://www.sec.gov" + l for l, q in links if q >= FIRST_QUARTER]


def purchases_from_zip(content: bytes, ciks: set[str]) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(content))
    read = lambda n, cols: pd.read_csv(z.open(n), sep="\t", usecols=cols, dtype=str, on_bad_lines="skip")
    sub = read("SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK", "DOCUMENT_TYPE"])
    sub["cik"] = sub["ISSUERCIK"].str.zfill(10)
    sub = sub[sub["cik"].isin(ciks) & sub["DOCUMENT_TYPE"].isin(["4", "4/A"])]
    tr = read("NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                                     "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    tr = tr[(tr["TRANS_CODE"] == "P") & (tr["TRANS_ACQUIRED_DISP_CD"] == "A")]
    own = read("REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
    own = own[own["RPTOWNER_RELATIONSHIP"].fillna("").str.contains("Officer|Director", case=False)]
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
    df["value"] = pd.to_numeric(df["TRANS_SHARES"], errors="coerce") * pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce")
    df["filed"] = pd.to_datetime(df["FILING_DATE"], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    return df[["cik", "ACCESSION_NUMBER", "filed", "TRANS_DATE", "RPTOWNERCIK", "value"]].dropna(subset=["filed"])


def cluster_events(p: pd.DataFrame, min_buyers: int, window_days: int) -> pd.DataFrame:
    out = []
    for cik, g in p.groupby("cik"):
        g = g.assign(d=pd.to_datetime(g["filed"])).sort_values("d")
        last_event = None
        for d in g["d"].unique():
            w = g[(g["d"] <= d) & (g["d"] > d - pd.Timedelta(days=window_days))]
            if w["RPTOWNERCIK"].nunique() >= min_buyers and w["value"].sum() >= MIN_VALUE_USD:
                if last_event is None or (d - last_event).days > COOLDOWN_DAYS:
                    acc = w[w["d"] == d]["ACCESSION_NUMBER"].iloc[0]
                    out.append({"cik": cik, "event": "insider_cluster", "kind": "filing",
                                "known_date": pd.Timestamp(d).strftime("%Y-%m-%d"),
                                "buyers": int(w["RPTOWNERCIK"].nunique()), "value_usd": float(w["value"].sum()),
                                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/"})
                last_event = d
    return pd.DataFrame(out)


def main() -> None:
    cfg = load_config()["radar"]["events"]
    uni = pd.read_csv(DATA_PRIVATE / "universe_with_cik_2026-11-02.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    ciks = set(uni["cik"])
    sec = SecClient()
    DIR.mkdir(parents=True, exist_ok=True)
    parts = []
    links = quarter_links(sec)
    for i, url in enumerate(links, 1):
        q = re.search(r"(\d{4}q\d)", url).group(1)
        part = DIR / f"{q}.pkl"
        if not part.exists():
            sec._throttle()
            resp = sec.session.get(url, timeout=300)
            resp.raise_for_status()
            purchases_from_zip(resp.content, ciks).to_pickle(part)   # zip itself is not kept (~13 MB each)
        parts.append(pd.read_pickle(part))
        if i % 10 == 0 or i == len(links):
            print(f"  {i}/{len(links)} quarters", flush=True)
    p = pd.concat(parts, ignore_index=True).drop_duplicates(["ACCESSION_NUMBER", "RPTOWNERCIK", "TRANS_DATE", "value"])
    p.to_pickle(PURCHASES)
    ev = cluster_events(p, cfg["insider_min_buyers"], cfg["insider_window_days"])
    ev = ev.merge(uni[["cik", "ticker"]], on="cik", how="left")
    ev.to_pickle(OUT)
    print(f"purchases: {len(p):,} by {p['RPTOWNERCIK'].nunique():,} insiders in {p['cik'].nunique():,} companies")
    print(f"cluster events: {len(ev):,} in {ev['cik'].nunique():,} companies · {ev['known_date'].min()} → {ev['known_date'].max()}")


if __name__ == "__main__":
    main()
