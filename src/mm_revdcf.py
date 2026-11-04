"""Moat Momentum v3.0 · reverse DCF: the revenue growth today's price implies (spec §4).

Free cash flow in year t = revenue₀ × (1+g)^t × after-tax clean operating margin × (1 − g ÷ ROIC): growth needs
reinvestment at the company's current return on capital (McKinsey value-driver link). Ten years at g, then 3% a year
forever, discounted at 9%. Implied g = the first growth rate, scanning upward from −20% to +60%, at which that value
equals EV. Expectation Gap = actual 3-year revenue growth − implied g. Fixed assumptions, set before any test.
"""
from __future__ import annotations

import math

import numpy as np

R, TG, YEARS, TAX = 0.09, 0.03, 10, 0.21


def model_value(g: float, revenue: float, margin: float, roic: float, r: float = R, tg: float = TG,
                years: int = YEARS) -> float:
    """Value of the operations for constant growth g over `years`, then tg. `margin` is after tax."""
    t = np.arange(1, years + 1)
    fcf = revenue * (1 + g) ** t * margin * (1 - g / roic)
    pv = float(np.sum(fcf / (1 + r) ** t))
    terminal = revenue * (1 + g) ** years * (1 + tg) * margin * (1 - tg / roic) / (r - tg)
    return pv + terminal / (1 + r) ** years


def implied_growth(ev: float, revenue: float, op_margin: float, roic: float, tax: float = TAX, r: float = R,
                   tg: float = TG, years: int = YEARS, lo: float = -0.20, hi: float = 0.60, step: float = 0.001,
                   value_fn=None) -> float:
    """First g in [lo, hi] where model value crosses EV; NaN when not defined (spec §4). `op_margin` is pre-tax."""
    vals = (ev, revenue, op_margin, roic)
    if any(v is None or not math.isfinite(v) for v in vals) or op_margin <= 0 or roic <= 0 or ev <= 0 or revenue <= 0:
        return float("nan")
    m = op_margin * (1 - tax)
    f = value_fn or (lambda g: model_value(g, revenue, m, roic, r, tg, years))
    grid = np.round(np.arange(lo, hi + step / 2, step), 6)
    diff = np.array([f(g) - ev for g in grid])
    for i in range(len(grid)):
        if diff[i] == 0:
            return float(grid[i])
        if i and np.sign(diff[i]) != np.sign(diff[i - 1]):
            a, b = grid[i - 1], grid[i]
            return float(a + (b - a) * (0 - diff[i - 1]) / (diff[i] - diff[i - 1]))
    return float("nan")


def expectation_gap(x: float, g: float) -> float:
    """Actual 3-year revenue growth minus implied growth; positive = growing faster than the price assumes."""
    if x is None or g is None or not (math.isfinite(x) and math.isfinite(g)):
        return float("nan")
    return x - g
