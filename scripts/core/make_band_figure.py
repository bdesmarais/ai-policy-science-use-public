#!/usr/bin/env python3
"""make_band_figure.py — the judge sits within/above the human-agreement BAND across the
curated->retrieved->real-world spectrum of benchmark pair structures. This is the empirical
core of the no-human-coder defense: on the benchmarks whose pair structure matches the noisy
application (Climate-FEVER, AVeriTeC), the judge agrees with the human gold MORE than the
human coders agree with each other."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(BASE, "paper", "figures", "fig_band.png")

# (benchmark, pair structure, judge kappa, human agreement, human label)
data = [
    ("SciFact",        "curated\n(cited abstracts)",       0.71, 0.75, r"$\kappa$=0.75"),
    ("Climate-FEVER",  "retrieved sentences\n(contested, lay)", 0.67, 0.33, r"$\alpha$=0.33"),
    ("AVeriTeC",       "web-retrieved\n(real-world claims)", 0.75, 0.62, r"$\kappa$=0.62"),
]
fig, ax = plt.subplots(figsize=(9, 4.6))
x = range(len(data)); w = 0.38
judge = [d[2] for d in data]; human = [d[3] for d in data]
b1 = ax.bar([i - w/2 for i in x], judge, w, label="judge vs human gold", color="#c0392b")
b2 = ax.bar([i + w/2 for i in x], human, w, label="human inter-annotator agreement", color="#5b6770")
for i, d in enumerate(data):
    ax.text(i - w/2, d[2] + 0.015, f"{d[2]:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.text(i + w/2, d[3] + 0.015, d[4], ha="center", va="bottom", fontsize=9, color="#444")
ax.set_xticks(list(x))
ax.set_xticklabels([f"{d[0]}\n{d[1]}" for d in data], fontsize=9)
ax.set_ylabel("chance-corrected agreement")
ax.set_ylim(0, 0.9)
ax.set_title("The judge is within or above the human-agreement band---and exceeds it\n"
             "on the retrieved-evidence benchmarks whose pair structure matches the application",
             fontsize=10.5)
ax.legend(loc="upper right", fontsize=9)
ax.annotate("application-like\n(retrieved, noisy)", xy=(1.5, 0.05), fontsize=8.5, color="#7a3a3a",
            ha="center")
ax.axvspan(0.5, 2.5, color="#f3e6e6", alpha=0.5, zorder=0)
fig.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote", OUT)
