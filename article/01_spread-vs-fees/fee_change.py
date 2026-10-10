"""bitbank BTC spot: the weekly spread from November 2025 to June 2026.

bitbank paid a negative maker fee on BTC spot and stopped on 2026-02-02 (its
notice gives the date; the book steps at 12:00 JST). If the spread is a form of
payment to whoever provides the quote, removing the payment should widen it.
XRP, whose fee did not change, is the control.

The measure is the mean spread. Both bitbank books sit one tick wide most of
the time and 2-6 bps wide for the rest, before the change as well as after it,
so the mean is close to the share of time the book is wide times about 2.8 bps,
and it moves the moment that share does. The median flips between the two
states only when the share crosses one half, which on BTC happened a month
after the change.

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
    """Each held day's median and mean spread."""
    out = {}
    for d in available_dates(ROOT, market, "OrderBook"):
        if not (SPAN[0] <= d <= SPAN[1]):
            continue
        s = load(ROOT, "BookState", market, d)["spread_bps"]
        if len(s) >= 500:
            out[d] = (float(s.median()), float(s.mean()))
    return out


def weekly(daily):
    """Thursday-to-Wednesday weeks: start date, days held, mean spread."""
    anchor = dt.date.fromisoformat(SELLOFF_WEEK)
    weeks = {}
    for d, (_, mean) in daily.items():
        day = dt.date.fromisoformat(d)
        start = day - dt.timedelta(days=(day - anchor).days % 7)
        weeks.setdefault(start.isoformat(), []).append(mean)
    return [[w, len(v), round(statistics.mean(v), 4)] for w, v in sorted(weeks.items())]


def window(daily, lo, hi):
    """Mean spread over a window, and the median spread for the taker table."""
    held = [v for d, v in daily.items() if lo <= d <= hi]
    return {
        "days": len(held),
        "spread_mean_bps": round(statistics.mean(m for _, m in held), 4),
        "spread_median_bps": round(statistics.median(s for s, _ in held), 6),
    }


out = {"change": CHANGE, "selloff_week": SELLOFF_WEEK, "windows": {}, "weekly": {}}
for market in (MARKET, CONTROL):
    daily = days(market)
    out["weekly"][market] = weekly(daily)
    for label, (lo, hi) in WINDOWS.items():
        out["windows"].setdefault(f"{label} {lo}..{hi}", {})[market] = window(daily, lo, hi)

for label, row in out["windows"].items():
    print(label)
    for m, w in row.items():
        print(f"   {m:18} days {w['days']:>3}   mean {w['spread_mean_bps']:.2f} bps   "
              f"median {w['spread_median_bps']:.4f} bps")
print("\nweek       BTC days  mean   XRP days  mean")
btc = {w: (n, v) for w, n, v in out["weekly"][MARKET]}
xrp = {w: (n, v) for w, n, v in out["weekly"][CONTROL]}
for w in sorted(set(btc) | set(xrp)):
    b, x = btc.get(w, (0, None)), xrp.get(w, (0, None))
    print(f"{w}   {b[0]:>4}  {b[1] if b[1] is not None else '-':>5}   {x[0]:>4}  {x[1] if x[1] is not None else '-':>5}")

dest = pathlib.Path(__file__).parent / "output" / "fee_change.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
