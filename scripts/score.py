"""Heuristic scoring for Albany policy journalism. Higher = more worth reading.
Mirrors the idea behind nycnewsengine.com: reward reporting depth and policy relevance, penalize
breaking/opinion/entertainment, boost stories where the Governor and the Legislature both appear."""
import math, re

INVESTIGATIVE = ["foil","freedom of information","records show","obtained by","documents show","internal","memo",
    "audit","investigation","analysis of","data show","according to data","exclusive","emails show","filings show",
    "review of","found that","comptroller","inspector general"]
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
    "concert","restaurant review","weather","lottery","obituary","real estate listing","dear abby"]

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

def _hits(text, terms): return sum(1 for t in terms if t in text)

def score(item, now_ts):
    text = (item.get("title","") + " " + item.get("summary","")).lower()
    tier = item.get("tier", 2)
    s = {1:30, 2:20, 3:12}.get(tier, 15)
    inv = min(_hits(text, INVESTIGATIVE), 3); s += inv*8
    pol = min(_hits(text, POLICY), 6);        s += pol*3
    gov = _hits(text, GOV_TERMS) > 0; leg = _hits(text, LEG_TERMS) > 0
    if gov and leg: s += 12
    if _hits(text, OPINION):  s -= 15
    if _hits(text, BREAKING): s -= 8
    if _hits(text, NOISE):    s -= 30
    age_h = max(0.0, (now_ts - item.get("published_ts", now_ts)) / 3600.0)
    s += 20 * math.exp(-age_h / 72.0)
    if item.get("kind") == "gnews" and item.get("sweep"): s -= 4   # sweeps are noisier
    tags = [k for k, terms in TAGS.items() if _hits(text, terms)]
    flags = []
    if inv: flags.append("investigative")
    if gov and leg: flags.append("gov+leg")
    if _hits(text, OPINION): flags.append("opinion")
    return round(s, 1), tags, flags
