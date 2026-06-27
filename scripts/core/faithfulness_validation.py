#!/usr/bin/env python3
"""
faithfulness_validation.py — validate that EXTRACTED claims are grounded in (entailed by)
their SOURCE press release, with no human coders. The most serious extraction failure is
fabrication/hallucination: a claim the model invented that the document does not support.
We check grounding automatically with NLI entailment (the standard out-of-the-box faithfulness
metric): for each extracted claim, split its source release into sentence windows, score
entailment(window -> claim), and take the maximum. A claim is GROUNDED if some part of its own
source entails it. We report the grounding rate overall and by party, and surface the
lowest-entailment claims (candidate fabrications) for a judge spot-check.
"""
import csv, json, os, re, sys, time
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = {"dem": os.path.join(BASE, "data", "Dem_AI"), "rep": os.path.join(BASE, "data", "Rep_AI")}
CLAIMS = {"dem": os.path.join(BASE, "data", "structured_claims", "Demsfull_AI_LMclaims.csv"),
          "rep": os.path.join(BASE, "data", "structured_claims", "Rep_AI_LMclaims.csv")}
OUT = os.path.join(BASE, "benchmarks", "results", "extraction_faithfulness.json")
NLI_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
THRESH = 0.5
MAXP = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = all claims


def strip_meta(claim):
    # remove the extractor's trailing parenthetical meta-commentary, keep the proposition
    return re.sub(r"\s*\((?:This|These|It|A claim|The claim|Similar|This is|This claim)[^)]*\)\s*$", "", claim).strip()


def sentences(text):
    text = re.sub(r"\s+", " ", text)
    s = re.split(r"(?<=[.!?])\s+", text)
    # also include sliding 2-sentence windows so a claim spanning two sentences can be grounded
    out = list(s)
    for i in range(len(s) - 1):
        out.append(s[i] + " " + s[i+1])
    return [x for x in out if len(x) > 15][:120]


def main():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(NLI_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL).to(dev).eval()
    # label order for this model: [entailment, neutral, contradiction]
    ent_idx = 0

    claims = []
    for party, path in CLAIMS.items():
        for r in csv.DictReader(open(path)):
            ct = (r.get("claim_text") or "").strip()
            pr = r.get("press_release") or ""
            if not ct or not pr:
                continue
            sp = os.path.join(SRC[party], pr)
            if not os.path.exists(sp):
                continue
            claims.append({"party": party, "pr": pr, "claim": ct})
    if MAXP:
        claims = claims[:MAXP]
    print(f"faithfulness over {len(claims)} extracted claims (NLI grounding vs own source)")

    # cache source sentences per release
    srccache = {}
    results, t0 = [], time.time()
    for k, c in enumerate(claims):
        key = (c["party"], c["pr"])
        if key not in srccache:
            srccache[key] = sentences(open(os.path.join(SRC[c["party"]], c["pr"])).read())
        sents = srccache[key]
        hyp = strip_meta(c["claim"])
        best = 0.0
        for i in range(0, len(sents), 16):
            batch = sents[i:i+16]
            enc = tok([(s, hyp) for s in batch], return_tensors="pt", truncation=True,
                      max_length=256, padding=True).to(dev)
            with torch.no_grad():
                logits = model(**enc).logits
                probs = torch.softmax(logits, dim=-1)[:, ent_idx]
            best = max(best, float(probs.max()))
            if best > 0.97:
                break
        results.append({"party": c["party"], "pr": c["pr"], "claim": hyp[:200], "max_entail": round(best, 3)})
        if (k+1) % 100 == 0:
            print(f"  {k+1}/{len(claims)} ({(time.time()-t0)/(k+1):.2f}s/claim)", flush=True)

    by = defaultdict(list)
    for r in results:
        by[r["party"]].append(r["max_entail"])
    rep = {"n": len(results), "threshold": THRESH, "nli_model": NLI_MODEL, "by_party": {}}
    for party, scores in by.items():
        grounded = sum(1 for s in scores if s >= THRESH)
        rep["by_party"][party] = {"n": len(scores), "grounded": grounded,
                                  "grounding_rate": round(grounded/len(scores), 3),
                                  "mean_max_entail": round(sum(scores)/len(scores), 3)}
    allscores = [r["max_entail"] for r in results]
    rep["overall_grounding_rate"] = round(sum(1 for s in allscores if s >= THRESH)/len(allscores), 3)
    rep["mean_max_entail"] = round(sum(allscores)/len(allscores), 3)
    rep["lowest"] = sorted(results, key=lambda r: r["max_entail"])[:25]
    json.dump(rep, open(OUT, "w"), indent=2)
    print(json.dumps({k: v for k, v in rep.items() if k != "lowest"}, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
