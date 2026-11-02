"""Day 3: Layer 1 score = gate + weighted percentile ranks + 10x plausibility penalty.

Run:  python src/score.py                 (as of the universe date, market cap from Stock Analysis)
Out:  data/private/layer1_scores_<date>.csv (local only: contains licensed market-cap columns)

Market cap is passed in, so the Day 4 backtest can supply a 2019 market cap instead.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

from sec_client import DATA_PRIVATE, ROOT
from signals import company_signals

CONFIG = ROOT / "config.yaml"


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def compute_signals(ciks: list[str], as_of: str, workers: int = 6) -> pd.DataFrame:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(company_signals, ciks, [as_of] * len(ciks), chunksize=20))
    return pd.DataFrame(rows)


def required_cagr(rev_ttm: pd.Series, market_cap: pd.Series, sector: pd.Series, cfg: dict) -> pd.Series:
    p = cfg["plausibility"]
    exit_ps = sector.map(p["exit_ps_by_sector"]).fillna(p["exit_ps_default"])
    required_rev = 10 * market_cap / exit_ps
    return (required_rev / rev_ttm) ** (1 / p["years"]) - 1


def score(sig: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """`sig` needs signal columns plus market_cap_usd and sector. Returns ranked eligible rows."""
    g = cfg["gate"]
    df = sig[sig["status"] == "ok"].copy()
    grow_ok = df["rev_growth"] >= g["min_rev_growth"]
    turn_ok = df["turnaround"].astype(bool) & g["allow_turnaround"]
    df = df[(grow_ok | turn_ok) & (df["rev_ttm"] >= g["min_rev_ttm_usd"])].copy()

    df["required_cagr"] = required_cagr(df["rev_ttm"], df["market_cap_usd"], df["sector"], cfg)

    def rank(s: pd.Series) -> pd.Series:
        return s.astype(float).rank(pct=True).fillna(0.5)

    comp = {
        "rev_growth": rank(df["rev_growth"]),
        "rev_accel": rank(df["rev_accel"]),
        "gm_delta": rank(df["gm_delta"]),
        "om_delta": rank(df["om_delta"]),
        "turnaround": df["turnaround"].astype(float),
        "low_dilution": rank(-df["share_growth"].astype(float)),
        "plausibility": rank(-df["required_cagr"]),
        "rev_new_high": rank(df["rev_vs_peak"]),
        "small_size": rank(-df["market_cap_usd"].astype(float)),
    }
    w = {k: 0.0 for k in comp} | cfg["weights"]
    assert abs(sum(w.values()) - 1) < 1e-9, "weights must sum to 1"
    df["score"] = sum(w[k] * comp[k] for k in w)
    for k, v in comp.items():
        df[f"r_{k}"] = v

    p = cfg["plausibility"]
    mega = 10 * df["market_cap_usd"] > p["mega_end_cap_usd"]
    df.loc[mega, "score"] *= p["mega_multiplier"]
    df["mega_penalty"] = mega

    pen = cfg["penalties"]
    diluted = df["share_growth"].astype(float) > pen["dilution_above"]
    lumpy = df["max_q_share"].astype(float) > pen["lumpy_q_share_above"]
    df.loc[diluted, "score"] *= pen["dilution_multiplier"]
    df.loc[lumpy, "score"] *= pen["lumpy_multiplier"]
    df["dilution_penalty"], df["lumpy_penalty"] = diluted, lumpy

    df = df.sort_values("score", ascending=False)
    df["rank"] = range(1, len(df) + 1)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="universe date; default from config.yaml")
    args = ap.parse_args()
    cfg = load_config()
    date = args.date or cfg["universe_date"]

    uni = pd.read_csv(DATA_PRIVATE / f"universe_with_cik_{date}.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]]
    sig = compute_signals(uni["cik"].tolist(), date)
    keep = ["cik", "ticker", "company_name", "sector", "industry", "market_cap_usd", "analyst_count",
            "flag_note", "revenue_ttm_usd", "financial_currency"]
    sig = sig.merge(uni[keep], on="cik", how="left")

    ranked = score(sig, cfg)
    out = DATA_PRIVATE / f"layer1_scores_{date}.csv"
    sig.merge(ranked[["cik", "required_cagr", "score", "rank", "mega_penalty", "dilution_penalty", "lumpy_penalty"] +
                     [c for c in ranked if c.startswith("r_")]], on="cik", how="left") \
       .sort_values("rank").to_csv(out, index=False)

    print(f"companies scored        : {len(sig)}")
    print("status                  :", sig["status"].value_counts().to_dict())
    print(f"passed gate (ranked)    : {len(ranked)}")
    print(f"turnarounds among ranked: {int(ranked['turnaround'].sum())}")
    print(f"mega-cap penalty applied: {int(ranked['mega_penalty'].sum())}")
    print(f"dilution penalty applied: {int(ranked['dilution_penalty'].sum())}")
    print(f"lumpy penalty applied   : {int(ranked['lumpy_penalty'].sum())}")
    print(f"output                  : {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
