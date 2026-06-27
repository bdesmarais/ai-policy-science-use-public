#!/usr/bin/env python3
"""Generate the figures for the rebuilt (validated-pipeline) paper from result JSONs."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(BASE, "benchmarks", "results")
STANCE = os.path.join(BASE, "outputs", "stance")
FIG = os.path.join(BASE, "paper", "figures")
os.makedirs(FIG, exist_ok=True)

LABELS = {"claude": "Claude Opus 4.8\n(judge)", "nli_deberta": "NLI\nDeBERTa", "nli_bart": "NLI\nBART",
          "tfidf": "TF-IDF\n(baseline)", "llm:Qwen/Qwen2.5-3B-Instruct": "Qwen2.5\n3B",
          "llm:microsoft/Phi-3.5-mini-instruct": "Phi-3.5\nmini", "llm:allenai/OLMo-2-1124-7B-Instruct": "OLMo-2\n7B"}
ORDER = ["claude", "llm:Qwen/Qwen2.5-3B-Instruct", "llm:microsoft/Phi-3.5-mini-instruct",
         "llm:allenai/OLMo-2-1124-7B-Instruct", "nli_deberta", "nli_bart", "tfidf"]


def load(*names):
    for n in names:
        p = os.path.join(RES, n)
        if os.path.exists(p):
            yield json.load(open(p))


def merge_validators(*reports):
    out = {}
    for r in reports:
        out.update(r.get("validators", {}))
    return out


def fig_validation():
    """Same-pairs accuracy with Wilson 95% CIs (the comparable evaluation): each validator on the
    EXACT pairs the proprietary judge labelled (SciFact n=66, Climate-FEVER n=45). Shows judge~NLI
    indistinguishable on clean SciFact, judge clearly ahead on hard Climate-FEVER."""
    # (label, acc, lo, hi); proprietary judge first, then open validators, then floor
    SCI = [("Claude\n(proprietary)", .80, .69, .88), ("NLI\nDeBERTa", .76, .64, .84),
           ("NLI\nBART", .74, .63, .83), ("Qwen2.5\n3B", .70, .58, .79),
           ("Phi-3.5\nmini", .53, .41, .65), ("OLMo-2\n7B", .53, .41, .65), ("TF-IDF", .44, .33, .56)]
    CF = [("Claude\n(proprietary)", .78, .64, .87), ("NLI\nDeBERTa", .49, .35, .63),
          ("NLI\nBART", .51, .37, .65), ("Qwen2.5\n3B", .56, .41, .69),
          ("Phi-3.5\nmini", .67, .52, .79), ("OLMo-2\n7B", .51, .37, .65), ("TF-IDF", .42, .29, .57)]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, data, title in [(axes[0], SCI, "SciFact (expert claims, $n{=}66$)"),
                            (axes[1], CF, "Climate-FEVER (contested lay claims, $n{=}45$)")]:
        x = np.arange(len(data))
        acc = [d[1] for d in data]
        lo = [d[1]-d[2] for d in data]; hi = [d[3]-d[1] for d in data]
        colors = ["#B2182B"] + ["#2166AC"]*5 + ["#999999"]
        ax.bar(x, acc, 0.62, yerr=[lo, hi], capsize=3, color=colors)
        ax.axhline(1/3, ls=":", c="gray", lw=1)
        ax.text(len(data)-1, 0.35, "chance (1/3)", fontsize=7, color="gray", ha="right")
        ax.set_xticks(x); ax.set_xticklabels([d[0] for d in data], fontsize=7.5)
        ax.set_title(title, fontsize=11); ax.set_ylim(0, 1)
        for xi, a in zip(x, acc):
            ax.text(xi, a + (hi[xi] if isinstance(hi, list) else 0) + 0.02, f"{a:.2f}", ha="center", fontsize=7)
    axes[0].set_ylabel("Accuracy vs. human gold (Wilson 95\\% CI)")
    axes[0].text(0.02, 0.95, "red = proprietary, blue = open, grey = floor", transform=axes[0].transAxes, fontsize=7)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_validation.png"), dpi=160)
    print("wrote fig_validation.png")


def fig_confusion():
    rep = next(load("report_scifact_full.json"), None)
    if not rep or "claude" not in rep["validators"]:
        print("no claude confusion"); return
    conf = rep["validators"]["claude"]["confusion"]
    cls = ["support", "refute", "silent"]
    M = np.array([[conf[a][b] for b in cls] for a in cls], float)
    Mn = M / M.sum(1, keepdims=True).clip(min=1)
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    im = ax.imshow(Mn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(3)); ax.set_yticks(range(3))
    ax.set_xticklabels(cls); ax.set_yticklabels(cls)
    ax.set_xlabel("Claude judge"); ax.set_ylabel("Human gold (SciFact)")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{int(M[i,j])}\n{Mn[i,j]:.0%}", ha="center", va="center",
                    color="white" if Mn[i, j] > 0.5 else "black", fontsize=9)
    ax.set_title("Claude judge vs. human gold")
    plt.colorbar(im, fraction=0.046, pad=0.04)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_confusion_scifact.png"), dpi=160)
    print("wrote fig_confusion_scifact.png")


def fig_support():
    """Support rate by party across judges (bespoke GPT-5 retrieval). Shows the level is
    judge-dependent (huge spread) while the Dem>=Rep ordering is robust; the validated judge
    (Claude, PPI-corrected) is the anchor."""
    p = os.path.join(STANCE, "policy_stance_gpt5.json")
    if not os.path.exists(p):
        print("no policy_stance_gpt5 yet"); return
    d = json.load(open(p))["support_rate_by_party"]
    order = [("nli_deberta", "NLI\nDeBERTa"), ("nli_bart", "NLI\nBART"),
             ("llm:Qwen/Qwen2.5-3B-Instruct", "Qwen2.5\n3B"),
             ("llm:allenai/OLMo-2-1124-7B-Instruct", "OLMo-2\n7B"),
             ("llm:microsoft/Phi-3.5-mini-instruct", "Phi-3.5\nmini")]
    rows = [(lab, d[k]["dem"], d[k]["rep"]) for k, lab in order if k in d]
    # validated judge (Claude) PPI estimate
    vr = json.load(open(os.path.join(STANCE, "validation_report.json")))["support_rate_by_party_ppi"]
    rows.append(("Claude judge\n(PPI, validated)", vr["dem"]["estimate"], vr["rep"]["estimate"]))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(rows)); w = 0.38
    dem = [r[1] for r in rows]; rep = [r[2] for r in rows]
    b1 = ax.bar(x - w/2, dem, w, label="Democratic", color="#2166AC")
    b2 = ax.bar(x + w/2, rep, w, label="Republican", color="#B2182B")
    # highlight the validated-judge anchor
    ax.axvspan(len(rows)-1.5, len(rows)-0.5, color="gold", alpha=0.15)
    ax.set_xticks(x); ax.set_xticklabels([r[0] for r in rows], fontsize=8)
    ax.set_ylabel("Share of claims judged 'support'"); ax.set_ylim(0, 1)
    ax.set_title("Corroboration rate by party is judge-dependent; Dem $\\geq$ Rep ordering is robust")
    ax.legend(loc="upper left", fontsize=9)
    for xi, dv, rv in zip(x, dem, rep):
        ax.text(xi - w/2, dv + 0.01, f"{dv:.2f}", ha="center", fontsize=7)
        ax.text(xi + w/2, rv + 0.01, f"{rv:.2f}", ha="center", fontsize=7)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_support_party.png"), dpi=160)
    print("wrote fig_support_party.png")


if __name__ == "__main__":
    fig_validation()
    fig_confusion()
    fig_support()
    print("done")
