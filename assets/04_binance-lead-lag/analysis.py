"""How far ahead of the JP venues does Binance move?

Mid-price is resampled onto a one-second grid, log returns are taken, and the
JP series is correlated against Binance shifted by k seconds. The lag with the
highest correlation is the lead.

Returns rather than levels, because one side is JPY and the other USDT and the
exchange rate would otherwise dominate. Seconds rather than ticks, because the
two venues do not update on the same clock.

Reproduces: 「最初の測定は「先行なし」だった」. Writes output/leadlag.json.
"""

import datetime as dt
import json
import math
import pathlib
import statistics
from zoneinfo import ZoneInfo

import komachi
import pyarrow.parquet as pq

ROOT = komachi.data_root() / "bronze" / "dataset=OrderBook"
LEAD = "BINANCE:BTC_USDT"
LAGGERS = ["COINCHECK:BTC_SPOT", "BITBANK:BTC_SPOT", "GMO:BTC_JPY"]
MAX_LAG = 60
JST = ZoneInfo("Asia/Tokyo")


def mid_series(market, date):
    """One mid-price per second of the JST day, carried forward."""
    ex, sym = market.split(":")
    p = ROOT / f"exchange={ex}" / f"symbol={sym}" / f"date={date}" / "data.parquet"
    if not p.exists():
        return None
    t = pq.read_table(p, columns=["ts", "bid0_price", "ask0_price"])
    ts = t.column("ts").to_pylist()
    b = t.column("bid0_price").to_pylist()
    a = t.column("ask0_price").to_pylist()
    if not ts:
        return None
    # Every venue uses the same JST midnight. Anchoring each grid to that
    # venue's first record can shift a market by a whole second when its first
    # snapshot arrives just after 00:00:01.
    start = int(dt.datetime.fromisoformat(date).replace(tzinfo=JST).timestamp())
    grid = [None] * 86400
    for tt, bb, aa in zip(ts, b, a):
        if bb is None or aa is None or bb > aa:
            continue
        i = int(tt) - start
        if 0 <= i < 86400:
            grid[i] = (bb + aa) / 2
    last = None
    for i in range(86400):
        if grid[i] is None:
            grid[i] = last
        else:
            last = grid[i]
    return start, grid


def returns(grid):
    out = [None] * len(grid)
    for i in range(1, len(grid)):
        p0, p1 = grid[i - 1], grid[i]
        if p0 and p1 and p0 > 0:
            out[i] = math.log(p1 / p0)
    return out


def corr(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 1000:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in pairs)
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else None


def best_lag(lead_r, lag_r):
    """Correlation at each shift. Positive k means Binance moved k seconds first."""
    curve = {}
    for k in range(-MAX_LAG, MAX_LAG + 1):
        if k >= 0:
            c = corr(lead_r[: len(lead_r) - k], lag_r[k:])
        else:
            c = corr(lead_r[-k:], lag_r[: len(lag_r) + k])
        if c is not None:
            curve[k] = c
    if not curve:
        return None, None, {}
    top = max(curve, key=curve.get)
    return top, curve[top], curve


def bars(grid, horizon):
    """Last mid in each horizon-second bar, then log returns between bars."""
    out = []
    for i in range(0, len(grid) - horizon, horizon):
        out.append(grid[i + horizon - 1])
    r = [None] * len(out)
    for i in range(1, len(out)):
        p0, p1 = out[i - 1], out[i]
        if p0 and p1 and p0 > 0:
            r[i] = math.log(p1 / p0)
    return r


HORIZONS = [1, 5, 15, 60, 300]
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

# Cache each day's grid: every market is compared against the same Binance day.
grids = {}


def grid_for(market, date):
    key = (market, date)
    if key not in grids:
        g = mid_series(market, date)
        grids[key] = g[1] if g else None
    return grids[key]


BAR_LAGS = 8  # in bars, so the window scales with the horizon

result = {
    "_measurement": {
        "dates": DATES,
        "source_grid_seconds": 1,
        "horizons_seconds": HORIZONS,
        "lag_window_bars": BAR_LAGS,
    }
}
for horizon in HORIZONS:
    print(f"--- {horizon}s bars ---", flush=True)
    for market in LAGGERS:
        lags, peaks, zeros = [], [], []
        for d in DATES:
            lg, mg = grid_for(LEAD, d), grid_for(market, d)
            if not lg or not mg:
                continue
            lr, mr = bars(lg, horizon), bars(mg, horizon)
            curve = {}
            for k in range(-BAR_LAGS, BAR_LAGS + 1):
                c = (
                    corr(lr[: len(lr) - k], mr[k:])
                    if k >= 0
                    else corr(lr[-k:], mr[: len(mr) + k])
                )
                if c is not None:
                    curve[k] = c
            if not curve:
                continue
            top = max(curve, key=curve.get)
            lags.append(top * horizon)
            peaks.append(curve[top])
            zeros.append(curve.get(0, 0))
        if not lags:
            continue
        result.setdefault(market, {})[f"{horizon}s"] = {
            "days": len(lags),
            "lag_seconds_median": statistics.median(lags),
            "peak_r_median": round(statistics.median(peaks), 4),
            "r_at_zero_median": round(statistics.median(zeros), 4),
        }
        r = result[market][f"{horizon}s"]
        print(
            f"  {market:<20} lag {r['lag_seconds_median']:>5}s   peak r {r['peak_r_median']:>7.4f}"
            f"   r@0 {r['r_at_zero_median']:>7.4f}",
            flush=True,
        )
    print(flush=True)

out = pathlib.Path(__file__).parent / "output" / "leadlag.json"
out.write_text(json.dumps(result, indent=2))
print("wrote", out.relative_to(pathlib.Path(__file__).parent))
