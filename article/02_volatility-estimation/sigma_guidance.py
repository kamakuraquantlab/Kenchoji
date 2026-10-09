"""From which sampling interval is sigma safe to use, per market?

Every market's RV rises with the interval and levels off somewhere between one
and five minutes. Below the level, sigma is understated, and anything a later
article builds on sigma -- barrier width, minimum holding time -- inherits the
shortfall, doubled where the quantity goes with sigma squared.

The level is the RV at 5, 10 and 30 minutes pooled together: the 30-minute RV
alone holds 48 returns a day and is too noisy to be a yardstick by itself.
The usable interval is the shortest one from which every longer interval is
within 5% of that level. Next to it, from response.py, the shortest horizon at
which Binance explains 90% of the market's moves -- the interval to use when
the market is to be read alongside Binance rather than on its own.

Reads vol.json and response.json rather than the warehouse, so it is instant
and always agrees with sections 3 and 5.

Reproduces: §7, §8. Writes output/sigma_guidance.json.
"""
import json, pathlib

here = pathlib.Path(__file__).parent
vol = json.loads((here / "output" / "vol.json").read_text())
response = json.loads((here / "output" / "response.json").read_text())
INTERVALS = [10, 30, 60, 300, 600, 1800]
LEVEL = [300, 600, 1800]
TOLERANCE = 0.95
SYNC_R2 = 0.90

out = {"level_intervals_sec": LEVEL, "tolerance": TOLERANCE, "sync_r2": SYNC_R2,
       "note": "share_of_level is RV at the interval over the pooled 5-30 minute "
               "RV. usable_from_sec is the shortest interval from which every "
               "longer one is within the tolerance.",
       "markets": {}}

print(f"{'market':22}" + "".join(f"{str(k) + 's':>7}" for k in INTERVALS) +
      f"{'usable':>9}{'R²≥0.9':>9}")
for m, r in vol.items():
    if m.startswith("_"):
        continue
    rv = r["rv_bps_mid_by_interval_sec"]
    level = (sum(rv[str(k)] ** 2 for k in LEVEL) / len(LEVEL)) ** 0.5
    share = {k: rv[str(k)] / level for k in INTERVALS}
    usable = next(k for k in INTERVALS
                  if all(share[j] >= TOLERANCE for j in INTERVALS if j >= k))
    sync = None
    if m in response:
        sync = next((int(h) for h, v in response[m]["by_horizon_sec"].items()
                     if v["r2"] >= SYNC_R2), None)
    out["markets"][m] = {"level_bps": round(level, 1),
                         "share_of_level": {str(k): round(share[k], 3) for k in INTERVALS},
                         "usable_from_sec": usable,
                         "sync_from_sec": sync}
    print(f"{m:22}" + "".join(f"{share[k]:>7.2f}" for k in INTERVALS) +
          f"{str(usable) + 's':>9}{(str(sync) + 's') if sync else '-':>9}")

dest = here / "output" / "sigma_guidance.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
