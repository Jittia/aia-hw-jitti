"""Moat Momentum · step 1b: point-in-time fact store → clean company-year table.

annual_table(facts, as_of) returns one row per (cik, fiscal year end) using only filings made on or before `as_of`
(for each tag and period, the latest value filed by then, so restatements count only once they were public).

Canonical metrics (first tag present wins; see TAG_PRIORITY), then the clean-up:
  one-offs   = impairments + restructuring + litigation + acquisition costs − gains on disposals (where tagged)
  clean OI   = operating income + one-offs
  NOPAT      = clean OI × (1 − tax rate)                       (one constant rate, settings.yaml)
  invested capital (IC) = equity + debt (incl. finance leases) − excess cash (cash above 2% of revenue)
  clean ROIC = NOPAT ÷ average IC of this and last year
and the ratios used by the risk gate and the five themes. Every derived value keeps the filing of its revenue fact
(`accn`, `filed`) so it can be traced to a 10-K.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TAG_PRIORITY: dict[str, list[str]] = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet",
                "SalesRevenueServicesNet", "RevenuesNetOfInterestExpense", "RegulatedAndUnregulatedOperatingRevenue",
                "HealthCareOrganizationRevenue", "OilAndGasRevenue", "RevenueMineralSales"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices",
             "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"],
    "gross_profit_tag": ["GrossProfit"],
    "op_income": ["OperatingIncomeLoss"],
    "sga_tag": ["SellingGeneralAndAdministrativeExpense"],
    "interest": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt", "InterestAndDebtExpense"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "da_tag": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
               "DepreciationAndAmortization"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],  # v3.0 display
    "restructuring": ["RestructuringCharges", "RestructuringSettlementAndImpairmentProvisions"],
    "litigation": ["LitigationSettlementExpense", "LossContingencyLossInPeriod"],
    "acq_costs": ["BusinessCombinationAcquisitionRelatedCosts"],
    # gains on assets/equipment usually sit inside operating income and are removed; gains on selling a whole business
    # usually sit below it (spot-check, TechnipFMC FY2024), so they are shown but not removed
    "gains": ["GainLossOnDispositionOfAssets", "GainLossOnDispositionOfAssets1", "GainLossOnSaleOfPropertyPlantEquipment"],
    "gains_business": ["GainLossOnSaleOfBusiness", "DisposalGroupNotDiscontinuedOperationGainLossOnDisposal"],
    "costs_total": ["CostsAndExpenses"],
    "assets": ["Assets"],
    "assets_cur": ["AssetsCurrent"],
    "liab_tag": ["Liabilities"],
    "liab_cur": ["LiabilitiesCurrent"],
    "liab_equity": ["LiabilitiesAndStockholdersEquity"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "equity_nci": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "StockholdersEquity"],
    "retained": ["RetainedEarningsAccumulatedDeficit"],
    "cash_tag": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "st_invest": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "receivables": ["AccountsReceivableNetCurrent"],
    "ppe": ["PropertyPlantAndEquipmentNet"],
    "goodwill": ["Goodwill"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "acquisitions": ["PaymentsToAcquireBusinessesNetOfCashAcquired"],
    "shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "op_lease": ["OperatingLeaseLiability"],
}
# Tags used as parts of sums (not a priority list): kept as raw columns.
RAW = ["GeneralAndAdministrativeExpense", "SellingAndMarketingExpense", "Depreciation", "AmortizationOfIntangibleAssets",
       "GoodwillImpairmentLoss", "AssetImpairmentCharges", "ImpairmentOfLongLivedAssetsHeldForUse",
       "ImpairmentOfIntangibleAssetsExcludingGoodwill", "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill",
       "GoodwillAndIntangibleAssetImpairment",
       "LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings",
       "CommercialPaper", "LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent",
       "FinanceLeaseLiability", "FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent",
       "CapitalLeaseObligations"]
REVENUE_TAGS = TAG_PRIORITY["revenue"]
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A"}


def known_as_of(facts: pd.DataFrame, as_of: str | pd.Timestamp | None) -> pd.DataFrame:
    """Latest value per (cik, tag, start, end) filed on or before `as_of` (None = everything)."""
    f = facts if as_of is None else facts[facts["filed"] <= pd.Timestamp(as_of)]
    return f.sort_values("filed").drop_duplicates(["cik", "tag", "start", "end"], keep="last")


def _first(df: pd.DataFrame, tags: list[str]) -> pd.Series:
    out = pd.Series(np.nan, index=df.index)
    for t in tags:
        if t in df:
            out = out.fillna(df[t])
    return out


def _col(df: pd.DataFrame, t: str) -> pd.Series:
    return df[t] if t in df else pd.Series(np.nan, index=df.index)


def _sum_any(*cols: pd.Series) -> pd.Series:
    """Sum treating missing as 0, but missing if every part is missing."""
    s = pd.concat(cols, axis=1)
    return s.sum(axis=1, min_count=1)


def annual_table(facts: pd.DataFrame, as_of: str | pd.Timestamp | None = None,
                 tax_rate: float = 0.21, excess_cash_pct: float = 0.02, ratios: bool = True,
                 known: pd.DataFrame | None = None) -> pd.DataFrame:
    k = known_as_of(facts, as_of) if known is None else known
    k = k[k["form"].isin(ANNUAL_FORMS)]

    # Fiscal years = periods with an annual revenue fact; one start per (cik, end), closest to 365 days.
    flows = k[k["kind"] == "A"].copy()
    flows["dur"] = (flows["end"] - flows["start"]).dt.days
    rev = flows[flows["tag"].isin(REVENUE_TAGS)].copy()
    rev["prio"] = rev["tag"].map({t: i for i, t in enumerate(REVENUE_TAGS)}).astype(int)
    rev["gap"] = (rev["dur"] - 364).abs()
    rev = rev.sort_values(["cik", "end", "prio", "gap"]).drop_duplicates(["cik", "end"])
    years = rev[["cik", "end", "start", "val", "tag", "accn", "filed"]].rename(
        columns={"val": "revenue", "tag": "revenue_tag", "start": "fy_start"})
    years = years[years["revenue"] > 0]

    # Flows: match on the same fiscal year (end ±3 days, ~1-year duration).
    flows = flows.merge(years[["cik", "end"]], on=["cik", "end"])
    flows = flows.sort_values("dur").drop_duplicates(["cik", "tag", "end"])
    wide_f = flows.pivot_table(index=["cik", "end"], columns="tag", values="val", aggfunc="first", observed=True)
    inst = k[k["kind"] == "I"].merge(years[["cik", "end"]], on=["cik", "end"])
    inst = inst.drop_duplicates(["cik", "tag", "end"], keep="last")
    wide_i = inst.pivot_table(index=["cik", "end"], columns="tag", values="val", aggfunc="first", observed=True)
    w = years.set_index(["cik", "end"]).join(wide_f, how="left", rsuffix="_f").join(wide_i, how="left", rsuffix="_i")
    w.columns = [str(c) for c in w.columns]
    d = _derive(w, tax_rate, excess_cash_pct)
    d = d.drop_duplicates(["cik", "fy"], keep="last")
    return add_ratios(d, tax_rate) if ratios else d


QUARTER_FORMS = {"10-Q", "10-Q/A"}
POINT_TAGS = {"WeightedAverageNumberOfDilutedSharesOutstanding"}  # an average, not a sum: use the year-to-date value


def ttm_rows(k: pd.DataFrame, tax_rate: float = 0.21, excess_cash_pct: float = 0.02) -> pd.DataFrame:
    """Trailing-12-month rows at every 10-Q period end (methodology v1.2), from facts already filtered by known_as_of:
      flow (income, cash flow) = last fiscal year + this year to date − the same period a year earlier
      balance sheet            = the 10-Q balance sheet at that quarter end
    Each tag is built only when all three parts were filed; the rest stays missing. Same clean-up as annual rows."""
    k = k.assign(tagc=pd.factorize(k["tag"].astype(str))[0].astype("int32"))
    day = pd.Timedelta(days=1)
    ann = k[(k["kind"] == "A") & k["form"].isin(ANNUAL_FORMS)]
    ann = pd.DataFrame({"cik": ann["cik"], "tagc": ann["tagc"], "key": ann["end"] + day,
                        "a_start": ann["start"], "a_val": ann["val"]})
    ytd = k[k["kind"].isin(["Q", "YTD"])].copy()
    ytd["nq"] = ((ytd["end"] - ytd["start"]).dt.days / 91.3).round().astype("int32")
    cur = ytd[ytd["form"].isin(QUARTER_FORMS)].assign(key=lambda x: x["start"])
    m = pd.merge_asof(cur.sort_values("key"), ann.sort_values("key"), on="key", by=["cik", "tagc"],
                      direction="nearest", tolerance=5 * day).dropna(subset=["a_val"])  # year to date starts after the last FY
    prior = pd.DataFrame({"cik": ytd["cik"], "tagc": ytd["tagc"], "nq": ytd["nq"], "key2": ytd["start"],
                          "p_end": ytd["end"], "p_val": ytd["val"]})
    m = pd.merge_asof(m.assign(key2=m["a_start"]).sort_values("key2"), prior.sort_values("key2"), on="key2",
                      by=["cik", "tagc", "nq"], direction="nearest", tolerance=5 * day)
    m = m[(m["end"] - m["p_end"]).dt.days.between(350, 380)]
    m["ttm"] = np.where(m["tag"].isin(POINT_TAGS), m["val"], m["a_val"] + m["val"] - m["p_val"])

    rev = m[m["tag"].isin(REVENUE_TAGS)].copy()
    rev["prio"] = rev["tag"].map({t: i for i, t in enumerate(REVENUE_TAGS)}).astype(int)
    rev = rev.sort_values(["cik", "end", "prio"]).drop_duplicates(["cik", "end"])
    years = rev[["cik", "end", "ttm", "tag", "accn", "filed"]].rename(columns={"ttm": "revenue", "tag": "revenue_tag"})
    years = years[years["revenue"] > 0]
    years["fy_start"] = years["end"] - pd.Timedelta(days=364)
    flows = m.merge(years[["cik", "end"]], on=["cik", "end"]).drop_duplicates(["cik", "tag", "end"])
    wide_f = flows.pivot_table(index=["cik", "end"], columns="tag", values="ttm", aggfunc="first", observed=True)
    inst = k[k["kind"] == "I"].merge(years[["cik", "end"]], on=["cik", "end"])
    inst = inst.drop_duplicates(["cik", "tag", "end"], keep="last")
    wide_i = inst.pivot_table(index=["cik", "end"], columns="tag", values="val", aggfunc="first", observed=True)
    w = years.set_index(["cik", "end"]).join(wide_f, how="left", rsuffix="_f").join(wide_i, how="left", rsuffix="_i")
    w.columns = [str(c) for c in w.columns]
    return _derive(w, tax_rate, excess_cash_pct)


def scoring_table(facts: pd.DataFrame, as_of: str | pd.Timestamp | None = None, tax_rate: float = 0.21,
                  excess_cash_pct: float = 0.02, ttm: bool = True, points: int = 15,
                  with_quarters: bool = False):
    """The table the score uses. ttm=False: fiscal years (methodology ≤ v1.1). ttm=True (v1.2): a rolling series
    ending at each company's latest period (a 10-Q TTM or a 10-K year), then the same period 1, 2, 3 … years earlier,
    so every point is a full 12 months and points are exactly one year apart. A point with no 12-month figure
    (quarterly data before 2011, or missing tags) falls back to the fiscal year ending nearest to it (within 6 months)."""
    k = known_as_of(facts, as_of)
    a = annual_table(facts, as_of, tax_rate, excess_cash_pct, ratios=False, known=k)
    a["is_ttm"] = False
    if not ttm and not with_quarters:
        return add_ratios(a.assign(period="FY" + a["fy"].astype(str)), tax_rate)
    t = ttm_rows(k, tax_rate, excess_cash_pct).reset_index(drop=True)
    t["is_ttm"] = True
    cand = pd.concat([a, t], ignore_index=True)
    if not ttm:
        a = a.assign(period="FY" + a["fy"].astype(str))
        s = add_ratios(a, tax_rate)
        return (s, cand) if with_quarters else s
    cand["row"] = np.arange(len(cand))
    latest = cand.groupby("cik")["end"].max()
    anchors = pd.concat([pd.DataFrame({"cik": latest.index, "k": i, "anchor": latest.to_numpy()})
                         .assign(anchor=lambda x, i=i: x["anchor"] - pd.DateOffset(years=i)) for i in range(points)])
    j = anchors.merge(cand[["cik", "end", "is_ttm", "row"]], on="cik")
    j["gap"] = (j["end"] - j["anchor"]).dt.days.abs()
    exact = j["gap"] <= 20
    j["pref"] = np.select([exact & ~j["is_ttm"], exact, ~j["is_ttm"] & (j["gap"] <= 183)], [0, 1, 2], 9)
    j = j[j["pref"] < 9].sort_values(["cik", "k", "pref", "gap"]).drop_duplicates(["cik", "k"])
    j = j.drop_duplicates(["cik", "row"])  # a fiscal year serves at most one point
    s = cand.loc[j["row"].to_numpy()].reset_index(drop=True)
    lab = latest.dt.year.where(latest.dt.month > 6, latest.dt.year - 1)
    s["fy_own"] = s["fy"]
    s["fy"] = (s["cik"].map(lab) - j["k"].to_numpy()).astype(int)
    s["period"] = np.where(s["is_ttm"], "TTM " + s["end"].dt.strftime("%b %Y"), "FY" + s["fy_own"].astype("Int64").astype(str))
    s = add_ratios(s.drop(columns="row").sort_values(["cik", "fy"]).reset_index(drop=True), tax_rate)
    return (s, cand.drop(columns="row")) if with_quarters else s


def _derive(w: pd.DataFrame, tax_rate: float, excess_cash_pct: float) -> pd.DataFrame:
    """Raw tag columns indexed by (cik, period end) → canonical values and the clean-up (no year-on-year ratios)."""
    d = pd.DataFrame(index=w.index)
    for c in ("revenue", "revenue_tag", "accn", "filed", "fy_start"):
        d[c] = w[c]
    for metric, tags in TAG_PRIORITY.items():
        if metric != "revenue":
            d[metric] = _first(w, tags)

    # --- canonical values ---
    d["gross_profit"] = d.pop("gross_profit_tag").fillna(d["revenue"] - d["cogs"])
    d["sga"] = d.pop("sga_tag").fillna(_sum_any(_col(w, "GeneralAndAdministrativeExpense"), _col(w, "SellingAndMarketingExpense")))
    d["da"] = d.pop("da_tag").fillna(_sum_any(_col(w, "Depreciation"), _col(w, "AmortizationOfIntangibleAssets")))
    d["interest"] = d["interest"].abs()
    parts = _sum_any(_col(w, "GoodwillImpairmentLoss"), _col(w, "ImpairmentOfIntangibleAssetsExcludingGoodwill")
                     .fillna(_col(w, "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill")),
                     _col(w, "ImpairmentOfLongLivedAssetsHeldForUse"))
    d["impairment"] = pd.concat([_col(w, "AssetImpairmentCharges"), _col(w, "GoodwillAndIntangibleAssetImpairment"), parts],
                                axis=1).max(axis=1)
    d["one_offs"] = _sum_any(d["impairment"], d["restructuring"], d["litigation"], d["acq_costs"], -d["gains"]).fillna(0.0)
    d["clean_oi"] = d["op_income"] + d["one_offs"]
    # cross-check: some filers tag a segment total as operating income (spot-check, TechnipFMC)
    gap = (d["op_income"] - (d["revenue"] - d["costs_total"])).abs()
    d["oi_check_gap"] = gap / d["op_income"].abs()  # share of operating income ...
    d.loc[gap < 0.01 * d["revenue"], "oi_check_gap"] = 0.0  # ... ignored when under 1% of revenue
    d["nopat"] = d["clean_oi"] * (1 - tax_rate)
    d["clean_ni"] = d["net_income"] + d["one_offs"] * (1 - tax_rate)

    ltd_split = _sum_any(_col(w, "LongTermDebtNoncurrent"), _col(w, "LongTermDebtCurrent").fillna(_col(w, "DebtCurrent")))
    ltd_cl = _sum_any(_col(w, "LongTermDebtAndCapitalLeaseObligations"), _col(w, "LongTermDebtAndCapitalLeaseObligationsCurrent"))
    ltd = _col(w, "LongTermDebt").fillna(ltd_split)
    leases_in = ltd.isna() & ltd_cl.notna()
    ltd = ltd.fillna(ltd_cl)
    used_debtcur = _col(w, "LongTermDebtCurrent").isna() & _col(w, "DebtCurrent").notna()
    st = _sum_any(_col(w, "ShortTermBorrowings"), _col(w, "CommercialPaper")).where(~used_debtcur)
    fin_lease = _col(w, "FinanceLeaseLiability").fillna(
        _sum_any(_col(w, "FinanceLeaseLiabilityNoncurrent"), _col(w, "FinanceLeaseLiabilityCurrent"))
    ).fillna(_col(w, "CapitalLeaseObligations")).where(~leases_in)
    d["debt"] = _sum_any(ltd, st, fin_lease).fillna(0.0)
    d["debt_reported"] = ltd.notna() | st.notna()

    d["cash"] = _sum_any(d.pop("cash_tag"), d["st_invest"])
    d["excess_cash"] = (d["cash"].fillna(0) - excess_cash_pct * d["revenue"]).clip(lower=0)
    d["liabilities"] = d.pop("liab_tag").fillna(d["liab_equity"] - d["equity_nci"])
    d["ic"] = d["equity"] + d["debt"] - d["excess_cash"]
    d["ic_ex_gw"] = d["ic"] - d["goodwill"].fillna(0) - d["intangibles"].fillna(0)
    d["fcf"] = d["cfo"] - d["capex"].fillna(0)
    d["ebitda"] = d["clean_oi"] + d["da"]
    d["net_debt"] = d["debt"] - d["cash"].fillna(0)
    d = d.reset_index().sort_values(["cik", "end"]).reset_index(drop=True)
    d["fy"] = d["end"].dt.year.where(d["end"].dt.month > 6, d["end"].dt.year - 1)  # FY label: year most months fall in
    return d


def _lag(d: pd.DataFrame, col: str, n: int) -> pd.Series:
    """Value n fiscal years earlier (by FY label, so a missing year gives NaN instead of a wrong lag)."""
    m = d.set_index(["cik", "fy"])[col]
    idx = pd.MultiIndex.from_arrays([d["cik"], d["fy"] - n])
    return pd.Series(m.reindex(idx).to_numpy(), index=d.index)


def add_ratios(d: pd.DataFrame, tax_rate: float) -> pd.DataFrame:
    def div(a, b):
        b = b.where(b != 0)
        return a / b

    avg = lambda col: pd.concat([d[col], _lag(d, col, 1)], axis=1).mean(axis=1)  # noqa: E731
    ic_avg = avg("ic")
    d["roic"] = div(d["nopat"], ic_avg.where(ic_avg > 0))
    ic_gw_avg = avg("ic_ex_gw")
    d["roic_ex_gw"] = div(d["nopat"], ic_gw_avg.where(ic_gw_avg > 0))
    ic3 = _lag(d, "ic", 3)
    d_ic3 = d["ic"] - ic3
    # only when capital grew by at least 10%: a tiny denominator gives meaningless ratios
    d["incr_roic"] = div(d["nopat"] - _lag(d, "nopat", 3), d_ic3.where((d_ic3 > 0) & (d_ic3 >= 0.10 * ic3.abs()))).clip(-1, 2)
    assets_avg = avg("assets")
    d["gross_margin"] = div(d["gross_profit"], d["revenue"])
    d["gp_assets"] = div(d["gross_profit"], assets_avg)
    d["op_margin"] = div(d["clean_oi"], d["revenue"])
    d_rev3 = d["revenue"] - _lag(d, "revenue", 3)
    d["incr_margin"] = div(d["clean_oi"] - _lag(d, "clean_oi", 3), d_rev3.where(d_rev3 > 0)).clip(-1, 1)
    d["sga_rev"] = div(d["sga"], d["revenue"])
    d["asset_turnover"] = div(d["revenue"], assets_avg)
    d["rev_growth"] = div(d["revenue"], _lag(d, "revenue", 1)) - 1
    d["rev_cagr3"] = div(d["revenue"], _lag(d, "revenue", 3)) ** (1 / 3) - 1
    d["fcf_conv"] = div(d["fcf"], d["clean_ni"].where(d["clean_ni"] > 0)).clip(-2, 3)
    d["accruals"] = div(d["net_income"] - d["cfo"], assets_avg)
    d["reinvest_rate"] = div(d["ic"] - _lag(d, "ic", 1), d["nopat"].where(d["nopat"] > 0)).clip(0, 1.5)
    d["runway"] = d["reinvest_rate"] * d["incr_roic"]
    # gross-margin stability: − standard deviation over the last 5 years (higher = steadier)
    gm = pd.concat([_lag(d, "gross_margin", i) for i in range(5)], axis=1)
    d["gm_stability"] = -gm.std(axis=1).where(gm.notna().sum(axis=1) >= 4)

    # --- risk gate inputs ---
    d["interest_cover"] = div(d["clean_oi"], d["interest"].where(d["interest"] > 0))
    d["nd_ebitda"] = div(d["net_debt"], d["ebitda"].where(d["ebitda"] > 0))
    d.loc[(d["ebitda"] <= 0) & (d["net_debt"] > 0), "nd_ebitda"] = np.inf
    ta, tl = d["assets"], d["liabilities"]
    d["altman_z"] = (6.56 * div(d["assets_cur"] - d["liab_cur"], ta) + 3.26 * div(d["retained"], ta)
                     + 6.72 * div(d["clean_oi"], ta) + 1.05 * div(d["equity_nci"], tl))
    d["beneish_m"], d["beneish_n"] = _beneish(d)
    d["beneish_sgi"] = (d["revenue"] / _lag(d, "revenue", 1)).where(lambda x: np.isfinite(x)).fillna(1.0)
    sh3 = _lag(d, "shares", 3)
    d["dilution"] = div(d["shares"], sh3) ** (1 / 3) - 1
    d["sbc_rev"] = div(d["sbc"], d["revenue"])
    d["goodwill_jump"] = div(d["goodwill"].fillna(0) - _lag(d, "goodwill", 3).fillna(0), ta)
    d.loc[d["goodwill"].isna() & _lag(d, "goodwill", 3).isna(), "goodwill_jump"] = 0.0
    return d


def _beneish(d: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Beneish (1999) 8-variable M-Score. A missing index is set to 1 (neutral); the count of indexes actually
    computed is returned so the gate can skip companies with too little data."""
    L = lambda c: _lag(d, c, 1)  # noqa: E731
    def r(a, b):
        return a / b.where(b != 0)
    rev, rev1 = d["revenue"], L("revenue")
    dsri = r(r(d["receivables"], rev), r(L("receivables"), rev1))
    gmi = r(r(rev1 - L("cogs"), rev1), r(rev - d["cogs"], rev))
    aq = lambda ca, ppe, ta: 1 - r(ca + ppe, ta)  # noqa: E731
    aqi = r(aq(d["assets_cur"], d["ppe"], d["assets"]), aq(L("assets_cur"), L("ppe"), L("assets")))
    sgi = r(rev, rev1)
    dep = lambda da, ppe: r(da, da + ppe)  # noqa: E731
    depi = r(dep(L("da"), L("ppe")), dep(d["da"], d["ppe"]))
    sgai = r(r(d["sga"], rev), r(L("sga"), rev1))
    lev = lambda cl, debt, ta: r(cl + debt, ta)  # noqa: E731
    lvgi = r(lev(d["liab_cur"], d["debt"], d["assets"]), lev(L("liab_cur"), L("debt"), L("assets")))
    tata = r(d["net_income"] - d["cfo"], d["assets"])
    idx = pd.concat([dsri, gmi, aqi, sgi, depi, sgai, lvgi], axis=1).replace([np.inf, -np.inf], np.nan)
    n = idx.notna().sum(axis=1) + tata.notna()
    idx = idx.fillna(1.0)
    m = (-4.84 + 0.92 * idx[0] + 0.528 * idx[1] + 0.404 * idx[2] + 0.892 * idx[3] + 0.115 * idx[4]
         - 0.172 * idx[5] + 4.679 * tata.fillna(0) - 0.327 * idx[6])
    return m, n
