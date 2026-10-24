"""Heuristic scoring for Albany policy journalism. Higher = more worth reading.
Mirrors the idea behind nycnewsengine.com: reward reporting depth and policy relevance, penalize
breaking/opinion/entertainment, boost stories where the Governor and the Legislature both appear."""
import math, re

# The language of investigative reporting: records obtained and analyzed. Kept narrow on purpose. Earlier
# versions included "investigation", "internal", "memo", "exclusive", "review of", "found that" and
# "comptroller", which pulled in criminal investigations, Fox exclusives and every DiNapoli story.
INVESTIGATIVE = ["foil","freedom of information","records show","records obtained","obtained by","documents show",
    "documents obtained","audit","analysis of","data show","according to data","emails show","filings show",
    "investigation found","investigation reveals","inspector general","whistleblower"]
POLICY = ["budget","article vii","bill","veto","sign","chapter amendment","legislat","assembly","senate","governor",
    "hochul","heastie","stewart-cousins","medicaid","essential plan","housing","seqra","rent","mta","congestion",
    "child care","childcare","pre-k","bail","discovery","involuntary","prison","doccs","parole","climate","clcpa",
    "energy","utility","tax","pension","tier 6","immigration","ice","redistricting","ethics","lobbying","dob",
    "comptroller","authority","agency","commissioner","regulation","school aid","foundation aid","cannabis",
    "casino","gun","3d-printed","insurance","transit","subway","election","primary","blakeman","campaign"]
GOV_TERMS = ["hochul","governor","gov.","executive chamber"]
LEG_TERMS = ["legislature","assembly","senate","heastie","stewart-cousins","lawmakers","legislators","albany"]
OPINION  = ["opinion:","op-ed","editorial:","letters:","commentary","column:","perspective:"]
BREAKING = ["live updates","live:","breaking","watch:","video:","photos:"]
NOISE    = ["knicks","yankees","mets","giants","jets","rangers","nets","islanders","celebrity","recipe","horoscope",
    "concert","podcast","restaurant review","weather","lottery","obituary","real estate listing","dear abby"]

TAGS = {
 "Budget":         ["budget","article vii","dob","comptroller","fiscal","spending","revenue","tax","pension","tier 6"],
 "Housing":        ["housing","rent","tenant","landlord","zoning","seqra","485-x","good cause","homeless","shelter"],
 "Public safety":  ["bail","discovery","police","nypd","crime","prison","doccs","parole","gun","3d-printed","jail","rikers","commission of correction"],
 "Health":         ["medicaid","essential plan","hospital","health","mental","involuntary","kendra","340b","insurance","drug"],
 "Education & child care": ["school","education","pre-k","3-k","2-care","child care","childcare","university","suny","cuny","foundation aid","class size"],
 "Transit":        ["mta","subway","congestion","transit","lirr","metro-north","bus","penn station","train"],
 "Environment & energy": ["climate","clcpa","energy","utility","solar","nuclear","data center","con ed","national grid","psc","emissions"],
 "Elections":      ["election","primary","campaign","poll","blakeman","redistricting","ballot","voters","gerrymander"],
 "Ethics & process": ["ethics","lobbying","corruption","indict","bribery","transparency","reinvent albany","message of necessity","chapter amendment","late budget","process"],
 "Immigration":    ["immigra","ice ","287(g)","sanctuary","asylum","migrant","daca","essential plan"],
 "Economy & labor":["minimum wage","labor","union","workforce","economic development","empire state development","business","jobs"],
}

# Outlet adjustments on top of tier (Chamber colleagues, 2026-10-24): the Times matters most, Fox a little less.
# A Fox 5 New York local-news segment is not docked; the national Fox brands are.
OUTLET_WEIGHT = {"New York Times": 6, "Fox News": -8, "Fox Business": -8, "FOX One": -8}   # Times trimmed 10 -> 6 (10/24): it was crowding Picks
# Which outlet leads a grouped story (cluster.py): tier first, then this rank, then score. Without it the lead
# was whichever copy scored highest, which favored free outlets with deks and readable bodies (FingerLakes1's
# rewrite of an AG release) over paywalled ones that arrive via Google with neither (Newsday's own report).
OUTLET_RANK = {"New York Times": 3, "Wall Street Journal": 2, "Newsday": 2, "Times Union": 2, "Daily News": 2,
    "Buffalo News": 2, "Politico": 2, "Politico NY Playbook": 2, "City & State": 2, "New York Focus": 2,
    "NY State of Politics": 2, "Gothamist": 2, "The City": 2, "Syracuse.com": 1, "Spectrum News": 1, "Crain's New York": 1,
    # syndicators and transcripts never lead: the original report does
    "AOL.com": -2, "Yahoo": -2, "Yahoo News": -2, "MSN": -2, "Mirage News": -2, "Hoodline": -2, "NYC.gov": -1, "Daily Kos": -1}
NYT_HOCHUL = 6          # on top of the outlet weight: the Times on the Governor is always worth reading
HOCHUL_RE = re.compile(r"\bhochul\b|\bgovernor\b|\bgov\.")

def hochul_where(item):
    """'headline' if the Governor is named in the headline, 'dek' if only in the summary, else None."""
    if HOCHUL_RE.search(item.get("title", "").lower()): return "headline"
    if HOCHUL_RE.search(item.get("summary", "").lower()): return "dek"
    return None

def is_op_head(text): return bool(_hits(text, OPINION))

def _hits(text, terms): return sum(1 for t in terms if t in text)

def score(item, now_ts):
    text = (item.get("title","") + " " + item.get("summary","")).lower()
    tier = item.get("tier", 2)
    s = {1:30, 2:20, 3:12}.get(tier, 15)
    inv_head = _hits(text, INVESTIGATIVE)
    inv = min(inv_head + item.get("inv_body", 0), 4); s += inv*8
    pol = min(_hits(text, POLICY), 6);        s += pol*3
    gov = _hits(text, GOV_TERMS) > 0; leg = _hits(text, LEG_TERMS) > 0
    if gov and leg: s += 12
    hoch = hochul_where(item)
    if hoch == "headline" and not is_op_head(text): s += 5   # she is the subject
    s += OUTLET_WEIGHT.get(item.get("outlet", ""), 0)
    if hoch and item.get("outlet") == "New York Times": s += NYT_HOCHUL
    is_op = bool(_hits(text, OPINION)) or bool(item.get("opinion"))
    if is_op:  s -= 15
    if _hits(text, BREAKING): s -= 8
    if _hits(text, NOISE):    s -= 30
    age_h = max(0.0, (now_ts - item.get("published_ts", now_ts)) / 3600.0)
    s += 20 * math.exp(-age_h / 72.0)
    s += 4 * min(item.get("n_cov", 1) - 1, 3)   # several outlets on the same event: the story matters (cluster.py)
    if item.get("kind") == "gnews" and item.get("sweep"): s -= 12   # sweeps are noisier (tier 2 base, so net = old tier 3 - 4)
    w = item.get("words", 0)
    if w >= 2000: s += 12           # magazine-length feature
    elif w >= 1200: s += 6          # long-form
    elif w >= 700: s += 3
    tags = [k for k, terms in TAGS.items() if _hits(text, terms)]
    flags = []
    if inv: flags.append("investigative")
    if gov and leg: flags.append("gov+leg")
    if is_op: flags.append("opinion")
    item["hochul"] = hoch
    return round(s, 1), tags, flags
