"""Compare the same calendar month one year apart in Makalu's lead-lag report.

Makalu's report computes one plain cross-correlation curve per JST day from
Hase MarketPrice at a fixed execution size.  This script turns its exported
daily.csv files into the compact table and two static figures used here.  It
does not read Makalu's EWLL feature dataset; that is a separate implementation.

Run after building the three Makalu reports, for example:

    python3 report_analysis.py --source /path/to/makalu/site/leadlag

Reproduces: 「同じ 8 月を、1 年離して比べる」 through
「変わったのは、先行の強さだった」 and their two figures.
Writes output/report_summary.json, output/leadlag_curve.png and
output/leadlag_daily.png.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PERIODS = {
    "2025-08": ("2025-08-01", "2025-08-31"),
    "2026-08": ("2026-08-01", "2026-08-31"),
}
PAIRS = {
    "BTC": "BINANCE_BTC_USDT__GMO_BTC_JPY",
    "ETH": "BINANCE_ETH_USDT__GMO_ETH_JPY",
    "XRP": "BINANCE_XRP_USDT__GMO_XRP_JPY",
}
LAGS = list(range(-500, 2001, 100))
COLORS = {"BTC": "#199e70", "ETH": "#3987e5", "XRP": "#d95926"}
MEASUREMENT = {
    "grid_ms": 100,
    "peak_search_lag_ms": [-1000, 3000],
    "curve_lag_ms": [-500, 2000],
    "market_price_max_spread_bps": 100,
    "periods": PERIODS,
    "comparison_design": "same calendar month, one year apart",
}


def curve_column(lag: int) -> str:
    return f"rho_lag_m{-lag}" if lag < 0 else f"rho_lag_{lag}"


def rounded(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def summarise(frame: pd.DataFrame) -> dict:
    lag = frame["peak_lag_ms"]
    median_curve = {value: frame[curve_column(value)].median() for value in LAGS}
    curve_peak = max(median_curve, key=median_curve.get)
    return {
        "days": len(frame),
        "first_date": frame["date"].min(),
        "last_date": frame["date"].max(),
        "peak_lag_ms_median": int(lag.median()),
        "median_curve_peak_lag_ms": curve_peak,
        "median_curve_peak_rho": rounded(median_curve[curve_peak]),
        "peak_lag_ms_counts": {
            str(int(value)): int(count)
            for value, count in lag.value_counts().sort_index().items()
        },
        "pct_days_positive": rounded((lag > 0).mean() * 100, 1),
        "pct_days_400_to_1000ms": rounded(lag.between(400, 1000).mean() * 100, 1),
        "peak_rho_100ms_median": rounded(frame["peak_rho"].median()),
        "rho_zero_100ms_median": rounded(frame["rho0"].median()),
        "rho_same_1s_median": rounded(frame["rho0_1s"].median()),
        "rho_next_1s_median": rounded(frame["rho1_1s"].median()),
        "rho_same_5s_median": rounded(frame["rho0_5s"].median()),
        "rho_next_5s_median": rounded(frame["rho1_5s"].median()),
    }


def change(first: dict, second: dict) -> dict:
    def pct(field: str) -> float:
        return rounded((second[field] / first[field] - 1) * 100, 1)

    return {
        "daily_peak_lag_ms_median_delta": second["peak_lag_ms_median"]
        - first["peak_lag_ms_median"],
        "median_curve_peak_lag_ms_delta": second["median_curve_peak_lag_ms"]
        - first["median_curve_peak_lag_ms"],
        "peak_rho_100ms_pct_change": pct("peak_rho_100ms_median"),
        "rho_next_1s_pct_change": pct("rho_next_1s_median"),
    }


def style(axis) -> None:
    axis.set_facecolor("#fbfaf7")
    axis.grid(color="#dddcd5", linewidth=0.7, alpha=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.tick_params(colors="#5f5e59", labelsize=9)


def draw_curve(frames: dict[str, dict[str, pd.DataFrame]], output: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), sharey=True, facecolor="#fbfaf7")
    styles = {"2025-08": "-", "2026-08": "--"}
    for ax, asset in zip(axes, PAIRS, strict=True):
        style(ax)
        for label, frame in frames[asset].items():
            values = [frame[curve_column(lag)].median() for lag in LAGS]
            ax.plot(
                LAGS,
                values,
                label=label,
                color=COLORS[asset],
                linestyle=styles[label],
                linewidth=2.2,
                alpha=1.0 if label == "2025-08" else 0.72,
            )
        ax.axvline(0, color="#898781", linestyle=":", linewidth=1)
        ax.set_title(asset)
        ax.set_xlabel("Binance lead (ms)")
    axes[0].set_ylabel("Median daily 100 ms return correlation")
    axes[-1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_daily(frames: dict[str, dict[str, pd.DataFrame]], output: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(9, 7.2), sharex=True, facecolor="#fbfaf7")
    offsets = {"2025-08": -0.12, "2026-08": 0.12}
    markers = {"2025-08": "o", "2026-08": "s"}
    legend_labels = {"2025-08": "2025-08 (circle)", "2026-08": "2026-08 (square)"}
    for ax, asset in zip(axes, PAIRS, strict=True):
        style(ax)
        for label, frame in frames[asset].items():
            days = pd.to_datetime(frame["date"]).dt.day + offsets[label]
            ax.scatter(
                days,
                frame["peak_lag_ms"],
                label=legend_labels[label],
                marker=markers[label],
                color=COLORS[asset],
                facecolors="none" if label == "2025-08" else COLORS[asset],
                s=24,
                alpha=0.72,
            )
        ax.axhspan(400, 1000, color=COLORS[asset], alpha=0.07)
        ax.set_ylabel(f"{asset}\nlag (ms)")
        ax.set_ylim(300, 900)
    axes[0].legend(frameon=False, ncol=2)
    axes[-1].set_xlabel("Day of August")
    axes[-1].set_xticks([1, 5, 10, 15, 20, 25, 31])
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", type=Path, required=True, help="Makalu site's leadlag directory"
    )
    args = parser.parse_args()
    output = Path(__file__).parent / "output"
    output.mkdir(exist_ok=True)

    frames, result = {}, {"measurement": MEASUREMENT, "pairs": {}}
    generated = set()
    for asset, key in PAIRS.items():
        directory = args.source / key
        meta = json.loads((directory / "report.json").read_text())
        generated.add(meta["generated_at"])
        frame = pd.read_csv(directory / "daily.csv")
        frames[asset] = {
            label: frame[frame["date"].between(start, end)].reset_index(drop=True)
            for label, (start, end) in PERIODS.items()
        }
        for label, part in frames[asset].items():
            if len(part) != 31:
                raise ValueError(
                    f"{asset} {label}: expected 31 daily rows, found {len(part)}"
                )
        summaries = {label: summarise(part) for label, part in frames[asset].items()}
        result["pairs"][asset] = {
            "lead": meta["lead"],
            "lag": meta["lag"],
            "execution_size": meta["execution_size"],
            "periods": summaries,
            "change_2025_to_2026": change(summaries["2025-08"], summaries["2026-08"]),
        }
    result["report_generated_at"] = sorted(generated)

    (output / "report_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    draw_curve(frames, output / "leadlag_curve.png")
    draw_daily(frames, output / "leadlag_daily.png")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
