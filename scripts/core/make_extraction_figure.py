#!/usr/bin/env python3
"""make_extraction_figure.py — figure for extraction validation:
(a) check-worthiness F1 vs human ClaimBuster labels by validator (vs SOTA ceiling);
(b) faithfulness/grounding rate by party + extraction yield neutrality."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CW = json.load(open(os.path.join(BASE, "benchmarks", "results", "extraction_checkworthiness.json")))
FA = json.load(open(os.path.join(BASE, "benchmarks", "results", "extraction_faithfulness.json")))
PN = json.load(open(os.path.join(BASE, "benchmarks", "results", "extraction_party_neutrality.json")))
OUT = os.path.join(BASE, "paper", "figures", "fig_extraction.png")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.3))

# (a) check-worthiness F1 by validator
order = [("claude_opus_4.8", "Claude 4.8\n(extractor)", "#c0392b"),
         ("microsoft/Phi-3.5-mini-instruct", "Phi-3.5", "#2166ac"),
         ("allenai/OLMo-2-1124-7B-Instruct", "OLMo-2", "#2166ac"),
         ("Qwen/Qwen2.5-3B-Instruct", "Qwen2.5", "#2166ac"),
         ("tfidf_lexical", "TF-IDF\nfloor", "#999999")]
names, f1s, cols = [], [], []
for k, lbl, c in order:
    v = CW["validators"].get(k, {})
    if "f1" in v:
        names.append(lbl); f1s.append(v["f1"]); cols.append(c)
bars = ax1.bar(names, f1s, color=cols, width=0.62)
for b, v in zip(bars, f1s):
    ax1.text(b.get_x()+b.get_width()/2, v+0.012, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
ax1.axhspan(0.69, 0.71, color="#7fbf7b", alpha=0.35)
ax1.text(len(names)-1, 0.705, "CheckThat! SOTA ~0.70", fontsize=8, color="#3a7d3a", ha="right", va="bottom")
ax1.set_ylim(0, 0.9); ax1.set_ylabel("F1 vs human check-worthiness")
ax1.set_title("(a) Extractor identifies check-worthy claims\nat the published state of the art")

# (b) faithfulness grounding by party + yield
parties = ["Democratic", "Republican"]
gr = [FA["by_party"].get("dem", {}).get("grounding_rate", 0),
      FA["by_party"].get("rep", {}).get("grounding_rate", 0)]
yld = [PN["dem"]["claims_per_release"], PN["rep"]["claims_per_release"]]
x = range(len(parties)); w = 0.36
b1 = ax2.bar([i-w/2 for i in x], gr, w, label="claim grounded in source", color="#5b8c5a")
ax2b = ax2.twinx()
b2 = ax2b.bar([i+w/2 for i in x], yld, w, label="claims / release (yield)", color="#d4a13a")
for b, v in zip(b1, gr):
    ax2.text(b.get_x()+b.get_width()/2, v+0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
for b, v in zip(b2, yld):
    ax2b.text(b.get_x()+b.get_width()/2, v+0.1, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
ax2.set_xticks(list(x)); ax2.set_xticklabels(parties)
ax2.set_ylim(0, 1.1); ax2.set_ylabel("faithfulness (grounding rate)")
ax2b.set_ylim(0, 10); ax2b.set_ylabel("claims per release")
ax2.set_title("(b) Faithful to source, and party-neutral in yield")
ax2.legend(loc="upper left", fontsize=8); ax2b.legend(loc="upper right", fontsize=8)

fig.suptitle("Validating claim extraction without human coders: check-worthiness, faithfulness, yield neutrality",
             fontsize=10.5, y=1.02)
fig.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches="tight")
print("wrote", OUT)
