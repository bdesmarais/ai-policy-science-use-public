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
    sci = merge_validators(*load("report_scifact_full.json", "report_scifact_panel.json"))
    cf = merge_validators(*load("report_cf.json", "report_cf_claude.json"))
    if not sci:
        print("no scifact report"); return
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, data, title in [(axes[0], sci, "SciFact (expert scientific claims)"),
                            (axes[1], cf, "Climate-FEVER (contested real-world claims)")]:
        vs = [v for v in ORDER if v in data]
        if not vs:
            ax.set_visible(False); continue
        x = np.arange(len(vs)); w = 0.38
        acc = [data[v]["accuracy"] for v in vs]
        f1 = [data[v]["macro_f1"] for v in vs]
        ax.bar(x - w/2, acc, w, label="Accuracy", color="#2166AC")
        ax.bar(x + w/2, f1, w, label="Macro-F1", color="#67A9CF")
        ax.axhline(1/3, ls=":", c="gray", lw=1)
        ax.text(len(vs)-1, 0.34, "chance (3-class)", fontsize=7, color="gray", ha="right")
        ax.set_xticks(x); ax.set_xticklabels([LABELS.get(v, v) for v in vs], fontsize=8)
        ax.set_title(title, fontsize=11); ax.set_ylim(0, 1)
        for xi, a in zip(x, acc):
            ax.text(xi - w/2, a + 0.01, f"{a:.2f}", ha="center", fontsize=7)
    axes[0].set_ylabel("Score vs. human gold labels"); axes[0].legend(loc="upper right", fontsize=9)
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
    files = {"openalex": os.path.join(STANCE, "policy_stance_openalex.json"),
             "gpt5": os.path.join(STANCE, "policy_stance_gpt5.json")}
    data = {k: json.load(open(p)) for k, p in files.items() if os.path.exists(p)}
    if not data:
        print("no policy_stance files yet"); return
    fig, ax = plt.subplots(figsize=(8, 4.6))
    # average support rate across validators per (retrieval, party)
    groups = []
    for retr, d in data.items():
        rates = d["support_rate_by_party"]
        for party in ["dem", "rep"]:
            vals = [rates[v].get(party) for v in rates if rates[v].get(party) is not None]
            groups.append((f"{retr}\n{party}", np.mean(vals) if vals else 0, np.std(vals) if vals else 0, party))
    x = np.arange(len(groups))
    colors = ["#2166AC" if g[3] == "dem" else "#B2182B" for g in groups]
    ax.bar(x, [g[1] for g in groups], yerr=[g[2] for g in groups], color=colors, capsize=4)
    ax.set_xticks(x); ax.set_xticklabels([g[0] for g in groups], fontsize=9)
    ax.set_ylabel("Share judged 'support' (mean across validators)")
    ax.set_title("Claim-support rate by party and retrieval method")
    ax.set_ylim(0, 1)
    for xi, g in zip(x, groups):
        ax.text(xi, g[1] + 0.02, f"{g[1]:.2f}", ha="center", fontsize=8)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_support_party.png"), dpi=160)
    print("wrote fig_support_party.png")


if __name__ == "__main__":
    fig_validation()
    fig_confusion()
    fig_support()
    print("done")
