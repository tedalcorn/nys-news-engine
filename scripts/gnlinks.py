#!/usr/bin/env python3
"""Resolve Google News redirect links (news.google.com/rss/articles/CBMi...) to the publisher's URL.

The redirect is opaque: Google's article page carries a signature and timestamp, and its batchexecute
endpoint trades them for the real URL. Two requests per link, and Google answers 429 after ~100 requests
from one IP in a short window, a limit shared with the Google News RSS queries the engine depends on.
So resolution never runs on the Pi. The resolve-links workflow runs this on GitHub Actions after every
push of items.json: N parallel jobs (N fresh IPs) each take a shard of the unresolved links, and a merge
job writes docs/data/links.json = {"links": {google_url: real_url}, "failed": {google_url: tries}}.
fetch.py applies that map on its next run; the page hides items whose link is still a Google redirect.

  gnlinks.py shard K N OUT.json   decode shard K of N unresolved links in docs/data/items.json -> OUT.json
  gnlinks.py merge SHARD.json...  fold shard results into docs/data/links.json, pruning applied entries
"""
import json, os, re, sys, time, hashlib
from urllib.parse import quote, urlparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS = os.path.join(ROOT, "docs", "data", "items.json")
LINKS = os.path.join(ROOT, "docs", "data", "links.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PER_SHARD = 45     # ~90 requests: under the 429 threshold for a fresh IP
MAX_AGE_D = 180    # the whole archive: the page hides unresolved items and search covers 180 days
MAX_TRIES = 4      # failures that are not 429 (page without a signature): give up after this many runs
SLEEP = 1.0


class Throttled(Exception): pass


def is_google(url): return "news.google." in (url or "")


def decode(url):
    aid = urlparse(url).path.rstrip("/").split("/")[-1]
    r = requests.get(f"https://news.google.com/articles/{aid}", headers={"User-Agent": UA}, timeout=15)
    if r.status_code == 429 or "/sorry/" in r.url: raise Throttled()
    sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
    ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
    if not (sg and ts):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
             "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts.group(1)), sg.group(1)]
    payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
    r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                      headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": UA},
                      data="f.req=" + quote(json.dumps(payload)), timeout=15)
    if r.status_code == 429: raise Throttled()
    real = json.loads(json.loads(r.text.split("\n\n", 1)[1])[0][2])[1]
    return real if isinstance(real, str) and real.startswith("http") and not is_google(real) else None


def load_links():
    try:
        d = json.load(open(LINKS))
        return {"links": d.get("links", {}), "failed": d.get("failed", {})}
    except Exception:
        return {"links": {}, "failed": {}}


def unresolved(items, now_ts):
    return [i for i in items if is_google(i.get("link")) and now_ts - i.get("published_ts", 0) <= MAX_AGE_D * 86400]


def apply(items, links=None):
    """Swap resolved links into items (fetch.py calls this). Returns how many changed."""
    links = links if links is not None else load_links()["links"]
    n = 0
    for i in items:
        real = links.get(i.get("link"))
        if real:
            i["gn_link"], i["link"] = i["link"], real
            if not i.get("domain"):
                i["domain"] = urlparse(real).netloc.replace("www.", "")
            n += 1
    return n


def shard(k, n, out):
    items = json.load(open(ITEMS)); now = time.time()
    known = load_links()
    todo = [i for i in unresolved(items, now)
            if i["link"] not in known["links"] and known["failed"].get(i["link"], 0) < MAX_TRIES
            and int(hashlib.sha1(i["id"].encode()).hexdigest(), 16) % n == k]
    todo.sort(key=lambda i: -i["published_ts"])
    res, done, fails = {}, 0, 0
    for i in todo[:PER_SHARD]:
        try:
            real = decode(i["link"])
        except Throttled:
            print(f"shard {k}/{n}: 429 after {done + fails} links"); break
        except Exception:
            real = None
        res[i["link"]] = real
        done += bool(real); fails += not real
        time.sleep(SLEEP)
    json.dump(res, open(out, "w"))
    print(f"shard {k}/{n}: {len(todo)} to do, {done} resolved, {fails} failed")


def merge(paths):
    items = json.load(open(ITEMS)); now = time.time()
    d = load_links()
    for p in paths:
        for gn, real in json.load(open(p)).items():
            if real: d["links"][gn] = real; d["failed"].pop(gn, None)
            else: d["failed"][gn] = d["failed"].get(gn, 0) + 1
    # keep only entries for links that are still unresolved in items.json: once fetch.py has applied
    # a mapping, the item carries the real URL and the entry is dead weight
    live = {i["link"] for i in unresolved(items, now)}
    d["links"] = {k: v for k, v in d["links"].items() if k in live}
    d["failed"] = {k: v for k, v in d["failed"].items() if k in live}
    json.dump(d, open(LINKS, "w"), indent=0)
    print(f"links.json: {len(d['links'])} resolved awaiting fetch.py, {len(d['failed'])} failing, {len(live)} unresolved in items.json")


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "shard": shard(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    elif len(sys.argv) >= 2 and sys.argv[1] == "merge": merge(sys.argv[2:])
    else: print(__doc__); sys.exit(2)
