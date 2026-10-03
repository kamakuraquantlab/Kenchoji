"""At which sampling interval is sigma safe to use, per market?

The signature plot says RV inflates as the interval shrinks. This turns that
into the practical number: how far above the 30-minute estimate is each
candidate interval? Anything a later article uses sigma for -- barrier width,
minimum holding time -- inherits this error, squared where the quantity depends
on sigma squared.

Reads vol.json rather than the warehouse, so it is instant and always agrees
with the table in section 3.

Reproduces: §7.1, §8. Writes output/sigma_guidance.json.
"""
import json, pathlib

here = pathlib.Path(__file__).parent
vol = json.loads((here / "output" / "vol.json").read_text())
BASE = "1800"
CANDIDATES = ["60", "300"]

out = {"base_interval_sec": int(BASE), "note":
       "excess_pct is how far the candidate interval's RV sits above the "
       "30-minute estimate. A sigma overstated by x% distorts a sigma-squared "
       "quantity by roughly 2x%.", "markets": {}}
rows = []
for m, r in vol.items():
    if m.startswith("_"):
        continue
    rv = r["rv_bps_mid_by_interval_sec"]
    if BASE not in rv:
        continue
    e = {c: round((rv[c] / rv[BASE] - 1) * 100, 1) for c in CANDIDATES if c in rv}
    out["markets"][m] = {"rv_1800s": rv[BASE],
                         **{f"excess_at_{c}s_pct": e[c] for c in e}}
    rows.append((m, rv[BASE], e))

print(f"{'market':22}{'RV 1800s':>10}{'60s excess':>12}{'300s excess':>13}")
for m, base, e in sorted(rows, key=lambda x: -x[2].get("60", 0)):
    print(f"{m:22}{base:>10.1f}{e.get('60', float('nan')):>11.1f}%{e.get('300', float('nan')):>12.1f}%")

dest = here / "output" / "sigma_guidance.json"
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
