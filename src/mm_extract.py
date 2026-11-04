"""Moat Momentum · step 1a: SEC bulk files → point-in-time fact store.

Input  (local, re-downloadable, git-ignored):
  data/cache/bulk/companyfacts.zip   https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip
  data/cache/bulk/submissions.zip    https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip
Output:
  data/cache/mm/companies.pkl   one row per CIK: name, SIC, tickers, exchanges, fiscal year end, 10-K list
  data/cache/mm/facts.pkl       one row per (tag, period, value change): the point-in-time store

Point-in-time store: for each tag and period we keep the FIRST filing and every LATER filing whose value differs
(a restatement). A lookup "as known on date D" = the latest kept row filed on or before D. Rows that only repeat an
earlier value are dropped, which keeps the store small without losing any information.

Kept: forms 10-K, 10-KT, 10-Q and their amendments; annual (350–380 days), quarterly (80–100 days) and year-to-date
(170–290 days) durations, and instants. Quarter / YTD rows from 2011 on (v1.2: needed for point-in-time TTM in the back-test).
Coarse filter here (finer rules in mm_universe): SIC outside 6000–6799 and annual revenue ≥ $50M at least once.

Run:  .venv/bin/python src/mm_extract.py          (cover-page share counts only: ... cover; v3.0 leading items: ... leading)
"""
from __future__ import annotations

import json
from datetime import date
import zipfile
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BULK = ROOT / "data" / "cache" / "bulk"
OUT = ROOT / "data" / "cache" / "mm"

FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "10-Q", "10-Q/A"}
SHORT_FROM = "2011-01-01"   # v1.2: back to 2011 so TTM can be rebuilt for every back-test date (2013–2023)

# Raw us-gaap tags pulled from companyfacts. Mapping to canonical metrics is done in mm_fundamentals.py.
TAGS = [
    # revenue
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet", "RevenuesNetOfInterestExpense",
    "RegulatedAndUnregulatedOperatingRevenue", "HealthCareOrganizationRevenue", "OilAndGasRevenue", "RevenueMineralSales",
    # costs and profit
    "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices",
    "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    "GrossProfit", "OperatingIncomeLoss", "OperatingExpenses", "CostsAndExpenses",
    "SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense", "SellingAndMarketingExpense",
    "ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    "InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt", "InterestAndDebtExpense",
    "IncomeTaxExpenseBenefit",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    "NetIncomeLoss", "ProfitLoss",
    "DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization",
    "Depreciation", "AmortizationOfIntangibleAssets",
    "ShareBasedCompensation", "AllocatedShareBasedCompensationExpense",
    # one-off items (clean-up bridge)
    "GoodwillImpairmentLoss", "AssetImpairmentCharges", "ImpairmentOfLongLivedAssetsHeldForUse",
    "ImpairmentOfIntangibleAssetsExcludingGoodwill", "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill",
    "GoodwillAndIntangibleAssetImpairment", "RestructuringCharges", "RestructuringSettlementAndImpairmentProvisions",
    "GainLossOnDispositionOfAssets", "GainLossOnDispositionOfAssets1", "GainLossOnSaleOfPropertyPlantEquipment",
    "GainLossOnSaleOfBusiness", "DisposalGroupNotDiscontinuedOperationGainLossOnDisposal",
    "LitigationSettlementExpense", "LossContingencyLossInPeriod", "BusinessCombinationAcquisitionRelatedCosts",
    # balance sheet (instants)
    "Assets", "AssetsCurrent", "Liabilities", "LiabilitiesCurrent", "LiabilitiesAndStockholdersEquity",
    "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "RetainedEarningsAccumulatedDeficit",
    "CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "AccountsReceivableNetCurrent", "InventoryNet", "PropertyPlantAndEquipmentNet",
    "Goodwill", "IntangibleAssetsNetExcludingGoodwill",
    "LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings",
    "CommercialPaper", "LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent",
    "FinanceLeaseLiability", "FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent",
    "CapitalLeaseObligations", "OperatingLeaseLiability",
    # cash flow
    "NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquireBusinessesNetOfCashAcquired",
    # shares
    "WeightedAverageNumberOfDilutedSharesOutstanding",
]
SHARE_TAGS = {"WeightedAverageNumberOfDilutedSharesOutstanding"}
REVENUE_TAGS = TAGS[:11]


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def _company_profile(sub: dict) -> dict:
    recent = sub.get("filings", {}).get("recent", {})
    tenk = [(f, d, a, p) for f, d, a, p in zip(recent.get("form", []), recent.get("filingDate", []),
                                               recent.get("accessionNumber", []), recent.get("primaryDocument", []))
            if f in ("10-K", "10-KT", "10-Q", "8-K", "10-K/A")]
    return {
        "name": sub.get("name"), "sic": int(sub["sic"]) if str(sub.get("sic") or "").isdigit() else None,
        "sic_desc": sub.get("sicDescription"), "tickers": sub.get("tickers") or [],
        "exchanges": sub.get("exchanges") or [], "fye": sub.get("fiscalYearEnd"),
        "state_inc": sub.get("stateOfIncorporation"), "filings": tenk,
    }


def _rows(cik: int, cf: dict) -> list[tuple]:
    gaap = cf.get("facts", {}).get("us-gaap", {})
    out = []
    for tag in TAGS:
        units = gaap.get(tag, {}).get("units", {})
        facts = units.get("shares" if tag in SHARE_TAGS else "USD", [])
        for f in facts:
            if f.get("form") not in FORMS:
                continue
            start, end = f.get("start"), f["end"]
            if start:
                days = _days(start, end)
                if 350 <= days <= 380:
                    kind = "A"
                elif 80 <= days <= 100:
                    kind = "Q"
                elif 170 <= days <= 290:
                    kind = "YTD"
                else:
                    continue
                if kind != "A" and end < SHORT_FROM:
                    continue
            else:
                kind = "I"
            out.append((cik, tag, kind, start, end, float(f["val"]), f["filed"], f["form"], f["accn"]))
    return out


def _max_annual_revenue(cf: dict) -> float:
    gaap = cf.get("facts", {}).get("us-gaap", {})
    best = 0.0
    for tag in REVENUE_TAGS:
        for f in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if f.get("start") and f.get("form") in FORMS:
                days = _days(f["start"], f["end"])
                if 350 <= days <= 380:
                    best = max(best, f["val"])
    return best


def _work(names: list[str]) -> tuple[list[dict], list[tuple]]:
    companies, rows = [], []
    with zipfile.ZipFile(BULK / "companyfacts.zip") as cz, zipfile.ZipFile(BULK / "submissions.zip") as sz:
        for name in names:
            cik = int(name[3:13])
            try:
                sub = json.loads(sz.read(name))
            except KeyError:
                continue
            prof = _company_profile(sub)
            sic = prof["sic"]
            if sic is None or 6000 <= sic <= 6799:
                continue
            cf = json.loads(cz.read(name))
            if _max_annual_revenue(cf) < 50_000_000:
                continue
            companies.append({"cik": cik, **prof})
            rows.extend(_rows(cik, cf))
    return companies, rows


def _compress(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the first filing per (cik, tag, start, end) and later filings only when the value changed."""
    df = df.sort_values(["cik", "tag", "start", "end", "filed", "accn"])
    key = ["cik", "tag", "start", "end"]
    prev_val = df.groupby(key, dropna=False)["val"].shift()
    keep = prev_val.isna() | (df["val"] != prev_val)
    return df[keep]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BULK / "companyfacts.zip") as cz:
        names = sorted(n for n in cz.namelist() if n.startswith("CIK") and n.endswith(".json"))
    chunks = [names[i::32] for i in range(32)]
    companies, rows = [], []
    with Pool(8) as pool:
        for i, (c, r) in enumerate(pool.imap_unordered(_work, chunks), 1):
            companies.extend(c)
            rows.extend(r)
            print(f"  chunk {i}/32 · companies kept {len(companies):,} · rows {len(rows):,}", flush=True)
    comp = pd.DataFrame(companies).sort_values("cik").reset_index(drop=True)
    facts = pd.DataFrame(rows, columns=["cik", "tag", "kind", "start", "end", "val", "filed", "form", "accn"])
    del rows
    facts = _compress(facts)
    for c in ("tag", "kind", "form"):
        facts[c] = facts[c].astype("category")
    for c in ("start", "end", "filed"):
        facts[c] = pd.to_datetime(facts[c])
    facts["cik"] = facts["cik"].astype("int32")
    comp.to_pickle(OUT / "companies.pkl")
    facts.reset_index(drop=True).to_pickle(OUT / "facts.pkl")
    print(f"done · companies {len(comp):,} · fact rows {len(facts):,}", flush=True)


def _cover_work(ciks: list[int]) -> list[tuple]:
    out = []
    with zipfile.ZipFile(BULK / "companyfacts.zip") as cz:
        for cik in ciks:
            try:
                cf = json.loads(cz.read(f"CIK{cik:010d}.json"))
            except KeyError:
                continue
            for f in cf.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}) \
                    .get("units", {}).get("shares", []):
                out.append((cik, f["end"], float(f["val"]), f["filed"], f.get("form"), f.get("accn")))
    return out


def cover_shares() -> None:
    """Shares outstanding from filing cover pages (dei) → data/cache/mm/cover_shares.pkl (added 2026-11-04 for the
    Screener's market value; the diluted weighted-average count is sometimes tagged in thousands or millions)."""
    ciks = pd.read_pickle(OUT / "companies.pkl")["cik"].tolist()
    rows = []
    with Pool(8) as pool:
        for r in pool.imap_unordered(_cover_work, [ciks[i::32] for i in range(32)]):
            rows.extend(r)
    df = pd.DataFrame(rows, columns=["cik", "end", "val", "filed", "form", "accn"])
    for c in ("end", "filed"):
        df[c] = pd.to_datetime(df[c])
    df.to_pickle(OUT / "cover_shares.pkl")
    print(f"cover shares: {len(df):,} rows, {df['cik'].nunique():,} companies", flush=True)


LEADING_TAGS = ["RevenueRemainingPerformanceObligation", "ContractWithCustomerLiability",
                "ContractWithCustomerLiabilityCurrent", "DeferredRevenue", "DeferredRevenueCurrent"]


def _leading_work(ciks: list[int]) -> list[tuple]:
    out = []
    with zipfile.ZipFile(BULK / "companyfacts.zip") as cz:
        for cik in ciks:
            try:
                g = json.loads(cz.read(f"CIK{cik:010d}.json")).get("facts", {}).get("us-gaap", {})
            except KeyError:
                continue
            for tag in LEADING_TAGS:
                for f in g.get(tag, {}).get("units", {}).get("USD", []):
                    if f.get("form") in FORMS and not f.get("start"):  # balances at a date only
                        out.append((cik, tag, f["end"], float(f["val"]), f["filed"]))
    return out


def leading() -> None:
    """v3.0 leading items (backlog, deferred revenue) → data/cache/mm/leading.pkl; shown in the product, not tested."""
    ciks = pd.read_pickle(OUT / "companies.pkl")["cik"].tolist()
    rows = []
    with Pool(8) as pool:
        for r in pool.imap_unordered(_leading_work, [ciks[i::32] for i in range(32)]):
            rows.extend(r)
    df = pd.DataFrame(rows, columns=["cik", "tag", "end", "val", "filed"])
    for c in ("end", "filed"):
        df[c] = pd.to_datetime(df[c])
    df = df.sort_values("filed").drop_duplicates(["cik", "tag", "end"], keep="last")  # latest restatement
    df.to_pickle(OUT / "leading.pkl")
    print(f"leading items: {len(df):,} rows, {df['cik'].nunique():,} companies", flush=True)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1:]
    cover_shares() if cmd == ["cover"] else leading() if cmd == ["leading"] else main()
