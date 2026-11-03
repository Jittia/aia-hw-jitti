"""Phase 1.5 history and change events: dates and point-in-time behaviour.

Run (after src/history.py and src/events.py):  .venv/bin/python -m unittest tests/test_events.py -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from events import OUT_EVENTS, OUT_HISTORY  # noqa: E402
from history import company_history  # noqa: E402

NVDA = "0001045810"


class History(unittest.TestCase):
    def test_nvda_quarter_known_on_its_10q_date(self):
        # Quarter ended 2023-07-30: revenue $13,507M (+101% YoY), first published in the 10-Q filed 2023-08-28.
        h = company_history(NVDA).set_index("end")
        row = h.loc["2023-07-30"]
        self.assertEqual(row["rev_q"], 13_507_000_000)
        self.assertEqual(row["known_date"], "2023-08-28")
        self.assertAlmostEqual(row["yoy_q"], 13_507 / 6_704 - 1, places=3)

    def test_known_date_never_before_quarter_end(self):
        h = pd.read_pickle(OUT_HISTORY)
        self.assertTrue((h["known_date"] > h["end"]).all())


class Events(unittest.TestCase):
    def test_nvda_revenue_acceleration_onset(self):
        ev = pd.read_pickle(OUT_EVENTS)
        nv = ev[(ev["cik"] == NVDA) & (ev["event"] == "rev_accel")]
        self.assertIn("2023-07-30", set(nv["end"]))
        hit = nv[nv["end"] == "2023-07-30"].iloc[0]
        self.assertEqual(hit["known_date"], "2023-08-28")   # visible only from the filing date, not the quarter end

    def test_events_are_onsets(self):
        # The same event type cannot fire for the same company in two consecutive quarters.
        ev = pd.read_pickle(OUT_EVENTS).sort_values(["cik", "event", "end"])
        h = pd.read_pickle(OUT_HISTORY)[["cik", "end"]].sort_values(["cik", "end"])
        h["next_end"] = h.groupby("cik")["end"].shift(-1)
        nxt = dict(zip(zip(h["cik"], h["end"]), h["next_end"]))
        pairs = set(zip(ev["cik"], ev["event"], ev["end"]))
        repeats = [(c, e, d) for c, e, d in pairs if (c, e, nxt.get((c, d))) in pairs]
        self.assertEqual(repeats, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
