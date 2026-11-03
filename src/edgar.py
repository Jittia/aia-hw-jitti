"""Day 2 · Task B: SEC EDGAR XBRL companyfacts — fetch, cache, and point-in-time lookups.

Fetch (resumable):  python src/edgar.py --date 2026-11-02
Lookup in code:     facts_as_of(cik, "revenue", "2019-12-31")

Point-in-time rule (PROJECT_MEMORY.md): a fact is visible on `as_of` only if its FILED date
is on or before `as_of`. For each period the earliest filing wins, so later restatements
cannot leak back into a historical run.

Source: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
"""
from __future__ import annotations

import argparse
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache

import pandas as pd

from sec_client import DATA_CACHE, DATA_PRIVATE, SecClient, cik10, read_cache

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
CACHE_DIR = DATA_CACHE / "companyfacts"

# Metric -> (taxonomy, unit, concepts in priority order). Companies switch concepts over time
# (e.g. SalesRevenueNet before ASC 606 in 2018, RevenueFromContract... after), so one metric
# merges several concepts; for each period the highest-priority concept that has it is used.
METRICS: dict[str, tuple[str, str, list[str]]] = {
    "revenue": ("us-gaap", "USD", [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
        "RevenuesNetOfInterestExpense",          # credit services, exchanges
        "RegulatedAndUnregulatedOperatingRevenue",
        "HealthCareOrganizationRevenue",
        "OilAndGasRevenue",
        "RevenueMineralSales",
    ]),
    "gross_profit": ("us-gaap", "USD", ["GrossProfit"]),
    "cost_of_revenue": ("us-gaap", "USD", [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ]),
    "operating_income": ("us-gaap", "USD", ["OperatingIncomeLoss"]),
    "cfo": ("us-gaap", "USD", ["NetCashProvidedByUsedInOperatingActivities"]),
    "capex": ("us-gaap", "USD", ["PaymentsToAcquirePropertyPlantAndEquipment"]),
    "acquisitions": ("us-gaap", "USD", [
        "PaymentsToAcquireBusinessesNetOfCashAcquired",
        "PaymentsToAcquireBusinessesGross",
    ]),
    "goodwill": ("us-gaap", "USD", ["Goodwill"]),  # instant; jumps when a company is bought, even for stock
    # Contracted future revenue (Phase 1.5): signed but not yet earned. Instants.
    "rpo": ("us-gaap", "USD", ["RevenueRemainingPerformanceObligation"]),
    "contract_liab": ("us-gaap", "USD", [
        "ContractWithCustomerLiability",
        "ContractWithCustomerLiabilityCurrent",
        "DeferredRevenue",              # pre-ASC 606 name
        "DeferredRevenueCurrent",
    ]),
    "shares_outstanding": ("dei", "shares", ["EntityCommonStockSharesOutstanding"]),
}


def cache_path(cik: int | str):
    return CACHE_DIR / f"CIK{cik10(cik)}.json.gz"


def filing_url(cik: int | str, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{accn}-index.htm"


@lru_cache(maxsize=64)
def load_companyfacts(cik: int | str) -> dict | None:
    """Read from cache only; run the fetch step first."""
    path = cache_path(cik)
    if not path.exists():
        bulk = DATA_CACHE / "bulk" / "companyfacts.zip"  # Moat Momentum keeps the bulk file instead of per-CIK copies
        if bulk.exists():
            with zipfile.ZipFile(bulk) as z:
                try:
                    return json.loads(z.read(f"CIK{cik10(cik)}.json"))
                except KeyError:
                    return None
        raise FileNotFoundError(f"companyfacts not cached for CIK {cik10(cik)}; run: python src/edgar.py")
    return read_cache(path)


def _raw_facts(cf: dict, taxonomy: str, concept: str, unit: str) -> list[dict]:
    return cf.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {}).get(unit, [])


def facts_as_of(cik: int | str, metric_or_concept: str, as_of: str | date,
                taxonomy: str = "us-gaap", unit: str = "USD") -> pd.DataFrame:
    """Facts visible on `as_of`, one row per period, earliest filing per period.

    `metric_or_concept` is a key of METRICS (merges alias concepts) or a raw XBRL concept name.
    Columns: metric, concept, start, end, period_days, val, form, fp, fy, filed, accn, url.
    """
    as_of = str(as_of)
    if metric_or_concept in METRICS:
        taxonomy, unit, concepts = METRICS[metric_or_concept]
    else:
        concepts = [metric_or_concept]
    cf = load_companyfacts(cik)
    if not cf:
        return pd.DataFrame()

    rows = []
    for priority, concept in enumerate(concepts):
        for f in _raw_facts(cf, taxonomy, concept, unit):
            if f["filed"] > as_of:
                continue  # point-in-time: not yet public on as_of
            rows.append({**f, "concept": concept, "priority": priority, "start": f.get("start")})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    if taxonomy == "dei" and unit == "shares":
        # Multi-class companies report one cover-page value per class in the same filing; sum them.
        df = (df.groupby(["end", "accn", "filed", "form", "concept", "priority"], dropna=False)
                .agg(val=("val", lambda s: s.drop_duplicates().sum()), fp=("fp", "first"), fy=("fy", "first"))
                .reset_index())
        df["start"] = None

    df["period_key"] = df["start"].fillna("") + "|" + df["end"]
    df = (df.sort_values(["period_key", "priority", "filed"])
            .groupby("period_key", as_index=False).head(1))
    df["period_days"] = (pd.to_datetime(df["end"]) - pd.to_datetime(df["start"])).dt.days + 1
    df["url"] = [filing_url(cik, a) for a in df["accn"]]
    df.insert(0, "metric", metric_or_concept)
    cols = ["metric", "concept", "start", "end", "period_days", "val", "form", "fp", "fy", "filed", "accn", "url"]
    return df[cols].sort_values(["end", "start"]).reset_index(drop=True)


def latest_annual(cik: int | str, metric: str, as_of: str | date) -> pd.Series | None:
    """Most recent ~12-month period (350–380 days) visible on `as_of`."""
    df = facts_as_of(cik, metric, as_of)
    if df.empty:
        return None
    annual = df[df["period_days"].between(350, 380)]
    return None if annual.empty else annual.iloc[-1]


def fetch_all(universe_date: str, refresh: bool = False) -> None:
    uni = pd.read_csv(DATA_PRIVATE / f"universe_with_cik_{universe_date}.csv", dtype={"cik": str})
    ciks = sorted(uni.loc[uni["include_flag"], "cik"].dropna().unique())
    sec = SecClient()
    todo = [c for c in ciks if refresh or not cache_path(c).exists()]
    print(f"included CIKs: {len(ciks)} · already cached: {len(ciks) - len(todo)} · to fetch: {len(todo)}", flush=True)
    def fetch(cik: str) -> bool:
        return sec.get_json_cached(COMPANYFACTS_URL.format(cik=cik), cache_path(cik), refresh=True) is not None

    missing = 0
    # Requests are ~0.5 s each, so one thread reaches only ~2/s; 6 workers share the 10/s throttle.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, ok in enumerate(pool.map(fetch, todo), 1):
            missing += not ok
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} fetched · no companyfacts (404): {missing}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-02")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    fetch_all(args.date, args.refresh)
