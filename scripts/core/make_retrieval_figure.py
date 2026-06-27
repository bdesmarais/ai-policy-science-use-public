#!/usr/bin/env python3
"""make_retrieval_figure.py — figure for the Claude-as-retriever experiment.
Two panels: (a) relevance yield + correct-abstention by arm; (b) DOI/verifiability by arm."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = json.load(open(os.path.join(BASE, "benchmarks", "results", "retrieval_experiment.json")))
OUT = os.path.join(BASE, "paper", "figures", "fig_retrieval.png")

ry = R["relevance_yield_empirical"]
ab = R["abstention_nonempirical"]
doi = R["doi_rate"]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

# Panel a: relevance yield (empirical) and correct abstention (non-empirical)
groups = ["Relevance yield\n(30 empirical claims)", "Correct abstention\n(20 non-empirical claims)"]
naive_vals = [ry["naive"], (ab["n_nonempirical"] - ab["naive_returned_refs_for"]) / ab["n_nonempirical"]]
claude_vals = [ry["claude"], ab["claude_abstained_on"] / ab["n_nonempirical"]]
x = range(len(groups)); w = 0.36
b1 = ax1.bar([i - w/2 for i in x], naive_vals, w, label="Naive keyword", color="#b0b0b0")
b2 = ax1.bar([i + w/2 for i in x], claude_vals, w, label="Claude-guided", color="#c0392b")
for b in list(b1) + list(b2):
    ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.02, f"{b.get_height():.2f}",
             ha="center", va="bottom", fontsize=10)
ax1.set_xticks(list(x)); ax1.set_xticklabels(groups, fontsize=9)
ax1.set_ylim(0, 1.12); ax1.set_ylabel("rate"); ax1.set_title("(a) Claim-targeted retrieval and abstention")
ax1.legend(loc="upper center", fontsize=9, framealpha=0.9)
ax1.axhline(0, color="k", lw=0.6)

# Panel b: DOI / verifiability rate
labels = ["Naive\nOpenAlex", "Claude\nOpenAlex", "GPT-5\ngenerative"]
vals = [doi["naive_openalex"], doi["claude_openalex"], 0.31]  # 0.31 = midpoint of reported 0.27-0.35
colors = ["#b0b0b0", "#c0392b", "#5b6770"]
bars = ax2.bar(labels, vals, color=colors, width=0.6)
ax2.errorbar(2, 0.31, yerr=[[0.04], [0.04]], fmt="none", ecolor="k", capsize=4)
for b, v in zip(bars, vals):
    ax2.text(b.get_x() + b.get_width()/2, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=10)
ax2.set_ylim(0, 1.05); ax2.set_ylabel("fraction of references with a DOI")
ax2.set_title("(b) Verifiability of retrieved references")

fig.suptitle("A single frontier model can do the retrieval: claim-targeted, abstaining, and fully verifiable",
             fontsize=11, y=1.02)
fig.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote", OUT)
