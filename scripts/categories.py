"""Which group of outlets each story's publisher belongs to (Ted, 11/9: split "general outlets").

`item["cat"]` is what the page shows: dot color, legend, outlet lists, the Scoring check page. Names and colors live in
docs/labels.js; this file only assigns the id. It is a LABEL. `item["tier"]` still sets the base score, and nothing here
changes a story's rank.

Outlets are sorted by the audience they write for, not their subject: Chalkbeat New York and Streetsblog NYC are New York
City outlets because those are the desks we pull. Every outlet ends up in exactly one group (assign(), last step).
"""
import collections
from urllib.parse import urlparse

ALBANY = ("timesunion.com", "nysfocus.com", "cityandstateny.com", "nystateofpolitics.com", "politico.com", "politicopro.com",
          "empirereportnewyork.com", "empire.streetsblog.org")
NATIONAL = ("nytimes.com", "wsj.com", "washingtonpost.com", "bloomberg.com", "bloomberglaw.com", "bgov.com", "reuters.com",
            "apnews.com", "npr.org", "cnn.com", "nbcnews.com", "abcnews.com", "abcnews.go.com", "cbsnews.com", "foxnews.com",
            "foxbusiness.com", "fox.com", "thehill.com", "usatoday.com", "newsweek.com", "washingtonexaminer.com",
            "washingtontimes.com", "theguardian.com", "independent.co.uk", "newsnationnow.com", "ms.now", "c-span.org",
            "fortune.com", "thedailybeast.com", "axios.com", "semafor.com", "theatlantic.com", "newyorker.com", "time.com",
            "forbes.com", "vox.com", "propublica.org")
NYC = ("nypost.com", "nydailynews.com", "gothamist.com", "thecity.nyc", "thecityreporter.nyc", "amny.com", "fox5ny.com", "ny1.com",
       "crainsnewyork.com", "therealdeal.com", "commercialobserver.com", "nyc.streetsblog.org", "chalkbeat.org", "documentedny.com",
       "gothamgazette.com", "politicsny.com", "nymag.com", "nysun.com", "thechiefleader.com", "gaycitynews.com",
       "lavocedinewyork.com", "wabcradio.com")
REGIONAL = ("newsday.com", "buffalonews.com", "syracuse.com", "lohud.com", "democratandchronicle.com")
ADVOCACY = ("nylcv.org", "nysut.org", "nyfb.org")   # interest groups that sweeps find; same score as any swept outlet

_BY_DOMAIN = [("albany", ALBANY), ("national", NATIONAL), ("nyc", NYC), ("regional", REGIONAL), ("advocacy", ADVOCACY)]


def host(item):
    h = urlparse(item.get("link") or "").netloc.lower().replace("www.", "")
    return (item.get("domain") or h) if (not h or "news.google" in h) else h


def _matches(h, domains):
    return any(h == d or h.endswith("." + d) for d in domains)


def relabel(item):
    """Two outlet names that hide a New York City newsroom: CBS's New York station and Spectrum's NY1."""
    u = urlparse(item.get("link") or "")
    h = host(item)
    if h == "cbsnews.com" and u.path.startswith("/newyork"):
        item["outlet"] = "CBS New York"
    elif h == "ny1.com":
        item["outlet"] = "NY1"


def category(item, officials):
    if item.get("outlet") in officials: return "official"
    if item.get("tier") == 3: return "advocacy"
    if item.get("outlet") == "CBS New York": return "nyc"
    h = host(item)
    for cat, domains in _BY_DOMAIN:
        if _matches(h, domains): return cat
    return {1: "albany", 4: "local"}.get(item.get("tier"), "other")


def assign(items, officials):
    """Set item["cat"]. An outlet's stories can differ (Google labels the same name across hosts): the majority decides for all."""
    off = set(officials)
    votes = collections.defaultdict(collections.Counter)
    for it in items:
        votes[it.get("outlet")][category(it, off)] += 1
    for it in items:
        it["cat"] = votes[it.get("outlet")].most_common(1)[0][0]
