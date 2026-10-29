"""How hard is it to win here, before any strategy exists? The model.

Six numbers describe the problem. Three come from the market and cannot be
chosen; three are the setup and can:

    from the market   s  round-trip cost, in bps
                      v  volatility over one window w, in bps
                      w  the window (here one minute)

    chosen by us      tp  take profit, placed at +tp * s on the mid
                      sl  stop loss,   placed at -sl * s on the mid
                      t   timeout, at t * w

Entry is at the ask, exit at the bid, so the mid has to travel s before the
position is flat:

    win  =  (tp - 1) * s        loss = (sl + 1) * s        timeout: mid move - s

With D the share of trades that hit a barrier at all, m the mean mid move at
timeout in units of s, and w the win rate among decisive trades,

    E/s = D*w*(tp-1) - D*(1-w)*(sl+1) + (1-D)*(m-1)

and E > 0 needs w >= [(1-D)(1-m) + D(sl+1)] / [D(tp+sl)].

D, m and the no-skill win rate come from a driftless walk with steps of
v / sqrt(20) every 3 seconds. When D = 1 the walk gives the no-skill win rate
sl / (tp + sl) and the required one (sl + 1) / (tp + sl), so the gap between
them is 1 / (tp + sl) whatever the market -- printed beside every row, because
that is the comparison section 3.3 makes. The market only enters through D.

It also gives the oracle of section 3.2 its random-walk baseline: on a
driftless walk, the time until the mid first reaches +S or -S has mean exactly
t_s = (S / v)^2, and its median and 90th percentile are fixed multiples of t_s
whatever the market.

paths.py repeats every setting on the real June paths.

Reproduces: the 25% no-skill win rate of §3.3 and the random-walk baseline of
§3.2. Writes output/feasibility.json.
"""
import argparse, json, math, pathlib
import numpy as np

here = pathlib.Path(__file__).parent
inp = json.loads((here / "output" / "inputs.json").read_text())
RNG = np.random.default_rng(7)
STEPS_PER_MIN = 20
N_PATHS = 20000
MAX_CELLS = 20_000_000          # keep one chunk under ~160MB
TIMEOUTS = [5, 15, 30, 60, 120, 240]
LADDER = [("出発点", 1, 1, 30), ("tp を上げる", 2, 1, 30), ("sl も上げる", 2, 2, 30),
          ("tp をさらに上げる", 3, 2, 30), ("t を 4 倍に", 3, 2, 120),
          ("両方広げる", 4, 3, 120)]


def simulate(v, s, tp, sl, t):
    """Driftless walk. Returns (D, mean timeout move in units of s, P(tp))."""
    n = max(1, int(round(t * STEPS_PER_MIN)))
    step_sd = v / math.sqrt(STEPS_PER_MIN)
    up, dn = tp * s, -sl * s
    chunk = max(500, min(N_PATHS, MAX_CELLS // n))
    n_tp = n_sl = n_to = 0
    to_sum = 0.0
    done = 0
    while done < N_PATHS:
        k = min(chunk, N_PATHS - done)
        path = np.cumsum(RNG.normal(0.0, step_sd, size=(k, n)), axis=1)
        hit_up, hit_dn = path >= up, path <= dn
        first_up = np.where(hit_up.any(axis=1), hit_up.argmax(axis=1), n + 1)
        first_dn = np.where(hit_dn.any(axis=1), hit_dn.argmax(axis=1), n + 1)
        tp_first, sl_first = first_up < first_dn, first_dn < first_up
        neither = ~(tp_first | sl_first)
        n_tp += int(tp_first.sum()); n_sl += int(sl_first.sum())
        n_to += int(neither.sum())
        if neither.any():
            to_sum += float(path[neither, -1].sum())
        done += k
    m_to = (to_sum / n_to / s) if n_to else 0.0
    return (n_tp + n_sl) / N_PATHS, m_to, n_tp / N_PATHS


def evaluate(v, s, tp, sl, t):
    D, m_to, p_tp = simulate(v, s, tp, sl, t)
    need = ((1 - D) * (1 - m_to) + D * (sl + 1)) / (D * (tp + sl)) if D > 0 else None
    w0 = p_tp / D if D > 0 else 0.0
    return {"tp": tp, "sl": sl, "timeout_min": t,
            "decisive_share": round(D, 3),
            "win_rate_no_skill_pct": round(w0 * 100, 1),
            "win_rate_needed_pct": round(need * 100, 1) if need else None,
            "gap_pp": round((need - w0) * 100, 1) if need else None,
            "one_over_tp_plus_sl_pp": round(100 / (tp + sl), 1),
            "cost_over_move": round(s / (v * math.sqrt(t)), 3)}


def oracle_baseline(steps_per_ts=2000, horizon_ts=10):
    """First time a driftless walk reaches +-1 when t_s = 1, in units of t_s."""
    n = steps_per_ts * horizon_ts
    chunk = max(1, MAX_CELLS // n)
    times = []
    done = 0
    while done < N_PATHS:
        k = min(chunk, N_PATHS - done)
        path = np.cumsum(RNG.normal(0.0, 1 / math.sqrt(steps_per_ts), size=(k, n)), axis=1)
        hit = np.abs(path) >= 1
        times.append(np.where(hit.any(axis=1), (hit.argmax(axis=1) + 1) / steps_per_ts, np.inf))
        done += k
    times = np.concatenate(times)
    return {"paths": N_PATHS, "horizon_ts": horizon_ts,
            "reached_share": round(float(np.isfinite(times).mean()), 4),
            "mean_over_ts": round(float(times[np.isfinite(times)].mean()), 3),
            "median_over_ts": round(float(np.median(times)), 3),
            "p90_over_ts": round(float(np.quantile(times, 0.9)), 3)}


ap = argparse.ArgumentParser(description="Feasibility of a triple barrier, per market.")
ap.add_argument("--tp", type=float, default=3.0)
ap.add_argument("--sl", type=float, default=1.0)
ap.add_argument("--t", type=float, default=30.0, help="timeout in minutes")
args = ap.parse_args()
std = (args.tp, args.sl, args.t)

mk = inp["markets"]
out = {"window": inp["window"], "settings": dict(zip(("tp", "sl", "t"), std)),
       "standard": {}, "by_timeout": {}, "ladder": None}

print(f"tp={args.tp:g}  sl={args.sl:g}  t={args.t:g} min   (w = 1 min)\n")
print(f"{'market':22}{'v':>6}{'s':>8}{'v/s':>6}{'D':>7}{'no skill':>10}{'needed':>9}"
      f"{'gap':>8}{'1/(tp+sl)':>11}{'s/(v√t)':>9}")
for m, r in mk.items():
    v, s = r["v_bps_per_min"], r["s_bps"]
    e = evaluate(v, s, *std)
    board = r["board_roundtrip_bps"]
    e.update({"v_over_s": round(v / s, 2), "v_over_board": round(v / board, 2),
              "fee_over_board": round((s - board) / board, 1),
              "drift_pct": round(math.expm1(r["drift_bps"] / 1e4) * 100, 1)})
    out["standard"][m] = e
    print(f"{m:22}{v:>6.2f}{s:>8.3f}{v/s:>6.2f}{e['decisive_share']:>7.3f}"
          f"{e['win_rate_no_skill_pct']:>9.1f}%{e['win_rate_needed_pct']:>8.1f}%"
          f"{e['gap_pp']:>7.1f}pp{e['one_over_tp_plus_sl_pp']:>9.1f}pp"
          f"{e['cost_over_move']:>9.3f}")

print(f"\n\nDecisive share D by timeout, tp={args.tp:g} sl={args.sl:g}\n")
print(f"{'market':22}" + "".join(f"{t:>8}" for t in TIMEOUTS))
for m in inp["in_scope"]:
    v, s = mk[m]["v_bps_per_min"], mk[m]["s_bps"]
    row = {t: evaluate(v, s, args.tp, args.sl, t) for t in TIMEOUTS}
    out["by_timeout"][m] = {str(t): e for t, e in row.items()}
    print(f"{m:22}" + "".join(f"{row[t]['decisive_share']:>8.3f}" for t in TIMEOUTS))

m = "COINCHECK:BTC_SPOT"
v, s = mk[m]["v_bps_per_min"], mk[m]["s_bps"]
print(f"\n\n{m}   v={v:.2f} bps/min  s={s:.3f} bps  v/s={v/s:.2f}\n")
steps = []
for label, tp, sl, t in LADDER:
    e = evaluate(v, s, tp, sl, t)
    e["label"] = label
    steps.append(e)
    print(f"{label:20}{tp:>4}{sl:>4}{t:>6}  D {e['decisive_share']:.3f}  "
          f"no skill {e['win_rate_no_skill_pct']:5.1f}%  needed {e['win_rate_needed_pct']:5.1f}%  "
          f"gap {e['gap_pp']:5.1f}pp  1/(tp+sl) {e['one_over_tp_plus_sl_pp']:5.1f}pp")
out["ladder"] = {"market": m, "v": v, "s": s, "steps": steps}

base = oracle_baseline()
out["oracle_random_walk"] = base
print(f"\n\nOracle on a driftless walk, in units of t_s = (s/v)^2:  "
      f"mean {base['mean_over_ts']:.3f}  median {base['median_over_ts']:.3f}  "
      f"p90 {base['p90_over_ts']:.3f}  (reached within {base['horizon_ts']} t_s: "
      f"{base['reached_share']:.2%})")

name = "feasibility.json" if std == (3.0, 1.0, 30.0) else "feasibility_custom.json"
dest = here / "output" / name
dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print("\nwrote", dest)
