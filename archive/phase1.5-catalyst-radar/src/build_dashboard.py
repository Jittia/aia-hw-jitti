"""Build output/dashboard.html (Phase 1.5 radar): one self-contained page, no external scripts.

Inputs: data/cache/radar_live.pkl (radar_watchlist.py), data/cache/event_study.pkl (event_study.py).
Market cap shown = latest Yahoo close × latest SEC share count (quarters.shares_as_of); no licensed screener data
is written into the page (public repo).

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
from sec_client import DATA_CACHE, ROOT

warnings.filterwarnings("ignore")

TEMPLATE = ROOT / "src" / "dashboard_template.html"
OUT = ROOT / "output" / "dashboard.html"


def current_market_caps(rows: pd.DataFrame) -> tuple[dict[str, float], str]:
    ytk = {t: yahoo_ticker(t) for t in rows["ticker"]}
    data = yf.download(list(ytk.values()), start="2026-06-01", auto_adjust=False, actions=True,
                       progress=False, group_by="column")
    caps, last_day = {}, ""
    for (t, y), cik in zip(ytk.items(), rows["cik"]):
        try:
            close, splits = data["Close"][y].dropna(), data["Stock Splits"][y]
        except KeyError:
            continue
        shares, _ = shares_as_of(cik, date.today().isoformat())
        if close.empty or shares is None:
            continue
        if (splits > 0).any():
            print(f"  split since 2026-06-01, check market cap: {t}")
        caps[t] = float(close.iloc[-1]) * shares
        last_day = max(last_day, close.index[-1].strftime("%Y-%m-%d"))
    return caps, last_day


def main() -> None:
    cfg = load_config()
    live = pd.read_pickle(DATA_CACHE / "radar_live.pkl")
    study = pd.read_pickle(DATA_CACHE / "event_study.pkl")
    rows = live["rows"].copy()
    caps, price_day = current_market_caps(rows)
    rows["market_cap_usd"] = rows["ticker"].map(caps)

    res = study["results"]
    groups = ["stage entry: confirmed", "stage entry: emerging", "stage entry: radar", "event: gm_step",
              "event: turn_positive", "event: rev_accel", "event: contract_jump", "event: insider_cluster",
              "event: officer_change", "event: material_deal", "all company-quarters"]
    lift = res[res["group"].isin(groups)][["group", "window", "n", "hit_5x", "hit_10x", "median", "halved", "lift_5x", "base_5x"]]

    payload = {
        "asOf": cfg["universe_date"], "priceDay": price_day, "built": date.today().isoformat(),
        "counts": live["counts"], "universe": 2499,
        "rows": json.loads(rows.drop(columns=["cik"]).to_json(orient="records")),
        "timelines": {t: live["timelines"].get(c, []) for t, c in zip(rows["ticker"], rows["cik"])},
        "lift": json.loads(lift.to_json(orient="records")), "groups": groups,
        "study": cfg["radar"]["study"], "stages": cfg["radar"]["stages"], "radarEvents": cfg["radar"]["radar_events"],
    }
    OUT.write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(payload)), encoding="utf-8")
    c = live["counts"]
    print(f"dashboard: {OUT.relative_to(ROOT)} · tier A {c['tier_a']} · tier B {c['tier_b']} · vetoed {c['vetoed']} · "
          f"market caps {len(caps)}/{len(rows)} (Yahoo close {price_day})")


if __name__ == "__main__":
    main()
