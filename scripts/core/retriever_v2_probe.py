#!/usr/bin/env python3
"""
Route 2 probe: can a *claim-targeted, reproducible, open* retriever lift the open pipeline off the
~1% floor that broad OpenAlex keyword search produces?

Three reproducible-and-open improvements over the baseline OpenAlex step:
  (a) query reformulation with an open model (Qwen2.5-3B) -> a focused scientific search query;
  (b) wider candidate retrieval (k=15 instead of 5);
  (c) recall-oriented aggregation: a CLAIM counts as corroborated if ANY retrieved reference is
      judged 'support' (matching the substantive question "is there scientific support for this claim?"
      rather than "is an arbitrary top-5 reference supportive?").
We judge with the open NLI surrogate (no proprietary model) and report claim-level corroboration by
party, against the baseline OpenAlex pair-level rate (~5%).
"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openalex_retrieval as oa
import benchmark_validation as bv
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
N_PER_PARTY = 25
K = 20


def reformulate_all(claims, model_id="Qwen/Qwen2.5-3B-Instruct"):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dev = "mps" if bv._has_mps() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float16).to(dev).eval()
    out = []
    P = ("Convert this policy claim into a focused scientific-literature search query that would find the "
         "specific study testing it. Name the key variables, population, intervention, and outcome. "
         "Output ONLY the query, no preamble.\n\nCLAIM: {c}\n\nQUERY:")
    for i, c in enumerate(claims):
        msg = [{"role": "user", "content": P.format(c=c)}]
        text = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        inp = tok(text, return_tensors="pt", truncation=True, max_length=1024).to(dev)
        with torch.no_grad():
            g = model.generate(**inp, max_new_tokens=40, do_sample=False, pad_token_id=tok.eos_token_id)
        q = tok.decode(g[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip().replace("\n", " ")
        out.append(q[:200] or c[:120])
        if (i + 1) % 10 == 0:
            print(f"  reformulated {i+1}/{len(claims)}", flush=True)
    del model; bv._empty_cache()
    return out


def retrieve_query(query, k=K):
    q = urllib.parse.quote(query)
    url = (f"{oa.OPENALEX}?search={q}&filter=type:article,has_abstract:true,"
           f"from_publication_date:1990-01-01&per-page={k}&sort=relevance_score:desc&mailto={oa.MAILTO}")
    data = oa._get(url) or {}
    refs = []
    for w in data.get("results", []):
        ab = oa._abstract_from_inverted(w.get("abstract_inverted_index"))
        if ab:
            refs.append({"title": w.get("title") or "", "abstract": ab,
                         "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None})
    return refs


def main():
    claims = []
    for party in ["dem", "rep"]:
        rows = json.load(open(os.path.join(BASE, "outputs", "structured_refs", f"{party}_claim_references.json")))
        seen = []
        for e in rows:
            c = (e.get("claim_text") or "").strip()
            if c and c not in seen:
                seen.append(c)
            if len(seen) >= N_PER_PARTY:
                break
        claims += [(party, c) for c in seen[:N_PER_PARTY]]
    # NOTE: open-LLM query reformulation was tried and produced verbose queries that triggered
    # OpenAlex HTTP 500s and under-matched; this clean test isolates recall-oriented aggregation over
    # the WORKING broad keyword retrieval (oa.retrieve), at k=20, with claim-level any-support.
    print("[route2] retrieving k=%d (broad keyword) from OpenAlex per claim ..." % K, flush=True)
    pairs, claim_idx = [], []
    for i, (party, c) in enumerate(claims):
        try:
            refs = oa.retrieve(c, K)
        except Exception as ex:
            print(f"  retrieve fail {i}: {ex}", flush=True); refs = []
        for r in refs:
            pairs.append({"party": party, "claim": c, "title": r["title"], "abstract": r["abstract"], "gold": ""})
            claim_idx.append(i)
        time.sleep(0.8)
    print(f"[route2] {len(pairs)} pairs; judging with NLI ...", flush=True)
    preds = bv.run_nli(pairs, bv.NLI_MODELS["nli_deberta"])

    # claim-level: corroborated if >=1 retrieved ref judged support
    by_claim = {}
    for idx, p, pr in zip(claim_idx, pairs, preds):
        d = by_claim.setdefault(idx, {"party": p["party"], "any_support": False, "n": 0, "n_support": 0})
        d["n"] += 1
        if pr == "support":
            d["any_support"] = True; d["n_support"] += 1
    res = {"dem": [], "rep": []}
    for idx, d in by_claim.items():
        res[d["party"]].append(1.0 if d["any_support"] else 0.0)
    print("\n========= ROUTE 2 RESULT (open NLI judge, claim-level any-support) =========")
    for party in ["dem", "rep"]:
        v = res[party]
        print(f"  {party}: claim-level corroboration = {np.mean(v):.3f}  (n_claims={len(v)})")
    pair_support = np.mean([1.0 if pr == "support" else 0.0 for pr in preds]) if preds else 0
    print(f"  pair-level support rate (all retrieved pairs) = {pair_support:.3f}  ({len(pairs)} pairs)")
    print("  BASELINE for comparison: OpenAlex k=5 pair-level support ~0.05; GPT-5+judge headline 0.71/0.54")
    json.dump({"claim_level": {p: float(np.mean(res[p])) for p in res}, "n_pairs": len(pairs),
               "pair_support": float(pair_support), "k": K, "n_per_party": N_PER_PARTY},
              open(os.path.join(BASE, "outputs", "route2_probe.json"), "w"), indent=2)
    print("[route2] wrote outputs/route2_probe.json")


if __name__ == "__main__":
    main()
