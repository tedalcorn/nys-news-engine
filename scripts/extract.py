#!/usr/bin/env python3
"""Fetch article body text for direct (non-Google) links, derive scoring signals, classify paywall.

We deliberately do NOT store the body text: we extract, derive signals, and persist only
`words`, `inv_body`, `paywall` and `extracted_ts` on the item. Keeps items.json small and
means each URL is fetched exactly once, ever.
"""
import json, re, time, os
from urllib.parse import urlparse
import requests

try:
    import trafilatura
except ImportError:
    trafilatura = None

from score import INVESTIGATIVE, _hits

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PER_RUN   = 20      # polite cap per run; cached forever, so the backlog drains over a few cycles
FRESH_H   = 48      # only bother with recent items
TIMEOUT   = 15
SLEEP     = 0.8

# domains we know sit behind a hard paywall - used as a fallback when the page won't tell us
HARD_PAYWALL = {"nytimes.com","wsj.com","bloomberg.com","newsday.com","timesunion.com",
                "nydailynews.com","politicopro.com","crainsnewyork.com","law360.com"}
METERED      = {"politico.com","nypost.com","thecity.nyc","gothamist.com"}

PAY_MARKERS = re.compile(
    r"subscribe to continue|already a subscriber|this content is for subscribers|"
    r"become a member to read|sign in to read|unlock this article|subscribers only",
    re.I)


def classify_paywall(host, status, html_text, words):
    """free | metered | hard | unknown"""
    # schema.org is the publisher's own declaration, required by Google - trust it first
    m = re.search(r'"isAccessibleForFree"\s*:\s*(false|"False"|"false")', html_text or "", re.I)
    if m:
        return "hard"
    if re.search(r'"isAccessibleForFree"\s*:\s*(true|"True"|"true")', html_text or "", re.I):
        return "free"
    if status in (401, 402, 403):
        return "hard" if host in HARD_PAYWALL else "metered"
    if html_text and PAY_MARKERS.search(html_text):
        return "metered"
    if host in HARD_PAYWALL:
        return "hard"
    if words and words >= 250:
        return "free"
    if host in METERED:
        return "metered"
    return "unknown"


def fetch_one(url):
    host = urlparse(url).netloc.replace("www.", "")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        body = trafilatura.extract(r.text) if trafilatura else ""
        body = body or ""
        words = len(body.split())
        return dict(words=words,
                    inv_body=_hits(body.lower(), INVESTIGATIVE),
                    paywall=classify_paywall(host, r.status_code, r.text, words),
                    status=r.status_code)
    except Exception as e:
        return dict(words=0, inv_body=0,
                    paywall=classify_paywall(host, 0, "", 0),
                    status=f"ERR:{type(e).__name__}")


def candidates(items, now_ts):
    """Where extra text could actually change the ranking: recent, decent outlet,
    not already done, not obvious opinion/noise - top of the pile plus the band
    around the Picks cutoff."""
    pool = [i for i in items
            if "extracted_ts" not in i
            and "news.google" not in i.get("link", "")
            and i.get("tier", 3) <= 2
            and (now_ts - i.get("published_ts", 0)) <= FRESH_H * 3600
            and "opinion" not in i.get("flags", [])]
    if not pool:
        return []
    pool.sort(key=lambda x: -x.get("score", 0))
    # headline already smells investigative -> always worth the fetch
    must = [i for i in pool if i.get("flags") and "investigative" in i["flags"]]
    top  = pool[:PER_RUN]
    cut  = len(pool) // 3                      # roughly where Picks stops mattering
    edge = pool[max(0, cut - 5): cut + 5]      # the band that can actually flip
    out, seen = [], set()
    for i in must + top + edge:
        if i["id"] not in seen:
            seen.add(i["id"]); out.append(i)
    return out[:PER_RUN]


def run(items, now_ts, verbose=True):
    todo = candidates(items, now_ts)
    if verbose:
        print(f"\nextract: {len(todo)} candidates this run")
    for i in todo:
        res = fetch_one(i["link"])
        i.update(words=res["words"], inv_body=res["inv_body"],
                 paywall=res["paywall"], extracted_ts=int(now_ts))
        if verbose:
            print(f"  {str(res['status']):>6}  {res['words']:5d}w  {res['paywall']:8s} "
                  f"{urlparse(i['link']).netloc.replace('www.','')[:22]:24s} {i['title'][:38]}")
        time.sleep(SLEEP)
    return len(todo)
