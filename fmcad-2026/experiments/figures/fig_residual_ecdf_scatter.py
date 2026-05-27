#!/usr/bin/env python3
"""fig_residual_ecdf_scatter.py — two chart types on the residual sweep.

Two-panel figure for the paper's §VI experimental evidence:

  Left panel: ECDF of T_emp - T_analytic over every cell in the
              1200-row B/D residual sweep. Vertical line at zero.
              The closer this curve is to a step at 0, the tighter
              the sandwich bound.

  Right panel: Scatter of T_analytic vs T_emp, one dot per cell.
               y = x line overlaid. A perfectly tight bound puts
               every point on y = x; systematic bias shows as a
               shifted cloud.

Voice: grayscale, thin lines, no colour. Matches Ferreira-Sherry
IMC/SIGCOMM figure style.

Build:
  python3 experiments/figures/fig_residual_ecdf_scatter.py \
    --input experiments/runs/b_d_grid_quiet_large.csv \
    --out figures/fig_residual_ecdf_scatter.pdf
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="experiments/runs/b_d_grid_quiet_large.csv")
    ap.add_argument("--out",   default="figures/fig_residual_ecdf_scatter.pdf")
    args = ap.parse_args()

    src = pathlib.Path(args.input)
    if not src.exists():
        print(f"[fig_residual_ecdf_scatter] missing {src}", file=sys.stderr)
        return 2

    rows = list(csv.DictReader(src.open()))
    residuals = []
    analytics = []
    empiricals = []
    for r in rows:
        if r.get("reason") != "starvation_detected":
            continue
        try:
            T_ana = float(r["T_analytic_rtt"])
            T_emp = float(r["T_emp_rtt"])
            res = float(r["residual_rtt"])
        except (TypeError, ValueError, KeyError):
            continue
        residuals.append(res)
        analytics.append(T_ana)
        empiricals.append(T_emp)

    if not residuals:
        print(f"[fig_residual_ecdf_scatter] no starvation_detected rows", file=sys.stderr)
        return 2

    print(f"[fig_residual_ecdf_scatter] n_cells = {len(residuals)}")
    residuals_sorted = sorted(residuals)
    mean_r = sum(residuals) / len(residuals)
    median_r = residuals_sorted[len(residuals_sorted) // 2]
    p05 = residuals_sorted[max(0, len(residuals_sorted) * 5 // 100 - 1)]
    p95 = residuals_sorted[min(len(residuals_sorted) - 1,
                                len(residuals_sorted) * 95 // 100)]
    print(f"  mean={mean_r:.2f}  median={median_r:.2f}  p05={p05:.2f}  p95={p95:.2f}")

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[fig_residual_ecdf_scatter] matplotlib missing", file=sys.stderr)
        return 2

    fig, (ax_ecdf, ax_scatter) = plt.subplots(
        1, 2, figsize=(7.2, 2.8), gridspec_kw={"wspace": 0.35}
    )

    # ── Left panel: ECDF ────────────────────────────────────────────
    import numpy as np
    x = np.array(sorted(residuals))
    y = np.arange(1, len(x) + 1) / len(x)
    ax_ecdf.plot(x, y, color="black", linewidth=1.2)
    ax_ecdf.axvline(0, color="0.5", linewidth=0.6, linestyle="--")
    ax_ecdf.axvline(median_r, color="0.3", linewidth=0.6, linestyle=":")
    # Per Aidan 2026-04-19: median label is plain text on the LEFT of
    # the vertical, no arrow. ha="right" aligns the text so it ends
    # just before the vertical line, clear of both the y-axis label
    # ("empirical CDF") and the dotted median line.
    dx_left = (max(residuals) - min(residuals)) * 0.04
    ax_ecdf.text(median_r - dx_left, 0.50, f"median $= {median_r:.1f}$",
                 fontsize=7, ha="right", va="center", color="0.2")
    ax_ecdf.set_xlabel(r"residual $T_{\mathrm{emp}} - T_{\mathrm{analytic}}$ (RTT)")
    ax_ecdf.set_ylabel("empirical CDF")
    ax_ecdf.set_ylim(0, 1.02)
    ax_ecdf.set_title("(a) ECDF of residuals", fontsize=9)
    ax_ecdf.spines["top"].set_visible(False)
    ax_ecdf.spines["right"].set_visible(False)
    ax_ecdf.grid(axis="y", linestyle=":", alpha=0.4)

    # ── Right panel: scatter with y = x line + sandwich band ────────
    ax_scatter.scatter(analytics, empiricals, s=6,
                       color="black", alpha=0.35, linewidths=0)
    lo = min(min(analytics), min(empiricals))
    hi = max(max(analytics), max(empiricals))
    xs = np.linspace(lo, hi, 100)
    ax_scatter.plot(xs, xs, color="0.5", linewidth=0.8, linestyle="--",
                    label=r"$y = x$ (tight bound)")
    # Sandwich band: y within +- p95 of x.
    band = max(abs(p05), abs(p95))
    ax_scatter.fill_between(xs, xs - band, xs + band,
                            color="0.85", alpha=0.4,
                            label=f"sandwich band ($\\pm{band:.0f}$ RTT)")
    ax_scatter.set_xlabel(r"analytic $T(B, D)$ (RTT)")
    ax_scatter.set_ylabel(r"empirical $T_{\mathrm{emp}}$ (RTT)")
    ax_scatter.set_xlim(lo - 2, hi + 2)
    ax_scatter.set_ylim(lo - 2, hi + 2)
    ax_scatter.set_title("(b) empirical vs analytic onset",
                          fontsize=9)
    ax_scatter.legend(loc="upper left", frameon=False, fontsize=7)
    ax_scatter.spines["top"].set_visible(False)
    ax_scatter.spines["right"].set_visible(False)
    ax_scatter.grid(linestyle=":", alpha=0.4)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"[fig_residual_ecdf_scatter] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
