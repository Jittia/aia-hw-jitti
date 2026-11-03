"""Moat Momentum · steps 2–5: universe → risk gate → five themes → Moat Score → confirmation.

score_as_of(table, companies, as_of, settings, live=True) works on the company-year table from mm_fundamentals and
uses only fiscal years filed by `as_of`. The same function serves the live run and every validation year.

Each indicator gets three components, each a 0–100 percentile WITHIN the company's industry (SIC 4-digit, widened to
3 then 2 digits until there are at least `min_peers` companies):
  LEVEL        latest fiscal year value
  TREND        least-squares slope over the last 5 fiscal years (needs ≥ 3)
  CONSISTENCY  share of the last 4 year-on-year changes that improved (needs ≥ 3)
Indicators that are themselves a change (incremental ROIC, incremental margin, peer-rank change) only have TREND.
Indicator score = blend of available components; theme score = mean of its indicators;
theme "improving" score = blend of TREND and CONSISTENCY only. Moat Score = weighted themes − risk penalties.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# name, theme, column, direction (+1 higher is better), components
INDICATORS = [
    ("roic_spread", "value", "roic_spread", 1, "LTC"),
    ("incr_roic", "value", "incr_roic", 1, "T"),
    ("gross_margin", "pricing", "gross_margin", 1, "LTC"),
    ("gp_assets", "pricing", "gp_assets", 1, "LTC"),
    ("gm_stability", "pricing", "gm_stability", 1, "L"),
    ("incr_margin", "scale", "incr_margin", 1, "T"),
    ("sga_rev", "scale", "sga_rev", -1, "LTC"),
    ("asset_turnover", "scale", "asset_turnover", 1, "LTC"),
    ("rev_excess", "peers", "rev_excess", 1, "LTC"),
    ("peer_rank_change", "peers", "peer_rank_change", 1, "T"),
    ("fcf_conv", "quality", "fcf_conv", 1, "LTC"),
    ("accruals", "quality", "accruals", -1, "LTC"),
    ("runway", "quality", "runway", 1, "L"),
]
THEMES = ["value", "pricing", "scale", "peers", "quality"]
THEME_NAMES = {"value": "Value creation", "pricing": "Pricing power", "scale": "Scale advantage",
               "peers": "Pulling away from peers", "quality": "Profit quality & runway"}
CORE = ["revenue", "gross_profit", "op_income", "equity", "assets", "cfo", "shares", "sga"]
RISKS = ["interest_cover", "net_debt_ebitda", "altman_z", "beneish_m", "dilution", "sbc_revenue", "goodwill_jump"]


def _lag(d: pd.DataFrame, col: str, n: int) -> pd.Series:
    m = d.set_index(["cik", "fy"])[col]
    idx = pd.MultiIndex.from_arrays([d["cik"], d["fy"] - n])
    return pd.Series(m.reindex(idx).to_numpy(), index=d.index)


def industry_groups(sic: pd.Series, min_peers: int) -> pd.Series:
    """Narrowest SIC level (4 → 3 → 2 digits → 'all') whose full group has at least min_peers members.
    Groups at a wider level include the narrower ones, so a company's peers are everyone in its chosen group."""
    s4 = sic.astype(int).astype(str).str.zfill(4)
    out = pd.Series("all", index=sic.index)
    for digits in (2, 3, 4):  # widest first, narrower overwrites when big enough
        g = s4.str[:digits]
        big = g.map(g.value_counts()) >= min_peers
        out = out.where(~big, "SIC " + g)
    return out


def rank_in_groups(values: pd.DataFrame, group: pd.Series, sic: pd.Series) -> pd.DataFrame:
    """0–100 percentile of each column against the company's chosen peer group. A wider group (e.g. SIC 36)
    contains every company whose SIC starts with it, including those placed in a narrower group."""
    out = pd.DataFrame(np.nan, index=values.index, columns=values.columns)
    sic4 = sic.astype("Int64").astype(str).str.zfill(4)
    for g in group.dropna().unique():
        members = group.notna() if g == "all" else (sic4.str.startswith(g[4:]) & group.notna())
        targets = group == g
        out.loc[targets] = (values[members].rank(pct=True) * 100).loc[targets]
    return out


def add_panel_columns(d: pd.DataFrame, companies: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Columns that need the whole panel (industry medians, peer ranks per year)."""
    d = d.copy()
    d["roic_spread"] = d["roic"] - settings["hurdle_rate"]
    sic = d["cik"].map(companies.set_index("cik")["sic"])
    d["sic"] = sic
    yr_group = industry_groups(sic, settings["scoring"]["min_peers"])  # broad, panel-wide grouping
    d["pgroup"] = yr_group
    med_g = d.groupby(["pgroup", "fy"])["rev_growth"].transform("median")
    d["rev_growth_excess"] = d["rev_growth"] - med_g
    med_c = d.groupby(["pgroup", "fy"])["rev_cagr3"].transform("median")
    d["rev_excess"] = d["rev_cagr3"] - med_c
    lvl = [d.groupby(["pgroup", "fy"])[c].rank(pct=True) for c in ("roic", "gross_margin", "op_margin", "asset_turnover")]
    d["peer_level_rank"] = pd.concat(lvl, axis=1).mean(axis=1) * 100
    d["peer_rank_change"] = d["peer_level_rank"] - _lag(d, "peer_level_rank", 3)
    return d


def _window(d: pd.DataFrame, latest: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """(companies × n) values for fiscal years t−n+1 … t (oldest first)."""
    m = d.set_index(["cik", "fy"])[col]
    cols = []
    for k in range(n - 1, -1, -1):
        idx = pd.MultiIndex.from_arrays([latest["cik"], latest["fy"] - k])
        cols.append(m.reindex(idx).to_numpy(dtype=float))
    return np.column_stack(cols)


def _slope(y: np.ndarray, min_pts: int = 3) -> np.ndarray:
    x = np.arange(y.shape[1], dtype=float)
    out = np.full(y.shape[0], np.nan)
    for i, row in enumerate(y):
        ok = np.isfinite(row)
        if ok.sum() >= min_pts:
            out[i] = np.polyfit(x[ok], row[ok], 1)[0]
    return out


def _consistency(y: np.ndarray, direction: int, min_changes: int = 3) -> np.ndarray:
    diff = np.diff(y, axis=1) * direction
    ok = np.isfinite(diff)
    n = ok.sum(axis=1)
    up = ((diff > 0) & ok).sum(axis=1)
    return np.where(n >= min_changes, up / np.maximum(n, 1), np.nan)


def pick_latest(d: pd.DataFrame, as_of: str, max_age_days: int = 548) -> pd.DataFrame:
    """Latest fiscal year per company filed by as_of and not older than ~18 months."""
    a = pd.Timestamp(as_of)
    x = d[(d["filed"] <= a) & (d["end"] >= a - pd.Timedelta(days=max_age_days))]
    return x.sort_values("end").drop_duplicates("cik", keep="last").reset_index(drop=True)


def universe(d: pd.DataFrame, latest: pd.DataFrame, companies: pd.DataFrame, as_of: str, settings: dict,
             live: bool) -> pd.DataFrame:
    u = settings["universe"]
    nyears = d[d["end"] <= latest.set_index("cik").reindex(d["cik"])["end"].to_numpy()].groupby("cik")["fy"].nunique()
    latest = latest.copy()
    latest["years"] = latest["cik"].map(nyears).fillna(0).astype(int)
    comp = companies.set_index("cik")
    latest["name"] = latest["cik"].map(comp["name"])
    latest["ticker"] = latest["cik"].map(comp["tickers"].map(lambda t: t[0] if t else None))
    latest["exchange"] = latest["cik"].map(comp["exchanges"].map(lambda e: e[0] if e else None))
    latest["sic_desc"] = latest["cik"].map(comp["sic_desc"])
    keep = (latest["revenue"] >= u["min_revenue_usd"]) & (latest["years"] >= u["min_years"])
    lo, hi = u["exclude_sic"]
    keep &= ~latest["sic"].between(lo, hi)
    if live:
        keep &= latest["exchange"].isin(u["exchanges"])
    latest["in_universe"] = keep
    return latest


def components(d: pd.DataFrame, latest: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Raw L/T/C values per indicator, then 0–100 percentiles within industry."""
    sc = settings["scoring"]
    n_t = sc["trend_years"]
    n_c = sc["consistency_years"] + 1
    raw = pd.DataFrame(index=latest.index)
    for name, _theme, col, direction, comps in INDICATORS:
        win = _window(d, latest, col, max(n_t, n_c))
        win = np.where(np.isfinite(win), win, np.nan)
        if "L" in comps:
            raw[f"{name}_L"] = win[:, -1] * direction
        if "T" in comps:
            raw[f"{name}_T"] = (_slope(win[:, -n_t:]) * direction) if comps != "T" else win[:, -1] * direction
        if "C" in comps:
            raw[f"{name}_C"] = _consistency(win[:, -n_c:], direction)
    inu = latest["in_universe"]
    grp = pd.Series(np.nan, index=latest.index, dtype=object)
    grp[inu] = industry_groups(latest.loc[inu, "sic"], sc["min_peers"])
    pct = rank_in_groups(raw, grp, latest["sic"])
    pct["industry_group"] = grp
    return raw, pct


def combine(pct: pd.DataFrame, settings: dict, penalties: pd.Series | None = None) -> pd.DataFrame:
    """Indicator → theme → Moat Score. Mirrored 1:1 in the web page so sliders re-rank instantly."""
    sc = settings["scoring"]
    b = {"L": sc["blend"]["level"], "T": sc["blend"]["trend"], "C": sc["blend"]["consistency"]}
    out = pd.DataFrame(index=pct.index)
    theme_ind, theme_imp = {t: [] for t in THEMES}, {t: [] for t in THEMES}
    for name, theme, _col, _dir, comps in INDICATORS:
        num = sum(pct[f"{name}_{c}"].fillna(0) * b[c] for c in comps)
        den = sum(pct[f"{name}_{c}"].notna() * b[c] for c in comps)
        out[f"ind_{name}"] = num / den.where(den > 0)
        imp = [c for c in comps if c in "TC"]
        if imp:
            num = sum(pct[f"{name}_{c}"].fillna(0) * b[c] for c in imp)
            den = sum(pct[f"{name}_{c}"].notna() * b[c] for c in imp)
            out[f"imp_{name}"] = num / den.where(den > 0)
            theme_imp[theme].append(out[f"imp_{name}"])
        theme_ind[theme].append(out[f"ind_{name}"])
    w = sc["theme_weights"]
    num = pd.Series(0.0, index=pct.index)
    den = pd.Series(0.0, index=pct.index)
    improving = pd.Series(0, index=pct.index)
    for t in THEMES:
        out[f"theme_{t}"] = pd.concat(theme_ind[t], axis=1).mean(axis=1)
        out[f"improving_{t}"] = pd.concat(theme_imp[t], axis=1).mean(axis=1)
        num += out[f"theme_{t}"].fillna(0) * w[t]
        den += out[f"theme_{t}"].notna() * w[t]
        improving += (out[f"improving_{t}"] >= sc["improving_rank"]).astype(int)
    out["themes_improving"] = improving
    out["themes_available"] = sum(out[f"theme_{t}"].notna() for t in THEMES)
    out["moat_raw"] = num / den.where(den > 0)
    out["moat_score"] = out["moat_raw"] - (penalties if penalties is not None else 0)
    out["moat_strengthening"] = improving >= sc["confirm_themes"]
    return out


def risk_gate(d: pd.DataFrame, latest: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Per rule: value, threshold, breach, worsening trend; then status remove / flag / pass per settings."""
    rg = settings["risk_gate"]
    r = pd.DataFrame(index=latest.index)
    r["interest_cover"] = latest["interest_cover"]
    r["net_debt_ebitda"] = latest["nd_ebitda"]
    r["altman_z"] = latest["altman_z"]
    r["beneish_m"] = latest["beneish_m"].where(latest["beneish_n"] >= 6)
    r["dilution"] = latest["dilution"]
    r["sbc_revenue"] = latest["sbc_rev"]
    r["goodwill_jump"] = latest["goodwill_jump"]
    rules = {
        "interest_cover": ("below", rg["interest_cover"]), "net_debt_ebitda": ("above", rg["net_debt_ebitda"]),
        "altman_z": ("below", rg["altman_z"]), "beneish_m": ("above", rg["beneish_m"]),
        "dilution": ("above", rg["dilution"]), "sbc_revenue": ("above", rg["sbc_revenue"]),
        "goodwill_jump": ("above", rg["goodwill_jump"]),
    }
    removed = pd.Series(False, index=latest.index)
    flags = pd.Series(0, index=latest.index)
    reasons = [[] for _ in range(len(latest))]
    # worsening trend: 3 consecutive years moving the wrong way and within 1.5x of the threshold
    trend = {"interest_cover": ("interest_cover", -1), "net_debt_ebitda": ("nd_ebitda", 1), "altman_z": ("altman_z", -1)}
    for rule, (side, cfg) in rules.items():
        th = cfg["below"] if side == "below" else cfg["above"]
        v = r[rule]
        breach = (v < th) if side == "below" else (v > th)
        breach &= v.notna()
        r[f"{rule}_breach"] = breach
        worse = pd.Series(False, index=latest.index)
        if rule in trend:
            col, sign = trend[rule]
            win = _window(d, latest, col, 4)
            dif = np.diff(np.where(np.isfinite(win), win, np.nan), axis=1) * sign
            worse = pd.Series((dif > 0).all(axis=1) & np.isfinite(dif).all(axis=1), index=latest.index)
            near = (v < th * 1.5) if side == "below" else (v > th / 1.5)
            worse &= near & ~breach
        r[f"{rule}_worsening"] = worse
        mode = cfg["mode"]
        if mode == "remove":
            removed |= breach
            flags += worse.astype(int)
        elif mode == "flag":
            flags += breach.astype(int) + worse.astype(int)
        for i in np.flatnonzero((breach | worse).to_numpy()):
            reasons[i].append(rule + (" (worsening)" if worse.iloc[i] and not breach.iloc[i] else ""))
    r["removed"] = removed
    r["flags"] = flags
    r["penalty"] = flags * rg["flag_penalty"]
    r["gate_reasons"] = ["; ".join(x) for x in reasons]
    return r


def confidence(d: pd.DataFrame, latest: pd.DataFrame) -> pd.Series:
    cov = np.mean([np.isfinite(_window(d, latest, c, 5)).mean(axis=1) for c in CORE], axis=0)
    big_adj = (latest["one_offs"].abs() > 0.5 * latest["op_income"].abs()).to_numpy()
    oi_gap = (latest["oi_check_gap"] > 0.10).to_numpy()
    lvl = np.where(cov >= 0.9, "High", np.where(cov >= 0.7, "Medium", "Low"))
    lvl = np.where(big_adj & (lvl == "High"), "Medium", lvl)
    lvl = np.where(oi_gap, np.where(lvl == "High", "Medium", "Low"), lvl)  # one level down
    return pd.Series(lvl, index=latest.index), pd.Series(cov, index=latest.index)


def score_as_of(d: pd.DataFrame, companies: pd.DataFrame, as_of: str, settings: dict, live: bool = True) -> dict:
    d = d[d["filed"] <= pd.Timestamp(as_of)]
    d = add_panel_columns(d, companies, settings)
    latest = pick_latest(d, as_of, settings["universe"]["latest_10k_within_days"])
    latest = universe(d, latest, companies, as_of, settings, live)
    raw, pct = components(d, latest, settings)
    gate = risk_gate(d, latest, settings)
    res = combine(pct, settings, gate["penalty"])
    latest["confidence"], latest["coverage"] = confidence(d, latest)
    res = pd.concat([latest, gate.add_prefix("gate_").rename(columns={"gate_gate_reasons": "gate_reasons"}), res], axis=1)
    res["industry_group"] = pct["industry_group"]
    u = res[res["in_universe"]]
    res["rank"] = u["moat_score"].rank(ascending=False, method="first")
    res["industry_rank"] = u.groupby("industry_group")["moat_score"].rank(ascending=False, method="first")
    elig = u[~u["gate_removed"] & u["moat_strengthening"]].sort_values("moat_score", ascending=False)
    res["shortlist"] = res.index.isin(elig.index[: settings["scoring"]["shortlist_size"]])
    return {"results": res, "raw": raw, "pct": pct, "panel": d}
