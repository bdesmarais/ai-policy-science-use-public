#!/usr/bin/env python3
"""
fetch_refresh_releases.py — fetch the full text of CA Assembly press releases from the
last 12 months (both caucuses), for refreshing the corpus. Resumable; polite delay.

Sources (the same caucus archives the original corpus came from):
  Democrats:   asmdc.org/index.php/press-releases/<YYYYMMDD-slug>
  Republicans: asmrc.org/<slug>/
Reads outputs/refresh/{dem,rep}_window_urls.json; writes stripped text to
outputs/refresh/text/<party>/<slug>.txt and a manifest.
"""
import json, os, re, subprocess, sys, time, html

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = os.path.join(BASE, "outputs", "refresh")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
DELAY = 0.3


def strip_html(h):
    h = re.sub(r"(?is)<(script|style|nav|header|footer|form)[^>]*>.*?</\1>", " ", h)
    # drop everything before main content if we can find an <article> or content div
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", h)
    body = m.group(1) if m else h
    body = re.sub(r"(?is)<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"\s+", " ", body).strip()
    return body


def fetch(url):
    try:
        out = subprocess.run(["curl", "-skL", "-A", UA, "-m", "30", url],
                             capture_output=True, text=True, timeout=40)
        return out.stdout
    except Exception:
        return ""


def main():
    manifest = []
    mpath = os.path.join(R, "fetch_manifest.json")
    if os.path.exists(mpath):
        manifest = json.load(open(mpath))
    done = {m["slug"] + "|" + m["party"] for m in manifest}
    items = []
    for party in ["dem", "rep"]:
        items += json.load(open(os.path.join(R, f"{party}_window_urls.json")))
    n = 0
    for it in items:
        key = it["slug"] + "|" + it["party"]
        if key in done:
            continue
        h = fetch(it["url"])
        txt = strip_html(h) if h else ""
        # keep only the substantive portion; many Drupal pages repeat menus -- cut obvious boilerplate
        fp = os.path.join(R, "text", it["party"], it["slug"][:120] + ".txt")
        open(fp, "w").write(txt)
        manifest.append({"party": it["party"], "date": it.get("date"), "slug": it["slug"],
                         "url": it["url"], "chars": len(txt), "file": fp})
        n += 1
        if n % 50 == 0:
            json.dump(manifest, open(mpath, "w"), indent=1)
            print(f"  fetched {n} new (total {len(manifest)})", flush=True)
        time.sleep(DELAY)
    json.dump(manifest, open(mpath, "w"), indent=1)
    print(f"done: {len(manifest)} releases fetched -> {mpath}")


if __name__ == "__main__":
    main()
