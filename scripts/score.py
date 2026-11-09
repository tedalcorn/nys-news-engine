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
# Opinion is the publisher's call, never ours (Ted, 11/9): the URL section, or the NYT API's own type_of_material
# (item["opinion"], set in fetch.py). No headline wording and no model verdict: Haiku hid an NYT news story on Hochul
# as opinion, and an "X for governor" endorsement pattern caught "Hochul wins reelection for governor".
# City & State files op-eds under /nyn-media/ with the label only in the slug; Churchill is the Times Union's columnist.
OPINION_URL = re.compile(r"/(opinion|opinions|editorial|editorials|letters|op-ed|op-eds|oped|commentary|columnists?|viewpoints?|churchill)/"
                         r"|cityandstateny\.com/.*/opinion-(?!poll)")
BREAKING = [re.compile(p) for p in (r"live updates", r"\blive:", r"\bbreaking\b", r"\bwatch:", r"\bvideo:", r"\bphotos?:", r"b-roll")]
NOISE    = ["knicks","yankees","mets","giants","jets","rangers","nets","islanders","celebrity","recipe","horoscope",
    "concert","podcast","restaurant review","weather","lottery","obituary","real estate listing","dear abby"]

# Topics = the Executive Chamber's deputy-secretary portfolios, in the Chamber's own wording (Ted, 2026-11-04;
# roster in "Deputy secretaries - backgrounds, tenure and your ties.docx", 10/1/26), then four cross-cutting
# topics no deputy owns. A story may carry several: stories often bridge portfolios. Each entry: the scope the
# classifier is told (classify.py) and the keywords used when an item has no current model verdict.
TOPICS = [
 ("Economic Development & Workforce", True,
  "Empire State Development, business attraction and incentives (Micron, semiconductors, film and other tax credits), "
  "small business, tourism, agriculture and farms, the Department of Labor, jobs, unemployment insurance, minimum wage, "
  "workforce training and apprenticeships, regional economic development councils, AI's effects on jobs",
  ["economic development","empire state development","esd","micron","semiconductor","chip plant","film tax credit",
   "tax credit","small business","business","tourism","agricultur","farm","farms","farmer","department of labor","jobs","job training",
   "workforce","apprentice","unemployment","minimum wage","wage theft","layoff","warn notice","employer","manufactur",
   "economy"]),
 ("Housing", True,
  "Homes and Community Renewal, housing supply and production, affordable housing, rent regulation, tenants and "
  "landlords, evictions, Good Cause, 485-x and other housing tax breaks, zoning and land use, homeownership, "
  "mortgages, NYCHA and public housing, building and fire codes, homelessness as a housing question",
  ["housing","homes and community renewal","hcr","rent","rents","rental","tenant","landlord","evict","good cause",
   "485-x","421-a","zoning","seqra","pro-housing","affordable housing","homeowner","mortgage","nycha","public housing",
   "mitchell-lama","apartment","building code","homeless"]),
 ("Health", True,
  "the Department of Health, Medicaid and the Essential Plan, hospitals and health systems, nursing homes, home care "
  "and CDPAP, health insurance coverage and costs, prescription drugs and pharmacies, 340B, public health, vaccines "
  "and outbreaks, reproductive and maternal health, the health workforce, federal health cuts",
  ["medicaid","essential plan","hospital","health","nursing home","home care","cdpap","health insurance","insurance coverage","premium","drug price",
   "prescription","pharmac","340b","vaccin","measles","outbreak","public health","abortion","reproductive","maternal",
   "doctor","physician","nurse","safety net","mco tax","obamacare","affordable care act","tobacco","vaping"]),
 ("Human Services & Mental Hygiene", True,
  "mental health (OMH), addiction and overdose (OASAS), developmental disabilities (OPWDD), psychiatric beds, "
  "involuntary commitment and Kendra's Law, 988, opioid settlement funds, SNAP and public assistance (OTDA), "
  "homeless services and shelters, children and families (OCFS): child welfare, foster care, child care subsidies, "
  "youth services and juvenile justice, aging services (NYSOFA), veterans' services",
  ["mental health","mental illness","psychiatr","involuntary","kendra","988","omh","oasas","opwdd","addiction",
   "substance use","overdose","opioid","fentanyl","naloxone","narcan","developmental disabilit","snap","food stamp",
   "public assistance","welfare","otda","ocfs","child welfare","foster care","child care","childcare","day care",
   "youth","juvenile","raise the age","office for the aging","aging services","older adults","older new yorkers","seniors","nysofa","veteran","shelter","homeless",
   "food bank","food insecurity"]),
 ("Public Safety", True,
  "crime and policing, the State Police, DCJS, DOCCS prisons and parole, jails and the Commission of Correction, "
  "criminal investigations and prosecutions (including the Attorney General's), sexual assault, bail, discovery and other criminal-justice law, guns and red-flag orders, prosecutors and sentencing, clemency, "
  "the prison strike and correction staffing, emergency management and homeland security (DHSES), domestic violence",
  ["bail","discovery","police","nypd","state police","trooper","crime","criminal","prison","doccs","correction",
   "parole","probation","gun","firearm","ghost gun","3d-printed","red flag","erpo","jail","rikers","incarcerat",
   "sentenc","clemency","district attorney","prosecutor","dcjs","homeland security","dhses","emergency management",
   "terror","domestic violence","shooting","halt act","solitary","retail theft","clean slate"]),
 ("Energy", True,
  "electricity and gas supply and prices, utility bills and rate cases, the Public Service Commission, NYSERDA, NYPA, "
  "LIPA, Con Ed, National Grid and other utilities, the grid and transmission, offshore wind, solar, nuclear, "
  "power plants, data centers' power demand, building electrification and heat pumps, energy targets in the climate law",
  ["energy","electric","utility","utilities","rate case","rate hike","psc","public service commission","nyserda","nypa",
   "power authority","lipa","con ed","con edison","national grid","nyseg","central hudson","grid","transmission",
   "offshore wind","wind farm","solar","nuclear","power plant","peaker","data center","heat pump","electrif",
   "all-electric","natural gas","pipeline","gas"]),
 ("Environment", True,
  "the Department of Environmental Conservation, climate change and emissions, the climate law (CLCPA) and "
  "cap-and-invest, the Climate Superfund, the Environmental Bond Act, air and water quality, PFAS and other "
  "contaminants, plastics, packaging and recycling, the Adirondacks and Catskills, state parks and public lands, "
  "wildlife, hunting and fishing, flooding and resilience",
  ["climate","clcpa","emissions","greenhouse","cap-and-invest","cap and invest","climate superfund","environmental",
   "environment","conservation","bond act","pollution","air quality","water quality","drinking water","pfas",
   "contamina","plastic","packaging","recycl","landfill","adirondack","catskill","state park","forest preserve",
   "wildlife","hunting","fishing","flood","resilien","superfund"]),
 ("Finance & Technology", True,
  "the Department of Financial Services: insurance regulation, banking, crypto; Taxation and Finance as tax "
  "administrator (refund and rebate checks, filing, collections), the State Insurance Fund, state IT (ITS) and "
  "cybersecurity, broadband, and technology policy: AI, children's online safety and social media, data privacy",
  ["financial services","dfs","bank","crypto","bitcoin","insurer","auto insurance","homeowners insurance",
   "taxation and finance","tax refund","rebate check","inflation refund","star check","state insurance fund",
   "artificial intelligence","ai","a.i.","chatbot","social media","online safety","kids online","safe for kids",
   "raise act","deepfake","algorithm","data privacy","privacy","cyber","broadband","connectall","tech","technology",
   "automation","empire ai","smartphone"]),
 ("Transportation", True,
  "the MTA, subways, buses and commuter rail, congestion pricing, the Department of Transportation, roads and bridges, "
  "the Thruway, the Port Authority and airports, Penn Station, the DMV, traffic safety and speed cameras, e-bikes",
  ["mta","subway","congestion","transit","lirr","metro-north","bus","buses","penn station","train","rail","thruway",
   "port authority","airport","jfk","laguardia","highway","bridge","road","roads","department of transportation","dot",
   "dmv","traffic safety","traffic death","traffic camera","speed camera","e-bike","fare","fares","commuter","gateway tunnel"]),
 ("Union Relations", True,
  "public-employee and other labor unions, collective bargaining and contracts, strikes and the Taylor Law, pensions "
  "and Tier 6, union positions on state policy: CSEA, PEF, NYSUT, UFT, DC 37, 1199SEIU, NYSNA, NYSCOPBA, Teamsters, AFL-CIO",
  ["union","unions","labor union","collective bargaining","contract talks","labor contract","strike","taylor law",
   "tier 6","pension","csea","pef","nysut","uft","dc 37","dc37","1199","seiu","nysna","nyscopba","teamsters",
   "afl-cio","hotel trades","32bj","organized labor"]),
 ("Gaming, Cannabis & Alcohol", True,
  "the Gaming Commission, casinos and downstate casino licenses, sports betting and mobile wagering, iGaming, horse "
  "racing and OTB, the lottery as policy; the Office of Cannabis Management and Cannabis Control Board, dispensaries "
  "and licensing, illicit smoke shops, hemp; the State Liquor Authority, liquor licenses and alcohol law",
  ["gaming","casino","sports betting","sports wagering","mobile betting","betting","gambling","igaming","racetrack",
   "horse racing","otb","gaming commission","cannabis","marijuana","dispensar","smoke shop","office of cannabis management",
   "caurd","hemp","liquor","alcohol","state liquor authority","sla","bars and restaurants","to-go drinks","wine","beer","brewer"]),
 ("Education", True,
  "the State Education Department and Board of Regents, school aid and Foundation Aid, class size, mayoral control, "
  "charter schools, testing and graduation requirements, literacy, special education, school meals and phones in "
  "schools, pre-K and 3-K, SUNY, CUNY, TAP and Excelsior, higher education",
  ["school","schools","education","regents","foundation aid","school aid","class size","mayoral control","charter school",
   "teacher","students","graduation","literacy","special education","pre-k","3-k","universal pre-k","suny","cuny",
   "university","college","tuition","excelsior","school meals","phone ban","cellphone","bell-to-bell"]),
 ("Budget", False,
  "the state budget and financial plan, deficits and gaps, Division of the Budget, tax rates and revenue, spending, "
  "the Comptroller's fiscal reports, federal funding cuts to the state",
  ["budget","article vii","dob","division of the budget","comptroller","fiscal","financial plan","deficit",
   "budget gap","spending","revenue","tax","taxes","rainy day","federal cuts","federal funding"]),
 ("Elections", False,
  "campaigns, polls, primaries, election administration, redistricting, ballot measures, voting law",
  ["election","primary","campaign","poll","blakeman","redistricting","ballot","voters","gerrymander","voting"]),
 ("Ethics & process", False,
  "the conduct of public officials: ethics, lobbying, corruption and indictments of officials, campaign finance, transparency and FOIL; "
  "not criminal cases that officials prosecute (those are Public Safety); how Albany works: messages of "
  "necessity, chapter amendments, late budgets, session rules",
  ["ethics","lobbying","corruption","indict","bribery","transparency","foil","reinvent albany","message of necessity",
   "chapter amendment","late budget","coelig"]),
 ("Immigration", False,
  "immigration enforcement, ICE and 287(g), sanctuary policy, asylum seekers and migrants, DACA",
  ["immigra","ice","287(g)","sanctuary","asylum","migrant","daca","deport","undocumented"]),
]
TAGS       = {n: kws for n, _, _, kws in TOPICS}
SCOPE      = {n: sc for n, _, sc, _ in TOPICS}
PORTFOLIOS = [n for n, p, _, _ in TOPICS if p]
OTHER_TOPICS = [n for n, p, _, _ in TOPICS if not p]

def _rx(term):
    """Word-start match; whole word when the term is short. As bare substrings "ice" matched "police" and
    "office" (52 of 74 Immigration hits on 10/25), "mental" matched "environmental", "bus" matched "business"."""
    t = re.escape(term)
    return re.compile(r"\b" + t + (r"\b" if len(term) <= 4 or term in ("mental", "union", "train", "drug") else ""))
POLICY_RE   = [_rx(t) for t in POLICY]
CAMPAIGN_RE = [_rx(t) for t in CAMPAIGN]
TOPIC_VERSION = 3   # = classify.VERSION when the topic list last changed; older verdicts' topics are ignored
TAG_RE      = {k: [_rx(t) for t in terms] for k, terms in TAGS.items()}

# Outlet adjustments on top of tier (Chamber colleagues, 2026-10-24): the Times matters most, Fox a little less.
# A Fox 5 New York local-news segment is not docked; the national Fox brands are.
# Prominence boosts (Ted, 11/9: show everything, boost the outlets that matter most to NYC and Albany readers). These are
# JUDGMENT, not measured audience: no source gives subscribers by NYC/Albany, and audited figures omit most of these papers.
OUTLET_WEIGHT = {"New York Times": 10,
    "NY Post Metro": 5, "NY Post Politics": 5, "Daily News": 4, "Times Union": 4, "Politico": 4, "Politico NY Playbook": 4, "Newsday": 4,
    "Fox News": -8, "Fox Business": -8, "FOX One": -8}
# A couple of points above the general run of outlets (Ted, 11/9). By domain, because Google labels these several ways
# (amNY / amNewYork, WSJ / Wall Street Journal). They are also spared the sweep penalty below: most reach us through sweeps.
DOMAIN_BOOST = {d: 2 for d in ("gothamist.com", "crainsnewyork.com", "bloomberg.com", "amny.com", "npr.org", "wsj.com",
    "chalkbeat.org", "cnn.com", "edition.cnn.com")}
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
TYPE_ADJ = {"policy": 4, "campaign": 0, "announcement": -6, "opinion": 0, "blotter": -12, "local": 0, "national": -15, "other": -8}

def _where(rx, item):
    """'headline' if the name is in the headline, 'dek' if only in the summary, else None."""
    if rx.search(item.get("title", "").lower()): return "headline"
    if rx.search(item.get("summary", "").lower()): return "dek"
    return None

def hochul_where(item): return _where(HOCHUL_RE, item)

def _hits(text, terms): return sum(1 for t in terms if t in text)

def _rhits(text, rxs): return sum(1 for r in rxs if r.search(text))

EDITORIAL_WORD = re.compile(r"\beditorial\b", re.I)   # the one headline word that counts (Ted, 11/9): the publisher saying so

def is_opinion(item):
    return bool(item.get("opinion") or OPINION_URL.search((item.get("link") or "").lower())
                or EDITORIAL_WORD.search(item.get("title") or ""))

def score(item, now_ts):
    text = (item.get("title","") + " " + item.get("summary","")).lower()
    tier = item.get("tier", 2)
    # tier 4 = local outlet (Ted, 11/6: "down-score them because they won't likely be breaking news that is as
    # important"). That is judged by the outlet alone: no story-level "local" penalty (Ted, 11/9).
    s = {1:30, 2:20, 3:12, 4:10}.get(tier, 15)
    pol = min(_rhits(text, POLICY_RE), 5); s += pol*3
    if _rhits(text, CAMPAIGN_RE): s += 3
    hoch = hochul_where(item)
    is_op = is_opinion(item)
    if hoch == "headline" and not is_op: s += 5   # she is the subject
    s += OUTLET_WEIGHT.get(item.get("outlet", ""), 0) + DOMAIN_BOOST.get(item.get("domain"), 0)
    if hoch and item.get("outlet") == "New York Times": s += NYT_HOCHUL
    if is_op:  s -= 15
    if any(r.search(text) for r in BREAKING): s -= 8
    if not pol and _hits(text, NOISE): s -= 30            # "knicks" was sinking James Dolan donor stories
    llm = item.get("llm")
    if llm and not llm.get("miss"): s += TYPE_ADJ.get(llm.get("type"), 0)
    age_h = max(0.0, (now_ts - item.get("published_ts", now_ts)) / 3600.0)
    s += 20 * math.exp(-age_h / 30.0)   # 20/9/4/2 at 0/24/48/72 h: a tiebreak among substantive stories, not a score of its own
    s += 4 * min(item.get("n_cov", 1) - 1, 3)   # several outlets on the same subject: the story matters (cluster.topics)
    if item.get("kind") == "gnews" and item.get("sweep") and tier != 4 and item.get("domain") not in DOMAIN_BOOST: s -= 12  # sweeps are noisier (tier 2 base, so net = old tier 3 - 4)
    w = item.get("words", 0)
    if w >= 2000: s += 12           # magazine-length feature
    elif w >= 1200: s += 6          # long-form
    elif w >= 700: s += 3
    if llm and not llm.get("miss"):
        tags = [t for t in llm.get("topics", []) if t in TAGS]
        if llm.get("v", 1) < TOPIC_VERSION:     # judged under an older topic list: the keywords until it is rejudged
            tags = [k for k, rxs in TAG_RE.items() if _rhits(text, rxs)]
    else:
        tags = [k for k, rxs in TAG_RE.items() if _rhits(text, rxs)]
    flags = ["opinion"] if is_op else []
    item["hochul"] = hoch
    item["mamdani"] = _where(MAMDANI_RE, item)
    return round(s, 1), tags, flags
