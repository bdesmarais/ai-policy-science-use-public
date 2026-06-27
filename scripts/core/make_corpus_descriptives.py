#!/usr/bin/env python3
"""Descriptive distributions of the AI corpus (for the application section).

Three panels: (a) empirical claims per release, (b) topic distribution of the
empirical AI claims, (c) AI claims over time. Reads the committed retrieved-pairs
file so it regenerates from data.
"""
import collections
import json
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TOPICS = [
    ("Algorithmic decisions & bias",
     ["algorithm", "automated decision", "adt", "ads ", "bias", "discriminat",
      "price-fix", "price fixing", "profiling", "credit", "lending", "housing"]),
    ("Chatbots & child safety",
     ["chatbot", "companion", "minor", "child", "kid"]),
    ("Data centers & energy",
     ["data center", "data-center", "energy", "electricity", "grid", "emission",
      "carbon", "waste heat", "power"]),
    ("Deepfakes & synthetic media",
     ["deepfake", "synthetic", "likeness", "image-based", "voice", "csam"]),
    ("Privacy & surveillance",
     ["surveillance", "facial", "biometric", "privacy", "personal information",
      "foreign government", "data broker"]),
    ("Misinformation & democracy",
     ["misinformation", "disinformation", "conspiracy", "election", "democracy",
      "extremis", "social media", "riot"]),
    ("Health & medicine",
     ["health", "patient", "medic", "clinical", "insurance", "diagnos", "therap"]),
    ("Labor & workforce",
     ["worker", "wage", "employ", "labor", "job", "workforce", "automation"]),
]


def categorize(text):
    t = text.lower()
    for name, kws in TOPICS:
        if any(w in t for w in kws):
            return name
    return "Other"


def main():
    d = json.load(open(os.path.join(ROOT, "outputs/ai_corpus/retrieved_pairs.json")))
    emp = [c for c in d if c.get("is_empirical")]

    # (a) claims per release
    per = collections.Counter(c["press_release"] for c in d)
    counts = list(per.values())

    # (b) topics
    tc = collections.Counter(categorize(c["claim_text"]) for c in emp)
    order = [n for n, _ in TOPICS] + ["Other"]
    tnames = [n for n in order if tc.get(n, 0) > 0]
    tvals = [tc[n] for n in tnames]

    # (c) over time (dated releases)
    years = collections.Counter()
    for c in d:
        m = re.match(r"^(\d{4})\d{4}", str(c.get("press_release", "")))
        if m:
            years[int(m.group(1))] += 1
    yrs = sorted(years)

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))

    ax = axes[0]
    ax.hist(counts, bins=range(1, 12), align="left", color="#2c5fa8", rwidth=0.85)
    ax.set_xlabel("Empirical claims per release")
    ax.set_ylabel("Releases")
    ax.set_title("(a) Claim yield per release", fontsize=11)
    ax.set_xticks(range(1, 11))
    ax.spines[["top", "right"]].set_visible(False)

    ax = axes[1]
    yp = range(len(tnames))[::-1]
    ax.barh(list(yp), tvals, color="#34495e")
    ax.set_yticks(list(yp))
    ax.set_yticklabels(tnames, fontsize=9)
    ax.set_xlabel("Empirical AI claims")
    ax.set_title("(b) What the AI claims are about", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)

    ax = axes[2]
    ax.bar([str(y) for y in yrs], [years[y] for y in yrs], color="#2c5fa8")
    ax.set_xlabel("Year")
    ax.set_ylabel("AI claims (dated releases)")
    ax.set_title("(c) AI attention over time", fontsize=11)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    out = os.path.join(ROOT, "paper/figures/fig_corpus_descriptives.png")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print("wrote", out)
    print("claims/release mean", round(sum(counts) / len(counts), 2), "max", max(counts),
          "| releases", len(per), "| empirical", len(emp), "of", len(d))
    print("topics:", dict(zip(tnames, tvals)))
    print("years:", {y: years[y] for y in yrs})


if __name__ == "__main__":
    main()
