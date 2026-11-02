"""Day 6: build output/dashboard.html, a single self-contained page (no external scripts).

Inputs (all produced by earlier steps):
  output/shortlist.csv, output/layer2_review.csv        Layer 2 results (SEC-derived)
  data/cache/backtest_results.csv, backtest_state.pkl   backtest (SEC + Yahoo)
  data/private/layer1_scores_<date>.csv                 only the funnel counts and Layer 1 status are used
Market cap shown = latest Yahoo close × latest SEC share count (quarters.shares_as_of). The licensed
Stock Analysis market cap is NOT written into the page (public repo).

Run:  python src/build_dashboard.py
"""
from __future__ import annotations

import json
import warnings
from datetime import date

import pandas as pd
import yfinance as yf

from prices import yahoo_ticker
from quarters import shares_as_of
from score import load_config
from sec_client import DATA_CACHE, DATA_PRIVATE, ROOT

warnings.filterwarnings("ignore")

TEMPLATE = ROOT / "src" / "dashboard_template.html"
OUT = ROOT / "output" / "dashboard.html"


def current_market_caps(review: pd.DataFrame, ciks: dict[str, str]) -> tuple[dict[str, float], str]:
    tickers = review["ticker"].tolist()
    ytk = {t: yahoo_ticker(t) for t in tickers}
    data = yf.download(list(ytk.values()), start="2026-01-01", auto_adjust=False, actions=True,
                       progress=False, group_by="column")
    caps, last_day = {}, ""
    for t, y in ytk.items():
        try:
            close = data["Close"][y].dropna()
            splits = data["Stock Splits"][y]
        except KeyError:
            continue
        shares, _ = shares_as_of(ciks[t], date.today().isoformat())
        if close.empty or shares is None:
            continue
        # SEC shares can predate a very recent split; such names are reported on build so they can be checked.
        if (splits[splits.index >= "2026-06-01"] > 0).any():
            print(f"  split since 2026-06-01, check market cap: {t}")
        caps[t] = float(close.iloc[-1]) * shares
        last_day = max(last_day, close.index[-1].strftime("%Y-%m-%d"))
    return caps, last_day


def main() -> None:
    cfg = load_config()
    d = cfg["universe_date"]
    review = pd.read_csv(ROOT / "output" / "layer2_review.csv")
    short = pd.read_csv(ROOT / "output" / "shortlist.csv")
    scores = pd.read_csv(DATA_PRIVATE / f"layer1_scores_{d}.csv", dtype={"cik": str})
    uni = pd.read_csv(DATA_PRIVATE / f"universe_with_cik_{d}.csv")

    ciks = dict(zip(scores["ticker"], scores["cik"]))
    caps, price_day = current_market_caps(review, ciks)
    review["market_cap_usd"] = review["ticker"].map(caps)
    short["market_cap_usd"] = short["ticker"].map(caps)

    funnel = [
        {"label": "US stocks from screener", "n": int(len(uni))},
        {"label": "File 10-Qs with the SEC", "n": int(uni["include_flag"].sum())},
        {"label": "Scorable (4+ quarters of data)", "n": int((scores["status"] == "ok").sum())},
        {"label": "Pass the growth / turnaround gate", "n": int(scores["rank"].notna().sum())},
        {"label": "Layer 1 top, read by AI", "n": int(cfg["top_n"])},
        {"label": "Watchlist (tier A + B)", "n": int(len(short))},
    ]

    res = pd.read_csv(DATA_CACHE / "backtest_results.csv")
    cur = res[res["variant"] == "config.yaml (current)"]
    state = pd.read_pickle(DATA_CACHE / "backtest_state.pkl")
    size = []
    for w, pop in state["pops"].items():
        sc = pop[pop["fwd_return"].notna() & (pop["status"] == "ok") & pop["market_cap_usd"].notna()]
        b = pd.cut(sc["market_cap_usd"], [0, 3e8, 1e9, 1e10, 1e15], labels=["< $300M", "$300M–1B", "$1–10B", "> $10B"])
        for label, g in (sc["fwd_return"] >= 10).groupby(b, observed=False):
            size.append({"window": w, "bucket": str(label), "rate": float(g.mean()), "hits": int(g.sum()), "n": int(len(g))})

    def records(df: pd.DataFrame) -> list[dict]:
        return json.loads(df.to_json(orient="records"))

    payload = {
        "asOf": d, "priceDay": price_day, "built": date.today().isoformat(),
        "funnel": funnel,
        "watchlist": records(short),
        "review": records(review),
        "backtest": records(cur[["window", "hits_top100", "tenbaggers_priced", "recall_top100", "precision_top100",
                                 "base_rate", "lift", "fivex_top100", "median_ret_top100", "median_ret_scorable",
                                 "loser_share_top100"]]),
        "variants": records(res[["variant", "window", "hits_top100", "lift", "fivex_top100", "median_ret_top100",
                                 "loser_share_top100"]]),
        "size": size,
        "weights": cfg["weights"],
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(payload))
    OUT.write_text(html, encoding="utf-8")
    print(f"dashboard: {OUT.relative_to(ROOT)} · watchlist {len(short)} · reviewed {len(review)} · "
          f"market caps {len(caps)}/{len(review)} (Yahoo close {price_day})")


if __name__ == "__main__":
    main()
