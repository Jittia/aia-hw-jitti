"""Phase 1.5: live watchlist from the radar stages (as of the universe date) + the AI filing reviews.

  Tier A   stage Confirmed (numbers, 2 quarters) AND AI review = structural catalyst, verified quote, not rejected
  Tier B   stage Emerging (numbers) and not rejected by an AI review (most are not reviewed yet: numbers only)
  Vetoed   Confirmed by the numbers but the AI review found a cycle, acquisition, one-off or no driver
Every AI quote is re-verified against its pack (same rules as layer2_merge.py).

Run:  python src/radar_watchlist.py
Out:  output/watchlist.csv (public: SEC/Yahoo-derived), data/cache/radar_live.pkl (rows + event timelines for the dashboard)
"""
from __future__ import annotations

import json
import re

import pandas as pd

from event_study import FILING_EVENTS, INSIDER_EVENTS, STAGE_HISTORY
from events import OUT_EVENTS
from layer2_merge import PACKS, RESULTS, STRUCTURAL, norm
from sec_client import DATA_CACHE, ROOT

AS_OF = "2026-11-02"
FRESH_DAYS = 200
OUT_CSV = ROOT / "output" / "watchlist.csv"
OUT_LIVE = DATA_CACHE / "radar_live.pkl"
TIMELINE_SINCE = "2024-01-01"


def reviews() -> pd.DataFrame:
    """All AI reviews (latest per ticker wins: batch < recheck < radar), each re-verified against its pack."""
    rows = []
    for pattern in ("batch_*.json", "recheck_*.json", "radar_*.json"):
        for f in sorted(RESULTS.glob(pattern)):
            rows += json.loads(f.read_text(encoding="utf-8"))
    rv = pd.DataFrame(rows).drop_duplicates("ticker", keep="last")
    ok = []
    for r in rv.itertuples():
        pack = (PACKS / f"{r.ticker}.md").read_text(encoding="utf-8")
        sources = set(re.findall(r"^Source: (\S+)", pack, re.M))
        ok.append(bool(r.evidence_quote) and norm(r.evidence_quote) in norm(pack) and r.evidence_url in sources
                  and len(str(r.evidence_quote).split()) <= 30)
    rv["evidence_verified"] = ok
    rv["red_flags"] = rv["red_flags"].map(lambda x: "; ".join(x) if isinstance(x, list) else str(x))
    return rv


def main() -> None:
    sh = pd.read_pickle(STAGE_HISTORY)
    last = sh.sort_values("known_date").groupby("cik").tail(1)
    live = last[pd.to_datetime(last["known_date"]) >= pd.Timestamp(AS_OF) - pd.Timedelta(days=FRESH_DAYS)].copy()

    rv = reviews()
    live = live.merge(rv.add_prefix("ai_").rename(columns={"ai_ticker": "ticker"}), on="ticker", how="left")
    reviewed = live["ai_verdict"].notna()
    structural_ok = (live["ai_evidence_verified"].fillna(False).astype(bool) & live["ai_catalyst_type"].isin(STRUCTURAL)
                     & (live["ai_verdict"] != "reject"))
    vetoed = reviewed & ~structural_ok

    live["tier"] = ""
    live.loc[live["confirmed"] & structural_ok, "tier"] = "A"
    live.loc[live["emerging"] & (live["tier"] == "") & ~vetoed, "tier"] = "B"
    live.loc[live["confirmed"] & vetoed, "tier"] = "vetoed"

    # Event timelines (all types, incl. context-only ones) for every listed company.
    ev = pd.concat([pd.read_pickle(OUT_EVENTS), pd.read_pickle(INSIDER_EVENTS), pd.read_pickle(FILING_EVENTS)],
                   ignore_index=True)
    listed = live[live["tier"] != ""]
    tl = ev[ev["cik"].isin(listed["cik"]) & (ev["known_date"] >= TIMELINE_SINCE) & (ev["known_date"] <= AS_OF)]
    timelines = {c: g.sort_values("known_date", ascending=False)[["known_date", "event", "url"]].to_dict("records")
                 for c, g in tl.groupby("cik")}

    cols = ["tier", "ticker", "end", "known_date", "recent_events", "stretch_10x", "rev_ttm", "yoy_ttm", "excess_yoy",
            "gm_ttm", "om_ttm", "dilution", "req_cagr", "ai_verdict", "ai_catalyst_type", "ai_confidence", "ai_driver",
            "ai_evidence_quote", "ai_evidence_url", "ai_red_flags", "ai_reason", "ai_evidence_verified", "url"]
    # Within a tier: AI "shortlist" before "watch" before not reviewed, then the biggest lead over the industry.
    listed = listed.assign(_v=listed["ai_verdict"].map({"shortlist": 0, "watch": 1}).fillna(2))
    out = listed.sort_values(["tier", "_v", "excess_yoy"], ascending=[True, True, False])[cols]
    out.to_csv(OUT_CSV, index=False)
    pd.to_pickle({"rows": out.assign(cik=listed.set_index("ticker").loc[out["ticker"], "cik"].values),
                  "timelines": timelines,
                  "counts": {"fresh": int(len(live)), "radar": int(live["radar"].sum()),
                             "emerging": int(live["emerging"].sum()), "confirmed": int(live["confirmed"].sum()),
                             "tier_a": int((live["tier"] == "A").sum()), "tier_b": int((live["tier"] == "B").sum()),
                             "vetoed": int((live["tier"] == "vetoed").sum())}}, OUT_LIVE)
    print(f"fresh {len(live)} · radar {int(live['radar'].sum())} · emerging {int(live['emerging'].sum())} · "
          f"confirmed {int(live['confirmed'].sum())}")
    print(f"tier A {(out['tier'] == 'A').sum()}: {out[out['tier'] == 'A']['ticker'].tolist()}")
    print(f"tier B {(out['tier'] == 'B').sum()} · vetoed by AI {(out['tier'] == 'vetoed').sum()}")
    print(f"AI reviews verified: {int(rv['evidence_verified'].sum())}/{len(rv)}")


if __name__ == "__main__":
    main()
