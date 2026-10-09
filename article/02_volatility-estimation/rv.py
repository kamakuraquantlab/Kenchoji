"""Realized volatility of one day, in bps, scaled to the full 24 hours.

Hase's `realized_vol_bps` sums the returns the grid holds, and the grid holds
fewer of them the coarser the interval: sampling a 86,400-second day every
1,800 seconds gives 48 points and 47 returns, so 23.5 hours, while every 10
seconds covers all but the last 10. The 30-minute RV came out about 1% low
against the 10-second one for that reason alone. Scaling each day by the
returns it should have held puts every interval on the same 24 hours; it also
treats a day whose book starts late the same way at every interval.
"""
import numpy as np


def rv_bps(grid, step: int = 1):
    """RV over one day's one-second grid, sampled every `step` seconds."""
    grid = np.asarray(grid)
    with np.errstate(invalid="ignore", divide="ignore"):
        returns = np.diff(np.log(grid[::step]))
    returns = returns[np.isfinite(returns)]
    if len(returns) < 10:
        return None
    full_day = len(grid) // step
    return float(np.sqrt((returns ** 2).sum() * full_day / len(returns)) * 1e4)


# A feed that stops for longer than this is not measured that day. The grid is
# forward filled, so an outage collapses every move inside it into one return
# at the first second after it: bitbank stopped for about two hours on
# 2026-06-16, and that single day doubled bitbank XRP's 10-second RV for the
# month. Five minutes keeps the ordinary pauses and drops the outages.
MAX_GAP_SEC = 300


def has_outage(book) -> bool:
    """True when the day's book has a gap longer than MAX_GAP_SEC."""
    ts = np.sort(np.asarray(book["ts"], dtype="float64"))
    return len(ts) < 2 or float(np.diff(ts).max()) > MAX_GAP_SEC


def pooled(values) -> float:
    """One RV for many days: the root of the mean daily realized variance.

    Not the median of the daily RVs. A median taken separately at each interval
    picks different days at each, and day-to-day volatility moves by more than
    the effect being measured; averaging the variance keeps the same days in
    every interval, so ratios between intervals, or between markets on the same
    days, cancel the day-to-day swing.
    """
    v = np.asarray(values, dtype="float64")
    return float(np.sqrt(np.mean(v ** 2)))
