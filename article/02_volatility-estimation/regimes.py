"""bitbank's BTC quote changed character in February 2026. Does the volatility
estimator change with it?

Before: the spread sat on the one-yen tick. After: roughly 1 bp. If the
high-frequency inflation in vol.json is driven by a narrow quote flickering
between levels, the early regime should inflate far more than the late one --
on the same market, with the same code.

Reproduces: §6. Writes output/regimes.json.
"""
import json, pathlib, statistics

import numpy as np

import komachi
from hase.dataset import load
from hase.layout import available_dates

ROOT = komachi.data_root()
MARKET = "BITBANK:BTC_SPOT"
REGIMES = {"tick-pinned 2025-07..2026-01": ("2025-07-01", "2026-01-31"),
           "wide 2026-03..2026-08": ("2026-03-01", "2026-08-31")}
INTERVALS = [1, 2, 5, 10, 30, 60, 300, 1800]
N = 12

alld = available_dates(ROOT, MARKET, "OrderBook")
out = {}
for label, (lo, hi) in REGIMES.items():
    ds = [d for d in alld if lo <= d <= hi]
    ds = ds[:: max(1, len(ds) // N)][:N]
    rv = {k: [] for k in INTERVALS}
    acs, spr, moved = [], [], []
    for d in ds:
        book = load(ROOT, "BookState", MARKET, d)
        if len(book) < 500:
            continue
        g = load(ROOT, "VolSpread", MARKET, d)["mid"].to_numpy()
        spr.append(float(book["spread_bps"].median()))
        for k in INTERVALS:
            with np.errstate(invalid="ignore", divide="ignore"):
                r = np.diff(np.log(g[::k]))
            r = r[np.isfinite(r)]
            if len(r) > 10:
                rv[k].append(float(np.sqrt((r ** 2).sum()) * 1e4))
        with np.errstate(invalid="ignore", divide="ignore"):
            r1 = np.diff(np.log(g)) * 1e4
        r1 = r1[np.isfinite(r1)]
        if len(r1) > 10_000 and r1[:-1].std() > 0:
            acs.append(float(np.corrcoef(r1[:-1], r1[1:])[0, 1]))
            moved.append(float((r1 != 0).mean() * 100))
    m = {k: round(statistics.median(v), 1) for k, v in rv.items() if v}
    out[label] = {
        "days": len(acs),
        "median_spread_bps": round(statistics.median(spr), 4),
        "rv_bps_by_interval_sec": m,
        "inflation_1s_over_1800s": round(m[1] / m[1800], 2),
        "ac1_1s_returns": round(statistics.median(acs), 4),
        "pct_seconds_mid_moved": round(statistics.median(moved), 1),
    }
    r = out[label]
    print(f"{label:32} spread {r['median_spread_bps']:>8.4f}bps  RV 1s {m[1]:>7.1f}  "
          f"1800s {m[1800]:>7.1f}  inflate {r['inflation_1s_over_1800s']:>5.2f}x  "
          f"AC(1) {r['ac1_1s_returns']:>8.4f}  moved {r['pct_seconds_mid_moved']:>5.1f}%", flush=True)

dest = pathlib.Path(__file__).parent / "output" / "regimes.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
