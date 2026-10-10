"""bitbank BTC spot: two weeks before the fee change and the weeks after.

bitbank paid a negative maker fee on BTC spot and stopped. If the spread is a
form of payment to whoever provides the quote, removing the payment should
widen it, and the archive should show the step.

bitbank's notice puts the change at 2026-02-02, and the book agrees to the
hour: from 12:00 JST that day the BTC best quote is a third thinner and wider
more of the time, while XRP, whose fee did not change, does neither. The windows
are placed around that, with two things kept out of them:

- 2026-02-05..08, the market-wide sell-off. XRP traded over a 33% range on
  Binance on 02-06, and every bitbank book widened with it, BTC and XRP alike.
- the change day itself.

Before is the two weeks to 02-01, after the two weeks from 02-09, and March
shows where the book settled. XRP over the same windows is the control: the
comparison is how much more BTC's spread moved than XRP's.

The daily median alone misstates the step. Both bitbank books sit one tick
wide most of the time and 2-6 bps wide for the rest, before the change as well
as after it, and a median of that mixture flips from one state to the other
once the wide share passes one half. So each window also reports the mean
spread and the share of time the spread was wide, and the median is kept at
six decimals so the ratios taken from it do not inherit any rounding.

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

import datetime as dt
import json
import pathlib
import statistics

import numpy as np

import komachi
from hase.dataset import load, trade_count
from hase.layout import available_dates

ROOT = komachi.data_root()
MARKET = "BITBANK:BTC_SPOT"
CONTROL = "BITBANK:XRP_SPOT"  # kept its negative maker fee; should not step
CHANGE = "2026-02-02 12:00 JST"  # the date is bitbank's notice; the hour is the book's
CHANGE_DAY = "2026-02-02"
SELLOFF = ("2026-02-05", "2026-02-08")  # market-wide; kept out of every window
WINDOWS = {
    "before 2026-01-19..02-01": ("2026-01-19", "2026-02-01"),
    "after  2026-02-09..02-22": ("2026-02-09", "2026-02-22"),
    "march  2026-03-01..03-31": ("2026-03-01", "2026-03-31"),
}
PLOT_WINDOW = ("2026-01-01", "2026-03-31")
# Wide means above this. The tight state is 0.0007-0.0010 bps on BTC and
# 0.03-0.05 bps on XRP, the wide one 1 bps and up, so 0.1 separates them on both.
WIDE_BPS = 0.1
JST = dt.timezone(dt.timedelta(hours=9))


def day_stats(book):
    """Median, mean and wide share of one day's spread. Snapshots are evenly
    spaced (about every 0.35 s), so plain averages are time averages."""
    s = book["spread_bps"]
    return float(s.median()), float(s.mean()), float((s > WIDE_BPS).mean())


def rv_bps(book):
    """Realized volatility of the day from one-minute mid returns, in bps.

    The spread widens when prices move, so a window that happens to be more
    volatile would widen it with no help from the fee. This is the check."""
    ts = book["ts"].to_numpy(dtype="float64")
    mid = book["mid"].to_numpy(dtype="float64")
    order = np.argsort(ts)
    ts, mid = ts[order], mid[order]
    grid = np.arange(ts[0] - ts[0] % 60, ts[-1], 60)
    idx = np.searchsorted(ts, grid, side="right") - 1
    r = np.diff(np.log(mid[idx[idx >= 0]]))
    r = r[np.isfinite(r)]
    return float(np.sqrt((r**2).sum()) * 1e4)


def window(market, lo, hi):
    """Daily medians of spread, mean spread, wide share, depth and RV, and the
    median trades per day, over one window."""
    spr, mean, wide, tob, vol = [], [], [], [], []
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
        tob.append(float(book["top_of_book"].median()))
        vol.append(rv_bps(book))
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
        "top_of_book_jpy": round(statistics.median(tob)),
        "rv_bps": round(statistics.median(vol)),
        "trades_per_day": round(statistics.median(tr)) if tr else None,
    }


def change_day(market):
    """Median depth and wide share before and after noon on the change day."""
    book = load(ROOT, "BookState", market, CHANGE_DAY)
    hour = np.array([dt.datetime.fromtimestamp(t, JST).hour for t in book["ts"]])
    out = {}
    for label, mask in (("00-12", hour < 12), ("12-24", hour >= 12)):
        part = book[mask]
        out[label] = {
            "top_of_book_jpy": round(float(part["top_of_book"].median())),
            "wide_share": round(float((part["spread_bps"] > WIDE_BPS).mean()), 3),
        }
    return out


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


out = {"change": CHANGE, "selloff_excluded": list(SELLOFF), "windows": {}}
for label, (lo, hi) in WINDOWS.items():
    r = window(MARKET, lo, hi)
    c = window(CONTROL, lo, hi)
    out["windows"][label] = {MARKET: r, CONTROL: c}
    print(label)
    for name, x in (("BTC spot", r), ("XRP ctrl", c)):
        print(
            f"   {name}   median {x['spread_bps']:>9.4f}   mean {x['spread_mean_bps']:>5.2f}   "
            f"wide {x['wide_share']:>4.0%}   top-of-book {x['top_of_book_jpy']:>8,} JPY   "
            f"RV {x['rv_bps']:>4}   trades/day {x['trades_per_day']:>7,}",
            flush=True,
        )

out["change_day_2026-02-02"] = {MARKET: change_day(MARKET), CONTROL: change_day(CONTROL)}
print("\nchange day 2026-02-02, before and after noon JST")
for m, halves in out["change_day_2026-02-02"].items():
    print(f"   {m:18}" + "   ".join(
        f"{h}: top-of-book {v['top_of_book_jpy']:>8,} JPY wide {v['wide_share']:.0%}"
        for h, v in halves.items()))

# Each row: date, median, mean, wide share.
out["daily_spread_bps_2026-01-01_2026-03-31"] = {
    MARKET: daily_spread(MARKET, *PLOT_WINDOW),
    CONTROL: daily_spread(CONTROL, *PLOT_WINDOW),
}

dest = pathlib.Path(__file__).parent / "output" / "fee_change.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
