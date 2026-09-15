#!/usr/bin/env python3
"""Fetch all sources, normalize, dedupe, score, merge with archive, write docs/data/items.json + meta.json.
Retention: 180 days. Safe to run repeatedly (idempotent by URL / normalized title)."""
import json, re, time, html, hashlib, os, sys, datetime as dt
from urllib.parse import urlparse, parse_qs, unquote
import feedparser, requests
sys.path.insert(0, os.path.dirname(__file__))
from sources import SOURCES, ALBANY_TERMS, SWEEP_EXCLUDE_DOMAINS
from score import score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
ITEMS = os.path.join(DATA, "items.json")
META  = os.path.join(DATA, "meta.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 nys-news-engine/1.0"
RETENTION_DAYS = 180
NOW = time.time()
OUTLET_MAP = {"newsday.com":"Newsday","spectrumlocalnews.com":"Spectrum News","nystateofpolitics.com":"NY State of Politics",
 "spectrum news ny1":"Spectrum News","governor kathy hochul (.gov)":"Governor's Office","the new york state senate (.gov)":"NY Senate",
 "new york state assembly (.gov)":"NY Assembly","cbcny":"Citizens Budget Commission","timesunion.com":"Times Union",
 "nydailynews.com":"Daily News","new york daily news":"Daily News","cityandstateny.com":"City & State","nysfocus.com":"New York Focus"}

def norm_title(t):
    t = html.unescape(t or "").lower()
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t)          # strip " - Outlet" suffix (Google News)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def dedupe_summary(title, summary, outlet=""):
    """Google News and .gov feeds set the dek to the headline (often + outlet). Drop those."""
    if not summary: return ""
    nt, ns = norm_title(title), norm_title(summary)
    no = norm_title(outlet or "")
    if no and ns.endswith(no): ns = ns[:-len(no)].strip()
    if not ns or ns == nt: return ""
    if nt and ns.startswith(nt) and len(ns[len(nt):].split()) <= 6: return ""
    if ns and nt.startswith(ns) and len(ns.split()) >= 4: return ""
    return summary

def is_site_name_only(title, *names):
    """True when the headline is really just the outlet/section name."""
    nt = norm_title(title)
    if not nt: return True
    for nm in names:
        nn = norm_title(nm or "")
        if not nn: continue
        if nt == nn: return True
        if nn in nt and len(nt.replace(nn, " ").split()) < 3: return True
    return False

def clean_summary(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:400]

def gnews_outlet(entry, fallback):
    src = entry.get("source", {}) or {}
    return (src.get("title") or fallback or "").strip()

def parse_ts(entry):
    for k in ("published_parsed", "updated_parsed"):
        v = entry.get(k)
        if v:
            try: return time.mktime(v)
            except Exception: pass
    return NOW

def fetch_source(src):
    try:
        r = requests.get(src["url"], headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"}, timeout=25)
        r.raise_for_status()
        fp = feedparser.parse(r.content)
    except Exception as e:
        return [], f"ERROR {type(e).__name__}: {e}"
    out = []
    for e in fp.entries:
        title = html.unescape(e.get("title", "")).strip()
        link  = e.get("link", "").strip()
        if not title or not link: continue
        outlet = src["name"]
        domain = src.get("domain", "")
        if src["kind"] == "gnews":
            glabel = gnews_outlet(e, src["name"])
            title  = re.sub(r"\s+-\s+" + re.escape(glabel) + r"\s*$", "", title).strip()
            title  = re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip() if title.count(" - ") else title
            outlet = OUTLET_MAP.get(glabel.lower(), glabel) if src.get("sweep") else src["name"]
            if src.get("sweep"):
                # drop sweep hits from outlets we already ingest natively
                og = (e.get("source", {}) or {}).get("href", "")
                d = urlparse(og).netloc.replace("www.", "")
                if d in SWEEP_EXCLUDE_DOMAINS: continue
                domain = d
        if len(title.split()) < 4: continue   # section pages, not articles
        if is_site_name_only(title, outlet, src["name"], src.get("domain")): continue
        summary = dedupe_summary(title, clean_summary(e.get("summary", "") or e.get("description", "")), outlet)
        text = (title + " " + summary).lower()
        if src.get("albany_filter") and not any(t in text for t in ALBANY_TERMS): continue
        ts = parse_ts(e)
        if NOW - ts > RETENTION_DAYS * 86400: continue
        out.append(dict(
            id=hashlib.sha1(link.encode()).hexdigest()[:12],
            title=title, link=link, outlet=outlet, domain=domain,
            summary=summary, published_ts=int(ts),
            published=dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
            tier=src["tier"], kind=src["kind"], sweep=bool(src.get("sweep")),
            source=src["name"], fetched_ts=int(NOW),
        ))
    return out, f"ok {len(out)}"

def main():
    os.makedirs(DATA, exist_ok=True)
    archive = {}
    if os.path.exists(ITEMS):
        try:
            for it in json.load(open(ITEMS)): archive[it["id"]] = it
        except Exception: archive = {}
    log = {}
    fresh = []
    for src in SOURCES:
        items, status = fetch_source(src)
        log[src["name"]] = status
        fresh.extend(items)
        print(f"{status:>10}  {src['name']}")
    # merge: new ids in; existing keep first-seen fetched_ts
    for it in fresh:
        if it["id"] in archive:
            archive[it["id"]]["published_ts"] = min(archive[it["id"]]["published_ts"], it["published_ts"])
            archive[it["id"]]["fetched_ts"] = archive[it["id"]].get("fetched_ts", it["fetched_ts"])
        else:
            archive[it["id"]] = it
    # retention
    cutoff = NOW - RETENTION_DAYS * 86400
    archive = {k: v for k, v in archive.items() if v["published_ts"] >= cutoff}
    # dedupe by normalized title: keep best tier, then earliest
    by_title = {}
    for it in archive.values():
        key = norm_title(it["title"])
        if len(key) < 12: key = it["id"]
        cur = by_title.get(key)
        if cur is None or (it["tier"], it["published_ts"]) < (cur["tier"], cur["published_ts"]):
            by_title[key] = it
    items = [it for it in by_title.values()
             if not is_site_name_only(it["title"], it.get("outlet"), it.get("source"), it.get("domain"))]
    for it in items:
        it["summary"] = dedupe_summary(it["title"], it.get("summary", ""), it.get("outlet", ""))
    for it in items:
        it["score"], it["tags"], it["flags"] = score(it, NOW)
    items.sort(key=lambda x: (-x["score"], -x["published_ts"]))
    json.dump(items, open(ITEMS, "w"), ensure_ascii=False, separators=(",", ":"))
    meta = dict(last_run=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                last_run_iso=dt.datetime.utcfromtimestamp(NOW).strftime("%Y-%m-%dT%H:%M:%SZ"), total=len(items),
                sources=log, outlets=sorted({i["outlet"] for i in items}),
                tags=sorted({t for i in items for t in i["tags"]}))
    json.dump(meta, open(META, "w"), indent=1)
    print(f"\n{len(items)} items after dedupe; {len(fresh)} fetched this run.")

if __name__ == "__main__":
    main()
