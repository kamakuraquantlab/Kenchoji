"""Spread plus fee: what a round trip actually costs.

The spread is measured. The fee schedule is NOT — it is an input, entered here
by hand, and every entry carries its source status. Nothing in this file is
evidence; it is arithmetic on top of evidence.

A taker's round trip is one full spread (buy at the ask, sell at the bid) plus
the taker fee twice. A maker's round trip earns the rebate twice and pays no
spread, which is why a negative maker fee attracts quoting and tightens the
book -- and why the venue has to fund it from the taker side.

    taker round trip (bps) = spread_bps + 2 * taker_fee_bps

Reproduces: §5. Writes output/total_cost.json.
"""

import json
import pathlib

here = pathlib.Path(__file__).parent
groups = json.loads((here / "output" / "groups_2026-06.json").read_text())["groups"]
flat = {m: r for g in groups.values() for m, r in g.items()}

# percent -> bps. status: "given" = supplied by the author, awaiting a dated
# primary source. "unknown" = not yet supplied; excluded from conclusions.
FEES = {
    "BITBANK:ETH_SPOT": {"maker_pct": -0.02, "taker_pct": 0.12, "status": "given"},
    "BITBANK:XRP_SPOT": {"maker_pct": -0.02, "taker_pct": 0.12, "status": "given"},
    "GMO:BTC_SPOT": {"maker_pct": -0.01, "taker_pct": 0.05, "status": "given"},
    "GMO:ETH_SPOT": {"maker_pct": -0.01, "taker_pct": 0.05, "status": "given"},
    "GMO:XRP_SPOT": {"maker_pct": -0.01, "taker_pct": 0.05, "status": "given"},
    "BITBANK:BTC_SPOT": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, post-2026-02 change",
    },
    "COINCHECK:BTC_SPOT": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, unconfirmed",
    },
    "COINCHECK:ETH_SPOT": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, unconfirmed",
    },
    "COINCHECK:XRP_SPOT": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, unconfirmed",
    },
    "GMO:BTC_JPY": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, unconfirmed; excludes leverage carry",
    },
    "GMO:ETH_JPY": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, unconfirmed; excludes leverage carry",
    },
    "GMO:XRP_JPY": {
        "maker_pct": 0.0,
        "taker_pct": 0.0,
        "status": "given, unconfirmed; excludes leverage carry",
    },
    "BINANCE:BTC_USDT": {"maker_pct": None, "taker_pct": None, "status": "unknown"},
    "BINANCE:ETH_USDT": {"maker_pct": None, "taker_pct": None, "status": "unknown"},
    "BINANCE:XRP_USDT": {"maker_pct": None, "taker_pct": None, "status": "unknown"},
}

out = {
    "note": "Fee schedule is hand-entered and unconfirmed. Confirm against each "
    "venue's own page with a check date before publishing.",
    "formula": "taker_roundtrip_bps = spread_bps + 2 * taker_fee_bps",
    "markets": {},
}
rows = []
for m, f in FEES.items():
    if m not in flat or f["taker_pct"] is None:
        continue
    spread = flat[m]["spread_bps"]
    taker_bps = f["taker_pct"] * 100  # 0.12% -> 12 bps
    maker_bps = f["maker_pct"] * 100
    total = spread + 2 * taker_bps
    out["markets"][m] = {
        "spread_bps": spread,
        "maker_fee_pct": f["maker_pct"],
        "taker_fee_pct": f["taker_pct"],
        "maker_fee_bps": round(maker_bps, 2),
        "taker_fee_bps": round(taker_bps, 2),
        "taker_roundtrip_bps": round(total, 4),
        "fee_share_of_total_pct": round(2 * taker_bps / total * 100, 1)
        if total
        else None,
        "fee_status": f["status"],
    }
    rows.append((total, m, spread, taker_bps, maker_bps))

print(
    f"{'market':22}{'spread':>9}{'maker':>8}{'taker':>8}{'round trip':>12}{'fee share':>11}"
)
for total, m, spread, tk, mk in sorted(rows):
    print(
        f"{m:22}{spread:>9.4f}{mk:>8.1f}{tk:>8.1f}{total:>12.2f}"
        f"{(2 * tk / total * 100 if total else 0):>10.1f}%"
    )

tight = min(rows, key=lambda r: r[2])
cheap = min(rows)
print(
    f"\ntightest spread: {tight[1]} at {tight[2]:.4f} bps -> round trip {tight[0]:.2f} bps"
)
print(f"cheapest round trip: {cheap[1]} at {cheap[0]:.2f} bps (spread {cheap[2]:.4f})")
out["inversion"] = {
    "tightest_spread_market": tight[1],
    "tightest_spread_bps": tight[2],
    "its_roundtrip_bps": round(tight[0], 2),
    "cheapest_roundtrip_market": cheap[1],
    "cheapest_roundtrip_bps": round(cheap[0], 2),
    "cheapest_roundtrip_spread_bps": cheap[2],
    "ratio": round(tight[0] / cheap[0], 1),
}
# The fee change, seen by a taker. bitbank BTC spot before: the maker rebate was
# funded by a 0.12% taker fee. After: no fee either side, and a wider quote.
fc = json.loads((here / "output" / "fee_change.json").read_text())
before_spread = fc["before  2026-01-29..02-04"]["BITBANK:BTC_SPOT"]["spread_bps"]
after_spread = fc["settled 2026-02-20..02-26"]["BITBANK:BTC_SPOT"]["spread_bps"]
BEFORE_TAKER_BPS, AFTER_TAKER_BPS = 12.0, 0.0  # 0.12% -> 12 bps, then none
out["fee_change_taker_view"] = {
    "before": {
        "spread_bps": before_spread,
        "taker_fee_bps": BEFORE_TAKER_BPS,
        "roundtrip_bps": round(before_spread + 2 * BEFORE_TAKER_BPS, 4),
    },
    "after": {
        "spread_bps": after_spread,
        "taker_fee_bps": AFTER_TAKER_BPS,
        "roundtrip_bps": round(after_spread + 2 * AFTER_TAKER_BPS, 4),
    },
    "spread_wider_x": round(after_spread / before_spread, 1),
    "taker_roundtrip_cheaper_x": round(
        (before_spread + 2 * BEFORE_TAKER_BPS) / (after_spread + 2 * AFTER_TAKER_BPS), 1
    ),
    "caveat": "assumes bitbank BTC spot taker fee was 0.12% before and 0% after; unconfirmed",
}
v = out["fee_change_taker_view"]
print(
    f"\nfee change, taker view: before {v['before']['roundtrip_bps']:.2f} bps"
    f" -> after {v['after']['roundtrip_bps']:.2f} bps"
    f"  (spread {v['spread_wider_x']}x wider, round trip {v['taker_roundtrip_cheaper_x']}x cheaper)"
)

dest = here / "output" / "total_cost.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
