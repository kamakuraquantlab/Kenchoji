"""bitbank BTC spot: the weekly spread from November 2025 to June 2026.

bitbank paid a negative maker fee on BTC spot and stopped on 2026-02-02 (its
notice gives the date; the book steps at 12:00 JST). If the spread is a form of
payment to whoever provides the quote, removing the payment should widen it.
XRP, whose fee did not change, is the control.

The measure is the mean spread across the day's BookState rows. Both books
alternate between tight and wide quotes, so the mean responds to how much of
the day the wide state holds; the median flips between states only after more
than half of the rows are in one state. A plain mean of rows is a time average
only if the rows are evenly spaced, so each window also reports the mean
weighted by how long each row stood and the median gap between rows: the rows
are 0.35 s apart throughout, and the two means agree within 0.02 bps.

The robustness block compares BTC with XRP on the dates both hold, on the
weeks where both hold five days or more, and with the time-weighted mean. It
is a check on the windows above, not a different estimate.

The series is weekly, Thursday to Wednesday, so that 2026-02-05..02-11, the
week of the market-wide sell-off, is one point: every bitbank book widened in
it, BTC and XRP alike. The archive does not hold every day; a week is the mean
of the days it does hold, and the count is kept so the figure can mark the thin
weeks.

Two windows summarise it for the text and for the taker cost in 5.2, both
clear of the change and the sell-off: before is 2025-11-01..2026-02-01, after
is 2026-03-01..06-30.

Reproducing this:

    1. komachi download --market <MARKET> --start <START> --days <N>
    2. hase derive BookState   --market <MARKET> --start <START> --end <END>
       hase derive MarketPrice --market <MARKET> --start <START> --end <END> \\
                              --execution-notional 1000000
    3. python fee_change.py

Step 2 is a cache rather than a prerequisite: what it writes, this script would
otherwise derive in memory at about a quarter of a second per market-day.
Nothing here writes, so step 3 against the seller's warehouse reads what is
already there and cannot overwrite it.

Reproduces: §3, §5.2. Writes output/fee_change.json.
"""

import datetime as dt
import json
import pathlib
import statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.layout import available_dates

ROOT = komachi.data_root()
MARKET = "BITBANK:BTC_SPOT"
CONTROL = "BITBANK:XRP_SPOT"  # kept its negative maker fee; should not step
CHANGE = "2026-02-02 12:00 JST"  # the date is bitbank's notice; the hour is the book's
SELLOFF_WEEK = "2026-02-05"  # market-wide; its Thursday anchors every week
SPAN = ("2025-11-01", "2026-06-30")
WINDOWS = {
    "before": ("2025-11-01", "2026-02-01"),
    "after": ("2026-03-01", "2026-06-30"),
}


def days(market):
    """Each held day's median spread, mean spread, time-weighted mean spread and
    median gap between BookState rows in seconds.

    The last two answer whether the plain mean is a time average: each row is
    weighted by how long it stood, until the next row."""
    out = {}
    for d in available_dates(ROOT, market, "OrderBook"):
        if not (SPAN[0] <= d <= SPAN[1]):
            continue
        book = load(ROOT, "BookState", market, d)
        if len(book) < 500:
            continue
        book = book.sort_values("ts")
        s = book["spread_bps"].to_numpy(dtype="float64")
        gap = np.diff(book["ts"].to_numpy(dtype="float64"))
        tw = float((s[:-1] * gap).sum() / gap.sum())
        out[d] = (float(np.median(s)), float(s.mean()), tw, float(np.median(gap)))
    return out


def weekly(daily):
    """Thursday-to-Wednesday weeks: start date, days held, mean spread."""
    anchor = dt.date.fromisoformat(SELLOFF_WEEK)
    weeks = {}
    for d, (_, mean, *_) in daily.items():
        day = dt.date.fromisoformat(d)
        start = day - dt.timedelta(days=(day - anchor).days % 7)
        weeks.setdefault(start.isoformat(), []).append(mean)
    return [[w, len(v), round(statistics.mean(v), 4)] for w, v in sorted(weeks.items())]


def window(daily, lo, hi):
    """Mean spread over a window, and the median spread for the taker table."""
    held = [v for d, v in daily.items() if lo <= d <= hi]
    return {
        "days": len(held),
        "spread_mean_bps": round(statistics.mean(v[1] for v in held), 4),
        "spread_median_bps": round(statistics.median(v[0] for v in held), 6),
        "spread_time_weighted_mean_bps": round(statistics.mean(v[2] for v in held), 4),
        "median_row_gap_sec": round(statistics.median(v[3] for v in held), 3),
    }



def paired_window(btc_daily, xrp_daily, lo, hi, complete_weeks=False, col=1):
    """Compare daily means on the same dates for BTC and XRP.

    complete_weeks=True uses only full Thu-Wed weeks with at least five
    overlapping observed days. col picks the day's statistic from days():
    1 the plain mean, 2 the time-weighted mean.
    """
    common = sorted(set(btc_daily) & set(xrp_daily))
    common = [d for d in common if lo <= d <= hi]
    if complete_weeks:
        anchor = dt.date.fromisoformat(SELLOFF_WEEK)
        weeks = {}
        for d in common:
            day = dt.date.fromisoformat(d)
            start = day - dt.timedelta(days=(day - anchor).days % 7)
            weeks.setdefault(start, []).append(d)
        common = [
            d
            for start, dates in sorted(weeks.items())
            if start.isoformat() >= lo
            and (start + dt.timedelta(days=6)).isoformat() <= hi
            and len(dates) >= 5
            for d in dates
        ]
    if not common:
        return {"matched_days": 0, "btc_mean_bps": None,
                "xrp_mean_bps": None, "gap_bps": None}
    btc_mean = statistics.mean(btc_daily[d][col] for d in common)
    xrp_mean = statistics.mean(xrp_daily[d][col] for d in common)
    return {
        "matched_days": len(common),
        "btc_mean_bps": round(btc_mean, 4),
        "xrp_mean_bps": round(xrp_mean, 4),
        "gap_bps": round(btc_mean - xrp_mean, 4),
    }


def robustness(daily_by_market):
    """Matched-date gap changes; descriptive only, not causal identification."""
    btc = daily_by_market[MARKET]
    xrp = daily_by_market[CONTROL]
    results = {}
    for key, complete_weeks, col in (
        ("matched_days", False, 1),
        ("matched_days_in_weeks_with_at_least_five_days", True, 1),
        ("matched_days_time_weighted", False, 2),
    ):
        before = paired_window(btc, xrp, *WINDOWS["before"], complete_weeks, col)
        after = paired_window(btc, xrp, *WINDOWS["after"], complete_weeks, col)
        difference = (
            round(after["gap_bps"] - before["gap_bps"], 4)
            if before["gap_bps"] is not None and after["gap_bps"] is not None
            else None
        )
        results[key] = {
            "before": before,
            "after": after,
            "difference_in_differences_bps": difference,
        }
    return results


out = {"change": CHANGE, "selloff_week": SELLOFF_WEEK, "windows": {}, "weekly": {}}
daily_by_market = {market: days(market) for market in (MARKET, CONTROL)}
for market, daily in daily_by_market.items():
    out["weekly"][market] = weekly(daily)
    for label, (lo, hi) in WINDOWS.items():
        out["windows"].setdefault(f"{label} {lo}..{hi}", {})[market] = window(daily, lo, hi)

out["robustness"] = robustness(daily_by_market)

for label, row in out["windows"].items():
    print(label)
    for m, w in row.items():
        print(f"   {m:18} days {w['days']:>3}   mean {w['spread_mean_bps']:.2f} bps   "
              f"time-weighted {w['spread_time_weighted_mean_bps']:.2f} bps   "
              f"median {w['spread_median_bps']:.4f} bps   row gap {w['median_row_gap_sec']} s")
print("\nrobustness: BTC minus XRP mean spread, before -> after")
for key, r in out["robustness"].items():
    b, a = r["before"], r["after"]
    print(f"   {key:48} days {b['matched_days']:>3} -> {a['matched_days']:>3}   "
          f"gap {b['gap_bps']:+.3f} -> {a['gap_bps']:+.3f}   "
          f"difference {r['difference_in_differences_bps']:+.3f} bps")
print("\nweek       BTC days  mean   XRP days  mean")
btc = {w: (n, v) for w, n, v in out["weekly"][MARKET]}
xrp = {w: (n, v) for w, n, v in out["weekly"][CONTROL]}
for w in sorted(set(btc) | set(xrp)):
    b, x = btc.get(w, (0, None)), xrp.get(w, (0, None))
    print(f"{w}   {b[0]:>4}  {b[1] if b[1] is not None else '-':>5}   {x[0]:>4}  {x[1] if x[1] is not None else '-':>5}")

dest = pathlib.Path(__file__).parent / "output" / "fee_change.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
