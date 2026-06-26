#!/usr/bin/env python3
"""Print every number needed to fill the paper's \\pending placeholders, from result JSONs."""
import json, os
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(BASE, "benchmarks", "results")
ST = os.path.join(BASE, "outputs", "stance")


def jload(p):
    return json.load(open(p)) if os.path.exists(p) else {}


def merge(*fs):
    out = {}
    for f in fs:
        out.update(jload(os.path.join(RES, f)).get("validators", {}))
    return out


print("=" * 60, "\nBENCHMARK VALIDATION (accuracy / macro-F1 vs human gold)\n" + "=" * 60)
for bench, files in [("SciFact", ["report_scifact_full.json", "report_scifact_panel.json"]),
                     ("Climate-FEVER", ["report_cf.json", "report_cf_claude.json"])]:
    v = merge(*files)
    print(f"\n[{bench}]  (n by validator varies; claude is a stratified blind sample)")
    for name in ["claude", "llm:Qwen/Qwen2.5-3B-Instruct", "llm:microsoft/Phi-3.5-mini-instruct",
                 "llm:allenai/OLMo-2-1124-7B-Instruct", "nli_deberta", "nli_bart", "tfidf"]:
        if name in v:
            m = v[name]
            print(f"  {name:42s} acc={m['accuracy']:.3f}  macroF1={m['macro_f1']:.3f}  n={m['n']}")

print("\n" + "=" * 60, "\nBENCHMARK pairwise kappa (claude vs panel/NLI)\n" + "=" * 60)
for f in ["report_scifact_full.json", "report_scifact_panel.json", "report_cf.json"]:
    d = jload(os.path.join(RES, f))
    if d.get("pairwise_kappa"):
        print(f"\n[{f}]")
        for k, val in d["pairwise_kappa"].items():
            print(f"  {k}: kappa={val['kappa']} (n={val['n']})")

print("\n" + "=" * 60, "\nPOLICY SUPPORT RATES by party (share judged 'support')\n" + "=" * 60)
for refs in ["gpt5", "openalex"]:
    d = jload(os.path.join(ST, f"policy_stance_{refs}.json"))
    if d:
        print(f"\n[{refs}]  n_pairs={d.get('n_pairs')}  by_party_n={d.get('by_party_n')}")
        for v, r in d.get("support_rate_by_party", {}).items():
            print(f"  {v:42s} dem={r.get('dem')}  rep={r.get('rep')}")

print("\n" + "=" * 60, "\nEXISTING PPI (GPT-5 refs + 120 Claude gold) — validation_report.json\n" + "=" * 60)
vr = jload(os.path.join(ST, "validation_report.json"))
for p, d in vr.get("support_rate_by_party_ppi", {}).items():
    print(f"  {p}: PPI={d.get('estimate')} CI={d.get('ci95')} naive={d.get('naive_estimate')} anchor_n={d.get('n_anchor')}")
