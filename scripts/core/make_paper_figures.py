#!/usr/bin/env python3
"""Generate the paper figures into paper/figures/ from the committed outputs.
Reads outputs/stance/validation_report.json for agreement + support rates; corpus and
education numbers are from the v3 EDA and the education pilot analysis (stable).
Run: python3 scripts/core/make_paper_figures.py"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIG = os.path.join(BASE, "paper", "figures")
os.makedirs(FIG, exist_ok=True)
rep = json.load(open(os.path.join(BASE, "outputs", "stance", "validation_report.json")))
DEM, REP = "#2166AC", "#B2182B"

# (a) AI engagement by party
fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
ax[0].bar(["Democratic", "Republican"], [0.0484, 0.0259], color=[DEM, REP], edgecolor="black")
ax[0].set_ylabel("Share of press releases mentioning AI"); ax[0].set_title("(a) Engagement with AI")
for i, v in enumerate([0.0484, 0.0259]):
    ax[0].text(i, v + 0.001, f"{v:.1%}", ha="center", fontweight="bold")
ax[1].bar(["Democratic", "Republican"], [3.276, 1.592], color=[DEM, REP], edgecolor="black")
ax[1].set_ylabel("Avg. AI statements per AI document"); ax[1].set_title("(b) Intensity")
for i, v in enumerate([3.276, 1.592]):
    ax[1].text(i, v + 0.05, f"{v:.2f}", ha="center", fontweight="bold")
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_ai_engagement.png"), dpi=200); plt.close()

# (b) cross-validator agreement (Cohen's kappa)
ag = rep["pairwise_agreement"]
order = [("claude_judge~nli_deberta", "Claude vs\nDeBERTa-NLI"),
         ("claude_judge~nli_bart", "Claude vs\nBART-NLI"),
         ("nli_deberta~nli_bart", "DeBERTa-NLI vs\nBART-NLI")]
ks = [ag[k]["cohens_kappa"] for k, _ in order if k in ag]
labs = [lab for k, lab in order if k in ag]
cols = ["#999999", "#999999", "#16a766"][:len(ks)]
fig, ax = plt.subplots(figsize=(6.4, 3.8))
ax.bar(labs, ks, color=cols, edgecolor="black")
for i, v in enumerate(ks):
    ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontweight="bold")
ax.axhline(0.4, ls="--", c="gray", lw=1); ax.text(len(ks)-0.5, 0.42, "moderate", color="gray", fontsize=8)
ax.set_ylabel("Cohen's $\\kappa$"); ax.set_ylim(0, 1)
ax.set_title("Cross-validator agreement: generative judge vs.\ndiscriminative NLI under-detect each other")
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_agreement.png"), dpi=200); plt.close()

# (c) support rate by party: naive NLI vs PPI-debiased (Claude gold)
sr = rep["support_rate_by_party_ppi"]
parties = [p for p in ("dem", "rep") if p in sr]
naive = [sr[p]["naive_estimate"] for p in parties]
ppi = [sr[p]["estimate"] for p in parties]
err = [[sr[p]["estimate"] - sr[p]["ci95"][0] for p in parties],
       [sr[p]["ci95"][1] - sr[p]["estimate"] for p in parties]]
x = np.arange(len(parties)); w = 0.35
fig, ax = plt.subplots(figsize=(6.4, 4))
ax.bar(x - w/2, naive, w, label="Naive NLI surrogate", color="#cccccc", edgecolor="black")
ax.bar(x + w/2, ppi, w, yerr=err, capsize=6, label="PPI-debiased (Claude gold)",
       color=[DEM, REP][:len(parties)], edgecolor="black")
ax.set_xticks(x); ax.set_xticklabels(["Democratic", "Republican"][:len(parties)])
ax.set_ylabel("Share of claims supported by retrieved science"); ax.set_ylim(0, 1)
ax.set_title("Estimated support rate: naive NLI vs. PPI-debiased")
for i, v in enumerate(naive): ax.text(x[i]-w/2, v+0.02, f"{v:.2f}", ha="center", fontsize=9)
for i, v in enumerate(ppi): ax.text(x[i]+w/2, v+err[1][i]+0.02, f"{v:.2f}", ha="center", fontsize=9, fontweight="bold")
ax.legend(loc="upper right", fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_support_rate.png"), dpi=200); plt.close()

# (d) education partisan asymmetry
topics = ["SEL / mental\nhealth", "School\nsafety", "Reading /\ncurriculum"]
demv, repv = [80, 38, 26], [1, 4, 7]
x = np.arange(len(topics)); w = 0.35
fig, ax = plt.subplots(figsize=(6.4, 3.8))
ax.bar(x - w/2, demv, w, label="Democratic", color=DEM, edgecolor="black")
ax.bar(x + w/2, repv, w, label="Republican", color=REP, edgecolor="black")
ax.set_xticks(x); ax.set_xticklabels(topics); ax.set_ylabel("Number of press releases")
ax.set_title("Education pilot: partisan asymmetry in topic attention")
ax.legend()
for i, v in enumerate(demv): ax.text(x[i]-w/2, v+0.5, str(v), ha="center", fontsize=9)
for i, v in enumerate(repv): ax.text(x[i]+w/2, v+0.5, str(v), ha="center", fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_education.png"), dpi=200); plt.close()

print("wrote figures to", FIG)
for f in sorted(os.listdir(FIG)):
    print("  ", f)
