#!/usr/bin/env python3
"""Re-retrieve references for every CA claim from OpenAlex (reproducible, real papers)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openalex_retrieval import retrieve
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(BASE, "outputs", "structured_refs_openalex")
os.makedirs(OUT, exist_ok=True)
for party in ["dem", "rep"]:
    src = os.path.join(BASE, "outputs", "structured_refs", f"{party}_claim_references.json")
    rows = json.load(open(src)); rows = rows if isinstance(rows, list) else list(rows.values())
    out = []
    for i, e in enumerate(rows):
        claim = (e.get("claim_text") or "").strip()
        refs = []
        if claim:
            try:
                refs = retrieve(claim, k=5)
            except Exception as ex:
                print(f"  {party} {i}: retrieve fail {ex}", flush=True)
        out.append({"press_release": e.get("press_release"), "claim_number": e.get("claim_number"),
                    "claim_text": claim, "references": refs})
        if (i + 1) % 25 == 0:
            print(f"  {party}: {i+1}/{len(rows)} claims, last got {len(refs)} refs", flush=True)
        time.sleep(0.8)
    json.dump(out, open(os.path.join(OUT, f"{party}_claim_references.json"), "w"), indent=1)
    print(f"{party}: wrote {len(out)} claims, {sum(len(o['references']) for o in out)} refs", flush=True)
print("DONE")
