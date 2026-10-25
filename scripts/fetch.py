#!/usr/bin/env python3
"""Fetch all sources, normalize, dedupe, score, merge with archive, write docs/data/items.json + meta.json.
Retention: 180 days. Safe to run repeatedly (idempotent by URL / normalized title)."""
import json, re, time, html, hashlib, os, sys, datetime as dt
from urllib.parse import urlparse, parse_qs, unquote
import feedparser, requests
try:
    from curl_cffi import requests as crequests   # browser TLS fingerprint; gets past Cloudflare on .gov sites
except ImportError:
    crequests = None
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(__file__))
from sources import SOURCES, ALBANY_TERMS, STATE_TERMS, BLOTTER, SWEEP_EXCLUDE_DOMAINS, NY_ANCHORS, OUT_OF_STATE, GENERIC_ALBANY, NYT_FACETS, NYT_GENERIC
from score import score
import extract, cluster, gnlinks, classify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
ITEMS = os.path.join(DATA, "items.json")
META  = os.path.join(DATA, "meta.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 nys-news-engine/1.0"
RETENTION_DAYS = 180
GN_MAX_AGE_DAYS = 10    # Google ignores when:Nd on long OR queries; anything older is that, not news
NOW = time.time()
RUNNER = os.environ.get("ENGINE_RUNNER", "local")      # "pi" | "actions" | "local" - recorded in meta.json
NYT_KEY = os.environ.get("NYT_API_KEY", "").strip()                       # Article Search app
NYT_TOP_KEY = os.environ.get("NYT_TOPSTORIES_KEY", "").strip() or NYT_KEY  # Top Stories app (NYT issues one key per app)
ET = ZoneInfo("America/New_York")
# Outlet labels that were renamed; applied to the archive on load so old and new items share a label.
OUTLET_RENAMES = {"NYT New York": "New York Times"}
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

NY_WORD = re.compile(r"\bny\b")
# ALBANY_TERMS match at word starts, and the short ones as whole words: as bare substrings "ed ra" (Ed Ra)
# matched "heated race" and "backed Raman", which let two Los Angeles mayoral stories through.
ALBANY_RE = [re.compile(r"(?<![a-z])" + re.escape(t) + (r"(?![a-z])" if len(t) <= 5 and t[-1].isalpha() else ""))
             for t in ALBANY_TERMS]
GENERIC_RE = [r for r, t in zip(ALBANY_RE, ALBANY_TERMS) if t in GENERIC_ALBANY]
COUNTY_LEG = re.compile(r"county legislat\w*")

def has_ny_anchor(text):
    return any(a in text for a in NY_ANCHORS) or bool(NY_WORD.search(text))

def passes_albany_filter(text, need_ny=False):
    """General-outlet filter. Returns (keep, gate): gate is None for an Albany-term hit, or the STATE_TERMS
    term that admitted the item. A bare 'governor' with an out-of-state marker fails. A state-term hit needs
    a New York anchor when the text names another state, or always for national feeds (need_ny)."""
    text = COUNTY_LEG.sub(" ", text)   # "Onondaga County Legislature" is not the Legislature
    ny = has_ny_anchor(text)
    elsewhere = any(t in text for t in OUT_OF_STATE)
    if any(r.search(text) for r in ALBANY_RE):
        specific = any(r.search(text) for r in ALBANY_RE if r not in GENERIC_RE)
        return (specific or ny or not elsewhere), None
    t2 = text.replace("law enforcement", "")
    hit = next((t for t in STATE_TERMS if t in t2), None)
    if not hit or ((need_ny or elsewhere) and not ny): return False, None
    if any(b in text for b in BLOTTER): return False, None
    return True, hit

def loose_ny(text):
    """Weaker test for the Legislature sweep: a New York anchor, or an Albany term with no other state named."""
    if has_ny_anchor(text): return True
    return any(r.search(text) for r in ALBANY_RE) and not any(t in text for t in OUT_OF_STATE)

def http_get(url, accept="*/*", timeout=25):
    """requests first; on 403/5xx retry with a Chrome TLS fingerprint if curl_cffi is installed."""
    r = requests.get(url, headers={"User-Agent": UA, "Accept": accept}, timeout=timeout)
    if r.status_code in (403, 429, 503, 520, 521, 522, 523) and crequests is not None:   # 52x = Cloudflare
        r = crequests.get(url, impersonate="chrome", headers={"Accept": accept}, timeout=timeout)
    r.raise_for_status()
    return r

def make_item(title, link, outlet, domain, summary, ts, src, **extra):
    d = dict(
        id=hashlib.sha1(link.encode()).hexdigest()[:12],
        title=title, link=link, outlet=outlet, domain=domain,
        summary=summary, published_ts=int(ts),
        published=dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
        tier=src["tier"], kind=src["kind"], sweep=bool(src.get("sweep")),
        source=src["name"], fetched_ts=int(NOW),
    )
    d.update(extra)
    return d

# ---------- governor.ny.gov/news, scraped directly ----------
GOV_ROW = re.compile(
    r'<div class="content-category">(.*?)</div>.*?<h3 class="content-title">\s*<a href="(/news/[^"]+)"[^>]*>(.*?)</a>'
    r'.*?<div class="content-dates">(.*?)</div>(?:.*?<div class="content-description[^"]*">(.*?)</div>\s*</div>)?', re.S)

def _strip(h):
    return html.unescape(" ".join(re.sub(r"<[^>]+>", " ", h or "").split()))

def gov_rows(page_html):
    out = []
    for cat, href, title, dates, desc in GOV_ROW.findall(page_html):
        cat = _strip(cat)
        if "espa" in cat.lower(): continue                      # Spanish duplicate of an English release
        d = _strip(dates).replace("|", " ")
        ts = None
        for fmt in ("%b %d, %Y %I:%M %p %Z", "%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p %Z", "%b %d, %Y"):
            try:
                naive = dt.datetime.strptime(re.sub(r"\s+(EDT|EST)$", "", d).strip(), fmt.replace(" %Z", ""))
                ts = naive.replace(tzinfo=ET).timestamp(); break
            except ValueError: continue
        if ts is None: ts = NOW
        out.append((_strip(title), "https://www.governor.ny.gov" + href, _strip(desc)[:400], ts, cat))
    return out

def fetch_gov(src):
    if crequests is None:
        return [], "skipped (curl_cffi not installed)"
    pages = []
    try:
        r = crequests.get(src["url"], impersonate="chrome", timeout=30); r.raise_for_status()
        pages.append(r.text)
        # page 2 arrives as a Drupal AJAX payload wrapped in <textarea>
        r = crequests.get(src["url"] + "?page=1&_wrapper_format=drupal_ajax", impersonate="chrome", timeout=30)
        if r.ok:
            body = re.sub(r"^\s*<textarea>|</textarea>\s*$", "", r.text.strip())
            try:
                cmds = json.loads(html.unescape(body)) if body.lstrip().startswith("[") else json.loads(body)
                pages.append("".join(c.get("data", "") for c in cmds if c.get("command") == "insert"))
            except Exception:
                pass
    except Exception as e:
        return [], f"ERROR {type(e).__name__}: {e}"
    out, seen = [], set()
    for ph in pages:
        for title, link, desc, ts, cat in gov_rows(ph):
            if link in seen or not title: continue
            seen.add(link)
            if NOW - ts > RETENTION_DAYS * 86400: continue
            out.append(make_item(title, link, src["name"], src["domain"], dedupe_summary(title, desc, src["name"]), ts, src))
    return out, (f"ok {len(out)}" if out else "ERROR parsed 0 rows (markup changed?)")

# ---------- NYT developer API: Top Stories (NY Region front) + Article Search (keyword) ----------
def _nyt_keep(title, abstract, facets):
    """Article Search matches the query anywhere in the body, so a Texas or Australian story that mentions
    Hochul once comes back. Require a New York anchor in the Times' facets or the text itself."""
    text = (title + " " + abstract).lower()
    f = " | ".join(facets).lower()
    if any(k in f for k in NYT_FACETS): return True
    ny = "new york" in f or has_ny_anchor(text)
    if ny and any(k in f for k in NYT_GENERIC): return True
    return ny and passes_albany_filter(text)[0]

def fetch_nyt(src):
    if not NYT_KEY:
        return [], "skipped (no NYT_API_KEY)"
    out, errs = [], []
    try:
        # Top Stories: what is on the NY Region section front right now (Times Newswire is no longer offered)
        r = requests.get("https://api.nytimes.com/svc/topstories/v2/nyregion.json",
                         params={"api-key": NYT_TOP_KEY}, timeout=25); r.raise_for_status()
        for a in (r.json().get("results") or []):
            title, abstract, link = (a.get("title") or "").strip(), (a.get("abstract") or "").strip(), a.get("url") or ""
            if not title or not link: continue
            facets = (a.get("per_facet") or []) + (a.get("org_facet") or []) + (a.get("geo_facet") or []) + (a.get("des_facet") or [])
            if not _nyt_keep(title, abstract, facets): continue
            try: ts = dt.datetime.fromisoformat(a["published_date"]).timestamp()
            except Exception: ts = NOW
            mt = (a.get("material_type_facet") or a.get("item_type") or "").lower()
            out.append(make_item(title, link, src["name"], src["domain"], abstract[:400], ts, src,
                                 paywall="hard", opinion=("op-ed" in mt or "editorial" in mt)))
    except Exception as e:
        errs.append(f"topstories {type(e).__name__}: {e}")
    # Article Search: one simple term per call. Boolean/phrase queries ("A OR \"B C\"") and fq filters
    # return hits:0 from the current gateway, so we run a few plain terms and let the facet filter decide.
    begin = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).strftime("%Y%m%d")
    seen = set()
    for term in ("Hochul", "Albany"):   # "Legislature" alone returns the world's legislatures
        time.sleep(13)   # keys are limited to a handful of calls per minute
        try:
            r = requests.get("https://api.nytimes.com/svc/search/v2/articlesearch.json",
                             params={"q": term, "sort": "newest", "begin_date": begin, "api-key": NYT_KEY}, timeout=25); r.raise_for_status()
            for d in ((r.json().get("response") or {}).get("docs") or []):   # docs is null, not [], on zero hits
                title = ((d.get("headline") or {}).get("main") or "").strip(); link = d.get("web_url") or ""
                abstract = (d.get("abstract") or d.get("snippet") or "").strip()
                if not title or not link or link in seen: continue
                seen.add(link)
                facets = [f"{k.get('name','')}:{k.get('value','')}" for k in d.get("keywords") or []]
                if not _nyt_keep(title, abstract, facets): continue
                try: ts = dt.datetime.fromisoformat(d["pub_date"].replace("+0000", "+00:00")).timestamp()
                except Exception: ts = NOW
                tom = (d.get("type_of_material") or "").lower()
                out.append(make_item(title, link, src["name"], src["domain"], abstract[:400], ts, src,
                                     paywall="hard", opinion=("op-ed" in tom or "editorial" in tom),
                                     words=int(d.get("word_count") or 0)))
        except Exception as e:
            errs.append(f"search {type(e).__name__}: {e}")
    errs = ["Top Stories API not enabled on this key (developer.nytimes.com/my-apps)" if e.startswith("topstories") and ("401" in e or "403" in e)
            else "Article Search not enabled on this key" if e.startswith("search") and ("401" in e or "403" in e) else _redact(e) for e in errs]
    status = f"ok {len(out)}" + (f" ({'; '.join(errs)})" if errs else "")
    if errs and not out: status = "ERROR " + "; ".join(errs)
    return out, status

def _redact(msg):
    """meta.json is public: strip any api-key query parameter from error text."""
    return re.sub(r"api-key=[^&\s]+", "api-key=***", str(msg))

def fetch_source(src):
    if src["kind"] == "gov": return fetch_gov(src)
    if src["kind"] == "nyt":
        items, status = fetch_nyt(src)
        return items, _redact(status)
    try:
        r = http_get(src["url"], accept="application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8")
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
            t2 = re.sub(r"\s+-\s+" + re.escape(glabel) + r"\s*$", "", title).strip()
            if t2 == title and title.count(" - "):            # label suffix not found verbatim: strip a generic one
                t2 = re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip()
            title = t2.lstrip("-– ").strip()
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
        gate = None
        if src.get("albany_filter"):
            keep, gate = passes_albany_filter(text, need_ny=bool(src.get("ny_anchor")))
            if not keep: continue
            if src.get("sweep") and src.get("ny_anchor"):
                # cross-outlet sweeps reach every state's press: "Assembly District 38" can be Ventura County
                if not has_ny_anchor(text): continue
                gate = gate or src["name"].replace("Google News: ", "") + " sweep"
        if src.get("loose_anchor") and not loose_ny(text): continue
        ts = parse_ts(e)
        if NOW - ts > RETENTION_DAYS * 86400: continue
        if src["kind"] == "gnews" and NOW - ts > GN_MAX_AGE_DAYS * 86400: continue
        extra = {"gate": gate} if gate else {}
        out.append(make_item(title, link, outlet, domain, summary, ts, src, **extra))
    return out, f"ok {len(out)}"

def _per_day(items, days=14):
    """Unique stories per publication day (ET), last N days, official releases counted separately.
    A story covered by twelve outlets counts once, on the day its lead item ran."""
    out = {}
    off = {"Governor's Office", "NY Senate", "NY Assembly"}
    for it in items:
        if it.get("cid", it["id"]) != it["id"] or gnlinks.is_google(it["link"]): continue   # hidden until resolved
        d = dt.datetime.fromtimestamp(it["published_ts"], ET).strftime("%Y-%m-%d")
        o = out.setdefault(d, {"stories": 0, "official": 0})
        o["official" if it["outlet"] in off else "stories"] += 1
    keys = sorted(out)[-days:]
    return {k: out[k] for k in keys}

def _gates(items, days=7):
    """Items admitted by the wider STATE_TERMS gate over the last week, by term: the #review page's tally."""
    cut = NOW - days * 86400
    c = {}
    for it in items:
        if it.get("gate") and it["published_ts"] >= cut: c[it["gate"]] = c.get(it["gate"], 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))

def main():
    os.makedirs(DATA, exist_ok=True)
    archive = {}
    if os.path.exists(ITEMS):
        try:
            for it in json.load(open(ITEMS)):
                it["outlet"] = OUTLET_RENAMES.get(it["outlet"], it["outlet"])
                archive[it["id"]] = it
        except Exception: archive = {}
    log = {}
    fresh = []
    for src in SOURCES:
        items, status = fetch_source(src)
        key = src["name"] if src["name"] not in log else f'{src["name"]} ({src["kind"]})'
        log[key] = status
        fresh.extend(items)
        print(f"{status:>10}  {src['name']}")
    # merge: new ids in; existing keep first-seen fetched_ts
    for it in fresh:
        if it["id"] in archive:
            archive[it["id"]]["published_ts"] = min(archive[it["id"]]["published_ts"], it["published_ts"])
            archive[it["id"]]["fetched_ts"] = archive[it["id"]].get("fetched_ts", it["fetched_ts"])
            if (it.get("words") or 0) > (archive[it["id"]].get("words") or 0):   # NYT API word count beats a paywall stub
                archive[it["id"]]["words"] = it["words"]
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
        rank = (it["tier"], it.get("kind") == "gnews", it["published_ts"])
        if cur is None or rank < (cur["tier"], cur.get("kind") == "gnews", cur["published_ts"]):
            by_title[key] = it
    items = [it for it in by_title.values()
             if not is_site_name_only(it["title"], it.get("outlet"), it.get("source"), it.get("domain"))]
    for it in items:
        it["summary"] = dedupe_summary(it["title"], it.get("summary", ""), it.get("outlet", ""))
    # Google News links are redirects (and dead ends for anyone signed into a Workspace account that blocks
    # Google News). The resolve-links workflow decodes them on GitHub Actions into docs/data/links.json
    # (never here: decoding counts against the same Google limit as the RSS queries, and a throttled Pi loses
    # every Google source until it clears); apply that map, and the page hides whatever is still unresolved.
    try:
        print(f"\ngnlinks: {gnlinks.apply(items)} links applied from links.json")
    except Exception as e:
        print(f"gnlinks step skipped: {type(e).__name__}: {e}")
    # with the real URL in hand, sections are visible: NY State of Politics carries Spectrum's wire sports
    items = [it for it in items if not re.search(r"/(sports|entertainment)/", urlparse(it["link"]).path)]
    # first pass so candidate selection has headline-only scores to sort on
    for it in items:
        it["score"], it["tags"], it["flags"] = score(it, NOW)
    try:
        extract.run(items, NOW)
    except Exception as e:
        print(f"extract step skipped: {type(e).__name__}: {e}")
    # with summaries in hand, a small model says what kind of story each new item is (classify.py); score.py
    # prefers its topics and type to the keyword guesses. Off when there is no API key.
    try:
        classify.run(items, NOW)
    except Exception as e:
        print(f"classify step skipped: {type(e).__name__}: {e}")
    for it in items:
        it["score"], it["tags"], it["flags"] = score(it, NOW)
    for it in items:   # the extractor can't reach most paywalled sites; the domain is the next best evidence
        if not it.get("paywall"):
            pw0 = extract.domain_paywall(it.get("domain") or urlparse(it["link"]).netloc)
            if pw0: it["paywall"] = pw0
    grouped = cluster.assign(items)
    for it in items:   # the coverage bonus needs n_cov
        it["score"], it["tags"], it["flags"] = score(it, NOW)
    items.sort(key=lambda x: (-x["score"], -x["published_ts"]))
    json.dump(items, open(ITEMS, "w"), ensure_ascii=False, separators=(",", ":"))
    pw = {}
    for it in items: pw[it.get("paywall","unknown")] = pw.get(it.get("paywall","unknown"),0)+1
    meta = dict(last_run=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                last_run_iso=dt.datetime.utcfromtimestamp(NOW).strftime("%Y-%m-%dT%H:%M:%SZ"), total=len(items),
                sources=log, outlets=sorted({i["outlet"] for i in items}),
                tags=sorted({t for i in items for t in i["tags"]}),
                paywall=pw, extracted=sum(1 for i in items if "extracted_ts" in i), runner=RUNNER,
                per_day=_per_day(items), grouped_stories=grouped, gates=_gates(items),
                unresolved_links=len(gnlinks.unresolved(items, NOW)),
                summaries=dict(total=sum(1 for i in items if i.get("summary")), og=sum(1 for i in items if i.get("summary_src") == "og"),
                               none=sum(1 for i in items if not i.get("summary"))),
                llm=classify.summary(items, NOW),
                # Mamdani named, the Governor not: Ted's candidate signal for "this is a City story" (10/25)
                zm_only=sum(1 for i in items if i.get("mamdani") and not i.get("hochul") and i["published_ts"] >= NOW - 7*86400))
    json.dump(meta, open(META, "w"), indent=1)
    print(f"\n{len(items)} items after dedupe ({grouped} multi-outlet stories); {len(fresh)} fetched this run.")

if __name__ == "__main__":
    main()
