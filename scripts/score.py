"""Heuristic scoring for Albany policy journalism. Higher = more worth reading.
Mirrors the idea behind nycnewsengine.com: reward reporting depth and policy relevance, penalize
breaking/opinion/entertainment. Since 2026-10-25 a model's verdict on what kind of story an item is
(classify.py: policy / campaign / announcement / opinion / blotter / local / national) and its topics are
preferred to the keyword guesses here whenever the item carries them; the keywords remain the fallback for
items not yet judged and for runs without an API key."""
import math, re

# The language of investigative reporting: records obtained and analyzed. Kept narrow on purpose. Earlier
# versions included "investigation", "internal", "memo", "exclusive", "review of", "found that" and
# "comptroller", which pulled in criminal investigations, Fox exclusives and every DiNapoli story.
# No longer scored (10/25: ~2 real records stories of 22 flagged a week); extract.py still counts inv_body.
INVESTIGATIVE = ["foil","freedom of information","records show","records obtained","obtained by","documents show",
    "documents obtained","audit","analysis of","data show","according to data","emails show","filings show",
    "investigation found","investigation reveals","inspector general","whistleblower"]
# Governance vocabulary: what state government does. "hochul", "governor", "blakeman", "election", "primary" and
# "campaign" used to sit in this list and filled five of six slots on any horse-race story (+15 to +18 for being
# about the race); they moved to CAMPAIGN, which is worth one slot at most.
POLICY = ["budget","article vii","bill","veto","sign","chapter amendment","legislat","assembly","senate",
    "heastie","stewart-cousins","medicaid","essential plan","housing","seqra","rent","mta","congestion",
    "child care","childcare","pre-k","bail","discovery","involuntary","prison","doccs","parole","climate","clcpa",
    "energy","utility","tax","pension","tier 6","immigration","ice","redistricting","ethics","lobbying","dob",
    "comptroller","authority","agency","commissioner","regulation","school aid","foundation aid","cannabis",
    "casino","gun","3d-printed","insurance","transit","subway"]
CAMPAIGN = ["election","primary","campaign","blakeman","poll","endorse","ballot","voters","debate"]
GOV_TERMS = ["hochul","governor","gov.","executive chamber"]
OPINION  = ["opinion:","op-ed","editorial:","editorial board","letters:","commentary","column:","perspective:",
    "editor's note","editor’s note","our view"]
# The URL is the reliable opinion signal: 27 of 34 /opinion/ items were unflagged on 10/25, all of Newsday's
# endorsements among them ("Josh Slaughter for Assembly District 3").
OPINION_URL = re.compile(r"/(opinion|opinions|editorial|editorials|letters|op-ed|oped|commentary|columnists?|viewpoints?)/")
ENDORSE_RE  = re.compile(r"^[A-Z][\w.'’\- ]{3,60} for (the )?(state )?(assembly|senate|congress|governor|attorney general|comptroller)\b", re.I)
BREAKING = [re.compile(p) for p in (r"live updates", r"\blive:", r"\bbreaking\b", r"\bwatch:", r"\bvideo:", r"\bphotos?:", r"b-roll")]
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
 "Immigration":    ["immigra","ice","287(g)","sanctuary","asylum","migrant","daca","essential plan"],
 "Economy & labor":["minimum wage","labor","union","workforce","economic development","empire state development","business","jobs"],
}

def _rx(term):
    """Word-start match; whole word when the term is short. As bare substrings "ice" matched "police" and
    "office" (52 of 74 Immigration hits on 10/25), "mental" matched "environmental", "bus" matched "business"."""
    t = re.escape(term)
    return re.compile(r"\b" + t + (r"\b" if len(term) <= 4 or term in ("mental", "union", "train", "drug") else ""))
POLICY_RE   = [_rx(t) for t in POLICY]
CAMPAIGN_RE = [_rx(t) for t in CAMPAIGN]
TAG_RE      = {k: [_rx(t) for t in terms] for k, terms in TAGS.items()}

# Outlet adjustments on top of tier (Chamber colleagues, 2026-10-24): the Times matters most, Fox a little less.
# A Fox 5 New York local-news segment is not docked; the national Fox brands are.
OUTLET_WEIGHT = {"New York Times": 6, "Fox News": -8, "Fox Business": -8, "FOX One": -8}   # Times trimmed 10 -> 6 (10/24): it was crowding Picks
# Which outlet led a grouped story when cluster.py ran (grouping off since 10/25; kept for cluster.py's import). Without it the lead
# was whichever copy scored highest, which favored free outlets with deks and readable bodies (FingerLakes1's
# rewrite of an AG release) over paywalled ones that arrive via Google with neither (Newsday's own report).
OUTLET_RANK = {"New York Times": 3, "Wall Street Journal": 2, "Newsday": 2, "Times Union": 2, "Daily News": 2,
    "Buffalo News": 2, "Politico": 2, "Politico NY Playbook": 2, "City & State": 2, "New York Focus": 2,
    "NY State of Politics": 2, "Gothamist": 2, "The City": 2, "Syracuse.com": 1, "Spectrum News": 1, "Crain's New York": 1,
    # syndicators and transcripts never lead: the original report does
    "AOL.com": -2, "Yahoo": -2, "Yahoo News": -2, "MSN": -2, "Mirage News": -2, "Hoodline": -2, "NYC.gov": -1, "Daily Kos": -1}
NYT_HOCHUL = 6          # on top of the outlet weight: the Times on the Governor is always worth reading
HOCHUL_RE  = re.compile(r"\bhochul\b|\bgovernor\b|\bgov\.")
MAMDANI_RE = re.compile(r"\bmamdani\b")
# What the model's story type is worth (classify.py). Policy reporting is the point of the tool; a press-release
# rewrite, a crime story, a City Hall story or a Washington story is not, however good the outlet.
TYPE_ADJ = {"policy": 4, "campaign": 0, "announcement": -6, "opinion": 0, "blotter": -12, "local": -10, "national": -15, "other": -8}

def _where(rx, item):
    """'headline' if the name is in the headline, 'dek' if only in the summary, else None."""
    if rx.search(item.get("title", "").lower()): return "headline"
    if rx.search(item.get("summary", "").lower()): return "dek"
    return None

def hochul_where(item): return _where(HOCHUL_RE, item)

def is_op_head(text): return bool(_hits(text, OPINION))

def _hits(text, terms): return sum(1 for t in terms if t in text)

def _rhits(text, rxs): return sum(1 for r in rxs if r.search(text))

def is_opinion(item, text):
    if _hits(text, OPINION) or item.get("opinion"): return True
    if OPINION_URL.search((item.get("link") or "").lower()): return True
    if ENDORSE_RE.match(item.get("title", "")): return True
    llm = item.get("llm")
    return bool(llm and llm.get("type") == "opinion")

def score(item, now_ts):
    text = (item.get("title","") + " " + item.get("summary","")).lower()
    tier = item.get("tier", 2)
    s = {1:30, 2:20, 3:12}.get(tier, 15)
    pol = min(_rhits(text, POLICY_RE), 5); s += pol*3
    if _rhits(text, CAMPAIGN_RE): s += 3
    hoch = hochul_where(item)
    if hoch == "headline" and not is_op_head(text): s += 5   # she is the subject
    s += OUTLET_WEIGHT.get(item.get("outlet", ""), 0)
    if hoch and item.get("outlet") == "New York Times": s += NYT_HOCHUL
    is_op = is_opinion(item, text)
    if is_op:  s -= 15
    if any(r.search(text) for r in BREAKING): s -= 8
    if not pol and _hits(text, NOISE): s -= 30            # "knicks" was sinking James Dolan donor stories
    llm = item.get("llm")
    if llm and not llm.get("miss"): s += TYPE_ADJ.get(llm.get("type"), 0)
    age_h = max(0.0, (now_ts - item.get("published_ts", now_ts)) / 3600.0)
    s += 20 * math.exp(-age_h / 30.0)   # 20/9/4/2 at 0/24/48/72 h: a tiebreak among substantive stories, not a score of its own
    if item.get("kind") == "gnews" and item.get("sweep"): s -= 12   # sweeps are noisier (tier 2 base, so net = old tier 3 - 4)
    w = item.get("words", 0)
    if w >= 2000: s += 12           # magazine-length feature
    elif w >= 1200: s += 6          # long-form
    elif w >= 700: s += 3
    if llm and not llm.get("miss"):
        tags = [t for t in llm.get("topics", []) if t in TAGS]
    else:
        tags = [k for k, rxs in TAG_RE.items() if _rhits(text, rxs)]
    flags = ["opinion"] if is_op else []
    item["hochul"] = hoch
    item["mamdani"] = _where(MAMDANI_RE, item)
    return round(s, 1), tags, flags
