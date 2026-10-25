"""Since 2026-10-25 only `topics()` is called: it counts related stories, it never folds rows. The 0.70 fold pass
nested a WXXI candidate interview under the Times Union's District 134 Q&A (the candidates' rare names drove
the match), and the count was shown as "17 outlets", which read as "this article ran in 17 places". Ted
likes the count; the page now says "+N related stories" and shows them under the row, every article its own row.

"""
"""Group items that report the same story from different outlets.

Same-title dedupe in fetch.py only catches syndicated copies. A Governor's announcement typically
arrives as ten or more differently worded headlines ("16 arrested in auto insurance crackdown",
"Rochester woman among 16 charged..."). Each item gets `cid`, the id of its story's lead item;
the page shows one row per story with the other outlets folded underneath.

Method: TF-IDF over headline words (dek words at half weight), IDF taken from the whole archive so
"Hochul" and "New York" count for little and "insurance", "staged", "16" count for a lot. Items are
visited oldest first; each joins the most similar open story within WINDOW_H hours if cosine
similarity to that story's centroid clears the threshold, else starts a new story.

Two passes (2026-10-24). FOLD (THRESHOLD 0.70) merges only near-identical copies: the same poll story
under three mastheads, a syndicated wire piece. Two outlets' own reporting of one event stays as two
rows; Ted: that repetition is itself the signal that a story matters. So the TOPIC pass (0.32, tuned
2026-10-23: 0.28 merged unrelated items, 0.36 split one announcement four ways) only counts the outlets
covering the same event, stored as `n_cov`, which score.py rewards and the page shows as a chip."""
import math, re, html
from collections import Counter
from score import OUTLET_RANK

THRESHOLD = 0.70        # fold: near-identical copies only
TOPIC_THRESHOLD = 0.32  # coverage count: same event, different reporting
WINDOW_H = 72
MIN_SHARED = 2          # distinctive words in common, so two short headlines can't match on one word
SAME_OUTLET = 0.70      # a second item from an outlet already in the story joins only if near-identical:
                        # Empire Center's nine regional "What They Make" posts are nine documents, not one

STOP = set("""a an the of to in on for and or but with as at by is are was were be been being from after before
over under into onto about than then this that these those it its it's his her their our your my we you they he she
him them who whom whose which what when where why how will would could should can may might must shall not no yes
new york ny n.y. nys says said say saying via amid among more most less least up down out off just also still now
here there all any some each every other another such only own same so too very s t one two first last year years
day days week weeks today tonight latest live update updates report reports news what's here's who's""".split())
OFFICIAL = {"Governor's Office", "NY Senate", "NY Assembly"}

def _stem(w):
    if len(w) > 5 and w.endswith("ies"): return w[:-3] + "y"
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"): return w[:-1]
    return w

def tokens(text):
    t = html.unescape(text or "").lower().replace("’", "'")
    t = re.sub(r"'s\b", "", t)
    t = re.sub(r"[^a-z0-9$ ]+", " ", t)
    return [_stem(w) for w in t.split() if w not in STOP and len(w) > 1]

def _vec(it, idf):
    v = Counter()
    for w in tokens(it.get("title", "")): v[w] += 1.0
    for w in tokens((it.get("summary") or "")[:240]): v[w] += 0.5
    out = {w: c * idf.get(w, 1.0) for w, c in v.items()}
    n = math.sqrt(sum(x * x for x in out.values())) or 1.0
    return {w: x / n for w, x in out.items()}

def eligible(it):
    """News items only. Official releases, opinion, and native think-tank posts (tier 3, not a sweep)
    are distinct documents even when they share a topic: CBC on Prop 5 is not Reinvent Albany on Prop 3."""
    if it.get("outlet") in OFFICIAL or it.get("opinion") or "opinion" in (it.get("flags") or []): return False
    return not (it.get("tier") == 3 and not it.get("sweep"))

def _cluster(items, idf, threshold):
    """Group eligible items into stories at the given similarity threshold; returns lists of members."""
    rare = lambda w: idf.get(w, 0) > 3.0
    stories, live = [], []   # live = stories still inside the time window
    for it in sorted((x for x in items if eligible(x)), key=lambda x: x["published_ts"]):
        v = _vec(it, idf)
        if not v: continue
        live = [s for s in live if it["published_ts"] - s["start"] <= WINDOW_H * 3600]
        best, bs = None, 0.0
        for s in live:
            n = math.sqrt(sum(x * x for x in s["c"].values())) or 1.0
            sim = sum(x * s["c"].get(w, 0.0) for w, x in v.items()) / n
            if it["outlet"] in s["outlets"] and sim < SAME_OUTLET: continue
            if sim > bs: best, bs = s, sim
        if best and bs >= threshold and len({w for w in v if rare(w)} & best["words"]) >= MIN_SHARED:
            best["m"].append(it)
            for w, x in v.items(): best["c"][w] = best["c"].get(w, 0.0) + x
            best["words"] |= {w for w in v if rare(w)}
            best["outlets"].add(it["outlet"])
        else:
            s = dict(start=it["published_ts"], m=[it], c=dict(v), words={w for w in v if rare(w)}, outlets={it["outlet"]})
            stories.append(s); live.append(s)
    return [s["m"] for s in stories]

def assign(items):
    """Set it["cid"] (the lead of its fold group, itself if unfolded) and it["n_cov"] (outlets covering the
    same event, loose pass). The lead is the member from the best outlet (tier, then OUTLET_RANK), score
    breaking ties. Returns the number of folded groups."""
    df = Counter()
    for it in items: df.update(set(tokens(it.get("title", ""))))
    N = max(len(items), 1)
    idf = {w: math.log((N + 1) / (c + 0.5)) for w, c in df.items()}
    for it in items: it["cid"], it["n_cov"] = it["id"], 1
    for m in _cluster(items, idf, TOPIC_THRESHOLD):
        n = len({x["outlet"] for x in m})
        for x in m: x["n_cov"] = n
    multi = 0
    for m in _cluster(items, idf, THRESHOLD):
        if len(m) < 2: continue
        multi += 1
        lead = max(m, key=lambda x: (-x.get("tier", 2), OUTLET_RANK.get(x.get("outlet"), 0), x.get("score", 0), -x["published_ts"]))
        for x in m: x["cid"] = lead["id"]
    return multi


def topics(items):
    """Set it["tid"] (the id shared by stories on the same subject, loose pass) and it["n_cov"] (distinct outlets
    in that group), leaving every item its own row (cid = id). Returns the number of groups with 2+ stories."""
    df = Counter()
    for it in items: df.update(set(tokens(it.get("title", ""))))
    N = max(len(items), 1)
    idf = {w: math.log((N + 1) / (c + 0.5)) for w, c in df.items()}
    groups = 0
    for it in items: it["cid"], it["tid"], it["n_cov"] = it["id"], it["id"], 1
    for m in _cluster(items, idf, TOPIC_THRESHOLD):
        if len(m) < 2: continue
        groups += 1
        tid = min(m, key=lambda x: x["published_ts"])["id"]
        n = len({x["outlet"] for x in m})
        for x in m: x["tid"], x["n_cov"] = tid, n
    return groups
