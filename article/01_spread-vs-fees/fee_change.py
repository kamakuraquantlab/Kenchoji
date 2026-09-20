"""bitbank BTC spot: the week before the fee change and the weeks after.

bitbank paid a negative maker fee on BTC spot and stopped. If the spread is a
form of payment to whoever provides the quote, removing the payment should
widen it, and the archive should show the step.

The step in the data is 2026-02-05, not January, and the fortnight after it is
unstable: the tight quote comes back for six days from 02-12 before going for
good. Three windows rather than two, so the transition is visible instead of
averaged away.

Reproducing this:

    1. komachi download --market <MARKET> --start <START> --days <N>
    2. hase derive BookState   --market <MARKET> --start <START> --end <END>
       hase derive MarketPrice --market <MARKET> --start <START> --end <END> \
                              --execution-notional 1000000
    3. python3 fee_change.py

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


def week(market, lo, hi):
    """Median spread, depth and trades per day over one window.

    The quote and the depth come from Hase's BookState, which is the same
    calculation this used to do inline against the raw book.
    """
    spr, tob, daily = [], [], []
    for d in available_dates(ROOT, market, "OrderBook"):
        if not (lo <= d <= hi):
            continue
        book = load(ROOT, "BookState", market, d)
        if len(book) < 500:
            continue
        s = float(book["spread_bps"].median())
        spr.append(s)
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
        "spread_bps": round(statistics.median(spr), 4),
        "top_of_book_jpy": round(statistics.median(tob)) if tob else None,
        "trades_per_day": round(statistics.median(tr)) if tr else None,
        "daily_spread_bps": daily,
    }


out = {}
for label, (lo, hi) in WINDOWS.items():
    r = week(MARKET, lo, hi)
    c = week(CONTROL, lo, hi)
    out[label] = {"BITBANK:BTC_SPOT": r, "control BITBANK:XRP_SPOT": c}
    print(f"{label}")
    print(
        f"   BTC spot   spread {r['spread_bps']:>9.4f} bps   top-of-book {r['top_of_book_jpy']:>9,} JPY   "
        f"trades/day {r['trades_per_day']:>7,}"
    )
    print(
        f"   XRP ctrl   spread {c['spread_bps']:>9.4f} bps   top-of-book {c['top_of_book_jpy']:>9,} JPY   "
        f"trades/day {c['trades_per_day']:>7,}",
        flush=True,
    )

dest = pathlib.Path(__file__).parent / "output" / "fee_change.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
