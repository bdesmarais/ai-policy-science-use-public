#!/usr/bin/env python3
"""make_refresh_figure.py — figure for the refreshed (last-12-month) application."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
C = json.load(open(os.path.join(BASE, "benchmarks", "results", "fresh_corroboration.json")))
DET = json.load(open(os.path.join(BASE, "outputs", "refresh", "ai_detection.json")))["engagement"]
OUT = os.path.join(BASE, "paper", "figures", "fig_refresh.png")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

# (a) fresh engagement: AI-related releases by party
parties = ["Democratic", "Republican"]
ai = [DET.get("dem", {}).get("ai", 0), DET.get("rep", {}).get("ai", 0)]
tot = [DET.get("dem", {}).get("total", 0), DET.get("rep", {}).get("total", 0)]
rate = [DET.get("dem", {}).get("ai_rate", 0) or 0, DET.get("rep", {}).get("ai_rate", 0) or 0]
bars = ax1.bar(parties, [r * 100 for r in rate], color=["#2166ac", "#b2182b"], width=0.55)
for b, a, t in zip(bars, ai, tot):
    ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.05,
             f"{a}/{t}\n({b.get_height():.1f}%)", ha="center", va="bottom", fontsize=9)
ax1.set_ylabel("AI-related releases (% of window)")
ax1.set_ylim(0, max([r*100 for r in rate] + [1]) * 1.5)
ax1.set_title("(a) AI engagement, last 12 months (to Jun 2026)")

# (b) fresh corroboration (validated judge, Crossref retrieval)
labels = ["end-to-end\n(44 claims)", "ceiling: perfect\nretrieval (37)"]
vals = [C["corroboration_raw"], C["corroboration_excl_miss"]]
lo = [C["wilson_raw"][0], None]
hi = [C["wilson_raw"][1], None]
bars = ax2.bar(labels, vals, color=["#c0392b", "#cccccc"], width=0.5,
               hatch=["", "//"], edgecolor=["#c0392b", "#888888"])
ax2.errorbar(0, vals[0], yerr=[[vals[0]-C["wilson_raw"][0]], [C["wilson_raw"][1]-vals[0]]],
             fmt="none", ecolor="k", capsize=5)
for b, v, w in zip(bars, vals, ["bold", "normal"]):
    ax2.text(b.get_x() + b.get_width()/2, v + 0.02, f"{v:.2f}", ha="center", va="bottom",
             fontsize=11, fontweight=w)
ax2.axhline(0.71, ls="--", color="#888", lw=1)
ax2.text(1.45, 0.715, "historical 0.71", fontsize=8, color="#666", ha="right")
ax2.set_ylim(0, 1.0); ax2.set_ylabel("claim-corroboration rate")
ax2.set_title("(b) End-to-end corroboration on fresh claims")

fig.suptitle("Refreshed application: model-guided pipeline, no second paid service, last 12 months",
             fontsize=11, y=1.02)
fig.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote", OUT)
