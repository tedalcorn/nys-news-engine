#!/usr/bin/env python3
"""Fetch the article page for direct (non-Google) links; keep the publisher's own summary, derive scoring
signals, classify paywall.

Four items in five arrive as a bare headline (Google News items, and the native feeds of Newsday, the Times
Union, City & State, NYSOP and CBS carry no dek). Every one of those sites still serves an `og:description`
meta tag on the article page, the one- or two-sentence summary written for search engines and social cards,
and it is served to crawlers even when the body is paywalled (checked 2026-10-25 across 16 outlets,
including Newsday, the Times Union, the Daily News and the Buffalo News). So one fetch per item gives us a
summary for the page and for the classifier, a word count where the body is readable, and the paywall class.

We deliberately do NOT store the body text: we extract, derive signals, and persist only `summary`
(when the feed gave none), `summary_src`, `words`, `inv_body`, `paywall` and `extracted_ts` on the item.
Each URL is fetched exactly once, ever.
"""
import json, re, time, os, html
from urllib.parse import urlparse

try:
    from curl_cffi import requests as cffi_requests     # browser impersonation: beats the bot blocks that 403 plain requests
except ImportError:
    cffi_requests = None
import requests

try:
    import trafilatura
except ImportError:
    trafilatura = None

from score import INVESTIGATIVE, _hits

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PER_RUN   = 60      # polite cap per run (~1 minute); cached forever, so the backlog drains over a few cycles
FRESH_H   = 7 * 24  # was 48 h for word counts alone; the summary is worth having for the whole browsing window
TIMEOUT   = 15
SLEEP     = 0.5

# domains we know sit behind a hard paywall - used as a fallback when the page won't tell us
HARD_PAYWALL = {"nytimes.com","wsj.com","bloomberg.com","newsday.com","timesunion.com",
                "nydailynews.com","politicopro.com","crainsnewyork.com","law360.com"}
# Subscription meters we know of. NY Post, Politico news pages, The City and Gothamist are free: they were listed
# here until 2026-10-24 and every story of theirs read "limited".
METERED      = set()

PAY_MARKERS = re.compile(
    r"subscribe to continue|already a subscriber|this content is for subscribers|"
    r"become a member to read|sign in to read|unlock this article|subscribers only",
    re.I)

# og:description boilerplate seen in the 10/25 sample: the site's name, a section blurb, a sign-up pitch
DESC_BOILERPLATE = re.compile(
    r"^(cbs news|fox 5|abc7|spectrum news|news ?10|wgrz|whec|wham|wivb|wkbw|wnyt|wrgb|wten|wsyr|wgrz|"
    r"a look at what.s making headlines|get the latest|read the latest|the latest news|sign up|subscribe|"
    r"breaking news|local news|stay informed|find out|watch|listen)", re.I)
META_DESC = [
    re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{10,})["\']', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']{10,})["\'][^>]+property=["\']og:description["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{10,})["\']', re.I),
    re.compile(r'<meta[^>]+content=["\']([^"\']{10,})["\'][^>]+name=["\']description["\']', re.I),
    re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.){20,})"'),      # schema.org NewsArticle as a last resort
]


def page_description(html_text, title="", outlet=""):
    """The publisher's summary, or "" when the page has none worth keeping."""
    for rx in META_DESC:
        m = rx.search(html_text or "")
        if not m: continue
        d = html.unescape(m.group(1).encode().decode("unicode_escape", "ignore") if "\\u" in m.group(1) else m.group(1))
        d = re.sub(r"<[^>]+>", " ", d); d = re.sub(r"\s+", " ", d).strip()
        if len(d) < 40 or DESC_BOILERPLATE.match(d): continue
        low = d.lower()
        if outlet and low.strip(" .") == outlet.lower(): continue
        if title and low.startswith(title.lower()[:40]): continue        # dek that just repeats the headline
        return d[:400]
    return ""


def classify_paywall(host, status, html_text, words):
    """free | metered | hard | unknown"""
    # schema.org is the publisher's own declaration, required by Google - trust it first
    m = re.search(r'"isAccessibleForFree"\s*:\s*(false|"False"|"false")', html_text or "", re.I)
    if m:
        return "hard"
    if re.search(r'"isAccessibleForFree"\s*:\s*(true|"True"|"true")', html_text or "", re.I):
        return "free"
    if status in (401, 402):
        return "hard" if host in HARD_PAYWALL else "metered"
    if status == 403:        # bot block (PIX11, SILive, Syracuse.com, Playbook), not a paywall
        return "hard" if host in HARD_PAYWALL else "unknown"
    if html_text and PAY_MARKERS.search(html_text):
        return "metered"
    if host in HARD_PAYWALL:
        return "hard"
    if words and words >= 250:
        return "free"
    if host in METERED:
        return "metered"
    return "unknown"


def domain_paywall(host):
    """'hard' / 'metered' for outlets we know, else None: the fallback for items never fetched."""
    host = (host or "").replace("www.", "")
    if host in HARD_PAYWALL: return "hard"
    if host in METERED: return "metered"
    return None


def _get(url):
    if cffi_requests:
        try:
            return cffi_requests.get(url, impersonate="chrome", timeout=TIMEOUT)
        except Exception:
            pass
    return requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)


def fetch_one(url, title="", outlet=""):
    host = urlparse(url).netloc.replace("www.", "")
    try:
        r = _get(url)
        body = trafilatura.extract(r.text) if trafilatura else ""
        body = body or ""
        words = len(body.split())
        return dict(words=words,
                    inv_body=_hits(body.lower(), INVESTIGATIVE),
                    paywall=classify_paywall(host, r.status_code, r.text, words),
                    desc=page_description(r.text, title, outlet),
                    status=r.status_code)
    except Exception as e:
        return dict(words=0, inv_body=0, desc="",
                    paywall=classify_paywall(host, 0, "", 0),
                    status=f"ERR:{type(e).__name__}")


def candidates(items, now_ts):
    """Every recent item with a real URL we have not fetched: newest first, so the page's Latest fills in
    before the backlog. Items fetched before 10/25 for a word count alone (no `summary_src`) and still
    without a summary get one more visit for the description."""
    pool = [i for i in items
            if "news.google" not in i.get("link", "")
            and i.get("kind") != "nyt"                      # API already gives abstract + word count; site returns a stub
            and (now_ts - i.get("published_ts", 0)) <= FRESH_H * 3600
            and ("extracted_ts" not in i
                 or (not i.get("summary") and "summary_src" not in i))]
    pool.sort(key=lambda x: -x.get("published_ts", 0))
    return pool[:PER_RUN]


def run(items, now_ts, verbose=True):
    todo = candidates(items, now_ts)
    if verbose:
        print(f"\nextract: {len(todo)} candidates this run")
    got = 0
    for i in todo:
        res = fetch_one(i["link"], i.get("title", ""), i.get("outlet", ""))
        i.update(words=max(res["words"], i.get("words") or 0), inv_body=res["inv_body"],   # keep the NYT API count
                 paywall=res["paywall"], extracted_ts=int(now_ts))
        if not i.get("summary") and res["desc"]:
            i["summary"] = res["desc"]; i["summary_src"] = "og"; got += 1
        elif not i.get("summary"):
            i["summary_src"] = "none"
        if verbose:
            print(f"  {str(res['status']):>6}  {res['words']:5d}w  {res['paywall']:8s} {'desc' if res['desc'] else '    '} "
                  f"{urlparse(i['link']).netloc.replace('www.','')[:22]:24s} {i['title'][:38]}")
        time.sleep(SLEEP)
    if verbose and todo:
        print(f"extract: {got} summaries recovered from og:description")
    return len(todo)
