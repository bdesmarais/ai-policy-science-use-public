#!/usr/bin/env python3
"""
detect_ai_releases.py — flag AI/automation-related press releases among the freshly fetched
12-month corpus, by full-text keyword detection (the engagement front-end), and emit a
ranked candidate list with snippets for claim extraction.

Reports, per party: total fetched, AI-mention count and rate (engagement refresh), and the
ranked AI releases to extract claims from.
"""
import json, os, re
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = os.path.join(BASE, "outputs", "refresh")

# strong AI/automation signals (word-boundary); a release qualifies if it has >=MIN hits
PATTERNS = [
    r"artificial intelligence", r"\bA\.?I\.?\b", r"deepfake", r"machine learning",
    r"algorithm", r"automated decision", r"facial recognition", r"chatbot",
    r"generative ai", r"large language model", r"\bGPT\b", r"autonomous vehicle",
    r"self-driving", r"surveillance pricing", r"automated", r"neural", r"biometric",
    r"data center", r"robot", r"digital replica", r"synthetic media",
]
RX = [re.compile(p, re.I) for p in PATTERNS]
MIN_HITS = 2          # at least two AI signals to count as AI-related
STRONG = re.compile(r"artificial intelligence|deepfake|\balgorithm|automated decision|"
                    r"facial recognition|generative ai|chatbot|machine learning", re.I)


def score(text):
    hits = sum(len(rx.findall(text)) for rx in RX)
    strong = len(STRONG.findall(text))
    return hits, strong


def main():
    manifest = json.load(open(os.path.join(R, "fetch_manifest.json")))
    by_party = defaultdict(lambda: {"total": 0, "ai": 0})
    ai_releases = []
    for m in manifest:
        try:
            txt = open(m["file"]).read()
        except FileNotFoundError:
            continue
        if len(txt) < 200:           # skip empty/blocked fetches
            continue
        by_party[m["party"]]["total"] += 1
        hits, strong = score(txt)
        # AI-related if >=2 total signals AND >=1 strong signal (avoids 'automated'-only noise)
        if hits >= MIN_HITS and strong >= 1:
            by_party[m["party"]]["ai"] += 1
            ai_releases.append({**{k: m[k] for k in ("party", "date", "slug", "file")},
                                "hits": hits, "strong": strong, "chars": len(txt)})
    ai_releases.sort(key=lambda r: (r["party"], r.get("date") or ""))
    rep = {p: {**v, "ai_rate": round(v["ai"] / v["total"], 4) if v["total"] else None}
           for p, v in by_party.items()}
    json.dump({"engagement": rep, "n_ai_releases": len(ai_releases), "ai_releases": ai_releases},
              open(os.path.join(R, "ai_detection.json"), "w"), indent=1)
    print("Engagement (fresh 12-month window):")
    for p, v in rep.items():
        print(f"  {p}: {v['ai']}/{v['total']} AI-related = {v['ai_rate']}")
    print(f"AI releases to extract from: {len(ai_releases)}")
    for r in ai_releases:
        print(f"  [{r['party']} {r.get('date')}] hits={r['hits']} strong={r['strong']} {r['slug'][:70]}")


if __name__ == "__main__":
    main()
