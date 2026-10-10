"""bitbank BTC spot: the week before the fee change and the weeks after.

bitbank paid a negative maker fee on BTC spot and stopped. If the spread is a
form of payment to whoever provides the quote, removing the payment should
widen it, and the archive should show the step.

The step in the data is 2026-02-05, not January, and the weeks after it are
unstable: the tight quote comes back from 02-12 to 02-18 and again from 02-25
to 02-28, and only from 03-01 is it gone for good. Three windows rather than
two, so the transition is visible instead of averaged away.

The daily median alone overstates the step. Both bitbank books sit one tick
wide most of the time and 2-6 bps wide for the rest, before the change as well
as after it, and a median of that mixture flips from one state to the other
once the wide share passes one half: 0.0008 to 0.8952 bps is a thousandfold,
while the mean rose under twofold. So each window also reports the mean spread
and the share of time the spread was wide, and the median is kept at six
decimals so the ratios taken from it do not inherit the rounding of 0.0008.

Reproducing this:

    1. komachi download --market <MARKET> --start <START> --days <N>
    2. hase derive BookState   --market <MARKET> --start <START> --end <END>
       hase derive MarketPrice --market <MARKET> --start <START> --end <END> \
                              --execution-notional 1000000
    3. python fee_change.py

Step 2 is a cache rather than a prerequisite: what it writes, this script would
otherwise derive in memory at about a quarter of a second per market-day.
Nothing here writes, so step 3 against the seller's warehouse reads what is
already there and cannot overwrite it.

Reproduces: §3, §5.2. Writes output/fee_change.json.
"""

import json
import pathlib
import statistics

import komachi
from hase.dataset import load, trade_count
from hase.layout import available_dates

ROOT = komachi.data_root()
MARKET = "BITBANK:BTC_SPOT"
WINDOWS = {
    "before  2026-01-29..02-04": ("2026-01-29", "2026-02-04"),
    "after   2026-02-05..02-11": ("2026-02-05", "2026-02-11"),
    "settled 2026-02-20..02-26": ("2026-02-20", "2026-02-26"),
}
CONTROL = "BITBANK:XRP_SPOT"  # kept its negative maker fee; should not step
PLOT_WINDOW = ("2026-01-01", "2026-03-31")
# Wide means above this. The tight state is 0.0007-0.0010 bps on BTC and
# 0.03-0.05 bps on XRP, the wide one 1 bps and up, so 0.1 separates them on both.
WIDE_BPS = 0.1


def day_stats(book):
    """Median, mean and wide share of one day's spread. Snapshots are evenly
    spaced (about every 0.35 s), so plain averages are time averages."""
    s = book["spread_bps"]
    return float(s.median()), float(s.mean()), float((s > WIDE_BPS).mean())


def week(market, lo, hi):
    """Median spread, depth and trades per day over one window.

    The quote and the depth come from Hase's BookState, which is the same
    calculation this used to do inline against the raw book.
    """
    spr, mean, wide, tob, daily = [], [], [], [], []
    for d in available_dates(ROOT, market, "OrderBook"):
        if not (lo <= d <= hi):
            continue
        book = load(ROOT, "BookState", market, d)
        if len(book) < 500:
            continue
        s, m, w = day_stats(book)
        spr.append(s)
        mean.append(m)
        wide.append(w)
        daily.append((d, round(s, 4)))
        tob.append(float(book["top_of_book"].median()))
    tr = [
        trade_count(ROOT, market, d)
        for d in available_dates(ROOT, market, "Trade")
        if lo <= d <= hi
    ]
    if not spr:
        return None
    return {
        "days": len(spr),
        "spread_bps": round(statistics.median(spr), 6),
        "spread_mean_bps": round(statistics.median(mean), 4),
        "wide_share": round(statistics.median(wide), 3),
        "top_of_book_jpy": round(statistics.median(tob)) if tob else None,
        "trades_per_day": round(statistics.median(tr)) if tr else None,
        "daily_spread_bps": daily,
    }


def daily_spread(market, lo, hi):
    """Daily median, mean and wide share over the full window of the figure."""
    out = []
    for d in available_dates(ROOT, market, "OrderBook"):
        if not (lo <= d <= hi):
            continue
        book = load(ROOT, "BookState", market, d)
        if len(book) >= 500:
            s, m, w = day_stats(book)
            out.append([d, round(s, 4), round(m, 4), round(w, 3)])
    return out


out = {}
for label, (lo, hi) in WINDOWS.items():
    r = week(MARKET, lo, hi)
    c = week(CONTROL, lo, hi)
    out[label] = {"BITBANK:BTC_SPOT": r, "control BITBANK:XRP_SPOT": c}
    print(f"{label}")
    print(
        f"   BTC spot   spread {r['spread_bps']:>9.4f} bps   mean {r['spread_mean_bps']:>6.3f}   wide {r['wide_share']:>4.0%}   top-of-book {r['top_of_book_jpy']:>9,} JPY   "
        f"trades/day {r['trades_per_day']:>7,}"
    )
    print(
        f"   XRP ctrl   spread {c['spread_bps']:>9.4f} bps   mean {c['spread_mean_bps']:>6.3f}   wide {c['wide_share']:>4.0%}   top-of-book {c['top_of_book_jpy']:>9,} JPY   "
        f"trades/day {c['trades_per_day']:>7,}",
        flush=True,
    )

# Each row: date, median, mean, wide share.
out["daily_spread_bps_2026-01-01_2026-03-31"] = {
    MARKET: daily_spread(MARKET, *PLOT_WINDOW),
    CONTROL: daily_spread(CONTROL, *PLOT_WINDOW),
}

dest = pathlib.Path(__file__).parent / "output" / "fee_change.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
