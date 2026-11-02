"""Day 4: point-in-time backtest of the Layer 1 score against 5-year 10-baggers.

  tune window    as of 2019-12-31 → 2024-12-31
  holdout window as of 2018-12-31 → 2023-12-31   (checks the chosen weights are not fitted to one period)

Ground truth = total return (Yahoo adjusted close) ≥ 10x. Market cap on the as-of date
= raw traded price × SEC cover-page shares visible on that date.

SURVIVORSHIP BIAS: the universe is today's listed companies (2026-11-02). Companies that went
bankrupt, were acquired or delisted are missing, so absolute hit rates are optimistic. The test
is still useful for comparing weight variants with each other on the same population.

Run:  python src/backtest.py          Out: output/backtest_report.md
"""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from prices import OUT as PRICES, yahoo_ticker
from quarters import instant_series
from score import compute_signals, load_config, score
from sec_client import DATA_CACHE, DATA_PRIVATE, ROOT

WINDOWS = {"tune": ("2019-12-31", "2024-12-31"), "holdout": ("2018-12-31", "2023-12-31")}
TOP_N = 100

# Weight variants (each must sum to 1). Penalties stay as in config.yaml.
DAY3_WEIGHTS = {"rev_growth": 0.20, "rev_accel": 0.20, "gm_delta": 0.10, "om_delta": 0.15,
                "turnaround": 0.10, "low_dilution": 0.05, "plausibility": 0.20, "small_size": 0.0,
                "rev_new_high": 0.0}
VARIANTS = {
    "config.yaml (current)": {},
    "day3_baseline": DAY3_WEIGHTS,
    "new_high": {**DAY3_WEIGHTS, "turnaround": 0.0, "rev_accel": 0.10, "rev_new_high": 0.20},
    "growth_heavy": {**DAY3_WEIGHTS, "rev_growth": 0.40, "gm_delta": 0.05, "om_delta": 0.10,
                     "turnaround": 0.0},
    "no_plausibility": {**DAY3_WEIGHTS, "rev_growth": 0.30, "rev_accel": 0.25, "om_delta": 0.20,
                        "plausibility": 0.0},
    "growth_only": {k: 0.0 for k in DAY3_WEIGHTS} | {"rev_growth": 1.0},
    "plausibility_heavy": {**DAY3_WEIGHTS, "rev_growth": 0.15, "rev_accel": 0.15, "gm_delta": 0.05,
                           "om_delta": 0.10, "turnaround": 0.05, "plausibility": 0.45, "small_size": 0.0},
    "size_heavy": {**DAY3_WEIGHTS, "rev_growth": 0.15, "rev_accel": 0.15, "gm_delta": 0.05,
                   "om_delta": 0.10, "turnaround": 0.05, "plausibility": 0.20, "small_size": 0.25},
}


def shares_as_of(cik: str, as_of: str) -> float | None:
    s = instant_series(cik, "shares_outstanding", as_of)
    return float(s.iloc[-1]["val"]) if not s.empty else None


def build_population(as_of: str, end: str) -> pd.DataFrame:
    """Signals as of `as_of` + market cap + forward return. Signals are cached per date."""
    uni = pd.read_csv(DATA_PRIVATE / "universe_with_cik_2026-11-02.csv", dtype={"cik": str})
    uni = uni[uni["include_flag"] & uni["is_primary_class"]][["cik", "ticker", "sector", "industry"]]

    cache = DATA_CACHE / f"signals_{as_of}.csv"
    if cache.exists():
        sig = pd.read_csv(cache, dtype={"cik": str})
    else:
        sig = compute_signals(uni["cik"].tolist(), as_of)
        sig["shares_asof"] = [shares_as_of(c, as_of) for c in sig["cik"]]
        sig.to_csv(cache, index=False)
    df = sig.merge(uni, on="cik", how="left")

    px = pd.read_csv(PRICES)
    df["yahoo_ticker"] = df["ticker"].map(yahoo_ticker)
    df = df.merge(px[["yahoo_ticker", f"adj_{as_of}", f"raw_{as_of}", f"adj_{end}"]], on="yahoo_ticker", how="left")
    df["market_cap_usd"] = df[f"raw_{as_of}"] * df["shares_asof"]
    df["fwd_return"] = df[f"adj_{end}"] / df[f"adj_{as_of}"]
    return df


def evaluate(pop: pd.DataFrame, cfg: dict) -> tuple[dict, pd.DataFrame]:
    """Population = priced at both dates (survivors). Recall counts every 10-bagger in it."""
    priced = pop[pop["fwd_return"].notna()].copy()
    scorable = priced[(priced["status"] == "ok") & priced["market_cap_usd"].notna()]
    ranked = score(scorable, cfg)
    top = ranked.head(TOP_N)
    tb_all = priced["fwd_return"] >= 10
    base = (scorable["fwd_return"] >= 10).mean()
    prec = (top["fwd_return"] >= 10).mean()
    return {
        "priced": len(priced), "scorable": len(scorable), "ranked": len(ranked),
        "tenbaggers_priced": int(tb_all.sum()), "tenbaggers_scorable": int((scorable["fwd_return"] >= 10).sum()),
        "hits_top100": int((top["fwd_return"] >= 10).sum()),
        "recall_top100": (top["fwd_return"] >= 10).sum() / max(int(tb_all.sum()), 1),
        "precision_top100": prec, "base_rate": base, "lift": prec / base if base else float("nan"),
        "fivex_top100": int((top["fwd_return"] >= 5).sum()),
        "median_ret_top100": top["fwd_return"].median(), "median_ret_scorable": scorable["fwd_return"].median(),
        "loser_share_top100": (top["fwd_return"] < 0.5).mean(),
    }, ranked


def with_weights(cfg: dict, override: dict) -> dict:
    c = copy.deepcopy(cfg)
    c["weights"].update(override)
    assert abs(sum(c["weights"].values()) - 1) < 1e-9, override
    return c


def main() -> None:
    cfg = load_config()
    pops = {name: build_population(*w) for name, w in WINDOWS.items()}
    results, ranked_by = [], {}
    for v, override in VARIANTS.items():
        c = with_weights(cfg, override)
        for wname, pop in pops.items():
            m, ranked = evaluate(pop, c)
            results.append({"variant": v, "window": wname, **m})
            ranked_by[(v, wname)] = ranked
    res = pd.DataFrame(results)
    res.to_csv(DATA_CACHE / "backtest_results.csv", index=False)
    cols = ["variant", "window", "hits_top100", "tenbaggers_priced", "recall_top100", "precision_top100",
            "base_rate", "lift", "fivex_top100", "median_ret_top100", "median_ret_scorable", "loser_share_top100"]
    with pd.option_context("display.width", 220, "display.float_format", "{:.3f}".format):
        print(res[cols].to_string(index=False))
    no_gate = copy.deepcopy(cfg)
    no_gate["gate"]["min_rev_growth"] = -1.0
    gate_rows = [{"window": w, **evaluate(pop, no_gate)[0]} for w, pop in pops.items()]

    pd.to_pickle({"pops": pops, "ranked": ranked_by, "results": res}, DATA_CACHE / "backtest_state.pkl")
    write_report(res, pd.DataFrame(gate_rows), pops, ranked_by)
    print(f"report: {REPORT.relative_to(ROOT)}")


REPORT = ROOT / "output" / "backtest_report.md"


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def write_report(res: pd.DataFrame, gate: pd.DataFrame, pops: dict, ranked_by: dict) -> None:
    """Public report: only SEC- and Yahoo-derived values (no licensed screener data)."""
    cur = "config.yaml (current)"
    lines = [
        "---", "title: Layer 1 backtest — 10-baggers 2018/2019 → 2023/2024", "type: note",
        "created: 2026-11-02", "updated: 2026-11-02", "tags: [backtest, US, layer1]",
        "sources: [SEC EDGAR XBRL companyfacts API, Yahoo Finance via yfinance]", "status: draft", "---", "",
        "# Layer 1 backtest", "",
        "**Question:** if the Layer 1 score had been run on a past date using only filings public at that time, "
        f"would its top {TOP_N} have contained the stocks that went on to return ≥10x in the next 5 years?", "",
        "## Method", "",
        "| Window | As of | Return measured to |", "|---|---|---|",
        *[f"| {w} | {a} | {e} |" for w, (a, e) in WINDOWS.items()], "",
        "- Fundamentals: SEC EDGAR XBRL companyfacts, only facts **filed on or before** the as-of date "
        "(https://data.sec.gov/api/xbrl/companyfacts/, retrieved 2026-11-02).",
        "- Prices: Yahoo Finance via `yfinance` (https://finance.yahoo.com, retrieved 2026-11-02). Return = adjusted close "
        "(splits + dividends). Market cap on the as-of date = actual traded price × SEC cover-page shares.",
        "- Universe: 2,499 US companies that file 10-Qs and are listed today; population = those with a price on both dates.",
        f"- Metrics: **hits** = 10-baggers in the top {TOP_N}; **recall** = hits ÷ all 10-baggers in the population; "
        "**precision** = hits ÷ 100; **lift** = precision ÷ base rate (1.0 = no better than random); "
        f"**5x+** = top-{TOP_N} names returning ≥5x; **halved** = share of the top {TOP_N} that lost ≥50%.", "",
        "> **Survivorship bias:** companies that went bankrupt, were acquired or delisted before 2026-11-02 are missing. "
        "Absolute hit rates and returns are therefore optimistic. The test is still fair for comparing variants, "
        "because they all see the same population.", "",
        "> **Small sample:** only ~25 ten-baggers per window. A difference of 1–2 hits between variants is noise, "
        "so the 5x+, median and halved columns (100 names each) matter more than the hit count.", "",
        "## Findings (2026-11-02)", "",
        "1. **The score beats random, modestly.** With the chosen weights the top 100 holds 4 ten-baggers in both "
        "windows against ~1.5 expected by chance (lift ≈ 2.7–2.9x). Most 10-baggers are still missed.",
        "2. **Size is the strongest single signal.** Companies under $300M became 10-baggers ~10x more often than "
        "$1–10B companies, in both windows (table below). Removing the plausibility/size terms gave the worst results.",
        "3. **About half of all 10-baggers could not be caught on the as-of date.** Their revenue was still shrinking "
        "(e.g. NVDA 2019) or they had no revenue yet (biotech). This is the accepted cost of the "
        "\"quant proof first\" rule. Switching the gate off barely changes results, because those companies rank low anyway.",
        "4. **Rebound vs new high is undecided.** Weighting \"revenue at a new high\" helped one window and hurt the other, "
        "so turnarounds stay in and `rev_new_high` stays at 0.",
        "5. **Weights were chosen by looking at both windows, so there is no untouched test period left.** "
        "The next honest check is forward tracking of the live shortlist.", "",
        "**Chosen:** size .15 / plausibility .30 (balanced; picked by Jitti over the higher-hit, higher-blow-up "
        "`size_heavy`). Full weights in `config.yaml`.", "",
        "## Results by weight variant", "",
        "| Variant | Window | Hits | 10-baggers | Recall | Precision | Base rate | Lift | 5x+ | Median top 100 | Median all | Halved |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res.itertuples():
        lines.append(f"| {r.variant} | {r.window} | {r.hits_top100} | {r.tenbaggers_priced} | {_pct(r.recall_top100)} | "
                     f"{_pct(r.precision_top100)} | {_pct(r.base_rate)} | {r.lift:.2f} | {r.fivex_top100} | "
                     f"{r.median_ret_top100:.2f}x | {r.median_ret_scorable:.2f}x | {_pct(r.loser_share_top100)} |")
    lines += ["", "Variant weights are listed in `src/backtest.py` (`VARIANTS`); the current choice is in `config.yaml`.", "",
              "## Does the growth gate (quant proof first) cost 10-baggers?", "",
              "Same current weights, gate switched off (declining-revenue companies also ranked):", "",
              "| Window | Hits | 5x+ | Median top 100 | Halved | Lift |", "|---|---|---|---|---|---|"]
    for r in gate.itertuples():
        lines.append(f"| {r.window} | {r.hits_top100} | {r.fivex_top100} | {r.median_ret_top100:.2f}x | "
                     f"{_pct(r.loser_share_top100)} | {r.lift:.2f} |")

    lines += ["", "## 10-baggers by market cap on the as-of date", "",
              "| Window | Market cap | 10-baggers | Companies | Rate |", "|---|---|---|---|---|"]
    for w, pop in pops.items():
        sc = pop[pop["fwd_return"].notna() & (pop["status"] == "ok") & pop["market_cap_usd"].notna()]
        b = pd.cut(sc["market_cap_usd"], [0, 3e8, 1e9, 1e10, 1e15], labels=["< $300M", "$300M–1B", "$1–10B", "> $10B"])
        for label, g in (sc["fwd_return"] >= 10).groupby(b, observed=False):
            lines.append(f"| {w} | {label} | {int(g.sum())} | {len(g)} | {_pct(g.mean())} |")

    lines += ["", "## Every 10-bagger and where the current score ranked it", ""]
    for w, pop in pops.items():
        ranked = ranked_by[(cur, w)].set_index("cik")["rank"]
        tb = pop[pop["fwd_return"] >= 10].copy()
        tb["rank"] = tb["cik"].map(ranked)
        min_rev = load_config()["gate"]["min_rev_ttm_usd"]
        tb["why"] = [("ranked" if pd.notna(rk) else
                      "not scorable: " + st if st != "ok" else
                      "failed gate: revenue shrinking" if (pd.notna(g) and g < 0) else
                      f"failed gate: TTM revenue < ${min_rev / 1e6:.0f}M" if (pd.notna(rv) and rv < min_rev) else
                      "no market cap (no SEC share count)")
                     for rk, st, g, rv in zip(tb["rank"], tb["status"], tb["rev_growth"], tb["rev_ttm"])]
        lines += [f"### {w} ({WINDOWS[w][0]} → {WINDOWS[w][1]})", "",
                  "| Ticker | 5y return | Rank | Market cap then | TTM rev growth then | Note |", "|---|---|---|---|---|---|"]
        for r in tb.sort_values(["rank", "fwd_return"], ascending=[True, False]).itertuples():
            mc = f"${r.market_cap_usd / 1e6:,.0f}M" if pd.notna(r.market_cap_usd) else "—"
            g = _pct(r.rev_growth) if pd.notna(r.rev_growth) else "—"
            rk = f"{int(r.rank)}" if pd.notna(r.rank) else "—"
            lines.append(f"| {r.ticker} | {r.fwd_return:.1f}x | {rk} | {mc} | {g} | {r.why} |")
        lines.append("")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
