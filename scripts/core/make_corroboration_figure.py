#!/usr/bin/env python3
"""Corroboration-by-party figure for the widened application.

Reads benchmarks/results/historical_corroboration.json and plots the model-guided
corroboration rate (validated judge) over the full AI corpus, by party and overall,
with Wilson 95% intervals, plus the current twelve-month-window replication.
"""
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main():
    d = json.load(open(os.path.join(ROOT, "benchmarks/results/historical_corroboration.json")))
    rows = [
        ("Overall\n(full corpus)", d["overall"]["support"], d["overall"]["n"], "#34495e"),
        ("Democratic", d["dem"]["support"], d["dem"]["n"], "#2c5fa8"),
        ("Republican", d["rep"]["support"], d["rep"]["n"], "#b03a2e"),
        ("Current window\n(replication)", 25, 44, "#7f8c8d"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ys = range(len(rows))[::-1]
    for y, (label, k, n, color) in zip(ys, rows):
        p, lo, hi = wilson(k, n)
        ax.errorbar(p, y, xerr=[[p - lo], [hi - p]], fmt="o", color=color,
                    capsize=4, markersize=8, lw=2)
        ax.text(hi + 0.02, y, f"{p:.2f}  ($n={n}$)", va="center", fontsize=10)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Corroboration rate (validated judge; retrieval misses counted as non-corroboration)",
                  fontsize=10)
    ax.axvline(0.5, color="0.85", lw=1, zorder=0)
    ax.set_title("Model-guided corroboration of legislators' AI claims, by party", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = os.path.join(ROOT, "paper/figures/fig_corroboration.png")
    fig.savefig(out, dpi=200)
    print("wrote", out)


if __name__ == "__main__":
    main()
