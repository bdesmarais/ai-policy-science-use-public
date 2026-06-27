#!/usr/bin/env python3
"""
relevance_validation.py — validate the model's RETRIEVAL-RELEVANCE judgment against human
labels, replacing the self-graded relevance yield with a human-anchored number (round-5
referee). Relevance is the one judgment humans agree on well (unlike stance on contested
claims), so this is a clean check, and we get it by transfer, with no in-domain coding.

SciFact's human evidence annotations (cited_doc_ids) are relevance labels: the cited abstract
is on-topic for the claim, a random other abstract is not. We test whether the model's
"is this reference relevant to the claim?" judgment recovers that human distinction.
"""
import json, os, re, sys, time, random, math
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BENCH = os.path.join(BASE, "benchmarks", "data")
OUT = os.path.join(BASE, "benchmarks", "results")
SAMPLE_PATH = os.path.join(BASE, "data", "relevance_sample.json")
PANEL = ["Qwen/Qwen2.5-3B-Instruct", "microsoft/Phi-3.5-mini-instruct", "allenai/OLMo-2-1124-7B-Instruct"]
SEED = 20260627
N_CLAIMS = 60

REL_PROMPT = """You are screening a retrieved reference for a fact-checking pipeline.
A reference is RELEVANT if it is on-topic for the CLAIM---i.e. it is about the same specific \
subject and could plausibly bear on whether the claim is true. It is IRRELEVANT if it is about \
a different topic and could not be used to assess the claim.
CLAIM: {claim}
REFERENCE TITLE: {title}
REFERENCE ABSTRACT: {abstract}
Is the reference relevant to the claim? Answer one word: RELEVANT or IRRELEVANT."""


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return (round(p, 3), round((c-h)/d, 3), round((c+h)/d, 3))


def prf(gold, pred):
    tp = sum(1 for g, p in zip(gold, pred) if g == 1 and p == 1)
    fp = sum(1 for g, p in zip(gold, pred) if g == 0 and p == 1)
    fn = sum(1 for g, p in zip(gold, pred) if g == 1 and p == 0)
    acc = sum(1 for g, p in zip(gold, pred) if g == p)/max(len(gold), 1)
    prec = tp/(tp+fp) if tp+fp else 0.0
    rec = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*prec*rec/(prec+rec) if prec+rec else 0.0
    return {"acc": round(acc, 3), "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}


def build_sample():
    corpus = {json.loads(l)["doc_id"]: json.loads(l) for l in open(os.path.join(BENCH, "corpus.jsonl"))}
    claims = [json.loads(l) for l in open(os.path.join(BENCH, "claims_dev.jsonl")) if json.loads(l).get("cited_doc_ids")]
    rng = random.Random(SEED)
    sample = rng.sample(claims, N_CLAIMS)
    allids = list(corpus)
    rows = []
    for c in sample:
        cited = set(c["cited_doc_ids"])
        # relevant pair: claim + a cited abstract
        cd = corpus.get(c["cited_doc_ids"][0])
        if cd:
            rows.append({"claim": c["claim"], "title": cd.get("title", ""),
                         "abstract": " ".join(cd.get("abstract", []))[:1600], "gold": 1})
        # irrelevant pair: claim + a random non-cited abstract
        rid = rng.choice(allids)
        while rid in cited:
            rid = rng.choice(allids)
        rd = corpus[rid]
        rows.append({"claim": c["claim"], "title": rd.get("title", ""),
                     "abstract": " ".join(rd.get("abstract", []))[:1600], "gold": 0})
    rng.shuffle(rows)
    for i, r in enumerate(rows):
        r["uid"] = f"rel{i}"
    json.dump(rows, open(SAMPLE_PATH, "w"), indent=1)
    return rows


def run_panel(rows, model_id, log_every=40):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=(torch.float16 if dev == "mps" else torch.float32)).to(dev).eval()
    out, t0 = [], time.time()
    for i, r in enumerate(rows):
        msg = [{"role": "user", "content": REL_PROMPT.format(claim=r["claim"], title=r["title"], abstract=r["abstract"][:1400])}]
        text = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        inp = tok(text, return_tensors="pt", truncation=True, max_length=2048).to(dev)
        with torch.no_grad():
            gen = model.generate(**inp, max_new_tokens=4, do_sample=False, pad_token_id=(tok.pad_token_id or tok.eos_token_id))
        ans = tok.decode(gen[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip().lower()
        out.append(0 if "irrelev" in ans else (1 if "relev" in ans else 0))
        if (i+1) % log_every == 0:
            print(f"    {model_id}: {i+1}/{len(rows)} ({(time.time()-t0)/(i+1):.2f}s)", flush=True)
    del model
    try:
        torch.mps.empty_cache()
    except Exception:
        pass
    return out


def run_tfidf(rows):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    claims = [r["claim"] for r in rows]
    docs = [f"{r['title']}. {r['abstract']}" for r in rows]
    X = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(claims + docs)
    n = len(rows)
    sims = cosine_similarity(X[:n], X[n:]).diagonal()
    return [1 if s >= 0.10 else 0 for s in sims]


def main():
    rows = build_sample()
    gold = [r["gold"] for r in rows]
    print(f"relevance sample: {len(rows)} ({Counter(gold)}) -> {SAMPLE_PATH}")
    report = {"n": len(rows), "gold_dist": dict(Counter(gold)),
              "note": "SciFact human cited-vs-random relevance labels; humans agree strongly on relevance",
              "validators": {}}
    report["validators"]["tfidf_cosine"] = prf(gold, run_tfidf(rows))
    print("  tfidf:", report["validators"]["tfidf_cosine"])
    for m in PANEL:
        try:
            pr = run_panel(rows, m)
            report["validators"][m] = prf(gold, pr)
            print(f"  {m}:", report["validators"][m])
        except Exception as e:
            report["validators"][m] = {"error": str(e)[:150]}
    cp = os.path.join(BASE, "data", "relevance_claude.json")
    if os.path.exists(cp):
        cl = json.load(open(cp))
        pred = [1 if cl.get(r["uid"]) in (1, "1", "relevant", True) else 0 for r in rows]
        report["validators"]["claude_opus_4.8"] = {**prf(gold, pred),
                                                    "acc_wilson95": list(wilson(sum(1 for g, p in zip(gold, pred) if g == p), len(gold)))}
        print("  claude:", report["validators"]["claude_opus_4.8"])
    json.dump(report, open(os.path.join(OUT, "relevance_validation.json"), "w"), indent=2)
    print("wrote relevance_validation.json")


if __name__ == "__main__":
    main()
