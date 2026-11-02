"""Day 3: turn point-in-time XBRL facts into discrete quarters and trailing-twelve-month (TTM) sums.

Why derivation is needed:
  - 10-Q income statements give 3-month figures, but 10-Q cash-flow statements are year-to-date only.
  - The 10-K gives the full year only, so Q4 never appears directly.
So a discrete quarter = a direct 3-month fact, or the difference between two cumulative facts
with the same fiscal start date whose end dates are one quarter apart (e.g. 12M − 9M = Q4).
"""
from __future__ import annotations

import pandas as pd

from edgar import facts_as_of

Q_DAYS = (80, 100)  # a quarter (52/53-week years give 84–98 days)


def _is_quarter_gap(a: str, b: str) -> bool:
    gap = (pd.Timestamp(b) - pd.Timestamp(a)).days
    return Q_DAYS[0] <= gap <= Q_DAYS[1]


def quarterly(cik: str, metric: str, as_of: str) -> pd.DataFrame:
    """Discrete quarters visible on `as_of`. Columns: end, val, source ('direct'|'derived'), filed, url."""
    f = facts_as_of(cik, metric, as_of)
    if f.empty or f["start"].isna().all():
        return pd.DataFrame(columns=["end", "val", "source", "filed", "url"])
    f = f.dropna(subset=["start"])

    out: dict[str, dict] = {}
    # Two 3-month facts can share an end date with slightly different start dates; earliest filing wins.
    for _, r in f[f["period_days"].between(*Q_DAYS)].sort_values("filed").iterrows():
        if r["end"] not in out:
            out[r["end"]] = {"end": r["end"], "val": r["val"], "source": "direct", "filed": r["filed"], "url": r["url"]}

    for _, grp in f.groupby("start"):
        grp = grp.sort_values("end")
        rows = grp.to_dict("records")
        for prev, nxt in zip(rows, rows[1:]):
            if nxt["end"] in out or not _is_quarter_gap(prev["end"], nxt["end"]):
                continue
            out[nxt["end"]] = {"end": nxt["end"], "val": nxt["val"] - prev["val"], "source": "derived",
                               "filed": max(prev["filed"], nxt["filed"]), "url": nxt["url"]}

    if not out:  # only annual/half-year facts, no quarter-shaped periods
        return pd.DataFrame(columns=["end", "val", "source", "filed", "url"])
    return pd.DataFrame(out.values()).sort_values("end").reset_index(drop=True)


def ttm(q: pd.DataFrame) -> pd.DataFrame:
    """Rolling 4-quarter sum, only where the 4 quarters are contiguous. Columns: end, ttm."""
    if len(q) < 4:
        return pd.DataFrame(columns=["end", "ttm"])
    ends, vals = q["end"].tolist(), q["val"].tolist()
    rows = []
    for i in range(3, len(q)):
        window = ends[i - 3:i + 1]
        if all(_is_quarter_gap(a, b) for a, b in zip(window, window[1:])):
            rows.append({"end": ends[i], "ttm": sum(vals[i - 3:i + 1])})
    return pd.DataFrame(rows, columns=["end", "ttm"])


def instant_series(cik: str, metric: str, as_of: str) -> pd.DataFrame:
    """Point-in-time instant values (e.g. shares outstanding). Columns: end, val, filed, url."""
    f = facts_as_of(cik, metric, as_of)
    if f.empty:
        return pd.DataFrame(columns=["end", "val", "filed", "url"])
    return f[["end", "val", "filed", "url"]].sort_values("end").reset_index(drop=True)
