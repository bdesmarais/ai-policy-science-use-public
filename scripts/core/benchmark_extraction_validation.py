#!/usr/bin/env python3
"""
benchmark_extraction_validation.py — validate the CLAIM-EXTRACTION step against human labels
WITHOUT new human coders, by transfer from a human-labeled check-worthiness benchmark.

The extractor's core decision is "is this an empirical claim for which you'd need a
reference?" -- i.e. check-worthy factual claim detection. ClaimBuster (Hassan et al.) labels
~23k US-debate sentences as check-worthy-factual (CFS), unimportant-factual (UFS), or
non-factual (NFS) by trained humans. We score the same models that drive extraction on this
benchmark (binary: check-worthy vs not), exactly as SciFact/Climate-FEVER anchored the judge.

Open panel + TF-IDF baseline run here programmatically; the frontier model (Claude) labels the
same blind sample in-session (committed to data/extraction_checkworthy_claude.json).
"""
import json, os, re, sys, time, math, random
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(BASE, "benchmarks", "results")
SAMPLE_PATH = os.path.join(BASE, "data", "extraction_checkworthy_sample.json")
PANEL = ["Qwen/Qwen2.5-3B-Instruct", "microsoft/Phi-3.5-mini-instruct", "allenai/OLMo-2-1124-7B-Instruct"]
SEED = 20260627

CW_PROMPT = """You are screening one sentence from political communication.
A CHECK-WORTHY EMPIRICAL CLAIM asserts a fact about the world that could be verified against \
evidence, data, or a scientific/statistical reference (statistics, causal or factual claims about \
programs, trends, or effects). NOT check-worthy: opinions, rhetoric, questions, greetings, \
procedural remarks, or vague value statements.
SENTENCE: "{text}"
Is this a check-worthy empirical factual claim? Answer with one word: YES or NO."""


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = p + z*z/(2*n)
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (round(p, 3), round((c-h)/d, 3), round((c+h)/d, 3))


def prf(gold, pred):
    tp = sum(1 for g, p in zip(gold, pred) if g == 1 and p == 1)
    fp = sum(1 for g, p in zip(gold, pred) if g == 0 and p == 1)
    fn = sum(1 for g, p in zip(gold, pred) if g == 1 and p == 0)
    acc = sum(1 for g, p in zip(gold, pred) if g == p) / max(len(gold), 1)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2*prec*rec/(prec+rec) if prec+rec else 0.0
    return {"acc": round(acc, 3), "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}


def build_sample(n_per_class=75):
    from datasets import load_dataset
    d = load_dataset("Nithiwat/claimbuster", split="train")
    cfs = [r["text"] for r in d if r["checkworthiness"] == 1]
    nfs = [r["text"] for r in d if r["checkworthiness"] == 2]
    ufs = [r["text"] for r in d if r["checkworthiness"] == 0]
    rng = random.Random(SEED)
    pos = rng.sample(cfs, n_per_class)
    neg = rng.sample(nfs, n_per_class // 2) + rng.sample(ufs, n_per_class - n_per_class // 2)
    rows = [{"text": t, "gold": 1} for t in pos] + [{"text": t, "gold": 0} for t in neg]
    rng.shuffle(rows)
    for i, r in enumerate(rows):
        r["id"] = f"cw{i}"
    json.dump(rows, open(SAMPLE_PATH, "w"), indent=1)
    return rows


def run_panel(rows, model_id, log_every=40):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=(torch.float16 if dev == "mps" else torch.float32)).to(dev)
    model.eval()
    out, t0 = [], time.time()
    for i, r in enumerate(rows):
        msg = [{"role": "user", "content": CW_PROMPT.format(text=r["text"][:400])}]
        text = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        inp = tok(text, return_tensors="pt", truncation=True, max_length=1024).to(dev)
        with torch.no_grad():
            gen = model.generate(**inp, max_new_tokens=4, do_sample=False,
                                 pad_token_id=(tok.pad_token_id or tok.eos_token_id))
        ans = tok.decode(gen[0][inp.input_ids.shape[1]:], skip_special_tokens=True).strip().lower()
        out.append(1 if ans.startswith("yes") or "yes" in ans[:6] else 0)
        if (i+1) % log_every == 0:
            print(f"    {model_id}: {i+1}/{len(rows)} ({(time.time()-t0)/(i+1):.2f}s)", flush=True)
    del model
    try:
        torch.mps.empty_cache()
    except Exception:
        pass
    return out


def run_tfidf_cw(rows):
    # lexical baseline: a sentence is "check-worthy" if it contains a number/stat or a
    # factual-assertion cue; non-factual if it's a question/greeting/opinion marker.
    num = re.compile(r"\d|\bpercent\b|\bmillion\b|\bbillion\b|\bthousand\b")
    cue = re.compile(r"\b(increase|decrease|more than|less than|rate|cause|reduce|rose|fell|"
                     r"spent|cost|study|data|evidence)\b", re.I)
    op = re.compile(r"\b(I think|I believe|should|wonderful|terrible|great|let me|thank|good morning)\b", re.I)
    out = []
    for r in rows:
        t = r["text"]
        score = (1 if num.search(t) else 0) + (1 if cue.search(t) else 0) - (1 if op.search(t) else 0)
        out.append(1 if score >= 1 else 0)
    return out


def main():
    rows = build_sample()
    gold = [r["gold"] for r in rows]
    print(f"ClaimBuster check-worthiness sample: {len(rows)} ({Counter(gold)}) -> {SAMPLE_PATH}")
    report = {"n": len(rows), "gold_dist": dict(Counter(gold)),
              "human_ceiling_note": "ClaimBuster trained-human agreement and CheckThat! SOTA F1~0.70 are the references",
              "validators": {}}
    # baseline
    pr = run_tfidf_cw(rows)
    report["validators"]["tfidf_lexical"] = {**prf(gold, pr), "checkworthy_rate": round(sum(pr)/len(pr), 3)}
    print("  tfidf:", report["validators"]["tfidf_lexical"])
    # open panel
    for m in PANEL:
        try:
            pr = run_panel(rows, m)
            report["validators"][m] = {**prf(gold, pr), "checkworthy_rate": round(sum(pr)/len(pr), 3)}
            print(f"  {m}:", report["validators"][m])
        except Exception as e:
            report["validators"][m] = {"error": str(e)[:200]}
            print(f"  {m}: ERROR {e}")
    # Claude (in-session) labels, if present
    cp = os.path.join(BASE, "data", "extraction_checkworthy_claude.json")
    if os.path.exists(cp):
        cl = json.load(open(cp))
        pred = [1 if cl.get(r["id"]) in (1, "1", "yes", True) else 0 for r in rows]
        report["validators"]["claude_opus_4.8"] = {**prf(gold, pred), "checkworthy_rate": round(sum(pred)/len(pred), 3)}
        print("  claude:", report["validators"]["claude_opus_4.8"])
    json.dump(report, open(os.path.join(OUT, "extraction_checkworthiness.json"), "w"), indent=2)
    print("wrote extraction_checkworthiness.json")


if __name__ == "__main__":
    main()
