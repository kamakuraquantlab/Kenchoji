"""The ratios the draft quotes, computed from the two measurement files.

Rule 1 in article/README.md: no number in a draft that is not in output/. A
ratio typed into prose is exactly the kind that goes stale when the underlying
measurement is regenerated.

Reproduces: §1〜§4 の倍率. Writes output/derived.json.
"""

import json
import pathlib
import statistics

here = pathlib.Path(__file__).parent
g = json.loads((here / "output" / "groups_2026-06.json").read_text())["groups"]
f = json.loads((here / "output" / "fee_change.json").read_text())
flat = {m: r for grp in g.values() for m, r in grp.items()}

pairs = [
    ("BTC", "GMO:BTC_SPOT", "GMO:BTC_JPY"),
    ("ETH", "GMO:ETH_SPOT", "GMO:ETH_JPY"),
    ("XRP", "GMO:XRP_SPOT", "GMO:XRP_JPY"),
]
out = {
    "gmo_spot_vs_leverage": {},
    "group_medians_bps": {},
    "fee_change": {},
    "scale": {},
}

for a, sp, lv in pairs:
    s, l = flat[sp], flat[lv]
    out["gmo_spot_vs_leverage"][a] = {
        "spot_bps": s["spread_bps"],
        "leverage_bps": l["spread_bps"],
        "leverage_spread_wider_x": round(l["spread_bps"] / s["spread_bps"], 2),
        "leverage_trades_more_x": round(l["trades_per_day"] / s["trades_per_day"], 2),
    }
for name, grp in g.items():
    v = [r["spread_bps"] for r in grp.values()]
    out["group_medians_bps"][name] = {
        "median": round(statistics.median(v), 4),
        "min": min(v),
        "max": max(v),
        "n": len(v),
    }
neg = out["group_medians_bps"]["negative maker fee"]["median"]
zero = out["group_medians_bps"]["zero fee"]["median"]
out["group_medians_bps"]["zero_over_negative_x"] = round(zero / neg, 2)

B = f["before  2026-01-29..02-04"]["BITBANK:BTC_SPOT"]
A = f["after   2026-02-05..02-11"]["BITBANK:BTC_SPOT"]
S = f["settled 2026-02-20..02-26"]["BITBANK:BTC_SPOT"]
cB = f["before  2026-01-29..02-04"]["control BITBANK:XRP_SPOT"]
cA = f["after   2026-02-05..02-11"]["control BITBANK:XRP_SPOT"]
out["fee_change"] = {
    "spread_wider_x": round(A["spread_bps"] / B["spread_bps"]),
    "depth_thinner_x": round(B["top_of_book_jpy"] / A["top_of_book_jpy"], 1),
    "trades_ratio_settled": round(S["trades_per_day"] / B["trades_per_day"], 2),
    "control_spread_change_x": round(cA["spread_bps"] / cB["spread_bps"], 2),
}
out["scale"] = {
    "binance_btc_over_gmo_leverage_trades_x": round(
        flat["BINANCE:BTC_USDT"]["trades_per_day"]
        / flat["GMO:BTC_JPY"]["trades_per_day"],
        1,
    ),
}

dest = here / "output" / "derived.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
print("\nwrote", dest)
