#!/usr/bin/env python3
"""
averitec_validation.py — validate the stance judge on AVeriTeC (Schlichtkrull et al., NeurIPS
2023): real-world claims fact-checked by 50 organizations, each paired with evidence
*retrieved from the web* and given a human verdict (reported inter-annotator kappa 0.619).

This directly answers the standing objection that the judge was only validated on benchmark
pairs "curated to be about each other": AVeriTeC's claim-evidence pairs are real-world claims
against *retrieved* (noisy, web-sourced) evidence -- the same pair structure the application
produces. If the judge matches AVeriTeC's human verdicts near the human-agreement band, the
curated-vs-application gap is closed with EXISTING human labels and no new coding.

Verdict mapping to our 3-way: Supported->support, Refuted->refute, Not Enough Evidence->silent.
"Conflicting Evidence/Cherrypicking" (a genuine 4th class) is excluded from the headline 3-way.
"""
import json, os, re, sys, random
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_validation as bv

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(BASE, "benchmarks", "results")
SAMPLE_PATH = os.path.join(BASE, "data", "averitec_sample.json")
PANEL = ["Qwen/Qwen2.5-3B-Instruct", "microsoft/Phi-3.5-mini-instruct", "allenai/OLMo-2-1124-7B-Instruct"]
SEED = 20260627
N_PER = 30
MAP = {"Supported": "support", "Refuted": "refute", "Not Enough Evidence": "silent"}


def evidence_passage(questions):
    parts = []
    for q in questions or []:
        ans = " ".join(a.get("answer", "") for a in (q.get("answers") or []) if a.get("answer"))
        if ans:
            parts.append(f"Q: {q.get('question','')} A: {ans}")
    return re.sub(r"\s+", " ", " ".join(parts)).strip()[:1700]


def build_sample():
    from datasets import load_dataset
    d = load_dataset("pminervini/averitec", split="train")
    buckets = {"support": [], "refute": [], "silent": []}
    for r in d:
        g = MAP.get(r["label"])
        if not g:
            continue
        ev = evidence_passage(r["questions"])
        if len(ev) < 60:
            continue
        buckets[g].append({"claim": r["claim"], "evidence": ev, "gold": g,
                           "speaker": r.get("speaker"), "source": r.get("reporting_source")})
    rng = random.Random(SEED)
    rows = []
    for g, items in buckets.items():
        rows += rng.sample(items, min(N_PER, len(items)))
    rng.shuffle(rows)
    for i, r in enumerate(rows):
        r["uid"] = f"av{i}"
    json.dump(rows, open(SAMPLE_PATH, "w"), indent=1)
    return rows


def to_pairs(rows):
    # judge/panel/NLI expect {claim,title,abstract}; evidence goes in the abstract slot
    return [{"claim": r["claim"], "title": "Retrieved web evidence (AVeriTeC)",
             "abstract": r["evidence"], "uid": r["uid"], "gold": r["gold"]} for r in rows]


def main():
    rows = build_sample()
    gold = [r["gold"] for r in rows]
    pairs = to_pairs(rows)
    print(f"AVeriTeC sample: {len(rows)} ({Counter(gold)}) -> {SAMPLE_PATH}")
    report = {"n": len(rows), "gold_dist": dict(Counter(gold)),
              "human_kappa_reported": 0.619, "validators": {}}

    # NLI surrogate
    try:
        pr = bv.run_nli(pairs, bv.NLI_MODELS["nli_deberta"])
        report["validators"]["nli_deberta"] = bv.metrics(gold, pr)
        print("  nli_deberta:", report["validators"]["nli_deberta"].get("accuracy"))
    except Exception as e:
        report["validators"]["nli_deberta"] = {"error": str(e)[:150]}
    # open panel
    for m in PANEL:
        try:
            pr = bv.run_llm_judge(pairs, m)
            report["validators"][m] = bv.metrics(gold, pr)
            print(f"  {m}:", report["validators"][m].get("accuracy"))
        except Exception as e:
            report["validators"][m] = {"error": str(e)[:150]}
            print(f"  {m}: ERROR {e}")
    # Claude in-session labels, if present
    cp = os.path.join(BASE, "data", "averitec_claude.json")
    if os.path.exists(cp):
        cl = json.load(open(cp))
        pred = [cl.get(r["uid"], "silent") for r in rows]
        report["validators"]["claude_opus_4.8"] = bv.metrics(gold, pred)
        print("  claude:", report["validators"]["claude_opus_4.8"].get("accuracy"))
    json.dump(report, open(os.path.join(OUT, "averitec_validation.json"), "w"), indent=2)
    print("wrote averitec_validation.json")


if __name__ == "__main__":
    main()
