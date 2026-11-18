"""How often does each venue's book actually update?

The lead-lag measurement cannot resolve a lead shorter than the interval at
which the slower side is recorded. This measures that floor.

Reproduces: 「板は、1 秒の内側でも動いている」. Writes output/cadence.json.
"""

import json
import pathlib
import statistics

import komachi
import pyarrow.parquet as pq

ROOT = komachi.data_root() / "bronze" / "dataset=OrderBook"
MARKETS = ["BINANCE:BTC_USDT", "COINCHECK:BTC_SPOT", "BITBANK:BTC_SPOT", "GMO:BTC_JPY"]
DATES = ["2026-01-14", "2026-03-11", "2026-05-13", "2026-07-08", "2026-08-12"]

out = {"_measurement": {"dates": DATES}}
for m in MARKETS:
    ex, sym = m.split(":")
    rows, gaps = [], []
    for d in DATES:
        p = ROOT / f"exchange={ex}" / f"symbol={sym}" / f"date={d}" / "data.parquet"
        if not p.exists():
            continue
        ts = pq.read_table(p, columns=["ts"]).column("ts").to_pylist()
        ts = sorted(float(x) for x in ts if x is not None)
        if len(ts) < 2:
            continue
        rows.append(len(ts))
        span = ts[-1] - ts[0]
        gaps.append(span / (len(ts) - 1))
    if not rows:
        continue
    out[m] = {
        "days": len(rows),
        "rows_per_day_median": int(statistics.median(rows)),
        "mean_interval_ms": round(statistics.median(gaps) * 1000, 1),
    }
    print(
        f"{m:20} {out[m]['rows_per_day_median']:>10,} rows/day   {out[m]['mean_interval_ms']:>7.1f} ms"
    )

dest = pathlib.Path(__file__).parent / "output" / "cadence.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("wrote", dest.relative_to(pathlib.Path(__file__).parent))
