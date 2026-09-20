"""Spread by fee structure, and what happens when the fee structure changes.

Two groups, classified by maker fee as of June 2026:

  negative maker  bitbank ETH/XRP spot, GMO BTC/ETH/XRP spot
  zero fee        Coincheck spot, GMO leverage (*_JPY), bitbank BTC spot

bitbank BTC spot is in the second group because it moved there: it paid a
negative maker fee until early 2026 and pays nothing now. That makes it a
natural experiment rather than just another row, and the event study at the
bottom uses it.

Binance is carried as the global reference. It charges a positive maker fee,
so it sits on the far side of the same axis.

Liquidity is measured alongside, because "more depth means tighter spread" and
"paying makers means tighter spread" are two different claims and the data has
to separate them.

FEE SCHEDULES ARE NOT MEASURED HERE. They are an input, and before publication
every one must be confirmed against the venue's own page with the date checked.

Reproducing this:

    1. komachi download --market <MARKET> --start <START> --days <N>
    2. hase derive BookState   --market <MARKET> --start <START> --end <END>
       hase derive MarketPrice --market <MARKET> --start <START> --end <END> \
                              --execution-notional 1000000
    3. python3 analysis.py

Step 2 is a cache rather than a prerequisite: what it writes, this script would
otherwise derive in memory at about a quarter of a second per market-day.
Nothing here writes, so step 3 against the seller's warehouse reads what is
already there and cannot overwrite it.

Reproduces: §1, §2, §4. Writes output/groups_2026-06.json.
"""

import argparse
import datetime as dt
import json
import pathlib
import statistics

import komachi
from hase.dataset import load, trade_count, usable
from hase.layout import available_dates

# Hase derives what this used to recompute inline: BookState is the quoted
# spread and the depth at the touch, MarketPrice walked to a cash amount is the
# round trip. Same definitions, one implementation, and the same one a reader
# gets from `pip install hase`.
ROOT = komachi.data_root()
DEFAULT_WINDOW = ("2026-06-01", "2026-06-28")  # the four weeks the article uses
SIZE_JPY = 1_000_000
MIN_SNAPSHOTS = 500  # a day thinner than this is not measured
MIN_FILLS = 20  # nor is a round trip the book could rarely complete

GROUPS = {
    "negative maker fee": [
        "BITBANK:ETH_SPOT",
        "BITBANK:XRP_SPOT",
        "GMO:BTC_SPOT",
        "GMO:ETH_SPOT",
        "GMO:XRP_SPOT",
    ],
    "zero fee": [
        "BITBANK:BTC_SPOT",
        "COINCHECK:BTC_SPOT",
        "COINCHECK:ETH_SPOT",
        "COINCHECK:XRP_SPOT",
        "GMO:BTC_JPY",
        "GMO:ETH_JPY",
        "GMO:XRP_JPY",
    ],
    "positive maker fee (reference)": [
        "BINANCE:BTC_USDT",
        "BINANCE:ETH_USDT",
        "BINANCE:XRP_USDT",
    ],
}


def days(market, dataset, lo, hi):
    return [d for d in available_dates(ROOT, market, dataset) if lo <= d <= hi]


def measure(market, lo, hi):
    """Median spread, top-of-book depth, real round-trip cost and trades/day.

    One day at a time, taking each day's median first and then the median of
    those. A day with ten times the snapshots would otherwise carry ten times
    the weight, and snapshot counts vary by venue and by day.
    """
    spr, tob, cost, fills = [], [], [], []
    for d in days(market, "OrderBook", lo, hi):
        book = load(ROOT, "BookState", market, d)
        if len(book) < MIN_SNAPSHOTS:
            continue
        spr.append(float(book["spread_bps"].median()))
        tob.append(float(book["top_of_book"].median()))

        # The walked spread at a cash amount: what the round trip really costs.
        # `execution_notional` rather than `execution_size` because the question
        # here is what a yen figure buys, and both sides are JPY-quoted.
        walked = load(ROOT, "MarketPrice", market, d, execution_notional=SIZE_JPY)
        fillable = usable(walked)
        fills.append(len(fillable) / len(walked) if len(walked) else 0.0)
        if len(fillable) >= MIN_FILLS:
            cost.append(float(fillable["spread_bps"].median()))

    trades = [
        n
        for n in (trade_count(ROOT, market, d) for d in days(market, "Trade", lo, hi))
        if n is not None
    ]

    if not spr:
        return None
    return {
        "days": len(spr),
        "spread_bps": round(statistics.median(spr), 4),
        "top_of_book_jpy": round(statistics.median(tob)) if tob else None,
        "roundtrip_1m_bps": round(statistics.median(cost), 3) if cost else None,
        # The share of snapshots whose book could complete the round trip,
        # across the window. It used to be the share of *days* with enough
        # fills to measure, which said nothing about how often an order would
        # actually go through.
        "fillable_1m_pct": round(statistics.mean(fills) * 100, 1) if fills else 0.0,
        "trades_per_day": round(statistics.median(trades)) if trades else None,
    }


def parse_args():
    a = argparse.ArgumentParser(
        description="Spread and liquidity by fee group, over any date range.",
        epilog="Defaults to the four weeks the article reports. Any range works; "
        "the archive is far longer than that window.",
    )
    a.add_argument(
        "--start", default=DEFAULT_WINDOW[0], help="first JST day, YYYY-MM-DD"
    )
    a.add_argument(
        "--end", help="last JST day, YYYY-MM-DD (default: --days after --start)"
    )
    a.add_argument("--days", type=int, help="length in days instead of --end")
    a.add_argument(
        "--out", help="output JSON path (default: output/groups_<start>_<end>.json)"
    )
    ns = a.parse_args()
    if ns.end and ns.days:
        a.error("give --end or --days, not both")
    if ns.days:
        ns.end = (
            dt.date.fromisoformat(ns.start) + dt.timedelta(days=ns.days - 1)
        ).isoformat()
    if not ns.end:
        ns.end = DEFAULT_WINDOW[1] if ns.start == DEFAULT_WINDOW[0] else ns.start
    if ns.end < ns.start:
        a.error("--end is before --start")
    return ns


args = parse_args()
WINDOW = (args.start, args.end)
span = (dt.date.fromisoformat(WINDOW[1]) - dt.date.fromisoformat(WINDOW[0])).days + 1
print(f"window {WINDOW[0]} .. {WINDOW[1]}  ({span} days)", flush=True)
if span % 7:
    print(
        f"note: {span} days is not a whole number of weeks, so weekdays are unevenly "
        f"represented. Spread has a weekday component; prefer multiples of 7.",
        flush=True,
    )

out = {"window": WINDOW, "days_requested": span, "groups": {}}
missing = []
for g, markets in GROUPS.items():
    out["groups"][g] = {}
    print(f"\n=== {g} ({WINDOW[0]} .. {WINDOW[1]}) ")
    print(
        f"{'market':22}{'spread bps':>12}{'top-of-book':>14}{'RT 1M bps':>11}{'trades/day':>12}"
    )
    for m in markets:
        r = measure(m, *WINDOW)
        if not r:
            missing.append(m)
            print(f"{m:22}  no data")
            continue
        out["groups"][g][m] = r
        print(
            f"{m:22}{r['spread_bps']:>12.4f}{(r['top_of_book_jpy'] or 0):>14,}"
            f"{(r['roundtrip_1m_bps'] if r['roundtrip_1m_bps'] is not None else float('nan')):>11.3f}"
            f"{(r['trades_per_day'] or 0):>12,}",
            flush=True,
        )

if args.out:
    dest = pathlib.Path(args.out)
elif WINDOW == DEFAULT_WINDOW:
    dest = pathlib.Path(__file__).parent / "output" / "groups_2026-06.json"
else:
    dest = (
        pathlib.Path(__file__).parent
        / "output"
        / f"groups_{WINDOW[0]}_{WINDOW[1]}.json"
    )

# A reader who downloaded two markets and ran this -- which is what section 7.1
# tells them to do -- would otherwise overwrite the article's evidence with a
# two-market file, and the ratios computed from it fail or, worse, quietly
# describe a different set of markets. A run that could not measure everything
# it claims does not get to be that file.
if missing and not args.out:
    dest = dest.with_name(dest.stem + "_partial.json")
    print(
        f"\n{len(missing)} of {sum(len(m) for m in GROUPS.values())} markets had no data "
        f"({', '.join(missing)}).\nWriting {dest.name} rather than the article's file. "
        f"Download the rest, or pass --out to name your own.",
        flush=True,
    )

dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
