#!/usr/bin/env python3
"""Analyses requested by the referee report:
 (1) every validator on the SAME pairs the judge saw, with Wilson 95% CIs (comparable accuracy);
 (2) the judge's Cohen kappa vs gold, to compare against human inter-annotator ceilings
     (SciFact human kappa=0.75; Climate-FEVER Krippendorff alpha=0.334);
 (3) TF-IDF floor on Climate-FEVER (was missing);
 (4) the judge's per-class behaviour on Climate-FEVER, esp. the SILENT/off-topic class
     (does it handle irrelevant pairings, i.e. the application regime?);
 (5) claim-extraction yield by party (extraction is unvalidated; check for differential rates).
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_validation as bv

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z*z/n
    c = p + z*z/(2*n)
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-h)/d, (c+h)/d)


def kappa(gold, pred):
    from sklearn.metrics import cohen_kappa_score
    idx = [i for i in range(len(pred)) if pred[i] != "abstain"]
    g = [gold[i] for i in idx]; p = [pred[i] for i in idx]
    return round(float(cohen_kappa_score(g, p, labels=bv.STANCES)), 3)


def same_pairs(benchmark, claude_labels_path, balanced=None):
    pairs = bv.LOADERS[benchmark](max_pairs=0)
    if balanced:  # replicate harness balanced-150 sampling (seed 7)
        import numpy as np
        rng = np.random.default_rng(7); by = {}
        for p in pairs: by.setdefault(p["gold"], []).append(p)
        sel = []
        for c, arr in by.items():
            idx = rng.choice(len(arr), size=min(balanced, len(arr)), replace=False)
            sel += [arr[i] for i in idx]
        rng.shuffle(sel); pairs = sel
    lab = json.load(open(claude_labels_path)).get("labels", {})
    sub = [p for p in pairs if p["uid"] in lab]      # EXACTLY the pairs the judge saw
    gold = [p["gold"] for p in sub]
    preds = {
        "claude": [lab[p["uid"]] for p in sub],
        "nli_deberta": bv.run_nli(sub, bv.NLI_MODELS["nli_deberta"]),
        "nli_bart": bv.run_nli(sub, bv.NLI_MODELS["nli_bart"]),
        "tfidf": bv.run_tfidf(sub),
        "llm:Qwen/Qwen2.5-3B-Instruct": bv.run_llm_judge(sub, "Qwen/Qwen2.5-3B-Instruct"),
        "llm:microsoft/Phi-3.5-mini-instruct": bv.run_llm_judge(sub, "microsoft/Phi-3.5-mini-instruct"),
        "llm:allenai/OLMo-2-1124-7B-Instruct": bv.run_llm_judge(sub, "allenai/OLMo-2-1124-7B-Instruct"),
    }
    n = len(sub)
    print(f"\n===== {benchmark}: ALL validators on the SAME {n} judge-seen pairs =====")
    print(f"gold dist: { {c: gold.count(c) for c in bv.STANCES} }")
    for name, pr in preds.items():
        correct = sum(1 for g, p in zip(gold, pr) if g == p)
        lo, hi = wilson(correct, n)
        print(f"  {name:42s} acc={correct/n:.3f} [{lo:.2f},{hi:.2f}]  kappa_vs_gold={kappa(gold, pr)}  (n={n})")
    return preds, gold


if __name__ == "__main__":
    same_pairs("scifact", os.path.join(BASE, "benchmarks", "claude_labels_scifact.json"))
    same_pairs("climate_fever", os.path.join(BASE, "benchmarks", "claude_labels_climate_fever.json"), balanced=150)

    # (3) TF-IDF floor on Climate-FEVER balanced
    import numpy as np
    pairs = bv.LOADERS["climate_fever"](max_pairs=0)
    rng = np.random.default_rng(7); by = {}
    for p in pairs: by.setdefault(p["gold"], []).append(p)
    sel = []
    for c, arr in by.items():
        idx = rng.choice(len(arr), size=min(150, len(arr)), replace=False); sel += [arr[i] for i in idx]
    tf = bv.run_tfidf(sel); gold = [p["gold"] for p in sel]
    acc = sum(1 for g, p in zip(gold, tf) if g == p)/len(sel)
    print(f"\n===== Climate-FEVER TF-IDF floor (balanced {len(sel)}): acc={acc:.3f} =====")

    # (4) judge per-class on Climate-FEVER (from existing report)
    rep = json.load(open(os.path.join(BASE, "benchmarks", "results", "report_cf_claude.json")))
    pc = rep["validators"]["claude"]["per_class"]
    print("\n===== Judge per-class on Climate-FEVER (does it handle off-topic=silent?) =====")
    for c in bv.STANCES:
        print(f"  {c:8s} P={pc[c]['precision']} R={pc[c]['recall']} F1={pc[c]['f1']} (support={pc[c]['support']})")

    # (5) extraction yield by party
    print("\n===== Claim-extraction yield by party =====")
    for party in ["dem", "rep"]:
        p = os.path.join(BASE, "outputs", "structured_refs", f"{party}_claim_references.json")
        rows = json.load(open(p)); rows = rows if isinstance(rows, list) else list(rows.values())
        prs = set(r.get("press_release") for r in rows)
        print(f"  {party}: {len(rows)} extracted claims across {len(prs)} AI press releases "
              f"({len(rows)/max(len(prs),1):.2f} claims/release)")
