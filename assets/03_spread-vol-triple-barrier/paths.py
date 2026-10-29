"""First-passage and triple-barrier measurements on the real June paths.

feasibility.py assumes the mid is a driftless walk with a constant v. Real
volatility clusters -- the month's v is pulled up by its busiest hours, so a
typical minute moves less -- and June 2026 fell by about a fifth in every
market. This enters at every minute of the month on the one-second mid grid and
records what the barriers actually did, with nothing predicted.  It also asks
the deliberately impossible oracle question: from each entry, how soon does
*either* a long or a short break even?  This is the first time the mid reaches
+S or -S, so it measures the market's available movement, not a tradable
two-sided position (opening both positions would pay the cost twice).

For the fixed triple-barrier setup it records:

    D        share of entries that hit a barrier before the timeout
    no skill win rate among those
    needed   the break-even win rate, from the same formula as feasibility.py
    pnl      mean outcome per trade in units of s, for a buy and for a sell

With no drift, a trade made with no prediction loses exactly s on average, so
pnl is -1. The buy and sell columns straddle -1 by the month's drift; their
mean is the drift-free figure.

Outcomes use the mid at the first second past the barrier, so a jump through it
counts at its real size. s is from inputs.json and held constant. Days with a
feed outage are left out, and no entry's window crosses one.

Reproduces: §3.2, §3.3, §4. Writes output/paths.json.
"""
import argparse
import datetime as dt, json, pathlib

import numpy as np

import komachi
from hase.dataset import load
from hase.derive.grid import quote_grid
from hase.layout import available_dates

ROOT = komachi.data_root()
here = pathlib.Path(__file__).parent
inp = json.loads((here / "output" / "inputs.json").read_text())
MIN_SNAPSHOTS, MAX_GAP_SEC = 500, 300
SETTINGS = [(3, 1, 5), (3, 1, 15), (3, 1, 30),
            (3, 1, 60), (3, 1, 120), (3, 1, 240)]
ENTRY_EVERY_SEC = 60
CHUNK = 400
ORACLE_TIMEOUT_MIN = 240

d0, d1 = (dt.date.fromisoformat(x) for x in inp["window"])
DATES = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def month(market):
    """The window's one-second mid, in log bps, NaN on dropped days."""
    have = set(available_dates(ROOT, market, "OrderBook"))
    parts = []
    for d in DATES:
        g = None
        if d in have:
            book = load(ROOT, "BookState", market, d)
            ts = np.sort(book["ts"].to_numpy(dtype="float64"))
            if len(book) >= MIN_SNAPSHOTS and np.diff(ts).max() <= MAX_GAP_SEC:
                g = quote_grid(ROOT, market, d)["mid"].to_numpy(dtype="float64")
        parts.append(g if g is not None else np.full(86400, np.nan))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.log(np.concatenate(parts)) * 1e4


def run(lp, s, tp, sl, t, side):
    T = t * 60
    ent = np.arange(0, len(lp) - T, ENTRY_EVERY_SEC)
    n_tp = n_sl = n_to = 0
    to_mv, pnl = [], []
    for c in range(0, len(ent), CHUNK):
        e = ent[c:c + CHUNK]
        W = side * (lp[e[:, None] + np.arange(T + 1)[None, :]] - lp[e][:, None])
        W = W[np.isfinite(W).all(axis=1)]
        if not len(W):
            continue
        hu, hd = W >= tp * s, W <= -sl * s
        fu = np.where(hu.any(1), hu.argmax(1), T + 9)
        fd = np.where(hd.any(1), hd.argmax(1), T + 9)
        up, dn = fu < fd, fd < fu
        no = ~(up | dn)
        n_tp += int(up.sum()); n_sl += int(dn.sum()); n_to += int(no.sum())
        idx = np.where(up, fu, np.where(dn, fd, T))
        mv = W[np.arange(len(W)), idx] / s
        pnl.append(mv - 1); to_mv.append(mv[no])
    pnl, to_mv = np.concatenate(pnl), np.concatenate(to_mv)
    N = n_tp + n_sl + n_to
    D = (n_tp + n_sl) / N
    m = float(to_mv.mean()) if len(to_mv) else 0.0
    need = ((1 - D) * (1 - m) + D * (sl + 1)) / (D * (tp + sl))
    w0 = n_tp / (n_tp + n_sl)
    return N, D, w0, need, float(pnl.mean())


def oracle_break_even(lp, s, timeout_min=ORACLE_TIMEOUT_MIN):
    """First time either hypothetical direction clears the round-trip cost.

    Each valid entry contributes one result.  A hit is abs(mid move) >= S;
    its sign says which direction an oracle would have selected.  Entries that
    do not hit before `timeout_min` are censored, not assigned that timeout.
    """
    T = timeout_min * 60
    ent = np.arange(0, len(lp) - T, ENTRY_EVERY_SEC)
    hit_seconds = []
    entries = 0
    for c in range(0, len(ent), CHUNK):
        e = ent[c:c + CHUNK]
        W = lp[e[:, None] + np.arange(T + 1)[None, :]] - lp[e][:, None]
        W = W[np.isfinite(W).all(axis=1)]
        if not len(W):
            continue
        hit = np.abs(W) >= s
        reached = hit.any(axis=1)
        entries += len(W)
        hit_seconds.extend(hit.argmax(axis=1)[reached].tolist())
    times = np.asarray(hit_seconds, dtype="float64")
    return {
        "timeout_min": timeout_min,
        "entries": entries,
        "reached_share": round(len(times) / entries, 3) if entries else None,
        "median_sec_reached": round(float(np.quantile(times, 0.5)), 1) if len(times) else None,
        "p90_sec_reached": round(float(np.quantile(times, 0.9)), 1) if len(times) else None,
    }


def correlation_summary(markets):
    """Descriptive correlations of observed oracle time with the inputs.

    Log Pearson correlation tests the scale relation suggested by the
    square-root formula; Spearman correlation tests only the market ordering.
    With six markets these are descriptive checks, not inferential tests.
    """
    if len(markets) < 3:
        return None

    def ranks(a):
        order = np.argsort(a)
        out = np.empty(len(a), dtype=float)
        out[order] = np.arange(len(a), dtype=float)
        return out

    times = np.asarray([markets[m]["oracle_break_even"]["median_sec_reached"] for m in markets], dtype=float)
    inputs = {
        "s_bps": np.asarray([inp["markets"][m]["s_bps"] for m in markets], dtype=float),
        "v1_bps_per_min": np.asarray([inp["markets"][m]["v_bps_per_min"] for m in markets], dtype=float),
        "s_over_v1": np.asarray([inp["markets"][m]["s_bps"] / inp["markets"][m]["v_bps_per_min"]
                                  for m in markets], dtype=float),
    }
    return {
        "markets": list(markets),
        "median_time_sec": times.tolist(),
        "log_pearson": {k: round(float(np.corrcoef(np.log(v), np.log(times))[0, 1]), 3)
                        for k, v in inputs.items()},
        "spearman": {k: round(float(np.corrcoef(ranks(v), ranks(times))[0, 1]), 3)
                     for k, v in inputs.items()},
    }


ap = argparse.ArgumentParser(description="Observed first passage and triple barriers per market.")
ap.add_argument("--market", action="append", choices=inp["in_scope"],
                help="Target market; repeat to run several. Defaults to all six.")
ap.add_argument("--output", type=pathlib.Path, default=here / "output" / "paths.json",
                help="JSON destination (default: output/paths.json).")
args = ap.parse_args()
TARGETS = args.market or inp["in_scope"]


out = {"window": inp["window"], "entry_every_sec": ENTRY_EVERY_SEC,
       "targets": TARGETS,
       "oracle_break_even": {"definition": "first abs(mid move) >= S; oracle selects that direction",
                              "timeout_min": ORACLE_TIMEOUT_MIN},
       "markets": {}}
for market in TARGETS:
    s = inp["markets"][market]["s_bps"]
    lp = month(market)
    oracle = oracle_break_even(lp, s)
    rows = {}
    for tp, sl, t in SETTINGS:
        N, D, w0, need, buy = run(lp, s, tp, sl, t, +1)
        *_, sell = run(lp, s, tp, sl, t, -1)
        rows[f"{tp}/{sl}/{t}"] = {
            "entries": N, "decisive_share": round(D, 3),
            "win_rate_no_skill_pct": round(w0 * 100, 1),
            "win_rate_needed_pct": round(need * 100, 1),
            "gap_pp": round((need - w0) * 100, 1),
            "pnl_buy_in_s": round(buy, 3), "pnl_sell_in_s": round(sell, 3),
            "pnl_mean_in_s": round((buy + sell) / 2, 3),
        }
        r = rows[f"{tp}/{sl}/{t}"]
        print(f"{market:20} tp {tp} sl {sl} t {t:>3}  N {N:>6}  D {D:.3f}  "
              f"no skill {w0*100:5.1f}%  needed {need*100:6.1f}%  gap {r['gap_pp']:6.1f}pp  "
              f"pnl buy {buy:+.3f}s sell {sell:+.3f}s", flush=True)
    out["markets"][market] = {"oracle_break_even": oracle, "triple_barrier": rows}
    print(f"{market:20} oracle ≤{ORACLE_TIMEOUT_MIN}m: {oracle['reached_share']:.1%} reached  "
          f"median {oracle['median_sec_reached']:.0f}s  p90 {oracle['p90_sec_reached']:.0f}s", flush=True)

out["cross_market_correlation"] = correlation_summary(out["markets"])
dest = args.output
dest.write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote", dest)
