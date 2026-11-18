"""Lead-lag at the resolution the effect actually lives at.

The first pass resampled to a 1-second grid and found no lead. Makalu's
production pipeline resamples at 100ms and searches -500..+2000ms, and finds
GMO lagging Binance by 600-700ms. A 1s grid cannot resolve that: the whole
effect fits inside one bar.

This re-runs the measurement on a 100ms grid with the same search range, using
plain per-day Pearson correlation of touch-mid returns. With --compare-start it
measures the same number of days in a second window, so a reader can repeat the
article's matched-month design directly from downloaded books.

Reproduces: 「自分で確かめるには」の raw-book check. Writes
output/leadlag_100ms.json.
"""

import argparse
import datetime as dt
import json
import pathlib
import statistics
from zoneinfo import ZoneInfo

import komachi
import numpy as np
import pyarrow.parquet as pq

JST = ZoneInfo("Asia/Tokyo")

ROOT = komachi.data_root() / "bronze" / "dataset=OrderBook"
STEP_MS = 100
LAGS_MS = list(range(-500, 2100, 100))
GRID = 24 * 60 * 60 * 1000 // STEP_MS

PAIRS = [
    ("BINANCE:BTC_USDT", "GMO:BTC_JPY"),
    ("BINANCE:BTC_USDT", "COINCHECK:BTC_SPOT"),
    ("BINANCE:BTC_USDT", "BITBANK:BTC_SPOT"),
    ("BINANCE:ETH_USDT", "GMO:ETH_JPY"),
    ("BINANCE:XRP_USDT", "GMO:XRP_JPY"),
]
DATES = [
    "2026-01-15",
    "2026-02-12",
    "2026-03-12",
    "2026-04-16",
    "2026-05-14",
    "2026-06-11",
    "2026-07-16",
    "2026-08-13",
]

parser = argparse.ArgumentParser()
parser.add_argument(
    "--start", help="First JST date (YYYY-MM-DD); defaults to the article's eight dates"
)
parser.add_argument(
    "--days", type=int, default=8, help="Number of consecutive days with --start"
)
parser.add_argument(
    "--compare-start",
    help="Optional first JST date for a second window of the same length",
)
parser.add_argument(
    "--asset",
    choices=["BTC", "ETH", "XRP", "ALL"],
    default="ALL",
    help="Limit the standard Binance-to-GMO pairs; default also runs BTC spot checks",
)
args = parser.parse_args()
if args.start:
    first = dt.date.fromisoformat(args.start)
    requested_dates = [str(first + dt.timedelta(days=i)) for i in range(args.days)]
else:
    requested_dates = DATES

periods = {args.start or "article-eight-dates": requested_dates}
if args.compare_start:
    second = dt.date.fromisoformat(args.compare_start)
    periods[args.compare_start] = [
        str(second + dt.timedelta(days=i)) for i in range(args.days)
    ]


def grid_mid(market, date):
    ex, sym = market.split(":")
    p = ROOT / f"exchange={ex}" / f"symbol={sym}" / f"date={date}" / "data.parquet"
    if not p.exists():
        return None
    t = pq.read_table(p, columns=["ts", "bid0_price", "ask0_price"])
    ts = np.asarray(t.column("ts").to_pylist(), dtype=np.float64)
    b = np.asarray(t.column("bid0_price").to_pylist(), dtype=np.float64)
    a = np.asarray(t.column("ask0_price").to_pylist(), dtype=np.float64)
    ok = np.isfinite(ts) & np.isfinite(b) & np.isfinite(a) & (b > 0) & (a >= b)
    ts, b, a = ts[ok], b[ok], a[ok]
    if len(ts) < 1000:
        return None
    day0 = dt.datetime.fromisoformat(date).replace(tzinfo=JST).timestamp()
    idx = np.floor((ts - day0) * 1000 / STEP_MS).astype(np.int64)
    keep = (idx >= 0) & (idx < GRID)
    idx, mid = idx[keep], ((b + a) / 2)[keep]
    out = np.full(GRID, np.nan)
    out[idx] = mid  # last book in each 100ms cell wins
    # forward fill
    m = np.isfinite(out)
    if not m.any():
        return None
    first = np.argmax(m)
    fill = np.maximum.accumulate(np.where(m, np.arange(GRID), 0))
    out = out[fill]
    out[:first] = np.nan
    return out


def dates_for(market):
    ex, sym = market.split(":")
    d = ROOT / f"exchange={ex}" / f"symbol={sym}"
    return {p.name.split("=")[1] for p in d.glob("date=*")} if d.exists() else set()


def measure(lead, lag, requested):
    common = dates_for(lead) & dates_for(lag)
    used_dates, per_day, r_opt, r_zero = [], [], [], []
    for date in (value for value in requested if value in common):
        lead_mid, lag_mid = grid_mid(lead, date), grid_mid(lag, date)
        if lead_mid is None or lag_mid is None:
            continue
        ok = np.isfinite(lead_mid) & np.isfinite(lag_mid)
        lead_mid = np.where(ok, lead_mid, np.nan)
        lag_mid = np.where(ok, lag_mid, np.nan)
        lead_return = np.diff(np.log(lead_mid))
        lag_return = np.diff(np.log(lag_mid))
        good = np.isfinite(lead_return) & np.isfinite(lag_return)
        lead_return = np.where(good, lead_return, 0.0)
        lag_return = np.where(good, lag_return, 0.0)
        if good.sum() < 100_000:
            continue
        best, best_lag, at_zero = 0.0, None, None
        for milliseconds in LAGS_MS:
            steps = milliseconds // STEP_MS
            if steps >= 0:
                x = lag_return[steps:]
                y = lead_return[: len(lead_return) - steps] if steps else lead_return
            else:
                x, y = lag_return[: len(lag_return) + steps], lead_return[-steps:]
            length = min(len(x), len(y))
            x, y = x[:length], y[:length]
            sx, sy = x.std(), y.std()
            if sx == 0 or sy == 0:
                continue
            correlation = float(
                ((x - x.mean()) * (y - y.mean())).mean() / (sx * sy)
            )
            if milliseconds == 0:
                at_zero = correlation
            if abs(correlation) > abs(best):
                best, best_lag = correlation, milliseconds
        if best_lag is None or at_zero is None:
            continue
        used_dates.append(date)
        per_day.append(best_lag)
        r_opt.append(abs(best))
        r_zero.append(abs(at_zero))

    if not per_day:
        return None
    return {
        "days": len(per_day),
        "dates": used_dates,
        "opt_lag_ms_median": statistics.median(per_day),
        "opt_lag_ms_per_day": per_day,
        "pct_days_positive": round(
            sum(1 for x in per_day if x > 0) / len(per_day) * 100, 1
        ),
        "r_at_opt_median": round(statistics.median(r_opt), 5),
        "r_at_zero_median": round(statistics.median(r_zero), 5),
        "gain_vs_zero": round(statistics.median(r_opt) / statistics.median(r_zero), 1)
        if statistics.median(r_zero)
        else None,
    }


result = {"measurement": {"grid_ms": STEP_MS, "periods": periods}, "pairs": {}}
selected_pairs = PAIRS
if args.asset != "ALL":
    selected_pairs = [
        pair
        for pair in PAIRS
        if pair[0] == f"BINANCE:{args.asset}_USDT"
        and pair[1] == f"GMO:{args.asset}_JPY"
    ]
for lead, lag in selected_pairs:
    pair_result = {}
    for label, dates in periods.items():
        measured = measure(lead, lag, dates)
        if measured is None:
            continue
        pair_result[label] = measured
        print(
            f"{label} {lag:22} lag {measured['opt_lag_ms_median']:>6.0f}ms  "
            f"pos {measured['pct_days_positive']:>5.1f}%  "
            f"r_opt {measured['r_at_opt_median']:.5f}  "
            f"r_0 {measured['r_at_zero_median']:.5f}"
        )
    if pair_result:
        result["pairs"][f"{lead}->{lag}"] = pair_result

dest = pathlib.Path(__file__).parent / "output" / "leadlag_100ms.json"
dest.write_text(json.dumps(result, indent=2) + "\n")
print("\nwrote", dest.relative_to(pathlib.Path(__file__).parent))
